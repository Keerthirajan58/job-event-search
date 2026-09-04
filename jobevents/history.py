"""First-seen dates, kept in git rather than in a cache.

`first_seen` is the only thing in the database that cannot be recomputed: it is a
record of when a listing entered the world, and once lost it is lost. It used to
live only in data/events.db, which is gitignored and survives between CI runs
purely by actions/cache. Caches get evicted, and the path changed once - either
way every event silently looked brand new, which made the "New" tab useless
because it listed all 97 of them.

So the dates live here instead: a small, diffable, committed JSON file. The
database stays the fast path; this is the durable one.
"""
import datetime as dt
import json
import os

PATH = "data/first_seen.json"
KEEP_DAYS = 120


def load(path=None):
    """{uid: "YYYY-MM-DD"}. Never raises - a broken file must not break a run."""
    path = path or PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (ValueError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for uid, day in raw.items():
        if isinstance(day, str) and len(day) >= 10:
            try:
                dt.date.fromisoformat(day[:10])
            except ValueError:
                continue
            out[str(uid)] = day[:10]
    return out


def save(known, seen_now, today=None, path=None):
    """Merge this run's sightings in, prune what has aged out, write.

    Anything seen in this run is kept regardless of age; everything else is kept
    only while it is recent, so the file cannot grow without bound.
    """
    path = path or PATH
    today = today or dt.date.today()
    merged = dict(known)
    for uid in seen_now:
        merged.setdefault(uid, today.isoformat())

    cutoff = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    pruned = {u: d for u, d in merged.items() if u in seen_now or d >= cutoff}

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(pruned.items())), fh, indent=0, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return pruned


def age_days(known, uid, today=None):
    day = known.get(uid)
    if not day:
        return None
    try:
        return ((today or dt.date.today()) - dt.date.fromisoformat(day)).days
    except ValueError:
        return None
