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
