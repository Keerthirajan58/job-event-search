# Job-Event Search — feasibility, architecture, and what I changed about your plan

Written after testing every source by hand on **2026-08-27**. All numbers below are
measured from live responses, not estimated.

---

## 1. Feasibility analysis

### The headline: your plan is feasible at $0, but you diagnosed the wrong problem

You framed this as a **discovery** problem ("find events across many platforms").
Measured reality for the Bay Area:

| | count |
|---|---|
| Luma events reachable in one lat/lng query stream | **932** |
| Meetup events across 12 keyword queries | 247 |
| Eventbrite events across 6 browse pages | 105 |
| HackerX Bay Area listings | 2 |
| **Total raw listings per run** | **~1,190** |
| Days in September 2026 with zero events | **0** |
| Events scoring ≥ 45/100 after filtering | **64** |
| Events scoring ≥ 80/100 | **8** |

Discovery is trivially solved. **Roughly 95% of what comes back is noise**, and the
noise is not "slightly off-topic tech" — it is Corgi Cafe parties, toddler sensory
play, sound baths, golf clinics and non-English community events. The hard problem
is **precision**, and that is where the engineering belongs.

Three pieces of evidence that shaped the whole design:

1. **Popularity is anti-correlated with value.** The single most-attended event in
   the window (1,055 registrations) is a *Short Story Symposium*. Ranking by
   attendance would actively mislead you.
2. **Naive keyword matching fails immediately.** A substring search for `hiring|job|fair`
   returns *"Bayview Transit Fair Family Fun Day"*, *"Berkeley FA26 Design Fair"* and
   *"Fairway Social at Stanford: Golf Clinic"*. Every pattern in this system is
   therefore anchored on word boundaries and expressed as a phrase.
3. **The dangerous false positive is audience mismatch, not topic mismatch.** Two
   events initially scored 86 and 90 out of 100. Reading their own descriptions:
   one is for *"Operators with years of experience in finance, bizops, legal,
   recruiting"*; the other is for *"Senior women & non-binary senior engineers"* in a
   members-only network. Both are real events with real hiring intent. Neither is
   attendable by a new-grad male engineer. Keyword scoring alone cannot see this.

### On "discovery is trivially solved" — a correction

That claim was too strong, and the pushback was right. Discovery of *listed* events is
solved. Discovery of the *right* events is not. So I tested the specific gaps rather
than assuming either way:

| Uncovered surface | Tested | Result |
|---|---|---|
| Community Luma calendars (AI Tinkerers, Llama Lounge, SF Tech Week, …) | probed 77 slugs | 25 real calendars; only **7** produce in-window Bay Area events, and nearly all of those events **already appear in the geo firehose** |
| University calendars | Stanford `events.stanford.edu/calendar.ics` | Works — 2,258 events, 756 in window, but only **57** loosely AI/CS/career and mostly medicine and law, 30 mi away. **Not added**: worse signal-to-noise than what we already have |
| Berkeley EECS | RSS feed | Reachable but effectively empty |
| Hackathon aggregators | `devpost.com/api/hackathons` | Worked once, now returns **403**. Not worked around |
| AI Tinkerers own site | `sf.aitinkerers.org` | **Cloudflare challenge (403)**. Not worked around |
| LinkedIn Events | — | Login wall. Still excluded |

So the honest finding is narrower than either claim: **the Bay Area AI/engineering
community has standardised on Luma**, which is why the firehose covers it so well. The
genuinely uncovered surface is real but small, and most of it is either blocked or
lower-quality than what we already collect. The 7 validated calendars are kept anyway —
they cost 7 requests, and SF Tech Week's calendar will fill up as Oct 5 approaches.

What *did* materially improve recall was unglamorous: **pagination depth**. The geo
query reaches Oct 31 and beyond in 20 pages, giving 735 events in the extended window.
Worth noting: **Oct 5 — the SF Tech Week kickoff — currently shows zero events.** They
are not posted yet. That is the strongest possible argument for the daily re-run.

### Your "1 worthwhile event per day for 30 days" requirement

**Achievable for roughly the first two weeks; not achievable as a one-shot 30-day
plan, for a reason no tool can fix.** Bay Area events are published 1–3 weeks ahead.
On any given day the far end of a 30-day window is genuinely close to empty — not
because collection failed, but because the events do not exist yet. Concretely:
the curated Luma SF feed today shows 0 events for 12 different September dates.

This makes the daily re-run the *primary* feature rather than a nice-to-have, and it
is why the tool keeps a SQLite history and flags newly-appeared events as `NEW`.

### Your "STRICTLY NO FALSE POSITIVES OR FALSE NEGATIVES" requirement

I can't build that, and neither can anyone else — it is asking a classifier to be
perfect on adversarially messy human-written text. Pretending otherwise would be
the most dangerous thing I could hand you. What the system actually guarantees:

* **Zero fabrication.** Every field traces to a fetched payload. Nothing is invented
  — no companies, no people, no events. If a field is unknown it is shown as unknown.
* **Zero stale recommendations.** Every shortlisted event's own page is re-fetched in
  the same run that recommends it, confirming it still exists and registration is open.
* **Bounded false negatives.** Nothing is silently discarded. Events with too little
  information land in category `U` (*insufficient data*), hard-capped at 44 so they
  can never be recommended but are never dismissed either. Every excluded listing is
  stored with the reason (`python3 run.py --audit`).
* **Honest confidence.** `HIGH`/`MEDIUM`/`LOW` measures *how much we know*, computed
  separately from the score, and the reason it is not HIGH is always printed.

That is the achievable version of what you asked for, and it is what got built.

---

## 2. Recommended architecture

Close to what you proposed, with two deliberate simplifications and one addition.

```
run.py                       one command, end to end
  │
  ├── collect ──────────────  4 source adapters, independent, fail-soft
  │     luma / meetup / hackerx / eventbrite
  │
  ├── normalize ────────────  tz-aware datetimes, haversine distance, city
  │                           canonicalisation, URL canonicalisation  (pure code)
  │
  ├── gate ─────────────────  drop: no title, past, outside window, virtual,
  │                           >35 mi, registration closed   (reason recorded)
  │
  ├── hydrate ──────────────  fetch full descriptions ONLY for the ~200 that
  │                           survive gates — not all 1,190
  │
  ├── dedupe ───────────────  date-bucketed; URL match or title similarity +
  │                           time/venue agreement; merges source links
  │
  ├── score ────────────────  category first, then capped points, every point
  │                           carrying a reason string
  │
  ├── annotate ─────────────  fit / who-to-meet / opener from your profile
  │
  └── emit ─────────────────  SQLite history + digest.json + index.html
```

**Changes from your proposal:**

| Your plan | What I built | Why |
|---|---|---|
| AI classification of events | Deterministic lexicon + decision tree; LLM optional and currently unused | Free LLM tiers are rate-limited and non-deterministic. A rule fires the same way every run and can be *debugged*. On this data the rules already separate signal from noise, and every score is explainable — which matters more than marginal accuracy when you're deciding how to spend an evening. |
| React dashboard | One generated static HTML file | No build step, no dependencies, opens offline, works on your phone. The UI was never the hard part. |
| Scheduled collection then dashboard | MVP-first: one command → JSON + HTML | Exactly as you suggested. Correct call. |
| `pip install` of requests/bs4/pandas | **Zero dependencies — stdlib only** | Runs on your system Python 3.9 with nothing installed. Nothing to break, nothing to update, no supply chain. |
| LinkedIn Events as a source | **Dropped** | Behind a login wall. Collecting it would require credential/ToS circumvention. Not worth the risk and not necessary. |
| — | **Eligibility detection** (added) | The highest-cost error is travelling to an event you cannot attend or that targets a different role. This was not in your spec and is the single most valuable thing the tool does. |
| Straight-line distance penalty | **Door-to-door travel time + fare from home** | Distance is a bad proxy in the Bay Area. Downtown is 5.5 mi but 36 min by BART; Palo Alto is 27 mi and 107 min via Caltrain for $23.72 round trip. One number cannot express both. |
| — | **Company roles + live openings** (added) | Turns "attend this" into "attend this: Stripe hosts it and has 7 roles you match, including ML Engineer in South SF." |
| — | **Verdict badge** (added) | The dashboard should answer "should I go?" before "what is the score?" |
| — | **Feedback loop + organiser prior** (added) | The only component that can outperform my hand-written rules, because it uses measured outcomes instead of my assumptions. |
| — | **Change detection** (added) | An event you already triaged can move venue, sell out, or start charging. |

---

## 3. Free technology stack

| Layer | Choice | Cost |
|---|---|---|
| Language | Python 3.9+ (your system Python) | $0 |
| Dependencies | **none** — `urllib`, `json`, `re`, `sqlite3`, `zoneinfo`, `html` | $0 |
| Storage | SQLite (`data/events.db`) | $0 |
| HTTP cache | gzipped files, 6h TTL | $0 |
| Dashboard | generated static HTML, dark-mode aware | $0 |
| Scheduling | GitHub Actions cron (2000 free min/month; this uses ~15) | $0 |
| Hosting | GitHub Pages, so the digest is on your phone | $0 |
| LLM | none required; optional Groq/Gemini/Cerebras free tier | $0 |

**On free LLM APIs, since you asked whether they exist *now*:** yes — Google AI
Studio, Groq, Cerebras, GitHub Models, Cloudflare Workers AI and NVIDIA NIM all
have real no-credit-card free tiers as of August 2026. They are rate-limited
(roughly 15–60 requests/min). None is needed here: with ~200 events to judge per
run, a free tier would work, but a rule that always fires identically beats a
non-deterministic call you cannot reproduce when it gets something wrong. Hooks are
in place if you later want an LLM to re-rank the top 20 only.

---

## 4. Data-source strategy

Tested individually, in the priority order you specified.

### Luma — **PRIMARY**. Official-quality public JSON, no auth.
`api.luma.com` serves the endpoints its own web app uses, with no key, no cookie
and no header requirement. Its `robots.txt` disallows only `/insights/`.

* `GET /discover/get-paginated-events?latitude=&longitude=&period=future` — the geo
  firehose. **932 Bay Area events**, cursor-paginated.
* `GET /calendar/get-items?calendar_api_id=cal-…` — curated community calendars
  (AI Tinkerers, Llama Lounge, SF Tech Week). High precision, low volume.
* `GET /url?url=<slug>` — resolves a slug to an event or calendar.
* `GET /event/get?event_api_id=evt-…` — full detail.

Returns everything needed: full description (ProseMirror), hosts **with bios**,
featured speakers, registration count, free/paid, sold-out, approval-required,
coordinates, timezone, and in-person vs online. This one source is ~80% of the value.

> One correction worth knowing: the `slug=sf` "featured city" feed returns only **58**
> events and looks sparse enough to make the project seem infeasible. The lat/lng
> query returns **932**. I nearly reached the wrong conclusion from the first one.

### Meetup — **SECONDARY**. Public search pages only; API is genuinely paid now.
The open REST API is retired. GraphQL requires an active **Meetup Pro** subscription
*plus* OAuth-consumer approval — so your budget rules it out, and `robots.txt`
disallows `/api/`, so their internal endpoint is off-limits too.

What works: `/find/?keywords=…&location=us--ca--San Francisco` is server-rendered and
embeds a complete Apollo cache in `__NEXT_DATA__` with **full descriptions**, ISO
datetimes with offsets, venues, groups and RSVP counts. One GET per keyword,
robots-clean. **247 events from 12 keywords.**

Caveat: only ~25% of Meetup's SF tech inventory is in-person now; the rest is online
and gated out. Its value is the classic named dev meetups Luma doesn't carry.

*Privacy note:* that cache also contains individual member records. The adapter reads
`rsvps.totalCount` only and stores no member data.

### HackerX — **HIGH-PRECISION, LOW-VOLUME**. Fully open.
`robots.txt` is `Allow: /` and explicitly permits `ClaudeBot`/`anthropic-ai`.
`/events/` carries one schema.org `Event` JSON-LD block per listing.

Two things that took reading the page to get right:
* JSON-LD carries **no URL**. The registration link lives in a sibling
  `data-event-id` attribute, which is an *Eventbrite* id —
  `eventbrite.com/e/<id>` 301s to the real page. Without that pairing every HackerX
  recommendation would link to a useless index page.
* Listings split into **DEVELOPER** and **EMPLOYER** tracks. The employer ticket is
  for companies who want to recruit. **Both current SF listings are employer-track**,
  so the tool keeps them as evidence a hiring event exists but excludes them from
  recommendations with that reason attached.

### Eventbrite — **TERTIARY, low yield.** Keep, but expect little.
The public Event Search API was switched off in **February 2020** and never replaced;
v3 now only serves your own organisation's events. `robots.txt` also disallows
`/api/v3/destination/events/`, their internal search API — not used.

What works: `/d/<place>/<category>/` browse pages embed
`window.__SERVER_DATA__.search_data.events.results` (18/page, 49 pages), with venue
coordinates and Eventbrite's own dedup hash. Descriptions are truncated, so the
detail page is fetched for shortlisted events only.

Measured quality is poor: paid workshops, resold conference tickets, and placeholder
listings (one "Women in Tech SF 2026" has the venue *"We're looking for a host in SF!"*).
It earns its place for the occasional real job fair, nothing more.

### LinkedIn Events — **DROPPED.**
Behind authentication. Collecting it means circumventing a login wall. Not done.

---

## 5. Event scoring methodology

Four stages. No stage is a black box.

**Stage 1 — Gates (before any scoring).** No title · already started · outside window ·
virtual · >35 mi from downtown SF · unresolvable location · registration closed.
Gated events are stored with the reason, never deleted.

**Stage 2 — Category, assigned first.** A–G as you specified, plus `U`.

| | ceiling | |
|---|---|---|
| A | 100 | explicit hiring/recruiting |
| B | 92 | technical depth + engineers + a format where people talk |
| C | 74 | startup/founder networking |
| D | 62 | general technical event |
| E | 32 | low-value / social / wrong audience |
| F | 30 | investor / pitch |
| G | 10 | irrelevant |
| **U** | **44** | **insufficient data — capped below the recommend threshold, not dismissed** |

Category is decided *before* points, and its ceiling is binding. This is what stops
an investor pitch night with excellent technical keywords from out-ranking a real
recruiting mixer — the failure mode you specifically called out.

**Stage 3 — Points, each with a reason string.** Category base, then:
hiring language (title weighted above body) · engineer audience named · technical term
density · conversation-friendly format (mixer/demo night) vs talks-only · **company
named in title/venue/host** · attendance sweet spot (40–400 is best; >900 penalised as
too crowded to meet anyone) · free vs priced · sold-out · approval-required · travel
distance · investor drag · **eligibility friction** · overlap with your background.

Two calibrations worth flagging:
* **Category A has a floor of 70.** HackerX-style organisers publish no attendance or
  price data, so they collect none of the metadata bonuses and a genuine recruiting
  event scored *59* — below an ordinary meetup. The format's value is real even when
  the metadata is thin.
* **Company names that are ordinary English words require corporate context.**
  `Cruise`, `Block`, `Square`, `Box`, `Stripe`, `Plaid`, `Glean`, `Temporal` and ~30
  others only count next to a marker like `@`, `HQ`, `hosted by`. This was found the
  hard way: *"Dreamforce Lunch **Cruise**"* was being credited with self-driving-car
  engineers on site.

**Stage 4 — Confidence, computed independently.** Downgraded by: description under
200 chars · no coordinates · page not re-checked · attendance unpublished · zero
registrations · high category on thin evidence · single uncorroborated source ·
audience restriction present. The reasons are always shown.

### Eligibility detection (not in your spec; the most valuable part)

The tool looks for the listing's **own audience definition** — text after *"Who this
is for"*, *"This event is for"*, *"Who should attend"*, *"Open only to"* — and checks
it for identity/membership restrictions, seniority requirements above new-grad, and
non-engineering target roles.

**Scope is the entire trick.** Matched against full body text these patterns fire on
*speaker bios*: a host's *"30+ years"* wrongly penalised **"Meet the Other Side: Job
Seekers × Hiring Teams"** — the best-fitting event in the whole window — dropping it
from 98 to 86. Restrictions are now read only from the title and the explicit audience
section. Unambiguous phrases (*"members only"*, *"invite-only"*) still count anywhere.

Restricted events are **never silently dropped**. The restricting sentence is quoted
back to you verbatim so you decide.

---

## 5b. What was added in phase 2, and the bugs each one exposed

Every feature below was validated against live data, and each caught a real defect.

**Cost of attendance** (`transit.py`). Models walk → rail → last-mile from Broad St,
with BART and Caltrain station tables. *Bug it exposed:* a Palo Alto venue 1.3 mi from
Caltrain fell through to the Muni model and produced a **194-minute** estimate at
$2.85. Rail routes now allow a bus connection up to 3.5 mi, and surface transit is
capped at 11 mi. Venues genuinely unreachable are labelled as such rather than given
an invented number.

**City-centroid fallback.** Many Meetup/Eventbrite listings publish a city but no
coordinates. *Bug it exposed:* an AI conference in **Santa Clara, 45 mi away**, was
being recommended at 70/100 purely because it named a Bay Area city and so escaped the
distance gate. Travel cost coverage went from partial to **100% of live events**.

**Company extraction with roles** (`companies.py`). *Bug it exposed:* a 180-char scan
window meant "Sponsored by Anthropic, Modal and Vercel." also claimed Scale AI,
Snowflake and Uber from the following sentences. Windows are now cut at the sentence
boundary, and the lead phrase is scanned along with it (because "Sponsored by" is
itself the corporate context that ambiguous names like Modal need).

**Live openings** (`openings.py`). Greenhouse and Ashby serve keyless public boards;
**43 of 49** mapped slugs verified live, the rest deleted rather than left failing.
Lever excluded — every slug guess 404'd. *Bug it exposed:* `new grad` was in the role
patterns, so "Associate Product **Manager**, New Grad" matched. New-grad terms are now
a sort key, not a qualifier, and "Sr" was added to the seniority filter after
"Sr Software Engineer" slipped through.

**Industry mismatch.** *Bug it exposed:* "California Sports & Ent. **Career Expo**"
scored 67 as a top recruiting event. It is a genuine career expo — for sports and
entertainment jobs. Hiring language is necessary but not sufficient.

**Structural route into category B.** Requiring 3+ technical terms for category B was
my own fix for a different false positive, and it created a **false negative**: "Demo
Night @ WorkOS" — 285 engineers demoing, host company with 5 verified openings — fell
to category D and dropped 20 points. Jargon density measures how verbose an organiser
is, not how good the event is. Category B now also admits build/demo formats backed by
a company with real involvement.

**Change detection.** *Bug it exposed:* including the description in the fingerprint
made hydration itself look like an edit — **296 spurious "changed" flags** on the second
run. A description appearing for the first time is now recognised as us fetching more
detail. Genuine changes: 4.

**Feedback loop** (`feedback.py`, `log_event.py`). Five questions after an event.
The organiser prior needs 2+ logged events, is bounded to ±10 points, scales with
sample size, and always prints as a line in the breakdown. `--stats` also reports
whether events scored ≥70 actually produced better nights than those below — if they
did not, the weights are wrong and your data should win.

## 5c. Deployment (phase 7)

`./deploy.sh` after `gh auth login`. It creates a public repo, sets Pages to build
from Actions, pushes, watches the run, then verifies the live page.

Four things about CI that needed handling, each found by testing rather than assumed:

**Pages requires a public repo on the free plan.** Private + Pages needs GitHub Pro,
which breaks the $0 rule. Consequence: the personal email came out of the User-Agent
and `HOME_LAT/LON` became an Ocean View neighbourhood centroid instead of a street
address (worth about a minute of travel-estimate accuracy). The page carries
`noindex, nofollow, noarchive` and a `robots.txt` disallow.

**State had to be split.** `data/events.db` is 5 MB and regenerable — committing it
daily would add ~50 MB of pack per two months, so CI restores it from `actions/cache`
with a rotating key. But the organiser prior lives in the same database and *is*
irreplaceable, so attendance moved to `data/attendance.db` (12 KB), which is committed.
Without that split the deployed dashboard could never reflect logged outcomes.

**`secrets` is not available in a step-level `if:`.** The original workflow's
`if: ${{ secrets.TELEGRAM_TOKEN != '' }}` would not have worked. The optional
notification step now maps the secret to `env` and tests the variable in shell.

**Pages must be configured before the first push.** The workflow triggers on push; a
run that builds before Pages is set to "GitHub Actions" fails at the deploy step. The
script therefore enables Pages first, with a retry after the push for the case where
a brand-new empty repo rejects the API call.

Two correctness fixes came out of thinking about a job that runs every day rather than
once: the window now ends on a **fixed date** (`WINDOW_END = 2026-10-31`) because a
rolling start with a fixed day-count would have been looking into December by late
October; and the dashboard now renders **full cards for the highest-value events
anywhere in the window**, not just the next seven days — previously WorkOS Demo Night
on Sept 14 and the Codex meetup on Sept 24 appeared only as one-line table rows, so
their cost, companies, openings and opener were invisible until the date came close.

## 5d. Phase 8 — the dashboard becomes a tool you operate

Four changes, in the order they mattered.

**Triage state (Going / Saved / Hidden).** The hard question was where state lives.
GitHub Pages serves static files; writing from the page would need a token in a public
repo, and a backend costs money. So marks live in `localStorage`, which is the right
answer for one user and turns out to be sufficient because event ids are stable —
`sha1(normalised title | date | city)` does not move when a listing is re-scraped, so
last night's marks still attach this morning. Verified before building anything else,
since the whole feature collapses if ids churn.

Two consequences handled rather than ignored: marks do not follow you between devices,
and the Python side cannot see them. Both are solved by the same file — the Sync button
exports `data/triage.json`, which is committed, embedded in the next build, and merged
client-side **by recency**, so the laptop and the phone converge without either
clobbering a newer decision. That file is also what lets the alerts know what you
already registered for.

**One card pool, six views.** Rather than six DOM containers with cards moved between
them, every recommended event is rendered once inside a day-grouped pool and each tab
is a *filter* over it. Nothing is duplicated, so the calendar and the lists cannot
disagree, and the calendar is annotated from the same DOM the lists read.

**Calendar.** A server-rendered month grid; JS only annotates counts, verdict-coloured
dots, and a marker on days you are already attending something. Tapping a date filters
to it. This was the cheapest of the four features and removed the most friction — the
window is 61 days, and scrolling it was the actual complaint.

**Alerts instead of a digest.** Covered in the README; the design point is that the
valuable behaviour is *silence*, and that non-repetition had to be enforced in a table
of `(uid, kind)` rather than hoped for.

Bugs this phase produced and what caught them:

| bug | found by |
|---|---|
| two toolbars both used `id="dosync"` — duplicate ids, and `getElementById` finds only the first | a duplicate-id scan of the emitted HTML |
| `import json` was inserted against `import html`, but the module aliases `import html as H`, so the seed crashed the run | the run failing outright |
| `actions/cache` was set to `path: data`, which would have restored a stale copy over the committed `attendance.db` and `triage.json` | reviewing what the cache actually covers against what git tracks |
| calendar legend referenced Python colour constants that never existed | first build after the rewrite |

The interactive layer is covered by 38 assertions run in jsdom (`scratchpad/test_dash.js`,
`test_seed.js`): tab switching, horizon toggle, each triage transition, undo, calendar
selection and annotation, `.ics` generation, the sync payload, reload persistence, and
both directions of the recency merge. A JS syntax error would silently break the entire
page, so `node --check` runs over the extracted script as well.

## 5e. Phase 8b — what the tests missed, and why

Four reported bugs, three found while writing tests for them, and one shipped
regression that broke the site outright. The last one is the instructive one.

**The page-breaking bug.** `#modal{display:flex}` was authored to centre the expanded
card. The HTML `hidden` attribute is honoured only by the user-agent rule
`[hidden]{display:none}`, and a user-agent rule loses to any author rule of equal
specificity — so the modal was painted on every load: an empty sheet over a blurred,
unclickable page. The dashboard suite asserted `element.hidden`, which was `true` the
entire time. 100 assertions passed against a completely broken page.

Two fixes, one structural and one procedural:

- `[hidden]{display:none!important}` as the first rule in the stylesheet, so no later
  `display` declaration can win that fight again.
- A third test suite that drives real Chrome and asserts what is *painted* and what is
  *clickable* — `elementFromPoint` at the centre of the viewport, `getComputedStyle`
  on everything marked hidden, and a real click through the calendar and modal. The
  jsdom suite also now checks computed display rather than the property.

The general lesson: a test that asserts the same abstraction the code uses cannot
catch a bug in that abstraction. `element.hidden` and "the user can see it" are not
the same claim, and only the second one matters.

**The other bugs this phase**

| bug | cause | caught by |
|---|---|---|
| New tab listed all 97 events | `first_seen` lived only in a gitignored DB restored from `actions/cache`; on a miss everything read as new | the user; now guarded by a CI check that fails if all listings read as first-seen-today |
| cost boxes were huge squares | the calendar CSS used `.cell`, which the cost strip already owned, so every box inherited `aspect-ratio:1/1` | reading the CSS after the user described the symptom |
| borderline rejected cards were triageable | compact audit cards carry `data-uid`, so they joined the pool, the badges and the calendar | the new dashboard suite |
| a calendar day could not be deselected | selecting rebuilt the grid and detached the clicked node | the new dashboard suite |
| the tomorrow reminder repeated | it recorded that it had fired but never checked | the new notify suite |
| "How this run went be" | `\25be` in a non-raw Python string ate `\25` as an octal escape | the first real screenshot |

## 6. Failure modes

| Failure | Likelihood | Blast radius | Mitigation in place |
|---|---|---|---|
| Luma changes its JSON shape | medium (undocumented API) | severe — 80% of value | Per-record `try/except`: one malformed event is skipped, the source still returns. Already caught a real case where `price` is `{"cents": 4000}`, not a number. |
| Meetup changes `__NEXT_DATA__` | medium | moderate | Adapter returns `[]`; other three sources unaffected. |
| Cloudflare starts challenging us | low (we self-throttle, identify ourselves) | source lost | `Blocked` exception stops that source immediately — never retried around. Luma's API needs no browser. |
| Eventbrite HTML restructure | medium | small (low-yield source) | Fails soft. |
| Lexicon misses a new phrasing | **high — the real risk** | false negatives | `--audit` lists everything excluded with reasons; `U` category holds the unjudgeable; borderline events shown in the review queue rather than hidden. |
| Over-aggressive eligibility rules | medium | false negatives | Already happened and was fixed by rescoping; the audit query that caught it is reusable. |
| Sparse far end of the window | **certain** | looks like a bug, isn't | Honest "No worthwhile event found" + best-candidate score, plus `NEW` flags on daily re-run. |
| Timezone/DST error | low | wrong day | All parsing tz-aware via `zoneinfo`; Luma's UTC + timezone name and Meetup's ISO offsets both verified. |
| DB accumulates rows from older code | certain | confusing audits only | `data/events.db` is append-only history; reports are always built from the live run. Delete it to reset. |

---

## 7. MVP definition — status: **done and working**

> One command → collect → deduplicate → rank → today's top events as JSON/HTML.

```
$ python3 run.py
1187 raw -> 634 unique -> 64 recommended across 30 days   (17s cached, ~250s cold)
```

Verified working: 4 sources · gates with recorded reasons · 200 detail fetches ·
cross-source dedupe (13 merged, including Luma+Meetup and Meetup+Eventbrite for the
same event) · A–G+U categories · explained scores · confidence · eligibility checks ·
per-event fit/who-to-meet/opener · SQLite history with `NEW` detection · `digest.json`
· dark-mode `index.html`.

## 8. Implementation plan

- [x] **Phase 0** — research and hand-test every source *(done; findings above)*
- [x] **Phase 1** — MVP: one command to ranked JSON + HTML *(done)*
- [x] **Phase 2** — precision hardening: eligibility, ambiguous companies, category
      floors, stub filtering *(done; each fix driven by a measured false positive)*
- [x] **Phase 3** — cost of attendance: travel time + fare from home *(done)*
- [x] **Phase 4** — company detection with roles, and verified live openings *(done)*
- [x] **Phase 5** — feedback loop and learned organiser prior *(done)*
- [x] **Phase 6** — verdict badges, change detection, extended window to Oct 31 *(done)*
- [x] **Phase 7** — daily automation: GitHub Actions cron + Pages *(done; `./deploy.sh`)*
- [x] **Phase 8** — interactive triage, New/changed view, calendar, alert-based
      Telegram *(done)*

The feedback loop is now in place but has no data. It becomes the most valuable part of
the system after roughly 20-30 logged events, at which point it starts overriding my
hand-written weights with your measured outcomes. Until then it is inactive by design.

### One thing deliberately NOT built

**speaker → LinkedIn → company → openings.** The chain breaks at LinkedIn: profiles
are behind a login wall, and scraping them would mean circumventing authentication and
collecting personal data about named individuals. What is used instead is the speaker
bio the organiser published on the event page itself — public, volunteered, and often
naming the employer anyway, which is the part that matters. Company detection then runs
on that. Same outcome where the information is legitimately available; no scraping of
people.
