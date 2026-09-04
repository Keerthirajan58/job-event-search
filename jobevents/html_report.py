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
/* MUST come first and MUST stay !important.
   The HTML `hidden` attribute is only honoured by the user-agent rule
   [hidden]{display:none}, which loses to ANY author rule of equal specificity -
   so `.bar{display:flex}` and `#modal{display:flex}` silently re-showed elements
   the script had hidden. That shipped a permanently-open empty modal over the
   whole page. Author-level !important is the only thing that cannot be
   out-specified by a later display rule. */
[hidden]{display:none!important}

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

/* ---------------------------------------------------- header summary */
.summary{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
margin:0 0 18px;font-size:12.5px;color:var(--dim)}
.summary .pill{background:var(--card);border:1px solid var(--line);border-radius:20px;
padding:4px 11px;font-weight:600;color:var(--ink)}
details.stats-d{margin:0 0 18px}
details.stats-d>summary{cursor:pointer;font-size:12.5px;color:var(--dim);
list-style:none;display:inline-flex;align-items:center;gap:6px;
border:1px solid var(--line);border-radius:20px;padding:4px 12px;background:var(--card)}
details.stats-d>summary::-webkit-details-marker{display:none}
details.stats-d>summary:hover{border-color:var(--accent);color:var(--ink)}
details.stats-d>summary::after{content:"▾";font-size:10px}
details.stats-d[open]>summary::after{content:"▴"}
details.stats-d .stats{margin-top:12px}

/* ---------------------------------------------------- tabs */
.tabbar{position:sticky;top:0;z-index:30;background:var(--bg);padding:10px 0 0;
margin:18px 0 16px;border-bottom:1px solid var(--line)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding-bottom:10px}
.tabsep{width:1px;align-self:stretch;background:var(--line);margin:2px 6px}
.tab{appearance:none;border:1px solid var(--line);background:var(--card);
color:var(--fg);font:inherit;font-size:13px;font-weight:600;padding:8px 14px;
border-radius:8px;cursor:pointer;display:inline-flex;align-items:center;gap:7px;
transition:border-color .12s,background .12s,color .12s}
.tab .dotc{width:7px;height:7px;border-radius:50%;background:var(--tc);flex:none}
.tab:hover{border-color:var(--tc)}
.tab[aria-selected="true"]{background:var(--tc);border-color:var(--tc);color:#fff}
.tab[aria-selected="true"] .dotc{background:rgba(255,255,255,.85)}
.tab .cnt{font-size:11px;font-weight:800;padding:1px 7px;border-radius:10px;
background:var(--line);color:var(--fg);min-width:18px;text-align:center}
.tab[aria-selected="true"] .cnt{background:rgba(255,255,255,.26);color:#fff}
.tab .cnt.zero{opacity:.5}
.t-upnext{--tc:#1462b5}.t-new{--tc:#c2410c}.t-calendar{--tc:#6d28d9}
.t-going{--tc:#15803d}.t-saved{--tc:#0e7490}.t-hidden{--tc:#6b7280}

/* ---------------------------------------------------- action buttons */
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 16px}
.bar .spacer{flex:1 1 auto}
.abtn{appearance:none;border:1px solid var(--line);background:var(--card);
color:var(--fg);font:inherit;font-size:12.5px;font-weight:600;padding:8px 13px;
border-radius:8px;cursor:pointer;text-decoration:none;display:inline-flex;
align-items:center;gap:7px;transition:border-color .12s,background .12s}
.abtn:hover{border-color:var(--accent);background:rgba(20,98,181,.06)}
.abtn.dl{background:#0f766e;border-color:#0f766e;color:#fff}
.abtn.dl:hover{background:#115e56;border-color:#115e56}
.abtn.quiet{border-style:dashed;color:var(--dim);font-weight:500}
.abtn.quiet:hover{color:var(--ink)}

/* ---------------------------------------------------- triage controls */
.triage{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0 0;
padding-top:12px;border-top:1px dashed var(--line)}
.tbtn{appearance:none;font:inherit;font-size:12.5px;font-weight:650;
padding:8px 14px;border-radius:8px;cursor:pointer;border:1.5px solid var(--bc);
background:var(--bg2);color:var(--bc);box-shadow:0 1px 0 rgba(0,0,0,.04);
display:inline-flex;align-items:center;gap:6px;transition:all .12s}
.tbtn:hover{background:var(--bc);color:#fff}
.tbtn[aria-pressed="true"]{background:var(--bc);color:#fff;
box-shadow:inset 0 1px 2px rgba(0,0,0,.2)}
.tbtn.go{--bc:#15803d;--bg2:rgba(21,128,61,.09)}
.tbtn.save{--bc:#0e7490;--bg2:rgba(14,116,144,.09)}
.tbtn.hide{--bc:#6b7280;--bg2:rgba(107,114,128,.09)}
.state{font-size:12px;color:var(--dim);margin-left:auto;font-weight:600}
.ev.is-going{border-left:3px solid #15803d}
.ev.is-saved{border-left:3px solid #0e7490}
.ev.is-hidden{opacity:.6}

/* ---------------------------------------------------- calendar
   NOTE: these are .cday, not .cell. The event cost strip already owns .cell, and
   an earlier version of this file collided with it - every "Getting there" box
   inherited aspect-ratio:1/1 and grew into a huge square. */
.calnav{display:flex;gap:8px;align-items:center;margin:0 0 14px;flex-wrap:wrap}
.calnav select{font:inherit;font-size:13px;font-weight:600;padding:7px 10px;
border:1px solid var(--line);border-radius:8px;background:var(--card);
color:var(--fg);cursor:pointer}
.calnav .nav{appearance:none;border:1px solid var(--line);background:var(--card);
color:var(--fg);width:34px;height:34px;border-radius:8px;cursor:pointer;
font-size:15px;line-height:1;display:inline-flex;align-items:center;
justify-content:center}
.calnav .nav:hover:not(:disabled){border-color:var(--accent)}
.calnav .nav:disabled{opacity:.35;cursor:default}
.cal{margin-bottom:8px}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}
.dow{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;
color:var(--dim);text-align:center;padding:4px 0;font-weight:700}
.cday{height:60px;border:1px solid var(--line);border-radius:9px;
background:var(--card);padding:6px 4px 4px;display:flex;flex-direction:column;
align-items:center;justify-content:flex-start;cursor:pointer;position:relative;
font-size:13px;transition:border-color .12s,background .12s}
.cday.out{opacity:.25;cursor:default;background:transparent;border-color:transparent}
.cday.none{cursor:default;color:var(--dim)}
.cday:not(.out):not(.none):hover{border-color:var(--accent);
background:rgba(20,98,181,.06)}
.cday.sel{border-color:var(--accent);background:rgba(20,98,181,.12);
box-shadow:inset 0 0 0 1px var(--accent)}
.cday.today .dnum{background:var(--fg);color:var(--bg);border-radius:50%;
width:21px;height:21px;display:flex;align-items:center;justify-content:center}
.cday .dnum{font-weight:650;line-height:21px;height:21px}
.cday .dots{display:flex;gap:2px;margin-top:4px;flex-wrap:wrap;
justify-content:center;max-width:100%}
.cday .dot{width:5px;height:5px;border-radius:50%;background:var(--dim)}
.cday .dot.go{background:var(--good)}.cday .dot.worth{background:var(--accent)}
.cday .dot.maybe{background:var(--warn)}
.cday .going{position:absolute;top:3px;right:4px;font-size:9px;color:var(--good)}
.callegend{font-size:11.5px;color:var(--dim);display:flex;gap:14px;flex-wrap:wrap;
margin:10px 0 18px;align-items:center}
.callegend span{display:inline-flex;align-items:center;gap:5px}
.callegend i{width:6px;height:6px;border-radius:50%;display:inline-block}

/* ---------------------------------------------------- brief day list */
.briefhead{font-size:13px;font-weight:700;margin:18px 0 9px}
.brief{display:flex;flex-direction:column;gap:7px}
.brow{display:flex;align-items:center;gap:12px;border:1px solid var(--line);
border-radius:9px;background:var(--card);padding:11px 13px}
.brow .bt{font-size:12.5px;font-weight:700;color:var(--dim);flex:none;
min-width:66px;font-variant-numeric:tabular-nums}
.brow .bn{font-size:14px;font-weight:600;flex:1 1 auto;min-width:0;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.brow .bs{font-size:11.5px;font-weight:800;padding:3px 8px;border-radius:20px;
flex:none;color:#fff}
.brow .bg{font-size:10px;font-weight:800;color:var(--good);flex:none}
.brow .bx{appearance:none;border:1px solid var(--line);background:var(--bg);
color:var(--fg);width:32px;height:32px;border-radius:8px;cursor:pointer;flex:none;
font-size:14px;line-height:1;display:inline-flex;align-items:center;
justify-content:center}
.brow .bx:hover{border-color:var(--accent);background:rgba(20,98,181,.09)}

/* ---------------------------------------------------- expanded card */
#modal{position:fixed;inset:0;z-index:200;display:flex;align-items:center;
justify-content:center;padding:22px 14px}
#modal .backdrop{position:absolute;inset:0;background:rgba(15,18,22,.55);
backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px)}
#modal .sheet{position:relative;background:var(--bg);border:1px solid var(--line);
border-radius:14px;max-width:760px;width:100%;max-height:88vh;overflow:auto;
box-shadow:0 24px 70px rgba(0,0,0,.4);padding:14px}
#modal .close{position:sticky;top:0;float:right;appearance:none;border:1px solid
var(--line);background:var(--card);color:var(--fg);width:34px;height:34px;
border-radius:50%;cursor:pointer;font-size:19px;line-height:1;z-index:2;
display:flex;align-items:center;justify-content:center}
#modal .close:hover{border-color:var(--bad);color:var(--bad)}
#modal .ev{display:block!important;margin:0;border:none;box-shadow:none;padding:4px}
body.modal-open{overflow:hidden}

/* ---------------------------------------------------- misc chrome */
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(90px);
background:var(--fg);color:var(--bg);padding:11px 16px;border-radius:9px;
font-size:13px;font-weight:600;box-shadow:0 6px 24px rgba(0,0,0,.25);z-index:300;
display:flex;align-items:center;gap:14px;transition:transform .2s;max-width:92vw}
.toast.show{transform:translateX(-50%) translateY(0)}
.toast button{appearance:none;background:transparent;border:1px solid currentColor;
color:inherit;font:inherit;font-size:12px;font-weight:700;padding:3px 10px;
border-radius:5px;cursor:pointer}
.ghost{border:1px dashed var(--line);border-radius:10px;padding:16px 18px;
color:var(--dim);font-size:13px;margin:10px 0;line-height:1.55}
.ghost b{color:var(--fg)}
.orphan{border:1px solid var(--line);border-left:3px solid var(--warn);
border-radius:9px;padding:12px 14px;margin:0 0 10px;background:var(--card)}
.orphan .t{font-weight:650;font-size:14.5px}
.orphan .m{font-size:12.5px;color:var(--dim);margin-top:3px}
.sync{margin-top:12px;border:1px solid var(--line);border-radius:10px;
padding:14px;background:var(--card)}
.sync textarea{width:100%;min-height:70px;font-family:ui-monospace,SFMono-Regular,
Menlo,monospace;font-size:11px;border:1px solid var(--line);border-radius:7px;
padding:9px;background:var(--bg);color:var(--fg);resize:vertical;margin:8px 0}
.daynote{font-size:12px;color:var(--dim);margin:2px 0 8px;line-height:1.5}
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
    p = ['<div class="%s"%s data-uid="%s" data-date="%s" data-start="%s" data-dur="%d" '
         'data-score="%d" data-verdict="%s" data-age="%s" data-changed="%d" '
         'data-title="%s" data-venue="%s" data-url="%s" data-time="%s">'
         % (cls, ' data-compact="1"' if compact else "", _e(ev.uid), _e(ev.date_key),
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


JS = r"""
(function(){
'use strict';
// Triage state lives in localStorage. The page is static on GitHub Pages, so the
// alternatives were a write token embedded in a public repo, or a paid backend.
// Marks survive the nightly rebuild because event ids are stable.
var KEY='jes.triage.v1', HORIZON=14, NEW_MAX_AGE=1;
var state={}, mode='upnext', selDate=null, showAll=false;
var calY=0, calM=0, modalCard=null, modalHome=null;

function load(){
  try{ state=JSON.parse(localStorage.getItem(KEY)||'{}')||{}; }
  catch(e){ state={}; }
  // Merge the copy committed to the repo, so a mark made on the laptop reaches
  // the phone. Whichever side is more recent wins.
  var seed={};
  try{ seed=JSON.parse(document.body.getAttribute('data-seed')||'{}')||{}; }
  catch(e){ seed={}; }
  var merged=0;
  Object.keys(seed).forEach(function(u){
    var sd=seed[u], mine=state[u];
    if(!sd || !sd.s) return;
    if(!mine || (sd.t||0) > (mine.t||0)){
      state[u]={s:sd.s,t:sd.t||0,m:sd.m||{}}; merged++;
    }
  });
  if(merged) save();
}
function save(){
  try{ localStorage.setItem(KEY,JSON.stringify(state)); }
  catch(e){ toast('Could not save - browser storage is blocked.'); }
}
function st(uid){ return (state[uid]||{}).s || ''; }
function esc(t){ var d=document.createElement('div'); d.textContent=t==null?'':t; return d.innerHTML; }
function $(s){ return document.querySelector(s); }
function $$(s){ return [].slice.call(document.querySelectorAll(s)); }

// Compact cards are the audit list of things that did NOT clear the bar.
// They must never count as triageable events.
var cards=$$('.ev[data-uid]:not([data-compact])');
var groups=$$('.day[data-date]');
var TODAY=document.body.getAttribute('data-today');
var WSTART=document.body.getAttribute('data-wstart')||TODAY;
var WEND=document.body.getAttribute('data-wend')||TODAY;

function daysFrom(iso){
  return Math.round((new Date(iso+'T00:00:00')-new Date(TODAY+'T00:00:00'))/864e5);
}

// ---------------------------------------------------------------- filtering
function visible(c){
  var uid=c.getAttribute('data-uid'), s=st(uid);
  var date=c.getAttribute('data-date');
  var age=c.getAttribute('data-age'), changed=c.getAttribute('data-changed')==='1';
  var future=date>=TODAY;
  if(mode==='going')  return s==='going';
  if(mode==='saved')  return s==='saved';
  if(mode==='hidden') return s==='hidden';
  if(mode==='new'){
    if(s==='hidden') return false;
    // "New" means new. Anything older than a day belongs in Up next, not here.
    var isNew = age!=='' && age!==null && parseInt(age,10)<=NEW_MAX_AGE;
    return future && ((!s && isNew) || changed);
  }
  // The calendar renders its own brief rows, so the full pool stays hidden.
  if(mode==='calendar') return false;
  if(s) return false;
  if(!future) return false;
  return showAll || daysFrom(date)<HORIZON;
}

function render(){
  var shown=0;
  cards.forEach(function(c){
    var v=visible(c);
    if(c!==modalCard){ c.hidden=!v; }
    if(v) shown++;
    var s=st(c.getAttribute('data-uid'));
    c.classList.toggle('is-going',s==='going');
    c.classList.toggle('is-saved',s==='saved');
    c.classList.toggle('is-hidden',s==='hidden');
    c.querySelectorAll('.tbtn[data-act]').forEach(function(b){
      b.setAttribute('aria-pressed', String(b.getAttribute('data-act')===s));
    });
    var lbl=c.querySelector('.state');
    if(lbl) lbl.textContent = s==='going' ? 'Registered / attending'
                            : s==='saved' ? 'Saved'
                            : s==='hidden' ? 'Hidden from the main list' : '';
  });
  groups.forEach(function(g){ g.hidden = !g.querySelector('.ev:not([hidden])'); });
  $('#calpanel').hidden = (mode!=='calendar');
  $('#horizonbar').hidden = (mode!=='upnext');
  $('#goingbar').hidden = (mode!=='going');
  renderOrphans();
  counts();
  if(mode==='calendar'){ paintCalendar(); renderBrief(); }
  else { $('#brief').innerHTML=''; $('#briefhead').hidden=true; }
  renderEmpty(shown);
}

function renderEmpty(shown){
  var e=$('#empty');
  if(mode==='calendar'){ e.hidden=true; return; }
  if(shown>0){ e.hidden=true; return; }
  e.innerHTML={
    upnext:'<b>Nothing left to triage.</b> Every upcoming event has been marked. Check <em>Saved</em> for the ones you were undecided about.',
    'new':'<b>Nothing new.</b> No listings appeared since yesterday, and nothing you are tracking has changed. That is the normal result on most days.',
    going:'<b>Nothing marked as going yet.</b> Press <em>I am going</em> on an event once you have registered and it moves here.',
    saved:'<b>Nothing saved.</b> Use <em>Save for later</em> when you are undecided.',
    hidden:'<b>Nothing hidden.</b> Anything you mark <em>Not interested</em> lands here, so it is never lost.'
  }[mode]||'';
  e.hidden=false;
}

function counts(){
  var keep=mode, n={};
  ['upnext','new','going','saved','hidden'].forEach(function(k){
    mode=k; n[k]=cards.filter(visible).length;
  });
  mode=keep;
  Object.keys(n).forEach(function(k){
    var el=$('.tab[data-panel="'+k+'"] .cnt');
    if(el){ el.textContent=n[k]; el.classList.toggle('zero',n[k]===0); }
  });
}

// ------------------------------------------------------- orphaned "going" items
function renderOrphans(){
  var box=$('#orphans'); box.innerHTML='';
  if(mode!=='going') return;
  var live={}; cards.forEach(function(c){ live[c.getAttribute('data-uid')]=1; });
  Object.keys(state).forEach(function(uid){
    if(state[uid].s!=='going' || live[uid]) return;
    var m=state[uid].m||{}, past=m.d && m.d<TODAY;
    var d=document.createElement('div');
    d.className='orphan';
    d.innerHTML='<div class="t">'+esc(m.ti||'(untitled)')+'</div><div class="m">'
      +esc(m.d||'?')+' '+esc(m.tm||'')+(m.v?' &middot; '+esc(m.v):'')+' &mdash; '
      +(past?'already happened':'no longer in the current feed')+'</div>'
      +(m.u?'<div class="m"><a href="'+esc(m.u)+'" target="_blank" rel="noopener">open listing</a></div>':'')
      +'<div class="triage"><button class="tbtn hide" data-forget="'+esc(uid)+'">Remove from my list</button></div>';
    box.appendChild(d);
  });
}

// ---------------------------------------------------------------- calendar
function monthCards(){
  var by={};
  cards.forEach(function(c){
    var s=st(c.getAttribute('data-uid'));
    if(s==='hidden') return;
    var d=c.getAttribute('data-date');
    if(!by[d]) by[d]={list:[],going:false};
    if(s==='going') by[d].going=true; else if(!s) by[d].list.push(c);
  });
  return by;
}

function buildGrid(){
  var by=monthCards();
  var first=new Date(calY,calM,1), start=(first.getDay()+6)%7;   // Monday-first
  var ndays=new Date(calY,calM+1,0).getDate();
  var html='<div class="grid">';
  ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].forEach(function(d){
    html+='<div class="dow">'+d+'</div>';
  });
  for(var i=0;i<start;i++) html+='<div class="cday out"></div>';
  for(var day=1; day<=ndays; day++){
    var iso=calY+'-'+String(calM+1).padStart(2,'0')+'-'+String(day).padStart(2,'0');
    var info=by[iso], n=info?info.list.length:0, going=info&&info.going;
    var cls='cday';
    if(iso<WSTART||iso>WEND) cls+=' out';
    else if(!n && !going) cls+=' none';
    if(iso===TODAY) cls+=' today';
    if(iso===selDate) cls+=' sel';
    html+='<div class="'+cls+'" data-cell="'+iso+'"><span class="dnum">'+day+'</span>';
    if(going) html+='<span class="going">&#9679;</span>';
    html+='<span class="dots">';
    if(info) info.list.slice(0,4).forEach(function(c){
      var v=c.getAttribute('data-verdict');
      html+='<span class="dot '+(v==='GO'?'go':v==='WORTH IT'?'worth':v==='MAYBE'?'maybe':'')+'"></span>';
    });
    html+='</span></div>';
  }
  return html+'</div>';
}

function paintCalendar(){
  $('#calgrid').innerHTML=buildGrid();
  $('#calmonth').value=String(calM);
  $('#calyear').value=String(calY);
  var minD=new Date(WSTART+'T00:00:00'), maxD=new Date(WEND+'T00:00:00');
  $('#calprev').disabled = (calY<minD.getFullYear()||
      (calY===minD.getFullYear()&&calM<=minD.getMonth()));
  $('#calnext').disabled = (calY>maxD.getFullYear()||
      (calY===maxD.getFullYear()&&calM>=maxD.getMonth()));
}

function renderBrief(){
  var head=$('#briefhead'), box=$('#brief');
  box.innerHTML='';
  if(!selDate){
    head.hidden=false;
    head.textContent='Pick a date above to see what is on.';
    return;
  }
  var rows=cards.filter(function(c){
    return c.getAttribute('data-date')===selDate && st(c.getAttribute('data-uid'))!=='hidden';
  }).sort(function(a,b){
    return (a.getAttribute('data-start')||'').localeCompare(b.getAttribute('data-start')||'');
  });
  var d=new Date(selDate+'T00:00:00');
  head.hidden=false;
  head.textContent=d.toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'})
                   +' — '+rows.length+(rows.length===1?' event':' events');
  if(!rows.length){
    box.innerHTML='<div class="ghost">Nothing recommended on this date.</div>';
    return;
  }
  rows.forEach(function(c){
    var uid=c.getAttribute('data-uid'), s=st(uid);
    var v=c.getAttribute('data-verdict'), sc=c.getAttribute('data-score');
    var col=v==='GO'?'var(--good)':v==='WORTH IT'?'var(--accent)':
            v==='MAYBE'?'var(--warn)':'var(--dim)';
    var r=document.createElement('div');
    r.className='brow';
    r.innerHTML='<span class="bt">'+esc(c.getAttribute('data-time')||'TBD')+'</span>'
      +'<span class="bn">'+esc(c.getAttribute('data-title'))+'</span>'
      +(s==='going'?'<span class="bg">GOING</span>':s==='saved'?'<span class="bg" style="color:#0e7490">SAVED</span>':'')
      +'<span class="bs" style="background:'+col+'">'+esc(sc)+'</span>'
      +'<button class="bx" data-expand="'+esc(uid)+'" title="Expand" '
      +'aria-label="Expand '+esc(c.getAttribute('data-title'))+'">&#10530;</button>';
    box.appendChild(r);
  });
}

// ---------------------------------------------------------------- expand modal
function openModal(uid){
  var card=cards.filter(function(c){ return c.getAttribute('data-uid')===uid; })[0];
  if(!card) return;
  // Move the real node rather than cloning it, so its triage buttons stay wired
  // to the same state and there is never a second copy to keep in sync.
  modalHome={parent:card.parentNode, next:card.nextSibling};
  modalCard=card;
  card.hidden=false;
  $('#sheetbody').appendChild(card);
  $('#modal').hidden=false;
  document.body.classList.add('modal-open');
  $('#modalclose').focus();
}
function closeModal(){
  if(!modalCard) return;
  modalHome.parent.insertBefore(modalCard, modalHome.next);
  modalCard=null; modalHome=null;
  $('#modal').hidden=true;
  document.body.classList.remove('modal-open');
  render();
}

// ---------------------------------------------------------------- .ics export
function pad(n){ return (n<10?'0':'')+n; }
function icsEsc(t){ return String(t||'').replace(/([,;\\])/g,'\\$1').replace(/\n/g,'\\n'); }
function buildICS(){
  var out=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//job-event-search//EN',
           'CALSCALE:GREGORIAN','METHOD:PUBLISH'], n=0;
  var now=new Date();
  var stamp=now.getUTCFullYear()+pad(now.getUTCMonth()+1)+pad(now.getUTCDate())+'T'
           +pad(now.getUTCHours())+pad(now.getUTCMinutes())+pad(now.getUTCSeconds())+'Z';
  cards.forEach(function(c){
    var uid=c.getAttribute('data-uid');
    if(st(uid)!=='going') return;
    var r=c.getAttribute('data-start');
    if(!r) return;
    var dur=parseInt(c.getAttribute('data-dur')||'120',10);
    // Floating local time: no VTIMEZONE needed, and every calendar app reads it as
    // the viewer's local time, which is correct for an in-person SF event.
    var sd=new Date(r.slice(0,4)+'-'+r.slice(4,6)+'-'+r.slice(6,8)+'T'
                    +r.slice(9,11)+':'+r.slice(11,13)+':00');
    var ed=new Date(sd.getTime()+dur*60000);
    function f(d){ return d.getFullYear()+pad(d.getMonth()+1)+pad(d.getDate())+'T'
                   +pad(d.getHours())+pad(d.getMinutes())+'00'; }
    out.push('BEGIN:VEVENT','UID:'+uid+'@job-event-search','DTSTAMP:'+stamp,
             'DTSTART:'+f(sd),'DTEND:'+f(ed),
             'SUMMARY:'+icsEsc(c.getAttribute('data-title')));
    var v=c.getAttribute('data-venue'); if(v) out.push('LOCATION:'+icsEsc(v));
    out.push('DESCRIPTION:'+icsEsc('Score '+c.getAttribute('data-score')+'/100. '
             +c.getAttribute('data-url')),
             'URL:'+icsEsc(c.getAttribute('data-url')),'END:VEVENT');
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
  if(!toastEl){ toastEl=document.createElement('div'); toastEl.className='toast';
                document.body.appendChild(toastEl); }
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
  save();
  // A decision made inside the expanded view is a decision - step back out.
  if(modalCard===card) closeModal(); else render();
  toast(st(uid)?{going:'Marked as going',saved:'Saved for later',hidden:'Hidden'}[act]
                :'Cleared',
        function(){ if(prev) state[uid]=prev; else delete state[uid]; save(); render(); });
}

function selectTab(name){
  mode=name;
  $$('.tab').forEach(function(x){
    x.setAttribute('aria-selected', String(x.getAttribute('data-panel')===name));
  });
  render();
  window.scrollTo({top:0,behavior:'smooth'});
}

document.addEventListener('click',function(e){
  var t=e.target; if(!t.closest) return;
  var el;
  if((el=t.closest('.tab'))){ selectTab(el.getAttribute('data-panel')); return; }
  if((el=t.closest('.tbtn[data-act]'))){ setTriage(el.closest('.ev'), el.getAttribute('data-act')); return; }
  if((el=t.closest('[data-forget]'))){
    var u=el.getAttribute('data-forget'), prev=state[u];
    delete state[u]; save(); render();
    toast('Removed', function(){ state[u]=prev; save(); render(); });
    return;
  }
  if((el=t.closest('[data-expand]'))){ openModal(el.getAttribute('data-expand')); return; }
  if(t.closest('#modalclose') || t.closest('#modal .backdrop')){ closeModal(); return; }
  if((el=t.closest('.cday[data-cell]')) && !el.classList.contains('out')){
    var d=el.getAttribute('data-cell');
    selDate=(selDate===d)?null:d;
    // Toggle the class in place rather than re-rendering the grid: rebuilding
    // detached the very node that was clicked, so the second click hit an orphan
    // and the day could never be deselected.
    $$('.cday[data-cell]').forEach(function(x){
      x.classList.toggle('sel', x.getAttribute('data-cell')===selDate);
    });
    renderBrief();
    return;
  }
  if(t.id==='calprev'||t.id==='calnext'){
    calM += (t.id==='calnext'?1:-1);
    if(calM<0){ calM=11; calY--; } if(calM>11){ calM=0; calY++; }
    selDate=null; paintCalendar(); renderBrief(); return;
  }
  if(t.id==='horizon'){
    showAll=!showAll;
    t.textContent = showAll?'Show only the next 2 weeks':'Show the whole window';
    render(); return;
  }
  if(t.id==='ics'){
    var ics=buildICS();
    if(!ics){ toast('Nothing marked as going yet.'); return; }
    download('job-events.ics',ics,'text/calendar');
    toast('Downloaded - open it to add these to your calendar.'); return;
  }
  if(t.closest('[data-sync]')){
    var box=$('#syncbox'); box.hidden=!box.hidden;
    if(!box.hidden){
      var slim={};
      Object.keys(state).forEach(function(u){ slim[u]={s:state[u].s,t:state[u].t,m:state[u].m}; });
      $('#syncjson').value=JSON.stringify(slim);
      box.scrollIntoView({behavior:'smooth',block:'nearest'});
    }
    return;
  }
  if(t.id==='copysync'){
    var ta=$('#syncjson'); ta.select();
    (navigator.clipboard? navigator.clipboard.writeText(ta.value)
     : Promise.reject()).then(
      function(){ toast('Copied. Paste into data/triage.json and commit.'); },
      function(){ toast('Select the text and copy manually.'); });
    return;
  }
  if(t.id==='dlsync'){
    download('triage.json',$('#syncjson').value,'application/json');
    toast('Saved triage.json - move it into data/ and commit.'); return;
  }
});

document.addEventListener('change',function(e){
  if(e.target.id==='calmonth'||e.target.id==='calyear'){
    calM=parseInt($('#calmonth').value,10);
    calY=parseInt($('#calyear').value,10);
    selDate=null; paintCalendar(); renderBrief();
  }
});

document.addEventListener('keydown',function(e){
  if(e.key==='Escape' && modalCard) closeModal();
});

// Open the calendar on the month containing today, or the window start.
(function initCal(){
  var d=new Date((TODAY>=WSTART?TODAY:WSTART)+'T00:00:00');
  calY=d.getFullYear(); calM=d.getMonth();
})();
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
           '<body data-today="%s" data-wstart="%s" data-wend="%s" data-seed="%s">'
           % (_e(tkey), _e(keys[0] if keys else tkey),
              _e(keys[-1] if keys else tkey),
              _e(json.dumps(seed or {}, separators=(",", ":")))),
           '<div class="wrap">']
    out.append("<h1>Where should I go to get hired?</h1>")
    out.append('<p class="sub">San Francisco &amp; Bay Area &nbsp;·&nbsp; window %s to %s '
               '&nbsp;·&nbsp; generated %s</p>'
               % (meta["window_start"], meta["window_end"],
                  dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
    out.append('<div class="summary"><span class="pill">%s recommended</span>'
               '<span>from %s listings scanned</span></div>'
               % (_e(meta["recommended"]), _e(meta["raw_listings"])))
    out.append('<details class="stats-d"><summary>How this run went</summary>'
               '<div class="stats">')
    for label, val in [("raw listings collected", meta["raw_listings"]),
                       ("unique events after dedupe", meta["unique_events"]),
                       ("recommended", meta["recommended"]),
                       ("filtered out", meta["gated"]),
                       ("HTTP requests", meta["http"]["fetched"]),
                       ("runtime", "%ss" % meta["runtime_s"])]:
        out.append('<div class="stat"><b>%s</b>%s</div>' % (_e(val), _e(label)))
    out.append('</div></details>')

    # ---------- tabs
    # Two groups: what to look at, then what you have already decided about.
    out.append('<div class="tabbar"><div class="tabs" role="tablist">')
    for pid, label in [("upnext", "Up next"), ("new", "New"), ("calendar", "Calendar")]:
        cnt = "" if pid == "calendar" else '<span class="cnt">0</span>'
        out.append('<button class="tab t-%s" role="tab" data-panel="%s" aria-selected="%s">'
                   '<span class="dotc"></span>%s%s</button>'
                   % (pid, pid, "true" if pid == "upnext" else "false", label, cnt))
    out.append('<span class="tabsep"></span>')
    for pid, label in [("going", "Going"), ("saved", "Saved"), ("hidden", "Hidden")]:
        out.append('<button class="tab t-%s" role="tab" data-panel="%s" aria-selected="false">'
                   '<span class="dotc"></span>%s<span class="cnt">0</span></button>'
                   % (pid, pid, label))
    out.append('</div></div>')

    # ---------- calendar (hidden unless the Calendar tab is active)
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    y0 = int((keys[0] if keys else tkey)[:4])
    y1 = int((keys[-1] if keys else tkey)[:4])
    out.append('<div id="calpanel" hidden><div class="calnav">')
    out.append('<button class="nav" id="calprev" aria-label="Previous month">&#8249;</button>')
    out.append('<select id="calmonth" aria-label="Month">')
    for i, name in enumerate(months):
        out.append('<option value="%d">%s</option>' % (i, name))
    out.append('</select><select id="calyear" aria-label="Year">')
    for y in range(y0, y1 + 1):
        out.append('<option value="%d">%d</option>' % (y, y))
    out.append('</select>')
    out.append('<button class="nav" id="calnext" aria-label="Next month">&#8250;</button>')
    out.append('</div><div class="cal" id="calgrid"></div>')
    out.append('<div class="callegend">'
               '<span><i style="background:var(--good)"></i>GO</span>'
               '<span><i style="background:var(--accent)"></i>worth it</span>'
               '<span><i style="background:var(--warn)"></i>maybe</span>'
               '<span><b style="color:var(--good)">&#9679;</b>&nbsp;you are going</span>'
               '</div>')
    out.append('<div class="briefhead" id="briefhead"></div><div class="brief" id="brief"></div>')
    out.append('</div>')

    # ---------- contextual toolbars
    out.append('<div class="bar" id="horizonbar">'
               '<button class="abtn" id="horizon">Show the whole window</button>'
               '</div>')
    out.append('<div class="bar" id="goingbar" hidden>'
               '<button class="abtn dl" id="ics">&#8681;&nbsp; Add these to my calendar</button>'
               '<span class="spacer"></span>'
               '<button class="abtn quiet" data-sync>Sync marks to my other devices</button>'
               '</div>')
    out.append('<div class="sync" id="syncbox" hidden>'
               '<p class="daynote"><b>What this is for.</b> Your Going / Saved / Hidden '
               'marks are stored in this browser only. Copying them into '
               '<code>data/triage.json</code> does two things: your phone picks up what '
               'you marked on your laptop, and the daily Telegram alert stops telling you '
               'about events you already registered for &mdash; and starts reminding you '
               'when to leave the house for them. Skip it if you only ever use one device '
               'and do not use the alerts.</p>'
               '<textarea id="syncjson" readonly></textarea>'
               '<div class="bar"><button class="abtn dl" id="copysync">Copy</button>'
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
    out.append('<div id="modal" hidden role="dialog" aria-modal="true" '
               'aria-label="Event detail"><div class="backdrop"></div>'
               '<div class="sheet"><button class="close" id="modalclose" '
               'aria-label="Close">&times;</button>'
               '<div id="sheetbody"></div></div></div>')
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
