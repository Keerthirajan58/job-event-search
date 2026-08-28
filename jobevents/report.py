"""Renderers: terminal digest, JSON, and a single self-contained HTML file."""
import datetime as dt
import html as H
import json
import os

from . import config
from .advice import action
from .companies import display as _cdisp
from .score import CATEGORIES

CAT_COLOR = {"A": "#0f7b3f", "B": "#1462b5", "C": "#8a5a00",
             "D": "#5b6570", "E": "#8a8f97", "F": "#a13b2f", "G": "#8a8f97"}
CONF_COLOR = {"HIGH": "#0f7b3f", "MEDIUM": "#8a5a00", "LOW": "#a13b2f", "N/A": "#8a8f97"}


# ------------------------------------------------------------------- grouping
def by_day(events, start, days):
    out = {}
    for i in range(days):
        d = start + dt.timedelta(days=i)
        out[d.isoformat()] = []
    for ev in events:
        if ev.date_key in out:
            out[ev.date_key].append(ev)
    for k in out:
        out[k].sort(key=lambda e: (-e.score, e.start or dt.datetime.max))
    return out


def pick(day_events, max_n=None, min_score=None):
    max_n = config.MAX_PER_DAY if max_n is None else max_n
    min_score = config.MIN_SCORE_RECOMMEND if min_score is None else min_score
    return [e for e in day_events if e.score >= min_score][:max_n]


# ------------------------------------------------------------------- terminal
def terminal_digest(days, new_uids, today, out=print):
    bar = "=" * 74
    out(bar)
    fmt = "%A, %B %-d, %Y" if _dash() else "%A, %B %d, %Y"
    out("  GOOD MORNING KEERTHI  -  %s" % today.strftime(fmt))
    out(bar)

    tkey = today.isoformat()
    if tkey in days:
        out("\nTODAY (%s)" % tkey)
        _emit_day(days[tkey], new_uids, out, verbose=True)

    out("\n" + bar)
    out("  NEXT 7 DAYS")
    out(bar)
    keys = sorted(days)
    for k in keys[:8]:
        if k == tkey:
            continue
        sel = pick(days[k])
        label = dt.date.fromisoformat(k).strftime("%a %b %-d" if _dash() else "%a %b %d")
        if not sel:
            near = days[k][0].score if days[k] else 0
            out("\n  %s  -  No worthwhile event found. (best candidate scored %d/100)"
                % (label, near))
            continue
        out("\n  %s" % label)
        for e in sel:
            flag = " *NEW*" if e.uid in new_uids else ""
            c = e.cost or {}
            trip = ("%dm/$%.0f" % (c["one_way_min"], c["total_cash"])
                    if c.get("known") else "  --  ")
            jobs = ("  %d roles" % sum(o["total"] for o in e.openings)
                    if e.openings else "")
            out("    %-10s %3d  %-7s %-9s %s%s%s"
                % (e.verdict or "?", e.score, e.time_str or "--", trip,
                   e.title[:40], jobs, flag))

    out("\n" + bar)
    out("  REST OF WINDOW - highest value to register for now")
    out(bar)
    later = []
    for k in keys[8:]:
        later.extend(pick(days[k], max_n=2))
    later.sort(key=lambda e: -e.score)
    for e in later[:12]:
        out("    %3d/100  %s  %-42s  %s" % (e.score, e.date_key, e.title[:42], e.url))
    if not later:
        out("    (nothing yet - events this far out are usually posted 1-3 weeks ahead)")


def _emit_day(day_events, new_uids, out, verbose=False):
    sel = pick(day_events)
    if not sel:
        best = day_events[0].score if day_events else 0
        out("  No worthwhile event found. (best candidate scored %d/100; "
            "threshold is %d)" % (best, config.MIN_SCORE_RECOMMEND))
    for i, e in enumerate(sel, 1):
        out("")
        out("  %d. [%s]  %d/100  %s%s"
            % (i, e.verdict or "?", e.score, e.title,
               "   *NEW*" if e.uid in new_uids else ""))
        place = ", ".join(x for x in [e.venue, e.city.title() if e.city else ""] if x)
        out("     %s  |  %s  |  %s  |  confidence %s"
            % (e.time_str or "time TBD", place or "location TBD",
               CATEGORIES[e.category][0], e.confidence))
        if e.changed_note:
            out("     CHANGED since last run: %s" % e.changed_note)
        c = e.cost or {}
        if c.get("known"):
            out("     Getting there: %d min each way by %s  |  $%.2f total tonight  |  "
                "%dh%02dm all in"
                % (c["one_way_min"], c["mode"], c["total_cash"],
                   c["total_minutes"] // 60, c["total_minutes"] % 60))
            if c.get("late_warning"):
                out("     GETTING HOME: %s" % c["late_warning"])
        strong_co = [x for x in (e.companies or []) if x["role"] != "mention"]
        if strong_co:
            out("     Companies present: %s"
                % ", ".join("%s (%s)" % (_cdisp(x["name"]), x["role"])
                            for x in strong_co[:4]))
        for o in (e.openings or [])[:2]:
            titles = "; ".join(r["title"] for r in o["roles"][:2])
            out("     HIRING NOW: %s has %d roles you match - %s"
                % (_cdisp(o["company"]), o["total"], titles[:70]))
        out("     Register: %s" % e.url)
        if verbose:
            elig = [n for n in e.fit_notes
                    if n.startswith(("ELIGIBILITY", "AUDIENCE MISMATCH"))]
            for n in elig:
                out("     !! %s" % n)
            out("     Why you should go:")
            for n in [x for x in e.fit_notes if x not in elig][:3]:
                out("       - %s" % n)
            out("     People to target:")
            for w in e.who_to_meet[:4]:
                out("       - %s" % w)
            out("     Your opener:")
            out("       \"%s\"" % e.opener)
            if e.followup:
                out("       %s" % e.followup)
            out("     Action: %s" % action(e))
            if e.verify_note:
                out("     Confidence caveats: %s" % e.verify_note)

    # what we deliberately skipped, so the user can sanity-check the filter
    skipped = [e for e in day_events if config.MIN_SCORE_REVIEW <= e.score
               < config.MIN_SCORE_RECOMMEND][:3]
    if skipped and verbose:
        out("\n  SKIP (borderline - shown so you can audit the filter):")
        for e in skipped:
            out("    %d/100  %s" % (e.score, e.title[:50]))
            out("            %s" % (e.reasons[0] if e.reasons else ""))


def _dash():
    try:
        dt.date(2026, 9, 1).strftime("%-d")
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------- JSON
def write_json(path, days, new_uids, meta):
    payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
               "meta": meta, "days": {}}
    for k, evs in days.items():
        sel = pick(evs)
        payload["days"][k] = {
            "recommended": [_json_event(e, new_uids) for e in sel],
            "review_queue": [_json_event(e, new_uids) for e in evs
                             if config.MIN_SCORE_REVIEW <= e.score
                             < config.MIN_SCORE_RECOMMEND][:5],
            "note": None if sel else "No worthwhile event found.",
        }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    return path


def _json_event(e, new_uids):
    d = e.to_dict()
    d["category_label"] = CATEGORIES[e.category][0]
    d["is_new"] = e.uid in new_uids
    d["recommended_action"] = action(e)
    d.pop("signals", None)
    return d
