# Job-Event Search

Finds and ranks Bay Area tech events by **how likely they are to help you get hired** —
not by popularity, not by how much they say "AI".

Zero dependencies. Zero API keys. Zero cost.

## Run it

```bash
python3 run.py
open out/index.html
```

First run takes ~4 minutes (fetches ~400 pages). Later runs take ~20 seconds thanks to
a 6-hour cache. Works on macOS system Python 3.9+ with nothing installed.

## Commands

```bash
python3 run.py                      # full run -> out/index.html + out/digest.json
python3 run.py --no-cache           # ignore the cache, refetch everything
python3 run.py --no-openings        # skip job-board lookups (faster)
python3 run.py --days 14            # shorter window
python3 run.py --start 2026-09-15   # different window start
python3 run.py --audit              # what got excluded and why (check for misses)
python3 run.py --explain "workos"   # full scoring breakdown for matching events

python3 log_event.py                # log what happened at an event you attended
python3 log_event.py --stats        # what the tool has learned from your outcomes
```

`--audit` and `--explain` are the two you'll actually use. When a recommendation looks
wrong, `--explain` shows every point added or removed and the exact text that
triggered it.

## Reading the output

Each event shows a **score /100**, a **category**, and a **confidence**. Score and
confidence are independent: `78/100 · MEDIUM` means "probably good, but we're working
from a thin listing."

| category | meaning |
|---|---|
| A | explicit recruiting / hiring |
| B | technical networking worth your evening |
| C | startup / founder networking |
| D | general technical event |
| E | low value, social, or wrong audience for you |
| F | investor / pitch |
| G | irrelevant |
| U | not enough information — never recommended, never dismissed |

Each card leads with a **verdict** so you do not have to interpret a number:

| verdict | meaning |
|---|---|
| GO | clear yes for that day |
| WORTH IT | solid use of an evening |
| MAYBE | only if nothing better appears |
| SKIP | do not spend the evening |
| CHECK ELIGIBILITY | good event, but the listing restricts who can attend |

**"No worthwhile event found"** is a real answer, not a bug. Nothing is invented to
fill a date.

Watch for **ELIGIBILITY CHECK** on a card. It means the listing restricts its audience
— members-only, a specific identity group, or a seniority band — and the restricting
sentence is quoted so you can decide before spending an evening on it.

### Cost of attendance

Every card shows door-to-door travel time and total spend **from Broad St**, because
distance is a bad proxy for effort here: downtown is 5.5 mi but ~36 min by BART, while
Palo Alto is 27 mi and ~107 min via Caltrain. It also warns when an event ends too
late to get home by transit. These are modelled estimates, not a routing API — see
`jobevents/transit.py`, where every constant is named and tunable.

### Companies and live openings

Companies are extracted with the **role they play** — venue, host, sponsor, speaker,
or a mere mention — because only the first four mean their people are in the room.
For companies with a public job board, the tool then checks whether they currently
have roles you match, in the Bay Area, that are not senior-level, and links each
posting directly.

A company is only reported as hiring when a real posting came back from its own
board. If a lookup fails, the tool says the lookup failed. It never guesses.

### Teaching it your preferences

```bash
python3 log_event.py          # after you attend: 5 questions, 30 seconds
python3 log_event.py --stats  # organiser track record + whether the score predicts your good nights
```

After two or more logged events from the same organiser, an **organiser prior**
(bounded to ±10 points) starts adjusting their future events, and always appears as
a line in the score breakdown. This is the part that will eventually beat the
hand-written rules, because it uses your outcomes instead of my assumptions.

## Tuning

Everything you'd want to change is in two files:

* `jobevents/config.py` — window, geography, distance limits, keywords, thresholds
  (`MIN_SCORE_RECOMMEND = 45`, `MAX_PER_DAY = 4`)
* `jobevents/features.py` — the phrase lexicon. Add a phrase here when `--audit` shows
  the tool missing something real.

Your profile and the conversation openers live in `jobevents/advice.py`.

## Using the dashboard

The page is a triage queue, not a wall of text. Six views:

| tab | what is in it |
|---|---|
| **Up next** | events you have not yet decided about, next 14 days (one button widens it to the whole window). This is the home view — anything you act on leaves it |
| **New & changed** | listings first seen in the last 3 days, plus anything you are tracking whose time, venue or price moved. Where to look first each morning |
| **Calendar** | month grid for the window. Tap a date to see only that day. Dots show how many events and how good; a green dot marks a day you are already going to something |
| **Going** | what you have registered for, with an **Add to my calendar (.ics)** button |
| **Saved** | undecided, for later |
| **Hidden** | dismissed. Nothing is ever deleted — it just stops cluttering Up next |

Each event card has **I am going / Save for later / Not interested**. Every action is
undoable from the toast that appears.

### Where your choices are stored, and the one manual step

Marks live in your browser's `localStorage`. The dashboard is a static page on
GitHub Pages, so the only alternatives were embedding a write token in a public repo
or paying for a backend — neither is acceptable. They survive the nightly rebuild
because every event has a stable id (`sha1(title|date|city)`).

To move them between devices, and to let the Telegram alerts know what you have
registered for, press **Sync** and commit the result:

```bash
# paste the copied blob into data/triage.json, then:
git add data/triage.json && git commit -m "sync triage" && git push
```

The next build embeds it in the page, so your phone picks up what you marked on your
laptop. Conflicts resolve by recency — the more recent decision wins, whichever
device made it — so neither side can silently clobber the other.

If an event you marked **Going** later drops out of the feed (the listing is pulled,
or the date passes), the Going tab still shows it from a stored snapshot, flagged as
*no longer in the current feed*. Something you registered for should never silently
vanish.

## Deploying it (daily digest on your phone, $0)

```bash
gh auth login       # opens a browser; the only manual step
./deploy.sh         # creates the repo, enables Pages, pushes, waits, verifies
```

`deploy.sh` is idempotent — re-run it any time. It prints the live URL at the end:

```
https://<your-github-username>.github.io/job-event-search/
```

After that the dashboard rebuilds **daily at 06:00 America/Los_Angeles** via GitHub
Actions (~8 of the 2000 free minutes per month). Force a refresh any time with:

```bash
gh workflow run daily-digest --repo <you>/job-event-search
```

### Two things to know about the deployment

**The repo must be public.** GitHub Pages on a free account only works from a public
repo; private + Pages requires GitHub Pro. So the code and the dashboard URL are both
world-readable. The page carries `noindex, nofollow, noarchive` plus a `robots.txt`
disallow, so it stays out of search results, but anyone with the link can read it.
For that reason `config.py` holds a neighbourhood centroid, not your street address,
and no email address.

**State is split deliberately.**

| file | in git? | why |
|---|---|---|
| `data/attendance.db` | **yes** (12 KB) | your logged outcomes — irreplaceable, and the deployed dashboard needs them for the organiser prior |
| `data/triage.json` | **yes** (tiny) | your Going / Saved / Hidden marks, exported from the dashboard's Sync button. Carries them between devices and tells the alerts what you already registered for |
| `data/events.db` | no (5 MB) | regenerable event catalogue; CI restores it from `actions/cache`. Losing it only means everything reads as "new" once |
| `data/cache/` | no (11 MB) | HTTP response cache |
| `out/` | no | published by Actions, no reason to version it |

So after you log an event locally, commit `data/attendance.db` and push — that is what
carries your feedback into the daily build.

### If a run fails

The workflow refuses to publish a thin dashboard: if fewer than
`MIN_EVENTS_SANITY` (120) unique in-window events survive collection, `run.py` exits
non-zero and the deploy step is skipped, leaving yesterday's good dashboard up. That is
the expected behaviour if a source starts blocking datacenter IPs — check the Actions
log to see which source returned nothing.

## The Telegram alerts

The first version was a digest: every morning, the top few events in the window.
Because the window barely changes day to day, neither did the message — the same list
every morning, which teaches you to swipe it away. So it is now an **alert**, and its
most important property is that it **says nothing when there is nothing to say**:

1. **New** — listings first seen in this run that score ≥62, excluding anything you
   have already triaged
2. **Changed** — the time, venue or price moved on something you marked Going or Saved
3. **Tomorrow** — what you are attending tomorrow, and **when to leave the house**,
   computed from the transit model
4. **Sunday** — one weekly pulse, so a quiet week never looks like a broken cron

Repetition is prevented in the database, not by luck: every alert is recorded as
`(uid, kind)` in an `alerts` table and is never sent twice. Sections 2 and 3 need
`data/triage.json` — see Sync above.

## Where the data comes from

Luma (public JSON API), Meetup (public search pages), HackerX (JSON-LD),
Eventbrite (public browse pages). No logins, no CAPTCHA bypass, no paid APIs, no
attendee personal data stored, self-throttled to one request per host per 0.6s.
See `ARCHITECTURE.md` for what each source can and can't do, and why LinkedIn is absent.

## Files

```
run.py                      pipeline entry point
jobevents/config.py         all tunables
jobevents/http.py           polite cached fetcher
jobevents/models.py         Event record + normalization (dates, geo, text)
jobevents/features.py       the phrase lexicon  <- the core of the product
jobevents/score.py          gates, categories, points, confidence
jobevents/dedupe.py         cross-source duplicate merging
jobevents/advice.py         your profile, fit notes, openers
jobevents/transit.py        travel time, fare, cost-of-attendance model
jobevents/companies.py      company extraction with roles (venue/host/sponsor/speaker)
jobevents/openings.py       public ATS job boards (Greenhouse, Ashby)
jobevents/enrich.py         post-scoring enrichment orchestration
jobevents/feedback.py       attendance log + learned organiser prior
jobevents/sources/*.py      one adapter per platform
log_event.py                log outcomes after an event
data/events.db              SQLite history (append-only; delete to reset)
out/index.html              the dashboard
out/digest.json             machine-readable digest
```

Read `ARCHITECTURE.md` for the feasibility analysis, measured source capabilities,
scoring methodology, and known failure modes.
