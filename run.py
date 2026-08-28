#!/usr/bin/env python3
"""Job-Event Search - one command, end to end.

    python3 run.py                 # collect, score, write out/digest.{json,html}
    python3 run.py --no-cache      # ignore the 6h response cache
    python3 run.py --explain "llm" # dump full scoring for events matching a string
    python3 run.py --audit         # show what was gated out and why

Stdlib only. No API keys. No paid services.
"""
import argparse
import datetime as dt
import hashlib
import sys
import time

from jobevents import config, enrich, feedback, http, report, score, store
from jobevents.advice import annotate
from jobevents.dedupe import dedupe
from jobevents.models import local_now, norm_title_key
from jobevents.sources import eventbrite, hackerx, luma, meetup

SOURCES = [("luma", luma), ("meetup", meetup), ("hackerx", hackerx),
           ("eventbrite", eventbrite)]


def make_uid(ev):
    key = "%s|%s|%s" % (norm_title_key(ev.title), ev.date_key,
                        ev.city or (round(ev.lat, 2) if ev.lat else ""))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def log(msg=""):
    print(msg, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--explain", metavar="SUBSTR")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--days", type=int, default=config.WINDOW_DAYS)
    ap.add_argument("--start", metavar="YYYY-MM-DD")
    ap.add_argument("--no-openings", action="store_true",
                    help="skip public job-board lookups (faster, fewer requests)")
    args = ap.parse_args(argv)

    if args.no_cache:
        config.CACHE_TTL_SECONDS = 0

    t0 = time.time()
    now = local_now()
    win_start = (dt.date.fromisoformat(args.start) if args.start
                 else max(config.WINDOW_START, now.date()))
    win_end = win_start + dt.timedelta(days=args.days - 1)

    log("=" * 74)
    log("  COLLECT   window %s .. %s   (%d days)" % (win_start, win_end, args.days))
    log("=" * 74)

    raw = []
    for name, mod in SOURCES:
        log("  [%s]" % name)
        try:
            got = mod.collect(log=log)
        except Exception as exc:
            log("    !! %s failed entirely: %s: %s" % (name, type(exc).__name__, exc))
            got = []
        log("    -> %d listings" % len(got))
        raw.extend(got)
    log("\n  TOTAL raw listings: %d" % len(raw))

    # ---- cheap pass: gate + score on title/summary only, to pick who deserves
    #      a detail fetch. Avoids ~900 extra HTTP requests per run.
    log("\n" + "=" * 74)
    log("  FILTER + HYDRATE")
    log("=" * 74)
    for ev in raw:
        score.evaluate(ev, now, win_start, win_end)
    in_window = [e for e in raw if not e.gate]
    log("  %d listings survive hard gates (geo/date/online/closed)" % len(in_window))

    shortlist = [e for e in in_window if e.score >= config.MIN_SCORE_REVIEW - 12
                 or e.category in ("A", "B", "C")]
    log("  %d qualify for a detail fetch (full description)" % len(shortlist))
    hydrated = 0
    for i, ev in enumerate(shortlist, 1):
        src = ev.sources[0]["source"]
        fn = {"luma": luma.hydrate, "eventbrite": eventbrite.hydrate}.get(src)
        if not fn or ev.verified:
            continue
        try:
            if fn(ev):
                hydrated += 1
        except Exception:
            pass
        if i % 25 == 0:
            log("    hydrated %d/%d ..." % (i, len(shortlist)))
    log("  fetched %d full descriptions" % hydrated)

    # ---- rescore with real descriptions, then dedupe
    for ev in in_window:
        score.evaluate(ev, now, win_start, win_end)
    log("\n" + "=" * 74)
    log("  DEDUPLICATE")
    log("=" * 74)
    events = dedupe([e for e in in_window if not e.gate], log=log)

    log("\n" + "=" * 74)
    log("  ENRICH   companies -> openings -> travel cost -> your history")
    log("=" * 74)
    con = store.connect()
    priors = feedback.organizer_priors(feedback.connect())
    if priors:
        log("  organiser priors learned from your logged events: %d" % len(priors))
    else:
        log("  no attendance logged yet - organiser prior inactive "
            "(run: python3 log_event.py)")

    for ev in events:
        score.evaluate(ev, now, win_start, win_end)   # merged fields may change score
        enrich.attach_companies(ev)
        score.evaluate(ev, now, win_start, win_end)   # company roles feed the score
        enrich.attach_cost(ev)
        ev.uid = make_uid(ev)

    # Job-board lookups only for events that could still be recommended - a
    # lookup on a 12/100 event is a wasted request.
    if not args.no_openings:
        cands = [e for e in events if e.score >= config.MIN_SCORE_REVIEW]
        log("  looking up public job boards for %d candidate events" % len(cands))
        for i, ev in enumerate(cands, 1):
            enrich.attach_openings(ev, log=None)
            if i % 40 == 0:
                log("    ... %d/%d" % (i, len(cands)))
        hits = [e for e in cands if e.openings]
        log("  %d events have companies with verified open roles you match" % len(hits))

    for ev in events:
        enrich.finalize(ev, priors)
        annotate(ev)

    gated = [e for e in raw if e.gate]
    for e in gated:
        e.uid = make_uid(e)

    # ---- persist
    new_uids, changed = store.upsert(con, events + gated)

    # Refuse to emit a dashboard built from a crippled collection run.
    if len(events) < config.MIN_EVENTS_SANITY:
        log("\n  ABORT: only %d unique in-window events (expected >=%d). A source is "
            "probably blocked or down; refusing to overwrite a good dashboard with a "
            "thin one. Re-run with --no-cache, or lower MIN_EVENTS_SANITY if the "
            "window is genuinely short." % (len(events), config.MIN_EVENTS_SANITY))
        return 2
    days = report.by_day(events, win_start, args.days)
    rec_total = sum(len(report.pick(v)) for v in days.values())
    store.record_run(con, len(raw), len(events), rec_total, len(gated), http.stats())

    # ---- modes
    if args.explain:
        _explain(events + gated, args.explain)
        return 0
    if args.audit:
        _audit(gated)
        return 0

    # ---- output
    log("\n")
    report.terminal_digest(days, new_uids, now.date(), out=log)
    if changed:
        log("\n  %d listings changed since the last run (venue/time/price/details):"
            % len(changed))
        by_uid = {e.uid: e for e in events}
        for uid, note in list(changed.items())[:8]:
            ev = by_uid.get(uid)
            if ev:
                log("    %s  %s  (%s)" % (ev.date_key, ev.title[:44], note))

    meta = {"window_start": str(win_start), "window_end": str(win_end),
            "raw_listings": len(raw), "unique_events": len(events),
            "recommended": rec_total, "gated": len(gated),
            "changed": len(changed),
            "with_openings": sum(1 for e in events if e.openings),
            "http": http.stats(), "runtime_s": round(time.time() - t0, 1)}
    jp = report.write_json(config.OUT_DIR + "/digest.json", days, new_uids, meta)

    from jobevents.html_report import write_html
    hp = write_html(config.OUT_DIR + "/index.html", days, new_uids, meta, now.date())

    log("\n" + "=" * 74)
    log("  %d raw -> %d unique -> %d recommended across %d days   (%.0fs, %d HTTP, %d cached)"
        % (len(raw), len(events), rec_total, args.days, time.time() - t0,
           http.stats()["fetched"], http.stats()["cached"]))
    log("  JSON: %s" % jp)
    log("  HTML: %s      <- open this" % hp)
    log("=" * 74)
    return 0


def _explain(events, needle):
    n = needle.lower()
    hits = [e for e in events if n in (e.title or "").lower()]
    print("\n%d events match %r\n" % (len(hits), needle))
    for e in sorted(hits, key=lambda x: -x.score):
        print("-" * 74)
        print("%s\n  %s  %s  %s" % (e.title, e.date_key, e.city, e.url))
        print("  score=%d cat=%s conf=%s gate=%s" % (e.score, e.category, e.confidence,
                                                     e.gate or "-"))
        for r in e.reasons:
            print("    %s" % r)
        for p in e.penalties:
            print("    %s" % p)
        sig = {k: v for k, v in (e.signals or {}).items() if v and k != "profile_fit"}
        print("  signals: %s" % sig)


def _audit(gated):
    from collections import Counter
    c = Counter(e.gate for e in gated)
    print("\nGATED OUT: %d listings\n" % len(gated))
    for reason, n in c.most_common():
        print("  %5d  %s" % (n, reason))
    print("\nSample of gated events with engineering-sounding titles "
          "(check for false negatives):")
    import re
    pat = re.compile(r"engineer|ml\b|ai\b|llm|hiring|developer|python|data", re.I)
    shown = 0
    for e in gated:
        if pat.search(e.title or "") and shown < 25:
            print("  [%s] %s  (%s)" % (e.date_key or "no-date", (e.title or "")[:56], e.gate))
            shown += 1


if __name__ == "__main__":
    sys.exit(main())
