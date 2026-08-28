"""Meetup adapter.

Access reality (checked, not assumed): the open REST API is retired and the
GraphQL API now requires a paid Meetup Pro subscription plus OAuth-consumer
approval, so there is no free programmatic route. Meetup's robots.txt disallows
/api/ - we do NOT touch their internal GraphQL endpoint.

What IS permitted and stable: the public /find/ search page is server-rendered
and embeds a complete Apollo cache in <script id="__NEXT_DATA__">, including each
event's full description, ISO datetime with offset, venue, group and RSVP count.
One HTTP GET per keyword, no auth, robots-clean.

Privacy note: that cache also contains individual member records. We read only
rsvps.totalCount and never store member data.
"""
import json
import re
import urllib.parse

from .. import config, http
from ..models import Event, clean_text, miles, norm_city, strip_html, to_local

NAME = "meetup"
_NEXT = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def _apollo(html):
    m = _NEXT.search(html)
    if not m:
        return {}
    try:
        return (json.loads(m.group(1)).get("props", {})
                .get("pageProps", {}).get("__APOLLO_STATE__", {}) or {})
    except Exception:
        return {}


def _node_to_event(node, state):
    # Meetup's Apollo cache also contains stub Event objects (referenced by
    # "similar events" widgets) that carry only an id. They are not results.
    if not (node.get("title") or "").strip() or not node.get("dateTime"):
        raise ValueError("stub event node without title/dateTime")
    ev = Event()
    ev.title = clean_text(node.get("title"))
    ev.description = strip_html(node.get("description"))
    ev.start = to_local(node.get("dateTime"))
    ev.end = to_local(node.get("endTime"))
    ev.is_online = (node.get("eventType") == "ONLINE")
    ev.url = node.get("eventUrl") or ""

    v = node.get("venue") or {}
    if isinstance(v, dict) and "__ref" in v:
        v = state.get(v["__ref"], {})
    if isinstance(v, dict):
        ev.venue = clean_text(v.get("name"))
        ev.address = clean_text(" ".join(filter(None, [v.get("address"), v.get("city"),
                                                       v.get("state")])))
        ev.city = norm_city(v.get("city"))
        ev.lat, ev.lon = v.get("lat"), v.get("lng")
        if ev.venue.lower() == "online event":
            ev.is_online = True
    ev.distance_mi = miles(ev.lat, ev.lon)

    g = node.get("group") or {}
    if isinstance(g, dict) and "__ref" in g:
        g = state.get(g["__ref"], {})
    if isinstance(g, dict):
        ev.organizer = clean_text(g.get("name"))
        stats = ((g.get("stats") or {}).get("eventRatings") or {})
        if stats.get("average"):
            ev.organizer_bio = ("Meetup group rating %.2f from %d ratings"
                                % (stats["average"], stats.get("totalRatings") or 0))
    # attendance: count only, never member identities
    rs = node.get("rsvps") or {}
    if isinstance(rs, dict):
        ev.attendee_count = rs.get("totalCount")
    fee = node.get("feeSettings")
    if fee:
        ev.is_free = False
        try:
            ev.price = float(fee.get("amount")) if fee.get("amount") else None
        except Exception:
            ev.price = None
    else:
        ev.is_free = True
    ev.sources = [{"source": NAME, "url": ev.url, "id": str(node.get("id") or ""),
                   "via": "find"}]
    ev.verified = True          # description came from the listing itself
    return ev


def collect(log=print):
    events, seen = [], set()
    for kw in config.MEETUP_KEYWORDS:
        q = urllib.parse.urlencode({
            "keywords": kw, "location": config.MEETUP_LOCATION,
            "source": "EVENTS", "distance": config.MEETUP_DISTANCE,
        })
        try:
            html = http.get(("https://www.meetup.com/find/?" + q))
        except http.Blocked as exc:
            log("    meetup %-24s BLOCKED (%s) - stopping this source" % (kw, exc))
            break
        except Exception as exc:
            log("    meetup %-24s FAIL (%s)" % (kw, type(exc).__name__))
            continue
        state = _apollo(html)
        n = 0
        for key, node in state.items():
            if not key.startswith("Event:") or key in seen:
                continue
            seen.add(key)
            try:
                events.append(_node_to_event(node, state))
                n += 1
            except Exception:
                continue
        log("    meetup %-24s %3d new events" % (kw, n))
    return events
