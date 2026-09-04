"""Single self-contained HTML dashboard. No build step, no CDN, no JS deps."""
import datetime as dt
import html as H
import json
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

/* ---------------------------------------------------- tabs */
.tabs{display:flex;gap:4px;flex-wrap:wrap;margin:20px 0 4px;
position:sticky;top:0;z-index:20;background:var(--bg);padding:8px 0;
border-bottom:1px solid var(--line)}
.tab{appearance:none;border:1px solid var(--line);background:var(--card);
color:var(--fg);font:inherit;font-size:13px;font-weight:600;padding:7px 13px;
border-radius:7px;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.tab:hover{border-color:var(--accent)}
.tab[aria-selected="true"]{background:var(--accent);color:#fff;border-color:var(--accent)}
.tab .cnt{font-size:11px;font-weight:700;padding:1px 6px;border-radius:10px;
background:rgba(0,0,0,.14)}
.tab[aria-selected="true"] .cnt{background:rgba(255,255,255,.25)}
.tab .cnt.zero{opacity:.45}
.panel[hidden]{display:none!important}

/* ---------------------------------------------------- triage controls */
.triage{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 0;
padding-top:10px;border-top:1px dashed var(--line)}
.tbtn{appearance:none;border:1px solid var(--line);background:transparent;
color:var(--fg);font:inherit;font-size:12.5px;font-weight:600;padding:6px 12px;
border-radius:6px;cursor:pointer;transition:background .12s,border-color .12s}
.tbtn:hover{border-color:var(--accent);background:rgba(20,98,181,.07)}
.tbtn[aria-pressed="true"]{color:#fff;border-color:transparent}
.tbtn.go[aria-pressed="true"]{background:var(--good)}
.tbtn.save[aria-pressed="true"]{background:var(--accent)}
.tbtn.hide[aria-pressed="true"]{background:var(--dim)}
.state{font-size:12px;color:var(--dim);align-self:center;margin-left:auto}
.ev.is-going{border-left:3px solid var(--good)}
.ev.is-saved{border-left:3px solid var(--accent)}
.ev.is-hidden{opacity:.55}

/* ---------------------------------------------------- calendar */
.calwrap{margin:14px 0 0}
.cal{margin-bottom:22px}
.cal h3{font-size:15px;margin:0 0 8px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}
.dow{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;
color:var(--dim);text-align:center;padding:4px 0;font-weight:700}
.cell{aspect-ratio:1/1;border:1px solid var(--line);border-radius:7px;
background:var(--card);padding:5px 4px 4px;display:flex;flex-direction:column;
align-items:center;justify-content:flex-start;cursor:pointer;position:relative;
font-size:13px;min-height:46px}
.cell.out{opacity:.28;cursor:default;background:transparent;border-color:transparent}
.cell.none{cursor:default;color:var(--dim)}
.cell:not(.out):not(.none):hover{border-color:var(--accent)}
.cell.sel{outline:2px solid var(--accent);outline-offset:-2px}
.cell.today .dnum{background:var(--fg);color:var(--bg);border-radius:50%;
width:20px;height:20px;display:flex;align-items:center;justify-content:center}
.cell .dnum{font-weight:650;line-height:20px;height:20px}
.cell .dots{display:flex;gap:2px;margin-top:3px;flex-wrap:wrap;
justify-content:center;max-width:100%}
.cell .dot{width:5px;height:5px;border-radius:50%;background:var(--dim)}
.cell .dot.go{background:var(--good)}.cell .dot.worth{background:var(--accent)}
.cell .dot.maybe{background:var(--warn)}
.cell .going{position:absolute;top:2px;right:3px;font-size:9px;color:var(--good);
font-weight:800}
.callegend{font-size:11.5px;color:var(--dim);display:flex;gap:14px;flex-wrap:wrap;
margin:2px 0 16px}
.callegend span{display:inline-flex;align-items:center;gap:5px}
.callegend i{width:6px;height:6px;border-radius:50%;display:inline-block}

/* ---------------------------------------------------- misc chrome */
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:14px 0 6px}
.abtn{appearance:none;border:1px solid var(--line);background:var(--card);
color:var(--fg);font:inherit;font-size:12.5px;font-weight:600;padding:7px 12px;
border-radius:6px;cursor:pointer;text-decoration:none;display:inline-block}
.abtn:hover{border-color:var(--accent)}
.abtn.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(80px);
background:var(--fg);color:var(--bg);padding:11px 16px;border-radius:8px;
font-size:13px;font-weight:600;box-shadow:0 6px 24px rgba(0,0,0,.25);z-index:100;
display:flex;align-items:center;gap:14px;transition:transform .2s;max-width:92vw}
.toast.show{transform:translateX(-50%) translateY(0)}
.toast button{appearance:none;background:transparent;border:1px solid currentColor;
color:inherit;font:inherit;font-size:12px;font-weight:700;padding:3px 10px;
border-radius:5px;cursor:pointer}
.ghost{border:1px dashed var(--line);border-radius:9px;padding:14px 16px;
color:var(--dim);font-size:13px;margin:10px 0}
.ghost b{color:var(--fg)}
.orphan{border:1px solid var(--line);border-left:3px solid var(--warn);
border-radius:9px;padding:12px 14px;margin:0 0 10px;background:var(--card)}
.orphan .t{font-weight:650;font-size:14.5px}
.orphan .m{font-size:12.5px;color:var(--dim);margin-top:3px}
.sync{margin-top:10px}
.sync textarea{width:100%;min-height:74px;font-family:ui-monospace,SFMono-Regular,
Menlo,monospace;font-size:11px;border:1px solid var(--line);border-radius:7px;
padding:9px;background:var(--card);color:var(--fg);resize:vertical}
.daynote{font-size:12px;color:var(--dim);margin:2px 0 8px}
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

    # Data attributes are the contract with the client-side layer: it filters,
    # counts, builds the calendar and writes .ics entirely from these, so there is
    # no second copy of the event data to keep in sync.
    dur = (ev.cost or {}).get("event_minutes") or 120
    p = ['<div class="%s" data-uid="%s" data-date="%s" data-start="%s" data-dur="%d" '
         'data-score="%d" data-verdict="%s" data-age="%s" data-changed="%d" '
         'data-title="%s" data-venue="%s" data-url="%s" data-time="%s">'
         % (cls, _e(ev.uid), _e(ev.date_key),
            _e(ev.start.strftime("%Y%m%dT%H%M%S") if ev.start else ""), dur,
            ev.score, _e(v), "" if ev.age_days is None else ev.age_days,
            1 if ev.changed_note else 0,
            _e(ev.title), _e(ev.venue or ""), _e(ev.url), _e(ev.time_str or ""))]

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

    if not compact:
        p.append('<div class="triage">'
                 '<button class="tbtn go" data-act="going" aria-pressed="false">'
                 'I am going</button>'
                 '<button class="tbtn save" data-act="saved" aria-pressed="false">'
                 'Save for later</button>'
                 '<button class="tbtn hide" data-act="hidden" aria-pressed="false">'
                 'Not interested</button>'
                 '<span class="state"></span></div>')

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


def _month_grids(keys, today):
    """Server-rendered month grids for the window. JS annotates them from the card
    pool, so the calendar can never disagree with the list."""
    if not keys:
        return ""
    first = dt.date.fromisoformat(keys[0])
    last = dt.date.fromisoformat(keys[-1])
    in_window = set(keys)
    out = ['<div class="calwrap">']
    out.append('<div class="callegend">'
               '<span><i style="background:var(--good)"></i>GO</span>'
               '<span><i style="background:var(--accent)"></i>worth it</span>'
               '<span><i style="background:var(--warn)"></i>maybe</span>'
               '<span><b style="color:var(--good)">&#9679;</b>&nbsp;you are going</span>'
               '<span>Tap a date to see that day only.</span>'
               '</div>')
    cur = dt.date(first.year, first.month, 1)
    while cur <= last:
        out.append('<div class="cal"><h3>%s</h3><div class="grid">' % cur.strftime("%B %Y"))
        for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
            out.append('<div class="dow">%s</div>' % d)
        # Monday-first offset
        lead = cur.weekday()
        for _ in range(lead):
            out.append('<div class="cell out"></div>')
        day = cur
        while day.month == cur.month:
            iso = day.isoformat()
            cls = "cell"
            if iso not in in_window:
                cls += " out"
            if day == today:
                cls += " today"
            out.append('<div class="%s" data-cell="%s"><span class="dnum">%d</span>'
                       '<span class="dots"></span></div>' % (cls, iso, day.day))
            day += dt.timedelta(days=1)
        out.append('</div></div>')
        cur = (cur.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    out.append('</div>')
    return "".join(out)


JS = r"""
(function(){
'use strict';
// Triage state lives in localStorage. The page is static on GitHub Pages, so the
// only alternatives were a secret embedded in a public page or a paid backend.
// For a single-user dashboard this is the right trade; the Sync panel bridges it
// back to the Python side for the Telegram alerts.
var KEY='jes.triage.v1', HORIZON=14;
var state={}, mode='upnext', selDate=null, showAll=false, undoStack=null;

function load(){
  try{ state=JSON.parse(localStorage.getItem(KEY)||'{}')||{}; }
  catch(e){ state={}; }
  // Merge the copy committed to the repo. Whichever side was marked more
  // recently wins, so syncing on the laptop carries over to the phone without
  // either device clobbering a newer decision made on the other.
  var seed={};
  try{ seed=JSON.parse(document.body.getAttribute('data-seed')||'{}')||{}; }
  catch(e){ seed={}; }
  var merged=0;
  Object.keys(seed).forEach(function(u){
    var s=seed[u], mine=state[u];
    if(!s || !s.s) return;
    if(!mine || (s.t||0) > (mine.t||0)){
      state[u]={s:s.s, t:s.t||0, m:s.m||{}};
      merged++;
    }
  });
  if(merged){ save(); }
}
function save(){
  try{ localStorage.setItem(KEY,JSON.stringify(state)); }
  catch(e){ toast('Could not save - browser storage is blocked.'); }
}
function st(uid){ return (state[uid]||{}).s || ''; }

var cards=[].slice.call(document.querySelectorAll('.ev[data-uid]'));
var groups=[].slice.call(document.querySelectorAll('.day[data-date]'));
var TODAY=document.body.getAttribute('data-today');

// ---------------------------------------------------------------- filtering
function visible(c){
  var uid=c.getAttribute('data-uid'), s=st(uid);
  var date=c.getAttribute('data-date');
  var age=c.getAttribute('data-age'), changed=c.getAttribute('data-changed')==='1';
  var future = date>=TODAY;
  if(mode==='going')  return s==='going';
  if(mode==='saved')  return s==='saved';
  if(mode==='hidden') return s==='hidden';
  if(mode==='new'){
    if(s==='hidden') return false;
    var isNew = age!=='' && parseInt(age,10)<=2;
    return future && (( !s && isNew ) || changed);
  }
  if(mode==='calendar'){
    if(s==='hidden') return false;
    return selDate ? date===selDate : false;
  }
  // upnext
  if(s) return false;
  if(!future) return false;
  if(showAll) return true;
  return daysFrom(date)<HORIZON;
}
function daysFrom(iso){
  return Math.round((new Date(iso+'T00:00:00')-new Date(TODAY+'T00:00:00'))/864e5);
}

function render(){
  var shown=0;
  cards.forEach(function(c){
    var v=visible(c);
    c.hidden=!v;
    if(v) shown++;
    var s=st(c.getAttribute('data-uid'));
    c.classList.toggle('is-going',s==='going');
    c.classList.toggle('is-saved',s==='saved');
    c.classList.toggle('is-hidden',s==='hidden');
    var btns=c.querySelectorAll('.tbtn');
    for(var i=0;i<btns.length;i++){
      btns[i].setAttribute('aria-pressed', String(btns[i].getAttribute('data-act')===s));
    }
    var lbl=c.querySelector('.state');
    if(lbl) lbl.textContent = s==='going' ? 'Registered / attending'
                            : s==='saved' ? 'Saved'
                            : s==='hidden' ? 'Hidden from the main list' : '';
  });
  groups.forEach(function(g){
    var any=g.querySelector('.ev:not([hidden])');
    g.hidden=!any;
  });
  document.getElementById('calpanel').hidden = (mode!=='calendar');
  document.getElementById('horizonbar').hidden = (mode!=='upnext');
  document.getElementById('goingbar').hidden = (mode!=='going');
  renderOrphans();
  renderEmpty(shown);
  counts();
  if(mode==='calendar') paintCalendar();
}

function renderEmpty(shown){
  var e=document.getElementById('empty');
  if(shown>0 && !(mode==='calendar'&&!selDate)){ e.hidden=true; return; }
  var msg={
    upnext:'<b>Nothing left to triage.</b> Every upcoming event has been marked. Check <em>Saved</em> for the ones you were undecided about.',
    'new':'<b>Nothing new.</b> No listings posted in the last 3 days, and nothing you are tracking has changed. That is a normal result - Bay Area events post 1-3 weeks ahead.',
    calendar: selDate ? '<b>Nothing on '+selDate+'.</b> Pick another date.' : 'Pick a date above to see that day&rsquo;s events.',
    going:'<b>Nothing marked as going yet.</b> Use <em>I am going</em> on an event once you have registered, and it will move here.',
    saved:'<b>Nothing saved.</b> Use <em>Save for later</em> when you are undecided.',
    hidden:'<b>Nothing hidden.</b> Anything you mark <em>Not interested</em> lands here, so it is never lost.'
  }[mode]||'';
  e.innerHTML=msg; e.hidden=!msg;
}

function counts(){
  var n={upnext:0,'new':0,going:0,saved:0,hidden:0};
  var m=mode;
  ['upnext','new','going','saved','hidden'].forEach(function(k){
    mode=k; n[k]=cards.filter(visible).length;
  });
  mode=m;
  Object.keys(n).forEach(function(k){
    var el=document.querySelector('.tab[data-panel="'+k+'"] .cnt');
    if(el){ el.textContent=n[k]; el.classList.toggle('zero',n[k]===0); }
  });
}

// ------------------------------------------------------- orphaned "going" items
// An event marked "going" whose date has passed, or whose listing was pulled,
// has no card in today's build. Showing the stored snapshot means a thing you
// registered for never silently disappears.
function renderOrphans(){
  var box=document.getElementById('orphans');
  box.innerHTML='';
  if(mode!=='going') return;
  var live={}; cards.forEach(function(c){ live[c.getAttribute('data-uid')]=1; });
  Object.keys(state).forEach(function(uid){
    if(state[uid].s!=='going' || live[uid]) return;
    var m=state[uid].m||{};
    var past = m.d && m.d < TODAY;
    var d=document.createElement('div');
    d.className='orphan';
    d.innerHTML='<div class="t">'+esc(m.ti||'(untitled)')+'</div>'
      +'<div class="m">'+esc(m.d||'?')+' '+esc(m.tm||'')+(m.v?' &middot; '+esc(m.v):'')
      +' &mdash; '+(past?'already happened':'no longer in the current feed')+'</div>'
      +(m.u?'<div class="m"><a href="'+esc(m.u)+'" target="_blank" rel="noopener">open listing</a></div>':'')
      +'<div class="triage"><button class="tbtn" data-forget="'+esc(uid)+'">Remove from my list</button></div>';
    box.appendChild(d);
  });
}
function esc(t){ var d=document.createElement('div'); d.textContent=t==null?'':t; return d.innerHTML; }

// ---------------------------------------------------------------- calendar
function paintCalendar(){
  var byDate={};
  cards.forEach(function(c){
    var uid=c.getAttribute('data-uid'), s=st(uid);
    if(s==='hidden') return;
    var d=c.getAttribute('data-date');
    (byDate[d]=byDate[d]||{list:[],going:false});
    if(s==='going'){ byDate[d].going=true; }
    else if(!s){ byDate[d].list.push(c.getAttribute('data-verdict')); }
  });
  [].slice.call(document.querySelectorAll('.cell[data-cell]')).forEach(function(cell){
    var d=cell.getAttribute('data-cell'), info=byDate[d];
    var dots=cell.querySelector('.dots');
    dots.innerHTML='';
    cell.classList.toggle('sel', d===selDate);
    var mark=cell.querySelector('.going'); if(mark) mark.remove();
    if(info && info.going){
      var g=document.createElement('span'); g.className='going'; g.textContent='●';
      cell.appendChild(g);
    }
    var n=info?info.list.length:0;
    cell.classList.toggle('none', n===0 && !(info&&info.going));
    (info?info.list:[]).slice(0,4).forEach(function(v){
      var e=document.createElement('span');
      e.className='dot '+(v==='GO'?'go':v==='WORTH IT'?'worth':v==='MAYBE'?'maybe':'');
      dots.appendChild(e);
    });
  });
}

// ---------------------------------------------------------------- .ics export
function pad(n){ return (n<10?'0':'')+n; }
function icsEscape(t){ return String(t||'').replace(/([,;\\])/g,'\\$1').replace(/\n/g,'\\n'); }
function buildICS(){
  var out=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//job-event-search//EN',
           'CALSCALE:GREGORIAN','METHOD:PUBLISH'];
  var now=new Date();
  var stamp=now.getUTCFullYear()+pad(now.getUTCMonth()+1)+pad(now.getUTCDate())+'T'
           +pad(now.getUTCHours())+pad(now.getUTCMinutes())+pad(now.getUTCSeconds())+'Z';
  var n=0;
  cards.forEach(function(c){
    var uid=c.getAttribute('data-uid');
    if(st(uid)!=='going') return;
    var startRaw=c.getAttribute('data-start');
    if(!startRaw) return;
    var dur=parseInt(c.getAttribute('data-dur')||'120',10);
    // Floating local time: no VTIMEZONE needed and every calendar app reads it
    // as the viewer's local time, which is correct for an in-person SF event.
    var sd=new Date(startRaw.slice(0,4)+'-'+startRaw.slice(4,6)+'-'+startRaw.slice(6,8)
                    +'T'+startRaw.slice(9,11)+':'+startRaw.slice(11,13)+':00');
    var ed=new Date(sd.getTime()+dur*60000);
    function fmt(d){ return d.getFullYear()+pad(d.getMonth()+1)+pad(d.getDate())+'T'
                     +pad(d.getHours())+pad(d.getMinutes())+'00'; }
    out.push('BEGIN:VEVENT');
    out.push('UID:'+uid+'@job-event-search');
    out.push('DTSTAMP:'+stamp);
    out.push('DTSTART:'+fmt(sd));
    out.push('DTEND:'+fmt(ed));
    out.push('SUMMARY:'+icsEscape(c.getAttribute('data-title')));
    var v=c.getAttribute('data-venue'); if(v) out.push('LOCATION:'+icsEscape(v));
    out.push('DESCRIPTION:'+icsEscape('Score '+c.getAttribute('data-score')+'/100. '
             +c.getAttribute('data-url')));
    out.push('URL:'+icsEscape(c.getAttribute('data-url')));
    out.push('END:VEVENT');
    n++;
  });
  out.push('END:VCALENDAR');
  return n? out.join('\r\n') : null;
}
function download(name,text,type){
  var b=new Blob([text],{type:type||'text/plain'});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(b); a.download=name;
  document.body.appendChild(a); a.click();
  setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); },0);
}

// ---------------------------------------------------------------- toast + undo
var toastEl;
function toast(msg,undo){
  if(!toastEl){
    toastEl=document.createElement('div'); toastEl.className='toast';
    document.body.appendChild(toastEl);
  }
  toastEl.innerHTML='<span></span>';
  toastEl.firstChild.textContent=msg;
  if(undo){
    var b=document.createElement('button'); b.textContent='Undo';
    b.onclick=function(){ undo(); toastEl.classList.remove('show'); };
    toastEl.appendChild(b);
  }
  toastEl.classList.add('show');
  clearTimeout(toastEl._t);
  toastEl._t=setTimeout(function(){ toastEl.classList.remove('show'); }, undo?6000:2600);
}

// ---------------------------------------------------------------- interactions
function setTriage(card,act){
  var uid=card.getAttribute('data-uid');
  var prev=state[uid]?JSON.parse(JSON.stringify(state[uid])):null;
  if(st(uid)===act){ delete state[uid]; }
  else{
    state[uid]={s:act,t:Date.now(),m:{
      ti:card.getAttribute('data-title'), d:card.getAttribute('data-date'),
      tm:card.getAttribute('data-time'), v:card.getAttribute('data-venue'),
      u:card.getAttribute('data-url')}};
  }
  save(); render();
  var word={going:'Marked as going',saved:'Saved for later',hidden:'Hidden'}[act]
            || 'Cleared';
  toast(st(uid)?word:'Cleared', function(){
    if(prev) state[uid]=prev; else delete state[uid];
    save(); render();
  });
}

document.addEventListener('click',function(e){
  var t=e.target;
  var tab=t.closest?t.closest('.tab'):null;
  if(tab){
    mode=tab.getAttribute('data-panel');
    [].slice.call(document.querySelectorAll('.tab')).forEach(function(x){
      x.setAttribute('aria-selected', String(x===tab));
    });
    render();
    window.scrollTo({top:0,behavior:'smooth'});
    return;
  }
  var btn=t.closest?t.closest('.tbtn[data-act]'):null;
  if(btn){ setTriage(btn.closest('.ev'), btn.getAttribute('data-act')); return; }
  var forget=t.closest?t.closest('[data-forget]'):null;
  if(forget){
    var u=forget.getAttribute('data-forget');
    var prev=state[u]; delete state[u]; save(); render();
    toast('Removed', function(){ state[u]=prev; save(); render(); });
    return;
  }
  var cell=t.closest?t.closest('.cell[data-cell]'):null;
  if(cell && !cell.classList.contains('out')){
    var d=cell.getAttribute('data-cell');
    selDate = (selDate===d)? null : d;
    render();
    return;
  }
  if(t.id==='horizon'){
    showAll=!showAll;
    t.textContent = showAll ? 'Show only the next 2 weeks'
                            : 'Show the whole window';
    render(); return;
  }
  if(t.id==='ics'){
    var ics=buildICS();
    if(!ics){ toast('Nothing marked as going yet.'); return; }
    download('job-events.ics',ics,'text/calendar');
    toast('Downloaded - open it to add these to your calendar.');
    return;
  }
  if(t.closest && t.closest('[data-sync]')){
    var box=document.getElementById('syncbox');
    box.hidden=!box.hidden;
    if(!box.hidden){
      var slim={};
      Object.keys(state).forEach(function(u){ slim[u]={s:state[u].s,t:state[u].t,m:state[u].m}; });
      document.getElementById('syncjson').value=JSON.stringify(slim);
    }
    return;
  }
  if(t.id==='copysync'){
    var ta=document.getElementById('syncjson');
    ta.select();
    navigator.clipboard.writeText(ta.value).then(
      function(){ toast('Copied. Paste it into data/triage.json and commit.'); },
      function(){ toast('Select the text and copy manually.'); });
    return;
  }
  if(t.id==='dlsync'){
    download('triage.json',document.getElementById('syncjson').value,'application/json');
    toast('Saved triage.json - move it into data/ and commit.');
    return;
  }
});

load();
render();
})();
"""


def write_html(path, days, new_uids, meta, today, seed=None):
    fmt_day = "%A, %B %-d" if _dash() else "%A, %B %d"
    keys = sorted(days)
    tkey = today.isoformat()

    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           # Published from a public repo so the URL is reachable by anyone who has
           # it. Keep it out of search results: this page states that its owner is
           # job-hunting and roughly where they commute from.
           '<meta name="robots" content="noindex, nofollow, noarchive">',
           '<title>Job-Event Search &mdash; SF</title><style>%s</style></head>' % CSS,
           # data/triage.json travels through git, so marks made on the laptop
           # reach the phone. The client merges it into localStorage by recency.
           '<body data-today="%s" data-seed="%s">'
           % (_e(tkey), _e(json.dumps(seed or {}, separators=(",", ":")))),
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

    # ---------- tabs
    tabs = [("upnext", "Up next", True), ("new", "New &amp; changed", False),
            ("calendar", "Calendar", False), ("going", "Going", False),
            ("saved", "Saved", False), ("hidden", "Hidden", False)]
    out.append('<div class="tabs" role="tablist">')
    for pid, label, sel in tabs:
        cnt = "" if pid == "calendar" else '<span class="cnt">0</span>'
        out.append('<button class="tab" role="tab" data-panel="%s" aria-selected="%s">'
                   '%s%s</button>' % (pid, "true" if sel else "false", label, cnt))
    out.append('</div>')

    # ---------- calendar (hidden unless the Calendar tab is active)
    out.append('<div id="calpanel" hidden>')
    out.append(_month_grids(keys, today))
    out.append('</div>')

    # ---------- contextual toolbars
    out.append('<div class="bar" id="horizonbar">'
               '<button class="abtn" id="horizon">Show the whole window</button>'
               '<button class="abtn" data-sync>Sync to the Telegram alerts</button>'
               '</div>')
    out.append('<div class="bar" id="goingbar" hidden>'
               '<button class="abtn primary" id="ics">Add these to my calendar (.ics)</button>'
               '<button class="abtn" data-sync>Sync to the Telegram alerts</button>'
               '</div>')
    out.append('<div class="sync" id="syncbox" hidden>'
               '<p class="daynote">The dashboard keeps your choices in this browser only. '
               'To let the daily Telegram alert know what you have registered for, copy '
               'this into <code>data/triage.json</code> in the repo and commit it.</p>'
               '<textarea id="syncjson" readonly></textarea>'
               '<div class="bar"><button class="abtn primary" id="copysync">Copy</button>'
               '<button class="abtn" id="dlsync">Download triage.json</button></div></div>')

    out.append('<div id="empty" class="ghost" hidden></div>')
    out.append('<div id="orphans"></div>')

    # ---------- the single card pool, grouped by day. Every panel is a view over
    #            this, so the calendar and the lists can never disagree.
    for k in keys:
        sel = pick(days[k])
        if not sel:
            continue
        d = dt.date.fromisoformat(k)
        label = d.strftime(fmt_day)
        if k == tkey:
            label = "Today &mdash; " + label
        elif (d - today).days == 1:
            label = "Tomorrow &mdash; " + label
        out.append('<div class="day" data-date="%s"><div class="dayhead">'
                   '<span class="d">%s</span><span class="n">%d candidate%s scanned</span>'
                   '</div>' % (_e(k), label, len(days[k]),
                               "" if len(days[k]) == 1 else "s"))
        for i, ev in enumerate(sel, 1):
            out.append(_event_card(ev, ev.uid in new_uids, rank=i))
        out.append('</div>')

    # ---------- transparency: what was scanned and rejected
    borderline = []
    for k in keys:
        borderline.extend([e for e in days[k]
                           if config.MIN_SCORE_REVIEW <= e.score < config.MIN_SCORE_RECOMMEND])
    borderline.sort(key=lambda e: -e.score)
    if borderline:
        out.append('<details style="margin-top:26px"><summary>Borderline events across '
                   'the whole window that were scanned but not recommended (%d)</summary>'
                   % len(borderline))
        out.append('<p class="daynote">Shown so you can audit the filter. If something '
                   'here looks like it should have been recommended, that is a scoring '
                   'bug worth fixing.</p>')
        for ev in borderline[:20]:
            out.append(_event_card(ev, False, compact=True))
        out.append('</details>')

    out.append('<div class="foot">Sources: Luma public event API, Meetup public search '
               'pages, HackerX JSON-LD, Eventbrite public browse pages. No logins, '
               'no CAPTCHA bypass, no paid APIs, no attendee personal data stored. '
               'Scores are rule-based and fully itemised above &mdash; nothing here is '
               'generated by a language model.<br><br>Your Going / Saved / Hidden marks '
               'are stored in this browser only (localStorage) and are never uploaded. '
               'They survive the daily rebuild because each event has a stable id, but '
               'they do not follow you to another device.</div>')
    out.append('</div>')
    out.append('<script>%s</script>' % JS)
    out.append('</body></html>')

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
