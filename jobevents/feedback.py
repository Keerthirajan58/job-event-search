"""Attendance logging and the organiser prior learned from it.

This is the only part of the system that can beat my hand-written rules, because
it replaces my guesses about what is valuable with your actual results. After
20-30 logged events the organiser prior starts saying things like "events run by
this group produce real conversations for you; generic AI networking nights do not".

Deliberate design choices:

* The prior is **bounded to +/-10 points**. Two data points must not be able to
  dominate a score, and a single bad night at a good organiser should not blacklist
  them. It only engages at >=2 logged events and grows with sample size.
* It keys on **organiser**, not event title, because organisers are what repeat.
* Outcomes are stored raw. If the weighting turns out wrong, the history is intact
  and can be re-scored without re-collecting anything.
"""
import datetime as dt
import os
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance (
  uid            TEXT PRIMARY KEY,
  title          TEXT,
  organizer      TEXT,
  event_date     TEXT,
  score_at_time  INTEGER,
  attended       INTEGER,      -- 1 yes / 0 no (registered but skipped)
  met_useful     INTEGER,      -- met someone who could realistically help
  hiring_present INTEGER,      -- someone from a hiring company was there
  would_repeat   INTEGER,      -- would attend another by this organiser
  conversations  INTEGER,      -- count of meaningful conversations
  notes          TEXT,
  logged_at      TEXT
);
"""

# Outcome weights -> a per-event quality value in roughly [-1, +1.6].
W = {"met_useful": 0.8, "hiring_present": 0.5, "would_repeat": 0.3}


def connect(path=None):
    """Open the attendance database, creating it if needed."""
    path = path or config.ATTENDANCE_DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def init(con):
    con.executescript(SCHEMA)
    return con


def log_event(con, uid, title, organizer, event_date, score, attended, met_useful,
              hiring_present, would_repeat, conversations, notes=""):
    init(con)
    con.execute("""INSERT INTO attendance VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(uid) DO UPDATE SET
                     attended=excluded.attended, met_useful=excluded.met_useful,
                     hiring_present=excluded.hiring_present,
                     would_repeat=excluded.would_repeat,
                     conversations=excluded.conversations, notes=excluded.notes,
                     logged_at=excluded.logged_at""",
                (uid, title, organizer, event_date, score, int(attended),
                 int(met_useful), int(hiring_present), int(would_repeat),
                 int(conversations or 0), notes,
                 dt.datetime.now().isoformat(timespec="seconds")))
    con.commit()


def _quality(row):
    """Per-event outcome quality from the logged answers."""
    attended, met, hiring, repeat, convos = row
    if not attended:
        return None
    q = (W["met_useful"] * met + W["hiring_present"] * hiring
         + W["would_repeat"] * repeat)
    if convos >= 4:
        q += 0.3
    elif convos >= 2:
        q += 0.15
    elif convos == 0:
        q -= 0.5
    return q


def organizer_priors(con):
    """{organizer_lower: (adjustment_points, n_events, mean_quality)}"""
    init(con)
    rows = con.execute("""SELECT organizer, attended, met_useful, hiring_present,
                                 would_repeat, conversations
                          FROM attendance WHERE organizer IS NOT NULL
                            AND TRIM(organizer) != ''""").fetchall()
    buckets = {}
    for org, *vals in rows:
        q = _quality(vals)
        if q is None:
            continue
        buckets.setdefault(org.strip().lower(), []).append(q)

    priors = {}
    for org, qs in buckets.items():
        n = len(qs)
        if n < 2:                       # one night is not evidence
            continue
        mean = sum(qs) / n
        # Confidence grows with n and saturates: 2 events -> 0.5, 5 -> 0.8, 10 -> 0.9
        conf = n / (n + 2.0)
        priors[org] = (round(max(-10.0, min(10.0, mean * 8.0 * conf)), 1), n, round(mean, 2))
    return priors


def global_calibration(con):
    """Does the score actually predict good nights? Reported, not auto-applied."""
    init(con)
    rows = con.execute("""SELECT score_at_time, attended, met_useful, hiring_present,
                                 would_repeat, conversations FROM attendance""").fetchall()
    hi, lo = [], []
    for score, *vals in rows:
        q = _quality(vals)
        if q is None or score is None:
            continue
        (hi if score >= 70 else lo).append(q)
    out = {"n_attended": len(hi) + len(lo)}
    if hi:
        out["mean_quality_score_70_plus"] = round(sum(hi) / len(hi), 2)
        out["n_70_plus"] = len(hi)
    if lo:
        out["mean_quality_below_70"] = round(sum(lo) / len(lo), 2)
        out["n_below_70"] = len(lo)
    return out


def apply_prior(ev, priors):
    """Adjust an event's score by its organiser's track record. Returns note or ''."""
    org = (ev.organizer or "").strip().lower()
    if not org or org not in priors:
        return ""
    adj, n, mean = priors[org]
    if abs(adj) < 1:
        return ""
    ev.score = max(0, min(100, ev.score + int(round(adj))))
    verb = "produced" if adj > 0 else "did not produce"
    note = ("%+d  Your own history: %d logged events by %s %s useful outcomes "
            "(mean quality %.2f)" % (adj, n, ev.organizer, verb, mean))
    ev.reasons.append(note) if adj > 0 else ev.penalties.append(note.lstrip("+"))
    return note
