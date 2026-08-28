"""Single self-contained HTML dashboard. No build step, no CDN, no JS deps."""
import datetime as dt
import html as H
import os

from . import config
from .advice import action
from .companies import display as _cdisp
from .report import CAT_COLOR, CONF_COLOR, pick
from .score import CATEGORIES

CSS = """
:root{--bg:#fbfbfa;--card:#fff;--ink:#1a1d21;--dim:#6b7280;--line:#e5e7eb;
--accent:#1462b5;--good:#0f7b3f;--warn:#8a5a00;--bad:#a13b2f}
@media (prefers-color-scheme:dark){:root{--bg:#14161a;--card:#1c1f24;--ink:#e8eaed;
--dim:#9aa2ad;--line:#2c3138;--accent:#5fa8ff;--good:#4ec27f;--warn:#e0a83c;--bad:#ef7b6b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--dim);font-size:13px;margin-bottom:22px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 26px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:9px;
padding:9px 13px;font-size:12px;color:var(--dim)}
.stat b{display:block;font-size:19px;color:var(--ink);font-weight:650}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);
margin:34px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--line)}
.day{margin-bottom:22px}
.dayhead{display:flex;align-items:baseline;gap:10px;margin:0 0 9px}
.dayhead .d{font-weight:650;font-size:15px}
.dayhead .n{color:var(--dim);font-size:12px}
.empty{background:var(--card);border:1px dashed var(--line);border-radius:9px;
padding:13px 15px;color:var(--dim);font-size:13px}
.ev{background:var(--card);border:1px solid var(--line);border-radius:11px;
padding:15px 17px;margin-bottom:11px}
.ev.top{border-left:3px solid var(--good)}
.evhead{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}
.title{font-weight:625;font-size:16px;letter-spacing:-.01em;margin:0 0 5px}
.title a{color:inherit;text-decoration:none}
.title a:hover{color:var(--accent);text-decoration:underline}
.score{flex:0 0 auto;text-align:center;min-width:62px}
.score .v{font-size:23px;font-weight:700;line-height:1}
.score .l{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em}
.meta{color:var(--dim);font-size:12.5px;margin:0 0 9px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 11px}
.tag{font-size:10.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;
padding:3px 8px;border-radius:20px;border:1px solid currentColor}
.new{background:var(--good);color:#fff;border-color:var(--good)}
.blk{margin:10px 0 0}
.blk .h{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--dim);
margin-bottom:4px;font-weight:650}
.blk ul{margin:0;padding-left:17px}
.blk li{font-size:13px;margin-bottom:3px}
.pos{color:var(--good)}.neg{color:var(--bad)}
.opener{background:rgba(20,98,181,.07);border-left:2px solid var(--accent);
padding:9px 12px;border-radius:0 7px 7px 0;font-size:13.5px;font-style:italic}
.act{font-size:13px;font-weight:600;margin-top:10px}
.srcs{font-size:12px;color:var(--dim);margin-top:9px}
.srcs a{color:var(--accent)}
.reg{display:inline-block;margin-top:11px;background:var(--accent);color:#fff;
text-decoration:none;padding:7px 15px;border-radius:7px;font-size:13px;font-weight:600}
details{margin-top:11px}
summary{cursor:pointer;font-size:12px;color:var(--dim);user-select:none}
.skip{opacity:.72}
.skip .title{font-size:14px;font-weight:550}
table.scan{width:100%;border-collapse:collapse;font-size:13px}
table.scan td{padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
table.scan td.s{font-weight:700;width:52px}
.foot{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);
color:var(--dim);font-size:12px}
.verdict{display:inline-block;font-size:11px;font-weight:750;letter-spacing:.08em;
padding:4px 10px;border-radius:5px;color:#fff;margin-bottom:7px}
.v-go{background:var(--good)}.v-worth{background:var(--accent)}
.v-maybe{background:var(--warn)}.v-skip{background:var(--dim)}
.v-elig{background:var(--bad)}
.strip{display:flex;flex-wrap:wrap;gap:0;margin:11px 0 0;border:1px solid var(--line);
border-radius:8px;overflow:hidden}
.cell{flex:1 1 130px;padding:8px 11px;border-right:1px solid var(--line)}
.cell:last-child{border-right:none}
.cell .k{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim)}
.cell .v{font-size:14px;font-weight:650;margin-top:2px}
.cell.warn .v{color:var(--bad)}
.cos{margin-top:4px;font-size:11.5px;color:var(--dim)}
.co{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;
padding:3px 9px;border-radius:20px;background:rgba(20,98,181,.10);
border:1px solid rgba(20,98,181,.28);margin:0 5px 5px 0}
.co .r{font-weight:500;font-size:10.5px;color:var(--dim);text-transform:uppercase;
letter-spacing:.04em}
.jobs{margin-top:8px;border-left:2px solid var(--good);padding:2px 0 2px 11px}
.jobs .jc{font-size:13px;font-weight:650;margin-bottom:2px}
.jobs a{color:var(--accent);text-decoration:none;font-size:12.5px}
.jobs a:hover{text-decoration:underline}
.jobs .jl{font-size:11.5px;color:var(--dim)}
.elig{background:rgba(161,59,47,.09);border-left:2px solid var(--bad);
padding:9px 12px;border-radius:0 7px 7px 0;font-size:13px;margin:10px 0 0}
.chg{font-size:12px;color:var(--warn);font-weight:600;margin-top:7px}
.fup{font-size:13px;color:var(--dim);margin-top:6px;padding-left:12px;
border-left:2px solid var(--line)}
"""


def _e(s):
    return H.escape(str(s or ""))


def _dash():
    try:
        dt.date(2026, 9, 1).strftime("%-d")
        return True
    except Exception:
        return False


def _tag(text, color):
    return '<span class="tag" style="color:%s">%s</span>' % (color, _e(text))


VERDICT_CLASS = {"GO": "v-go", "WORTH IT": "v-worth", "MAYBE": "v-maybe",
                 "SKIP": "v-skip", "CHECK ELIGIBILITY": "v-elig"}


def _event_card(ev, is_new, rank=0, compact=False):
    """One event. Ordered to answer "should I go?" before "what is the score?"."""
    cat_label = CATEGORIES[ev.category][0]
    cls = "ev top" if (rank == 1 and not compact) else ("ev skip" if compact else "ev")
    v = ev.verdict or "SKIP"
    p = ['<div class="%s">' % cls]

    # ---- header: verdict, title, score
    p.append('<div class="evhead"><div style="flex:1 1 auto">')
    p.append('<span class="verdict %s">%s</span>' % (VERDICT_CLASS.get(v, "v-skip"), _e(v)))
    if is_new:
        p.append(' <span class="tag new">new today</span>')
    p.append('<p class="title"><a href="%s" target="_blank" rel="noopener">%s</a></p>'
             % (_e(ev.url), _e(ev.title)))

    place = ", ".join(x for x in [_e(ev.venue), _e(ev.city.title()) if ev.city else ""] if x)
    meta_bits = [ev.time_str or "time TBD"]
    if place:
        meta_bits.append(place)
    if ev.attendee_count is not None:
        meta_bits.append("%d registered" % ev.attendee_count)
    p.append('<p class="meta">%s</p>' % " &nbsp;·&nbsp; ".join(meta_bits))

    p.append('<div class="tags">')
    p.append(_tag(cat_label, CAT_COLOR.get(ev.category, "#666")))
    p.append(_tag("confidence " + ev.confidence, CONF_COLOR.get(ev.confidence, "#666")))
    if ev.sold_out:
        p.append(_tag("sold out", "#a13b2f"))
    if ev.requires_approval:
        p.append(_tag("approval needed", "#8a5a00"))
    p.append('</div></div>')
    p.append('<div class="score"><div class="v" style="color:%s">%d</div>'
             '<div class="l">/100</div></div></div>'
             % (CAT_COLOR.get(ev.category, "#666"), ev.score))

    if ev.changed_note:
        p.append('<p class="chg">Changed since your last run: %s</p>' % _e(ev.changed_note))

    if compact:
        p.append('<div class="blk"><div class="h">Why it scored low</div><ul><li>%s</li></ul>'
                 '</div></div>' % _e(ev.reasons[0] if ev.reasons else ""))
        return "".join(p)

    # ---- eligibility warning, first and unmissable
    elig = [n for n in ev.fit_notes if n.startswith(("ELIGIBILITY", "AUDIENCE MISMATCH"))]
    for n in elig:
        p.append('<div class="elig">%s</div>' % _e(n))

    # ---- cost of attendance strip
    c = ev.cost or {}
    p.append('<div class="strip">')
    if c.get("known"):
        p.append('<div class="cell"><div class="k">Getting there</div>'
                 '<div class="v">%d min each way</div><div class="cos">%s</div></div>'
                 % (c["one_way_min"], _e(c["detail"])))
        cash_cls = "cell warn" if c["total_cash"] > 25 else "cell"
        p.append('<div class="%s"><div class="k">Cost tonight</div><div class="v">$%.2f</div>'
                 '<div class="cos">$%.2f transit round trip%s</div></div>'
                 % (cash_cls, c["total_cash"], c["fare_round_trip"],
                    " + $%.0f ticket" % c["ticket"] if c["ticket"] else ", free entry"))
        p.append('<div class="cell"><div class="k">Total time</div>'
                 '<div class="v">%dh %02dm</div><div class="cos">travel + %d min event</div></div>'
                 % (c["total_minutes"] // 60, c["total_minutes"] % 60, c["event_minutes"]))
        if c.get("late_warning"):
            p.append('<div class="cell warn"><div class="k">Getting home</div>'
                     '<div class="v">check it</div><div class="cos">%s</div></div>'
                     % _e(c["late_warning"]))
    else:
        p.append('<div class="cell"><div class="k">Getting there</div>'
                 '<div class="v">unknown</div><div class="cos">%s</div></div>'
                 % _e(c.get("note", "venue coordinates not published")))
    p.append('</div>')

    # ---- companies present + verified openings
    strong_co = [x for x in (ev.companies or []) if x["role"] != "mention"]
    if strong_co:
        p.append('<div class="blk"><div class="h">Companies with people in the room</div><div>')
        for x in strong_co[:6]:
            p.append('<span class="co">%s <span class="r">%s</span></span>'
                     % (_e(_cdisp(x["name"])), _e(x["role"])))
        p.append('</div></div>')
    if ev.openings:
        p.append('<div class="blk"><div class="h">Open roles you match, verified on their '
                 'own job board today</div>')
        for o in ev.openings[:3]:
            p.append('<div class="jobs"><div class="jc">%s &mdash; %d relevant opening%s</div>'
                     % (_e(_cdisp(o["company"])), o["total"], "" if o["total"] == 1 else "s"))
            for r in o["roles"][:3]:
                p.append('<a href="%s" target="_blank" rel="noopener">%s</a>'
                         '<span class="jl"> &nbsp;%s</span><br>'
                         % (_e(r["url"]), _e(r["title"]), _e(r["location"])))
            p.append('<a href="%s" target="_blank" rel="noopener">see all &rarr;</a></div>'
                     % _e(o.get("board", "")))
        p.append('</div>')

    # ---- why / who / opener
    why = [n for n in ev.fit_notes if n not in elig]
    if why:
        p.append('<div class="blk"><div class="h">Why you should go</div><ul>')
        for n in why[:4]:
            p.append("<li>%s</li>" % _e(n))
        p.append('</ul></div>')

    p.append('<div class="blk"><div class="h">People to target</div><ul>')
    for w in ev.who_to_meet[:5]:
        p.append("<li>%s</li>" % _e(w))
    p.append('</ul></div>')

    p.append('<div class="blk"><div class="h">Your opener</div>'
             '<div class="opener">%s</div>' % _e(ev.opener))
    if ev.followup:
        p.append('<div class="fup">%s</div>' % _e(ev.followup))
    p.append('</div>')

    # ---- score breakdown
    p.append('<details><summary>Score breakdown &amp; confidence notes</summary>'
             '<div class="blk"><ul>')
    for r in ev.reasons:
        p.append('<li class="%s">%s</li>' % ("pos" if r.startswith("+") else "", _e(r)))
    for x in ev.penalties:
        p.append('<li class="neg">%s</li>' % _e(x))
    p.append('</ul>')
    if ev.verify_note:
        p.append('<div class="h" style="margin-top:8px">Why confidence is not HIGH</div>'
                 '<ul><li>%s</li></ul>' % _e(ev.verify_note))
    p.append('</div></details>')

    p.append('<p class="act">Action: %s</p>' % _e(action(ev)))
    if len(ev.sources) > 1:
        links = ", ".join('<a href="%s" target="_blank" rel="noopener">%s</a>'
                          % (_e(s["url"]), _e(s["source"])) for s in ev.sources if s.get("url"))
        p.append('<p class="srcs">Also listed on: %s</p>' % links)
    else:
        p.append('<p class="srcs">Source: %s</p>'
                 % _e(ev.sources[0]["source"] if ev.sources else "?"))
    p.append('<a class="reg" href="%s" target="_blank" rel="noopener">Register &rarr;</a>'
             % _e(ev.url))
    p.append('</div>')
    return "".join(p)


def write_html(path, days, new_uids, meta, today):
    fmt_day = "%A, %B %-d" if _dash() else "%A, %B %d"
    keys = sorted(days)
    tkey = today.isoformat()

    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           # Published from a public repo so the URL is reachable by anyone who has
           # it. Keep it out of search results: this page states that its owner is
           # job-hunting and roughly where they commute from.
           '<meta name="robots" content="noindex, nofollow, noarchive">',
           '<title>Job-Event Search &mdash; SF</title><style>%s</style></head><body>' % CSS,
           '<div class="wrap">']
    out.append("<h1>Where should I go to get hired?</h1>")
    out.append('<p class="sub">San Francisco &amp; Bay Area &nbsp;·&nbsp; window %s to %s '
               '&nbsp;·&nbsp; generated %s</p>'
               % (meta["window_start"], meta["window_end"],
                  dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
    out.append('<div class="stats">')
    for label, val in [("raw listings collected", meta["raw_listings"]),
                       ("unique events after dedupe", meta["unique_events"]),
                       ("recommended", meta["recommended"]),
                       ("filtered out", meta["gated"]),
                       ("HTTP requests", meta["http"]["fetched"]),
                       ("runtime", "%ss" % meta["runtime_s"])]:
        out.append('<div class="stat"><b>%s</b>%s</div>' % (_e(val), _e(label)))
    out.append('</div>')

    # ---------- TODAY
    if tkey in days:
        out.append("<h2>Today &mdash; %s</h2>" % _e(today.strftime(fmt_day)))
        sel = pick(days[tkey])
        if not sel:
            best = days[tkey][0].score if days[tkey] else 0
            out.append('<div class="empty"><b>No worthwhile event found today.</b><br>'
                       'Best candidate scored %d/100; the recommend threshold is %d. '
                       'Use the evening for applications and referral follow-ups instead.</div>'
                       % (best, config.MIN_SCORE_RECOMMEND))
        for i, ev in enumerate(sel, 1):
            out.append(_event_card(ev, ev.uid in new_uids, rank=i))
        skips = [e for e in days[tkey] if config.MIN_SCORE_REVIEW <= e.score
                 < config.MIN_SCORE_RECOMMEND][:3]
        if skips:
            out.append('<details><summary>Borderline events today that were '
                       'not recommended (%d)</summary>' % len(skips))
            for ev in skips:
                out.append(_event_card(ev, False, compact=True))
            out.append('</details>')

    # ---------- THIS WEEK
    out.append("<h2>Next 7 days</h2>")
    for k in keys[:8]:
        if k == tkey:
            continue
        d = dt.date.fromisoformat(k)
        sel = pick(days[k])
        out.append('<div class="day"><div class="dayhead"><span class="d">%s</span>'
                   '<span class="n">%d candidate%s scanned</span></div>'
                   % (_e(d.strftime(fmt_day)), len(days[k]), "" if len(days[k]) == 1 else "s"))
        if not sel:
            best = days[k][0].score if days[k] else 0
            out.append('<div class="empty">No worthwhile event found. '
                       '(best candidate scored %d/100)</div>' % best)
        for i, ev in enumerate(sel, 1):
            out.append(_event_card(ev, ev.uid in new_uids, rank=i))
        out.append('</div>')

    # ---------- TOP OF THE WINDOW (full detail, any date)
    everything = [e for k in keys for e in pick(days[k])]
    beyond_week = [e for e in everything if e.date_key not in set(keys[:8])]
    beyond_week.sort(key=lambda e: -e.score)
    if beyond_week:
        out.append("<h2>Highest value further out &mdash; register now</h2>")
        out.append('<p class="sub" style="margin-top:-6px">These are past the next '
                   'seven days, so they are easy to forget &mdash; and the good ones '
                   'sell out or close registration first.</p>')
        for i, ev in enumerate(beyond_week[:6], 1):
            out.append(_event_card(ev, ev.uid in new_uids, rank=i))

    # ---------- REST OF WINDOW
    out.append("<h2>Everything else in the window</h2>")
    shown = {id(e) for e in beyond_week[:6]}
    later = [e for e in beyond_week if id(e) not in shown]
    if later:
        out.append('<table class="scan">')
        for ev in later[:25]:
            out.append('<tr><td class="s" style="color:%s">%d</td>'
                       '<td><a href="%s" target="_blank" rel="noopener">%s</a><br>'
                       '<span style="color:var(--dim);font-size:12px">%s · %s · %s</span></td></tr>'
                       % (CAT_COLOR.get(ev.category, "#666"), ev.score, _e(ev.url), _e(ev.title),
                          _e(ev.date_key), _e(ev.time_str or "time TBD"),
                          _e(CATEGORIES[ev.category][0])))
        out.append('</table>')
    else:
        out.append('<div class="empty">Nothing yet this far out. Bay Area events are '
                   'typically posted 1&ndash;3 weeks ahead, so re-run daily.</div>')

    out.append('<div class="foot">Sources: Luma public event API, Meetup public search '
               'pages, HackerX JSON-LD, Eventbrite public browse pages. No logins, '
               'no CAPTCHA bypass, no paid APIs, no attendee personal data stored. '
               'Scores are rule-based and fully itemised above &mdash; nothing here is '
               'generated by a language model.</div>')
    out.append('</div></body></html>')

    outdir = os.path.dirname(path) or "."
    os.makedirs(outdir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(out))
    # Belt and braces alongside the meta tag above.
    with open(os.path.join(outdir, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write("User-agent: *\nDisallow: /\n")
    # GitHub Pages runs Jekyll by default, which ignores files it does not
    # recognise; .nojekyll serves the directory verbatim.
    open(os.path.join(outdir, ".nojekyll"), "w").close()
    return path
