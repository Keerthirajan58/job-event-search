"""HackerX adapter.

HackerX runs recruiting-format events - rotating 1:1 conversations between
software engineers and hiring companies - which is structurally the highest
job-value format in this dataset. Volume is low (1-3 Bay Area events a month) but
precision is near-perfect, so it is worth its own adapter.

Access: robots.txt is `Allow: /` and explicitly permits ClaudeBot/anthropic-ai;
/events/ is server-rendered with one schema.org Event JSON-LD block per listing.

Two things this adapter must get right, learned from the live page:

1. Each listing is an <li> containing BOTH the JSON-LD (name, date, description)
   and a `<div class="eb-event" data-event-id="...">`. That id is an Eventbrite
   event id, and https://www.eventbrite.com/e/<id> 301s to the real registration
   page. The JSON-LD itself carries no url, so without this pairing every HackerX
   event would link to the generic index - useless for actually registering.

2. Listings come in an EMPLOYER track and a DEVELOPER track. The employer ticket
   is for companies who want to recruit; a candidate registering for it is a
   mistake. We keep employer listings (they prove a hiring event exists on that
   date) but gate them with an explicit reason.
"""
import json
import re

from .. import config, http
from ..models import Event, clean_text, miles, norm_city, strip_html, to_local

NAME = "hackerx"
_LI = re.compile(r"<li>(?:(?!</li>).)*?</li>", re.S)
_LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_EID = re.compile(r"data-event-id=['\"](\d+)['\"]")
_HXS = re.compile(r"data-hx-search=['\"]([^'\"]*)['\"]")

BAY_HINTS = ("san francisco", "bay area", "oakland", "berkeley", "palo alto",
             "mountain view", "san jose", "sunnyvale", "santa clara", "menlo park",
             "silicon valley", "redwood city", "san mateo")


def _ld_event(li):
    for block in _LD.findall(li):
        try:
            data = json.loads(block)
        except Exception:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict) and "Event" in str(node.get("@type", "")):
                return node
    return None


def collect(log=print):
    try:
        html = http.get(config.HACKERX_EVENTS_URL)
    except Exception as exc:
        log("    hackerx FAIL (%s)" % type(exc).__name__)
        return []

    out, bay, employer = [], 0, 0
    for li in _LI.findall(html):
        node = _ld_event(li)
        if not node:
            continue
        eid = _EID.search(li)
        hxs = (_HXS.search(li).group(1) if _HXS.search(li) else "").lower()
        title = clean_text(node.get("name"))
        haystack = (hxs + " " + title).lower()
        if not any(h in haystack for h in BAY_HINTS):
            continue
        bay += 1

        ev = Event()
        ev.title = title
        ev.start = to_local(node.get("startDate"))
        ev.end = to_local(node.get("endDate"))
        ev.is_online = ("online" in hxs) or ("Online" in (node.get("eventAttendanceMode") or ""))
        ev.description = strip_html(node.get("description"))

        loc = node.get("location")
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        if isinstance(loc, dict):
            ev.venue = clean_text(loc.get("name"))
            addr = loc.get("address")
            if isinstance(addr, dict):
                ev.address = clean_text(" ".join(filter(None, [
                    addr.get("streetAddress"), addr.get("addressLocality"),
                    addr.get("addressRegion")])))
                ev.city = norm_city(addr.get("addressLocality"))
            elif isinstance(addr, str):
                ev.address = clean_text(addr)
            geo = loc.get("geo") or {}
            ev.lat, ev.lon = geo.get("latitude"), geo.get("longitude")
        if not ev.city:
            ev.city = next((h for h in BAY_HINTS if h in haystack), "")
        ev.distance_mi = miles(ev.lat, ev.lon)

        org = node.get("organizer")
        ev.organizer = clean_text(org.get("name") if isinstance(org, dict) else org) or "HackerX"

        # real, working registration link (see module docstring)
        ev.url = ("https://www.eventbrite.com/e/%s" % eid.group(1) if eid
                  else config.HACKERX_EVENTS_URL)

        offers = node.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if isinstance(offers, dict) and offers.get("price") is not None:
            try:
                p = float(offers["price"])
                ev.price, ev.is_free = p, (p == 0)
            except Exception:
                pass
        ev.registration_open = "Cancelled" not in (node.get("eventStatus") or "")

        is_employer = ("employer" in haystack)
        if is_employer:
            employer += 1
            # keep the record, but never recommend it to a candidate
            ev.registration_open = False
            ev.verify_note = ("HackerX EMPLOYER track - this ticket is for companies "
                              "that want to recruit, not for candidates. Look for the "
                              "matching DEVELOPER-track listing on the same date.")
        else:
            ev.description += (
                " HackerX is a tech recruiting event: rotating 1:1 conversations "
                "between software engineers and hiring companies. Recruiters and "
                "hiring managers attend, and candidates are expected to bring a resume.")
        ev.sources = [{"source": NAME, "url": ev.url,
                       "id": eid.group(1) if eid else ev.url, "via": "jsonld+eb-id",
                       "track": "employer" if is_employer else "developer"}]
        ev.verified = True
        out.append(ev)

    log("    hackerx %3d Bay Area listings (%d employer-track, excluded from "
        "recommendations)" % (bay, employer))
    return out
