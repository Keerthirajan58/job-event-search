"""Luma (lu.ma) adapter - the primary source.

Access: api.luma.com serves public event JSON with no auth, no cookies and no
key. Its robots.txt disallows only /insights/; /discover/, /url and /event/get
are permitted. We still self-throttle.

Two tiers:
  * TRUSTED CALENDARS  - curated community calendars (AI Tinkerers, Llama Lounge,
    SF Tech Week...). Very high precision, low volume.
  * GEO DISCOVER       - lat/lng firehose. ~930 events/month for the Bay Area,
    ~95% of it irrelevant. High recall, needs hard filtering.

Cost control: the discover feed omits descriptions, so we fetch event detail only
for the shortlist that survives cheap gates (see hydrate()).
"""
import urllib.parse

from .. import config, http
from ..models import (Event, clean_text, miles, norm_city, prosemirror_text,
                      to_local)

API = "https://api.luma.com"
NAME = "luma"


def _price(ticket_info):
    """Luma sends price as {"cents": 4000, "currency": "usd"} or null."""
    for key in ("price", "max_price"):
        p = ticket_info.get(key)
        if isinstance(p, dict) and p.get("cents") is not None:
            try:
                return round(float(p["cents"]) / 100.0, 2)
            except Exception:
                continue
        if isinstance(p, (int, float)) and p:
            return round(float(p) / 100.0, 2)
    return None


def _entry_to_event(entry, source_label):
    e = entry.get("event") or {}
    ga = e.get("geo_address_info") or {}
    coord = e.get("coordinate") or {}
    ti = entry.get("ticket_info") or {}
    hosts = entry.get("hosts") or []
    guests = entry.get("featured_guests") or []
    slug = e.get("url") or ""
    url = "https://lu.ma/%s" % slug if slug else ""

    ev = Event()
    ev.title = clean_text(e.get("name"))
    ev.start = to_local(e.get("start_at"), e.get("timezone"))
    ev.end = to_local(e.get("end_at"), e.get("timezone"))
    ev.is_online = (e.get("location_type") == "online")
    ev.venue = clean_text(ga.get("sublocality") or ga.get("place_name") or "")
    ev.address = clean_text(ga.get("full_address") or ga.get("address") or "")
    ev.city = norm_city(ga.get("city_state") or ga.get("city"))
    ev.lat = coord.get("latitude")
    ev.lon = coord.get("longitude")
    ev.distance_mi = miles(ev.lat, ev.lon)
    ev.organizer = clean_text((entry.get("calendar") or {}).get("name")
                              or (hosts[0].get("name") if hosts else ""))
    ev.organizer_bio = clean_text((entry.get("calendar") or {}).get("description_short")
                                  or (hosts[0].get("bio_short") if hosts else ""))
    ev.speakers = [clean_text(g.get("name")) for g in guests if g.get("name")][:12]
    ev.url = url
    ev.is_free = ti.get("is_free")
    ev.price = _price(ti)
    ev.sold_out = bool(ti.get("is_sold_out"))
    ev.requires_approval = bool(ti.get("require_approval"))
    ev.registration_open = entry.get("registration_availability") != "closed"
    ev.attendee_count = entry.get("guest_count")
    ev.sources = [{"source": NAME, "url": url, "id": e.get("api_id") or "",
                   "via": source_label}]
    return ev


def _paginate(path, params, max_pages=25):
    out, cursor, pages = {}, None, 0
    while pages < max_pages:
        q = dict(params)
        q["period"] = "future"
        q["pagination_limit"] = 50
        if cursor:
            q["pagination_cursor"] = cursor
        try:
            d = http.get_json("%s/%s?%s" % (API, path, urllib.parse.urlencode(q)))
        except http.Blocked:
            break
        except Exception:
            break
        for en in d.get("entries") or []:
            out[en.get("api_id")] = en
        pages += 1
        cursor = d.get("next_cursor")
        if not d.get("has_more") or not cursor:
            break
    return out


def collect(log=print):
    """Return list[Event] from both tiers."""
    events, seen = [], set()

    # ---- tier 1: trusted calendars
    for slug, why in config.LUMA_TRUSTED_CALENDARS.items():
        try:
            meta = http.get_json("%s/url?url=%s" % (API, urllib.parse.quote(slug)))
        except Exception as exc:
            log("    luma calendar %-14s SKIP (%s)" % (slug, type(exc).__name__))
            continue
        if meta.get("kind") != "calendar":
            log("    luma calendar %-14s SKIP (slug is %s, not a calendar)"
                % (slug, meta.get("kind")))
            continue
        cal = (meta.get("data") or {}).get("calendar") or {}
        cid = cal.get("api_id")
        if not cid:
            continue
        ents = _paginate("calendar/get-items", {"calendar_api_id": cid}, max_pages=6)
        n = 0
        for aid, en in ents.items():
            if aid in seen:
                continue
            seen.add(aid)
            try:
                events.append(_entry_to_event(en, "trusted:%s" % slug))
                n += 1
            except Exception as exc:
                log("      skipped malformed entry %s (%s)" % (aid, type(exc).__name__))
        log("    luma calendar %-14s %3d events  (%s)" % (slug, n, why))

    # ---- tier 2: geo discover firehose
    for label, lat, lon in config.LUMA_GEO_POINTS:
        ents = _paginate("discover/get-paginated-events",
                         {"latitude": lat, "longitude": lon})
        n = 0
        bad = 0
        for aid, en in ents.items():
            if aid in seen:
                continue
            seen.add(aid)
            try:
                events.append(_entry_to_event(en, "geo:%s" % label))
                n += 1
            except Exception:
                bad += 1
        if bad:
            log("      %d malformed entries skipped" % bad)
        log("    luma geo      %-14s %3d new events" % (label, n))
    return events


def hydrate(ev, log=None):
    """Fetch the full event page for descriptions/speakers. Returns True if enriched."""
    src = next((s for s in ev.sources if s["source"] == NAME), None)
    if not src or not src.get("id"):
        return False
    try:
        d = http.get_json("%s/event/get?event_api_id=%s" % (API, src["id"]))
    except Exception:
        return False
    desc = prosemirror_text(d.get("description_mirror"))
    if desc:
        ev.description = desc
    cats = [c.get("name") for c in (d.get("categories") or []) if c.get("name")]
    if cats:
        ev.description += "  [luma categories: %s]" % ", ".join(cats)
    guests = [clean_text(g.get("name")) for g in (d.get("featured_guests") or [])
              if g.get("name")]
    if guests:
        ev.speakers = guests[:12]
    hosts = d.get("hosts") or []
    if hosts:
        bios = [clean_text(h.get("bio_short")) for h in hosts if h.get("bio_short")]
        if bios:
            ev.organizer_bio = " | ".join(bios)[:600]
    ti = d.get("ticket_info") or {}
    if ti:
        ev.is_free = ti.get("is_free", ev.is_free)
        pr = _price(ti)
        if pr is not None:
            ev.price = pr
        ev.sold_out = bool(ti.get("is_sold_out"))
        ev.requires_approval = bool(ti.get("require_approval"))
    if d.get("guest_count") is not None:
        ev.attendee_count = d.get("guest_count")
    ev.registration_open = d.get("registration_availability") != "closed"
    ev.verified = True
    return True
