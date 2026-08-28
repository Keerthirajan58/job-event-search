"""SQLite persistence.

Two jobs only:
  1. Remember when we first saw an event, so the daily digest can say NEW.
  2. Keep history (including gated events and their gate reason) so a suspected
     false negative can be audited rather than argued about.
"""
import datetime as dt
import json
import os
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  uid            TEXT PRIMARY KEY,
  title          TEXT,
  start_local    TEXT,
  date_key       TEXT,
  city           TEXT,
  venue          TEXT,
  url            TEXT,
  organizer      TEXT,
  distance_mi    REAL,
  score          INTEGER,
  category       TEXT,
  confidence     TEXT,
  gate           TEXT,
  is_online      INTEGER,
  attendee_count INTEGER,
  first_seen     TEXT,
  last_seen      TEXT,
  fingerprint    TEXT,
  desc_len       INTEGER,
  payload        TEXT
);
CREATE INDEX IF NOT EXISTS idx_date  ON events(date_key);
CREATE INDEX IF NOT EXISTS idx_score ON events(score DESC);
CREATE TABLE IF NOT EXISTS runs (
  run_at TEXT PRIMARY KEY, collected INTEGER, unique_events INTEGER,
  recommended INTEGER, gated INTEGER, http_stats TEXT
);
"""


# Columns added after the first version shipped. Kept as a list so an existing
# database is migrated in place rather than requiring a delete.
MIGRATIONS = [("events", "fingerprint", "TEXT"),
              ("events", "desc_len", "INTEGER")]


def connect(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for table, column, decl in MIGRATIONS:
        have = {r[1] for r in con.execute("PRAGMA table_info(%s)" % table)}
        if column not in have:
            con.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, decl))
    con.commit()
    return con


def fingerprint(ev):
    """Fields whose change actually matters to a decision to attend."""
    import hashlib
    parts = [ev.title, ev.start.isoformat() if ev.start else "", ev.venue, ev.address,
             str(ev.is_free), str(ev.price), str(ev.sold_out),
             str(ev.registration_open), (ev.description or "")[:2000]]
    return hashlib.sha1("|".join(p or "" for p in parts).encode()).hexdigest()[:16]


def upsert(con, events):
    """Insert/update. Returns (new_uids, changed_uids).

    `changed` powers the "details changed since you last saw this" flag, which the
    daily digest needs: an event you already dismissed can move venue, sell out, or
    start charging, and an event you registered for can change its time.
    """
    now = dt.datetime.now().isoformat(timespec="seconds")
    new, changed = set(), {}
    cur = con.cursor()

    # A gated raw listing and the merged live event can share a uid (same title,
    # date and city). Writing both in one pass made the second look like an edit
    # of the first and produced phantom "venue changed" flags on a cold run.
    # Keep one record per uid, preferring the live, merged one.
    best = {}
    for ev in events:
        cur_best = best.get(ev.uid)
        if cur_best is None:
            best[ev.uid] = ev
        elif cur_best.gate and not ev.gate:
            best[ev.uid] = ev
        elif not cur_best.gate and not ev.gate:
            # both live: prefer the richer record
            if len(ev.description or "") > len(cur_best.description or ""):
                best[ev.uid] = ev
    for ev in best.values():
        fp = fingerprint(ev)
        cur.execute("SELECT first_seen, fingerprint, start_local, venue, score, desc_len "
                    "FROM events WHERE uid=?", (ev.uid,))
        row = cur.fetchone()
        first = row[0] if row else now
        dlen = len(ev.description or "")
        # A description appearing for the first time is US fetching more detail, not
        # the organiser editing the event. Flagging it produced ~300 false alarms.
        filled_in = bool(row) and (row[5] or 0) == 0 and dlen > 0
        if not row:
            new.add(ev.uid)
        elif row[1] and row[1] != fp and not filled_in:
            bits = []
            old_start = row[2]
            if old_start and ev.start and old_start != ev.start.isoformat():
                bits.append("time moved from %s" % old_start[11:16])
            if row[3] and ev.venue and row[3] != ev.venue:
                bits.append("venue changed from %s" % row[3])
            if row[4] is not None and abs((row[4] or 0) - ev.score) >= 8:
                bits.append("score moved %d -> %d" % (row[4], ev.score))
            changed[ev.uid] = "; ".join(bits) or "listing details were edited"
        ev.changed_note = changed.get(ev.uid, "")
        cur.execute("""
          INSERT INTO events (uid,title,start_local,date_key,city,venue,url,organizer,
            distance_mi,score,category,confidence,gate,is_online,attendee_count,
            first_seen,last_seen,fingerprint,desc_len,payload)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(uid) DO UPDATE SET
            title=excluded.title, start_local=excluded.start_local,
            date_key=excluded.date_key, city=excluded.city, venue=excluded.venue,
            url=excluded.url, organizer=excluded.organizer,
            distance_mi=excluded.distance_mi, score=excluded.score,
            category=excluded.category, confidence=excluded.confidence,
            gate=excluded.gate, is_online=excluded.is_online,
            attendee_count=excluded.attendee_count, last_seen=excluded.last_seen,
            fingerprint=excluded.fingerprint, desc_len=excluded.desc_len,
            payload=excluded.payload
        """, (ev.uid, ev.title, ev.start.isoformat() if ev.start else None, ev.date_key,
              ev.city, ev.venue, ev.url, ev.organizer, ev.distance_mi, ev.score,
              ev.category, ev.confidence, ev.gate, int(ev.is_online),
              ev.attendee_count, first, now, fp, dlen,
              json.dumps(ev.to_dict(), default=str)))
    con.commit()
    return new, changed


def record_run(con, collected, uniq, recommended, gated, http_stats):
    con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?)",
                (dt.datetime.now().isoformat(timespec="seconds"), collected, uniq,
                 recommended, gated, json.dumps(http_stats)))
    con.commit()
