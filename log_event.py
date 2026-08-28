#!/usr/bin/env python3
"""Log what happened at an event you attended, so the tool learns your outcomes.

    python3 log_event.py              # pick from recent events, answer 5 questions
    python3 log_event.py --stats      # what the tool has learned so far

Answers are stored raw in data/events.db (table `attendance`). The organiser prior
derived from them is applied on the next run and always shown as a line in the
score breakdown, never silently.
"""
import argparse
import datetime as dt
import sys

from jobevents import feedback, store


def _ask_yn(q, default=None):
    suffix = " [y/n]" if default is None else (" [Y/n]" if default else " [y/N]")
    while True:
        a = input(q + suffix + ": ").strip().lower()
        if not a and default is not None:
            return default
        if a in ("y", "yes"):
            return True
        if a in ("n", "no"):
            return False
        print("  please answer y or n")


def _ask_int(q, default=0):
    a = input("%s [%d]: " % (q, default)).strip()
    try:
        return int(a) if a else default
    except ValueError:
        return default


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--days-back", type=int, default=21)
    args = ap.parse_args(argv)

    con = store.connect()          # event catalogue (regenerable)
    fcon = feedback.connect()      # your outcomes (irreplaceable, committed to git)

    if args.stats:
        priors = feedback.organizer_priors(fcon)
        cal = feedback.global_calibration(fcon)
        print("\nLogged attendance: %d events\n" % cal.get("n_attended", 0))
        if not priors:
            print("  Not enough data yet. The organiser prior needs 2+ logged events")
            print("  from the same organiser before it will affect any score.")
        else:
            print("  Organiser track record (adjustment applied to future events):")
            for org, (adj, n, mean) in sorted(priors.items(), key=lambda kv: -kv[1][0]):
                print("    %+5.1f pts  n=%-3d mean=%+.2f  %s" % (adj, n, mean, org))
        if "mean_quality_score_70_plus" in cal and "mean_quality_below_70" in cal:
            print("\n  Is the score predictive of your good nights?")
            print("    events scored >=70 : mean outcome %+.2f  (n=%d)"
                  % (cal["mean_quality_score_70_plus"], cal["n_70_plus"]))
            print("    events scored  <70 : mean outcome %+.2f  (n=%d)"
                  % (cal["mean_quality_below_70"], cal["n_below_70"]))
            print("    If the second number is not clearly lower, the scoring weights")
            print("    need retuning - your data beats my defaults.")
        print()
        return 0

    cutoff = (dt.date.today() - dt.timedelta(days=args.days_back)).isoformat()
    rows = con.execute("""SELECT uid,title,organizer,date_key,score FROM events
                          WHERE gate='' AND date_key >= ? AND date_key <= ?
                          ORDER BY date_key DESC, score DESC LIMIT 40""",
                       (cutoff, dt.date.today().isoformat())).fetchall()
    if not rows:
        print("No events in the last %d days in the database. Run `python3 run.py` first."
              % args.days_back)
        return 1

    print("\nRecent events (most recent first):\n")
    for i, (_uid, title, org, d, sc) in enumerate(rows, 1):
        print("  %2d. [%s] %3d  %-46s  %s" % (i, d, sc or 0, (title or "")[:46],
                                              (org or "")[:24]))
    sel = input("\nWhich number did you attend? (blank to cancel): ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(rows)):
        print("cancelled")
        return 0
    uid, title, org, d, sc = rows[int(sel) - 1]

    print("\n%s\n%s" % (title, "-" * min(len(title or ""), 60)))
    attended = _ask_yn("Did you actually attend", True)
    if attended:
        met = _ask_yn("Did you meet someone who could realistically help you get hired")
        hiring = _ask_yn("Was anyone there from a company that is actively hiring")
        repeat = _ask_yn("Would you attend another event by this organiser")
        convos = _ask_int("How many meaningful conversations", 0)
    else:
        met = hiring = repeat = False
        convos = 0
    notes = input("Anything worth remembering (optional): ").strip()

    feedback.log_event(fcon, uid, title, org, d, sc, attended, met, hiring, repeat,
                       convos, notes)
    print("\nLogged. Run `python3 log_event.py --stats` to see what it has learned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
