"""Telegram alerts. Sends nothing when there is nothing you do not already know.

The first version was a digest: every morning it listed the top few events in the
window. Since the window barely changes day to day, so did the message - the same
list, every day, which trains you to ignore it. A notification you learn to swipe
away is worse than no notification.

So this is an ALERT, not a digest. It answers "what changed since yesterday?" and
stays silent when the answer is nothing:

  1. NEW      listings first seen this run that clear the bar
  2. CHANGED  time / venue / price moved on something you are going to or saved
  3. TOMORROW what you are attending tomorrow, and when to leave the house
  4. SUNDAY   one weekly state-of-the-window, so silence never looks like breakage

Repetition is prevented in the database, not by luck: every alert is recorded as
(uid, kind) and never sent twice. Sections 2 and 3 need data/triage.json, which
the dashboard's Sync button produces - see jobevents/triage.py.

    export TELEGRAM_TOKEN=123:abc
    export TELEGRAM_CHAT=456789
    python3 -m jobevents.notify
"""
import datetime as dt
import json
import os
import sqlite3
import urllib.parse
import urllib.request

from . import config, triage
from .companies import display as _cdisp

MIN_NEW_SCORE = 62          # roughly "WORTH IT" and up
MAX_NEW = 5
ALERT_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
  uid      TEXT,
  kind     TEXT,
  sent_at  TEXT,
  PRIMARY KEY (uid, kind)
);
"""


def _con(path=None):
    con = sqlite3.connect(path or config.DB_PATH)
    con.executescript(ALERT_SCHEMA)
    return con


def _already(con, uid, kind):
    return con.execute("SELECT 1 FROM alerts WHERE uid=? AND kind=?",
                       (uid, kind)).fetchone() is not None


def _mark(con, uid, kind):
    con.execute("INSERT OR REPLACE INTO alerts VALUES (?,?,?)",
                (uid, kind, dt.datetime.now().isoformat(timespec="seconds")))


def _fmt_date(iso):
    try:
        return dt.date.fromisoformat(iso).strftime("%a %b %d")
    except ValueError:
        return iso


def _leave_by(ev):
    """When to walk out of the door, from the transit model."""
    c = ev.get("cost") or {}
    if not (c.get("known") and ev.get("start")):
        return None
    try:
        start = dt.datetime.fromisoformat(ev["start"])
    except ValueError:
        return None
    # 5 minutes of slack on top of the modelled door-to-door time.
    return (start - dt.timedelta(minutes=c["one_way_min"] + 5)).strftime("%-I:%M %p")


def _one_liner(ev):
    c = ev.get("cost") or {}
    bits = []
    if c.get("known"):
        bits.append("%d min %s, $%.2f" % (c["one_way_min"], c["mode"], c["total_cash"]))
    jobs = sum(o["total"] for o in (ev.get("openings") or []))
    if jobs:
        names = ", ".join(_cdisp(o["company"]) for o in ev["openings"][:2])
        bits.append("%s hiring %d role%s you match" % (names, jobs, "" if jobs == 1 else "s"))
    return " · ".join(bits)


def build_message(digest_path="out/digest.json", con=None, today=None,
                  marks=None, dry_run=False):
    """Returns the message text, or None when there is nothing worth sending."""
    with open(digest_path, encoding="utf-8") as fh:
        d = json.load(fh)
    events = [e for v in (d.get("days") or {}).values()
              for e in (v.get("recommended") or [])]
    if not events:
        return None

    today = today or dt.date.today()
    marks = triage.load() if marks is None else marks
    going = triage.by_status(marks, "going")
    saved = triage.by_status(marks, "saved")
    hidden = triage.by_status(marks, "hidden")
    owned = _con() if con is None else con

    sections, to_mark = [], []

    # ---- 1. genuinely new, worth the trip, and not already triaged
    fresh = [e for e in events
             if e.get("age_days") == 0
             and e["score"] >= MIN_NEW_SCORE
             and e["uid"] not in marks
             and not _already(owned, e["uid"], "new")]
    fresh.sort(key=lambda e: -e["score"])
    if fresh:
        head = ("%d new event%s worth your time"
                % (len(fresh), "" if len(fresh) == 1 else "s"))
        body = [head, ""]
        for e in fresh[:MAX_NEW]:
            body.append("%s %s — %s  [%s %d]"
                        % (_fmt_date(e["date"]), e["time"] or "time TBD",
                           e["title"], e.get("verdict", "?"), e["score"]))
            extra = _one_liner(e)
            if extra:
                body.append("   " + extra)
            body.append("   " + e["url"])
        if len(fresh) > MAX_NEW:
            body.append("")
            body.append("...and %d more on the dashboard." % (len(fresh) - MAX_NEW))
        sections.append("\n".join(body))
        to_mark += [(e["uid"], "new") for e in fresh]

    # ---- 2. something you are committed to has moved
    tracked = going | saved
    moved = [e for e in events
             if e["uid"] in tracked and e.get("changed_note")
             and not _already(owned, e["uid"], "changed:" + e["changed_note"][:40])]
    if moved:
        body = ["Changed — you are tracking these", ""]
        for e in moved:
            tag = "going" if e["uid"] in going else "saved"
            body.append("%s — %s (%s)" % (_fmt_date(e["date"]), e["title"], tag))
            body.append("   " + e["changed_note"])
            body.append("   " + e["url"])
        sections.append("\n".join(body))
        to_mark += [(e["uid"], "changed:" + e["changed_note"][:40]) for e in moved]

    # ---- 3. tomorrow's commitments, with a leave-by time
    tom = (today + dt.timedelta(days=1)).isoformat()
    plans = [e for e in events if e["uid"] in going and e["date"] == tom
             and not _already(owned, e["uid"], "tomorrow:" + tom)]
    if plans:
        body = ["Tomorrow you are going to:", ""]
        for e in plans:
            body.append("%s — %s" % (e["time"] or "time TBD", e["title"]))
            if e.get("venue"):
                body.append("   " + e["venue"])
            lb = _leave_by(e)
            if lb:
                c = e["cost"]
                body.append("   leave by %s (%d min by %s)"
                            % (lb, c["one_way_min"], c["mode"]))
            if e.get("opener"):
                body.append("   opener: " + e["opener"])
        sections.append("\n".join(body))
        # keyed on the date so it fires once per event per day
        to_mark += [(e["uid"], "tomorrow:" + tom) for e in plans]

    # ---- 4. Sunday: a weekly pulse so silence is never ambiguous
    if today.weekday() == 6 and not _already(owned, "weekly", "w:" + today.isoformat()):
        go = [e for e in events if e.get("verdict") == "GO" and e["uid"] not in hidden]
        untriaged = [e for e in events if e["uid"] not in marks and e["date"] >= today.isoformat()]
        body = ["Weekly pulse", "",
                "%d events in the window, %d you have not triaged yet."
                % (len(events), len(untriaged)),
                "%d currently rated GO. %d marked going, %d saved."
                % (len(go), len(going), len(saved))]
        if not marks:
            body.append("")
            body.append("No triage file yet — press Sync on the dashboard and commit "
                        "data/triage.json so these alerts can tell what you have "
                        "already registered for.")
        sections.append("\n".join(body))
        to_mark.append(("weekly", "w:" + today.isoformat()))

    if not sections:
        if con is None:
            owned.close()
        return None

    if not dry_run:
        for uid, kind in to_mark:
            _mark(owned, uid, kind)
        owned.commit()
    if con is None:
        owned.close()

    return "\n\n———\n\n".join(sections)


def main():
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if not token or not chat:
        print("TELEGRAM_TOKEN / TELEGRAM_CHAT not set - nothing to do.")
        return 0
    text = build_message()
    if not text:
        print("Nothing new since the last run - deliberately sending nothing.")
        return 0
    body = urllib.parse.urlencode({
        "chat_id": chat, "text": text, "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token,
                                 data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        print("telegram:", r.status, "-", len(text), "chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
