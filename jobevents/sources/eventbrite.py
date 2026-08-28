"""Eventbrite adapter.

Access reality: the public Event Search API was switched off in February 2020 and
never replaced - the v3 API now only serves your OWN organisation's events, so it
is useless for discovery. Eventbrite's robots.txt also disallows
/api/v3/destination/events/ (their internal search API), so we do not call it.

What is permitted: the /d/<place>/<category>/ browse pages are server-rendered and
embed `window.__SERVER_DATA__` with a `search_data.events.results` array. robots
allows /d/. Each result carries name, summary, ISO date + time + timezone, venue
with coordinates, organiser id, and Eventbrite's own dedup hash.

Quality warning (measured, not assumed): Eventbrite's SF "tech" inventory is
mostly low-signal - paid workshops, resold conference tickets, placeholder
listings. It is kept as a third source for the occasional real job fair, and its
events are treated as unverified until the detail page confirms them.
"""
import json
import re

from .. import config, http
from ..models import Event, clean_text, miles, norm_city, strip_html, to_local

NAME = "eventbrite"


def _server_data(html):
    i = html.find("window.__SERVER_DATA__")
    if i < 0:
        return {}
    start = html.find("{", i)
    if start < 0:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
        return obj
    except Exception:
        return {}


def _result_to_event(r):
    ev = Event()
    ev.title = clean_text(r.get("name"))
    ev.description = strip_html(r.get("full_description") or r.get("summary") or "")
    tz = r.get("timezone")
    sd, st = r.get("start_date"), r.get("start_time")
    ev.start = to_local("%sT%s" % (sd, st) if sd and st else sd, tz)
    ed, et = r.get("end_date"), r.get("end_time")
    ev.end = to_local("%sT%s" % (ed, et) if ed and et else ed, tz)
    ev.is_online = bool(r.get("is_online_event"))
    v = r.get("primary_venue") or {}
    a = v.get("address") or {}
    ev.venue = clean_text(v.get("name"))
    ev.address = clean_text(a.get("localized_address_display"))
    ev.city = norm_city(a.get("city"))
    try:
        ev.lat, ev.lon = float(a.get("latitude")), float(a.get("longitude"))
    except Exception:
        ev.lat = ev.lon = None
    ev.distance_mi = miles(ev.lat, ev.lon)
    ev.url = r.get("url") or ""
    ev.registration_open = not bool(r.get("is_cancelled"))
    ev.sources = [{"source": NAME, "url": ev.url,
                   "id": str(r.get("eventbrite_event_id") or ""),
                   "via": "browse", "dedup_hash": (r.get("dedup") or {}).get("hash", "")}]
    ev.verified = False         # summary only; detail page confirms later
    return ev


def collect(log=print):
    events, seen = [], set()
    for place, cat in config.EVENTBRITE_SLICES:
        for page in range(1, config.EVENTBRITE_MAX_PAGES + 1):
            url = "https://www.eventbrite.com/d/%s/%s/?page=%d" % (place, cat, page)
            try:
                html = http.get(url)
            except http.Blocked as exc:
                log("    eventbrite %s/%s p%d BLOCKED (%s)" % (place, cat, page, exc))
                return events
            except Exception as exc:
                log("    eventbrite %s/%s p%d FAIL (%s)" % (place, cat, page,
                                                            type(exc).__name__))
                break
            data = _server_data(html)
            results = ((data.get("search_data") or {}).get("events") or {}).get("results") or []
            n = 0
            for r in results:
                eid = str(r.get("eventbrite_event_id") or r.get("id") or "")
                if not eid or eid in seen:
                    continue
                seen.add(eid)
                try:
                    events.append(_result_to_event(r))
                    n += 1
                except Exception:
                    continue
            log("    eventbrite %-14s %-16s p%d  %3d new" % (place, cat, page, n))
            if not results:
                break
    return events


_LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def hydrate(ev, log=None):
    """Fetch the /e/ page for the real description + confirm it still exists."""
    if not ev.url:
        return False
    try:
        html = http.get(ev.url)
    except Exception:
        return False
    for block in _LD.findall(html):
        try:
            node = json.loads(block)
        except Exception:
            continue
        nodes = node if isinstance(node, list) else [node]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            if "Event" in str(n.get("@type", "")):
                if n.get("description"):
                    ev.description = strip_html(n["description"])
                off = n.get("offers")
                if isinstance(off, list):
                    off = off[0] if off else {}
                if isinstance(off, dict):
                    try:
                        p = float(off.get("price"))
                        ev.price, ev.is_free = p, (p == 0)
                    except Exception:
                        pass
                    avail = str(off.get("availability") or "")
                    if "SoldOut" in avail:
                        ev.sold_out = True
                    if "InStock" not in avail and "PreOrder" not in avail and avail:
                        ev.registration_open = False
                ev.verified = True
                return True
    return False
