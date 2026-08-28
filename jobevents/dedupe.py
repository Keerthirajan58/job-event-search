"""Cross-source duplicate detection. Pure code, no LLM.

An event routinely appears on Luma, Meetup, Eventbrite and the organiser's own
page. Two listings are the same event when they share a day AND either
  (a) a canonical registration URL, or
  (b) a strongly-similar normalized title plus a compatible location/time.

Merging keeps the richest field from each listing and unions the source links, so
the report can show one event with "also on Meetup, Eventbrite".
"""
import difflib

from .models import canon_url, miles, norm_title_key

TITLE_SIM = 0.72          # tuned on live SF data; below this, treat as distinct
TIME_SLACK_H = 6.0
NEAR_VENUE_MI = 0.6


def _token_jaccard(a, b):
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _same(a, b):
    if not a.start or not b.start:
        return False
    if a.start.date() != b.start.date():
        return False

    ua, ub = canon_url(a.url), canon_url(b.url)
    if ua and ua == ub:
        return True

    ka, kb = norm_title_key(a.title), norm_title_key(b.title)
    if not ka or not kb:
        return False
    sim = max(_token_jaccard(ka, kb), difflib.SequenceMatcher(None, ka, kb).ratio())
    if sim < TITLE_SIM:
        return False

    # Same day + very similar title. Confirm with time or place if we have them.
    dt_h = abs((a.start - b.start).total_seconds()) / 3600.0
    if dt_h > TIME_SLACK_H:
        return False
    if None not in (a.lat, a.lon, b.lat, b.lon):
        d = miles(a.lat, a.lon, b.lat, b.lon)
        if d is not None and d > NEAR_VENUE_MI:
            return False
    elif a.city and b.city and a.city != b.city:
        return False
    return True


_PREF = {"luma": 3, "meetup": 2, "hackerx": 4, "eventbrite": 1}


def _rank(ev):
    return max((_PREF.get(s["source"], 0) for s in ev.sources), default=0)


def _merge(primary, other):
    """Fold `other` into `primary`, keeping the better value for each field."""
    if len(other.description or "") > len(primary.description or ""):
        primary.description = other.description
    for f in ("venue", "address", "city", "organizer", "organizer_bio"):
        if not getattr(primary, f) and getattr(other, f):
            setattr(primary, f, getattr(other, f))
    if primary.lat is None and other.lat is not None:
        primary.lat, primary.lon = other.lat, other.lon
        primary.distance_mi = other.distance_mi
    if primary.attendee_count is None:
        primary.attendee_count = other.attendee_count
    elif other.attendee_count:
        primary.attendee_count = max(primary.attendee_count, other.attendee_count)
    if primary.is_free is None:
        primary.is_free = other.is_free
    if primary.price is None:
        primary.price = other.price
    if len(other.speakers) > len(primary.speakers):
        primary.speakers = other.speakers
    primary.sold_out = primary.sold_out or other.sold_out
    primary.verified = primary.verified or other.verified
    have = {(s["source"], s.get("id")) for s in primary.sources}
    for s in other.sources:
        if (s["source"], s.get("id")) not in have:
            primary.sources.append(s)
    return primary


def dedupe(events, log=print):
    """Bucket by date to keep this O(n * bucket) rather than O(n^2)."""
    buckets = {}
    for ev in events:
        buckets.setdefault(ev.start.date() if ev.start else None, []).append(ev)

    out, merged = [], 0
    for _day, group in buckets.items():
        group.sort(key=_rank, reverse=True)      # richest source becomes primary
        kept = []
        for ev in group:
            hit = next((k for k in kept if _same(k, ev)), None)
            if hit:
                _merge(hit, ev)
                merged += 1
            else:
                kept.append(ev)
        out.extend(kept)
    log("    deduplicated: %d listings -> %d unique events (%d merges)"
        % (len(events), len(out), merged))
    return out
