"""Telegram alerts. The property under test is mostly SILENCE."""
import datetime as dt
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jobevents import notify


def digest(events):
    days = {}
    for e in events:
        days.setdefault(e["date"], {"recommended": [], "review_queue": []})
        days[e["date"]]["recommended"].append(e)
    return {"days": days, "meta": {}}


def ev(uid, **kw):
    base = {"uid": uid, "title": "Event " + uid, "date": "2026-09-20",
            "time": "6:00 PM", "start": "2026-09-20T18:00:00", "score": 80,
            "verdict": "GO", "age_days": 0, "changed_note": "", "url": "https://x/" + uid,
            "venue": "SoMa", "cost": {}, "openings": [], "opener": ""}
    base.update(kw)
    return base


class TestNotify(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.dpath = os.path.join(self.dir, "digest.json")
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(notify.ALERT_SCHEMA)
        self.today = dt.date(2026, 9, 15)          # a Tuesday, so no weekly pulse

    def write(self, events):
        with open(self.dpath, "w") as fh:
            json.dump(digest(events), fh)

    def build(self, **kw):
        kw.setdefault("con", self.con)
        kw.setdefault("today", self.today)
        kw.setdefault("marks", {})
        return notify.build_message(self.dpath, **kw)

    # ---------------------------------------------------------------- new
    def test_new_high_scoring_event_is_announced(self):
        self.write([ev("a", score=80)])
        msg = self.build()
        self.assertIn("Event a", msg)
        self.assertIn("1 new event worth your time", msg)

    def test_the_same_event_is_never_announced_twice(self):
        """The bug that made the old digest worthless."""
        self.write([ev("a")])
        self.assertIsNotNone(self.build())
        self.assertIsNone(self.build())

    def test_low_scoring_new_events_are_ignored(self):
        self.write([ev("a", score=40)])
        self.assertIsNone(self.build())

    def test_events_that_are_not_new_are_ignored(self):
        self.write([ev("a", age_days=6)])
        self.assertIsNone(self.build())

    def test_already_triaged_events_are_not_announced(self):
        self.write([ev("a")])
        self.assertIsNone(self.build(marks={"a": {"s": "going", "m": {}}}))

    def test_dry_run_does_not_record_so_it_can_repeat(self):
        self.write([ev("a")])
        self.assertIsNotNone(self.build(dry_run=True))
        self.assertIsNotNone(self.build(dry_run=True))

    def test_new_list_is_capped_but_says_how_many_more(self):
        self.write([ev("u%d" % i, score=90 - i) for i in range(9)])
        msg = self.build()
        self.assertIn("9 new events", msg)
        self.assertIn("and 4 more", msg)

    # ------------------------------------------------------------ changed
    def test_change_to_a_tracked_event_is_announced(self):
        self.write([ev("a", age_days=9, changed_note="time moved from 18:00")])
        msg = self.build(marks={"a": {"s": "going", "m": {}}})
        self.assertIn("Changed", msg)
        self.assertIn("time moved from 18:00", msg)

    def test_change_to_an_untracked_event_is_not_announced(self):
        self.write([ev("a", age_days=9, changed_note="time moved")])
        self.assertIsNone(self.build())

    def test_a_second_distinct_change_still_alerts(self):
        self.write([ev("a", age_days=9, changed_note="time moved from 18:00")])
        marks = {"a": {"s": "going", "m": {}}}
        self.assertIsNotNone(self.build(marks=marks))
        self.assertIsNone(self.build(marks=marks))          # same change, silent
        self.write([ev("a", age_days=9, changed_note="venue changed from SoMa")])
        self.assertIsNotNone(self.build(marks=marks))       # different change, alerts

    # ----------------------------------------------------------- tomorrow
    def test_tomorrow_reminder_includes_a_leave_by_time(self):
        self.write([ev("a", date="2026-09-16", start="2026-09-16T18:00:00",
                       age_days=9,
                       cost={"known": True, "one_way_min": 40, "mode": "BART",
                             "total_cash": 9.0})])
        msg = self.build(marks={"a": {"s": "going", "m": {}}})
        self.assertIn("Tomorrow you are going to", msg)
        self.assertIn("leave by 5:15 PM", msg)   # 18:00 - 40min - 5min slack

    def test_tomorrow_only_covers_events_you_are_going_to(self):
        self.write([ev("a", date="2026-09-16", age_days=9)])
        self.assertIsNone(self.build(marks={"a": {"s": "saved", "m": {}}}))

    def test_tomorrow_fires_once_per_day(self):
        self.write([ev("a", date="2026-09-16", age_days=9)])
        marks = {"a": {"s": "going", "m": {}}}
        self.assertIsNotNone(self.build(marks=marks))
        self.assertIsNone(self.build(marks=marks))

    # ------------------------------------------------------------- weekly
    def test_sunday_sends_a_pulse_even_with_nothing_new(self):
        self.write([ev("a", age_days=30)])
        msg = self.build(today=dt.date(2026, 9, 20))       # Sunday
        self.assertIn("Weekly pulse", msg)

    def test_weekday_with_nothing_new_sends_nothing(self):
        self.write([ev("a", age_days=30)])
        self.assertIsNone(self.build())

    def test_empty_digest_sends_nothing(self):
        self.write([])
        self.assertIsNone(self.build())


if __name__ == "__main__":
    unittest.main()
