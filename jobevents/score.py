"""Category assignment, 0-100 job-value score, and confidence.

Design decisions worth knowing:

1. GATES run before scoring. A gated event is never ranked and never shown as a
   recommendation, but it IS retained in the DB with its gate reason so a false
   negative can be audited later. Nothing is silently dropped.

2. CATEGORY comes first, then the score is capped by category. This is what stops
   an investor pitch night with great tech keywords from out-ranking a real
   recruiting mixer. The user asked for that behaviour explicitly.

3. Every point added or removed carries a human-readable reason string. There are
   no unexplained magic numbers in the output.

4. CONFIDENCE is independent of score. It measures *how much we know*, not *how
   good it is*. Thin descriptions, missing coordinates and unverified pages all
   lower confidence even when the score is high.
"""
from . import config, features
from .models import city_coords, miles

# Category -> (label, score ceiling)
CATEGORIES = {
    "A": ("HIGH-VALUE RECRUITING / HIRING", 100),
    "B": ("HIGH-VALUE TECHNICAL NETWORKING", 92),
    "C": ("USEFUL STARTUP / FOUNDER NETWORKING", 74),
    "D": ("GENERAL TECHNICAL EVENT", 62),
    "E": ("LOW-VALUE / MOSTLY SOCIAL", 32),
    "F": ("INVESTOR / PITCH / NON-HIRING", 30),
    "G": ("IRRELEVANT TO JOB SEARCH", 10),
    # U is deliberately capped just below the recommend threshold: an event we
    # know nothing about must never be presented as a recommendation, but it also
    # must not be confidently dismissed as irrelevant. It lands in the review
    # queue, which is how we bound false negatives instead of pretending to have none.
    "U": ("INSUFFICIENT DATA - REVIEW MANUALLY", 44),
}


# ------------------------------------------------------------------- 1. gates
def gate(ev, now, win_start, win_end):
    """Return a reason string if the event must be excluded, else ''."""
    if not (ev.title or "").strip():
        return "listing has no title"
    if not ev.start:
        return "no parseable start time"
    d = ev.start.date()
    if ev.start < now:
        return "already started/occurred"
    if d < win_start or d > win_end:
        return "outside %s..%s window" % (win_start, win_end)
    if ev.is_online:
        return "virtual event (no in-person networking)"

    # No coordinates published: fall back to the city centroid so the distance
    # gate still applies. Without this a Santa Clara event 45 mi out slipped
    # through purely because it published a city name and no lat/lng.
    if ev.lat is None and ev.city:
        cc = city_coords(ev.city)
        if cc:
            ev.lat, ev.lon = cc
            ev.distance_mi = miles(cc[0], cc[1])
            ev.coords_approx = True

    if ev.distance_mi is not None and ev.distance_mi > config.HARD_MAX_MI:
        return "%.0f mi from downtown SF (limit %.0f)" % (ev.distance_mi, config.HARD_MAX_MI)
    if ev.lat is None and ev.city and ev.city not in _bay_cities():
        return "location not resolvable to the Bay Area (city=%r)" % ev.city
    if ev.lat is None:
        return "no location published - cannot confirm it is in the Bay Area"
    if not ev.registration_open:
        return "registration closed"
    return ""


_BAY = None


def _bay_cities():
    global _BAY
    if _BAY is None:
        _BAY = set(config.SF_PROPER) | {
            "oakland", "berkeley", "emeryville", "alameda", "albany", "el cerrito",
            "richmond", "san leandro", "hayward", "fremont", "union city", "newark",
            "palo alto", "east palo alto", "menlo park", "mountain view", "sunnyvale",
            "santa clara", "san jose", "cupertino", "los altos", "los altos hills",
            "redwood city", "san carlos", "belmont", "san mateo", "foster city",
            "burlingame", "millbrae", "hillsborough", "atherton", "portola valley",
            "stanford", "milpitas", "campbell", "saratoga", "sausalito", "mill valley",
            "tiburon", "san rafael", "larkspur", "corte madera", "walnut creek",
            "pleasanton", "dublin", "livermore", "danville", "san ramon", "concord",
            "brisbane", "colma", "pacifica", "half moon bay", "treasure island",
        }
    return _BAY


# --------------------------------------------------------------- 2. categorize
def categorize(ev, s):
    """Deterministic decision tree -> (category_key, [reasons])."""
    r = []
    hs, hst = s["hiring_strong"], s["hiring_strong_title"]
    inv, invt = s["investor"], s["investor_title"]
    eng = s["audience_eng"]
    depth = s["tech_depth"]
    build, net, talks = s["format_build"], s["format_network"], s["format_talks_only"]
    noise_t, noise_b = s["hard_noise_title"], s["hard_noise_body"]
    biz = s["nontech_biz"]

    # --- G: irrelevant. Noise in the TITLE is decisive; noise only in the body
    #     is not, because a tech event can mention "food truck" in its logistics.
    if noise_t and not (hs or eng or depth):
        r.append("Title matches non-professional activity (%s) with no engineering signal"
                 % ", ".join(noise_t[:3]))
        return "G", r
    if not depth and not eng and not hs and not net:
        # Distinguish "genuinely irrelevant" from "we simply have no text". The
        # second is an information problem, not a verdict.
        if s["desc_len"] < 120:
            r.append("Listing has almost no description (%d chars) - not enough "
                     "information to judge. Not dismissed; needs a manual look."
                     % s["desc_len"])
            return "U", r
        r.append("No engineering, hiring or networking signal found anywhere in the listing")
        return "G", r
    if s["ascii_ratio"] < 0.5:
        r.append("Title is predominantly non-English (ascii ratio %.2f) - likely a "
                 "different-language community" % s["ascii_ratio"])
        return "G", r

    # --- eligibility override: a real hiring event you cannot attend, or whose
    #     stated audience is a different role/seniority, is not a recommendation.
    if s["elig_role_mismatch"]:
        r.append("The listing's own audience definition names non-engineering roles "
                 "(%s) and does not name engineers - you are not the intended attendee"
                 % ", ".join(s["elig_role_mismatch"][:3]))
        if s["elig_seniority"]:
            r.append("It also requires seniority you do not have yet (%s)"
                     % ", ".join(s["elig_seniority"][:2]))
        return "E", r

    # --- A hiring events must be hiring for HIS field. A sports career expo is a
    #     real recruiting event and still worthless to a software engineer.
    if hs and s["industry_mismatch"] and len(depth) < 2 and not eng:
        r.append("Genuine recruiting event, but for a different industry (%s) - no "
                 "engineering roles indicated" % ", ".join(s["industry_mismatch"][:3]))
        return "E", r

    # --- A: explicit hiring. Requires a STRONG phrase, not the soft lexicon.
    if hs:
        # An investor pitch that merely says "we're hiring" is still an investor event.
        if invt and not hst:
            r.append("Pitch/investor framing in the title outweighs hiring mention in body")
        else:
            where = "title" if hst else "description"
            r.append("Explicit hiring/recruiting language in %s: %s" % (where, ", ".join(hs[:3])))
            if eng:
                r.append("Targets engineers directly (%s)" % ", ".join(eng[:2]))
            return "A", r

    # --- F: investor / pitch / non-hiring
    if invt or (len(inv) >= 2 and not hs):
        r.append("Investor/pitch orientation: %s" % ", ".join((invt or inv)[:3]))
        if not eng:
            r.append("No engineer-audience signal - room is likely founders and investors")
        return "F", r

    # --- E: mostly social / non-technical business
    if biz and not depth:
        r.append("Non-technical business framing (%s) with no technical depth"
                 % ", ".join(biz[:3]))
        return "E", r
    if noise_b and not depth and not hs:
        r.append("Social/lifestyle content (%s) and no technical depth"
                 % ", ".join(noise_b[:3]))
        return "E", r

    # --- B: high-value technical networking. Two routes in, because jargon density
    #        measures how verbose an organiser is, not how good the event is.
    #        Requiring 3+ technical terms alone demoted "Demo Night @ WorkOS" - 285
    #        engineers demoing at a company with 5 verified openings - to category D.
    company_backed = [c for c, m in (ev.signals.get("company_roles") or {}).items()
                      if m["role"] in ("venue", "host", "sponsor")]
    depth_route = len(depth) >= 3 and (eng or build) and (net or build)
    structural_route = build and (eng or company_backed) and (net or company_backed)
    if depth_route or structural_route:
        if depth_route:
            r.append("Technical depth (%s) plus an engineer audience and a "
                     "conversation-friendly format" % ", ".join(depth[:4]))
        else:
            r.append("Build/demo format where engineers show their work, backed by %s - "
                     "the room is practitioners regardless of how the listing is written"
                     % (", ".join(c.title() for c in company_backed[:2])
                        if company_backed else "an engineer audience"))
        if company_backed:
            r.append("Hosted at / by: %s" % ", ".join(c.title() for c in company_backed[:3]))
        return "B", r

    # --- C: startup / founder networking that still has technical people
    if s["founder_only"] or ("startup" in ev.text_blob().lower() and not depth):
        r.append("Startup/founder oriented; useful for warm intros but not a hiring channel")
        return "C", r

    # --- D: general technical event (talks, meetups without strong networking)
    if depth or eng:
        bits = []
        if depth:
            bits.append("technical content (%s)" % ", ".join(depth[:3]))
        if talks and not net:
            bits.append("talk/lecture format limits networking")
        r.append("General technical event: " + "; ".join(bits))
        return "D", r

    r.append("Networking format present but no technical or hiring signal")
    return "E", r


# ------------------------------------------------------------------ 3. scoring
def score(ev, s, cat):
    """Additive, fully-explained score. Returns (points, reasons, penalties)."""
    pts, reasons, pens = 0, [], []

    def add(n, why):
        nonlocal pts
        pts += n
        reasons.append("%+d  %s" % (n, why))

    def sub(n, why):
        nonlocal pts
        pts -= n
        pens.append("-%d  %s" % (n, why))

    # --- base by category
    base = {"A": 55, "B": 44, "C": 30, "D": 24, "E": 8, "F": 8, "G": 0,
            "U": 20}[cat]
    add(base, "Base for category %s (%s)" % (cat, CATEGORIES[cat][0]))

    # --- hiring evidence
    if s["hiring_strong_title"]:
        add(14, "Hiring intent stated in the event title: %s"
                % ", ".join(s["hiring_strong_title"][:2]))
    elif s["hiring_strong"]:
        add(8, "Hiring intent stated in the description: %s"
               % ", ".join(s["hiring_strong"][:2]))
    if len(s["hiring_soft"]) >= 3:
        add(4, "Recruiting vocabulary throughout (%s)" % ", ".join(s["hiring_soft"][:3]))

    # --- audience
    if s["audience_eng"]:
        add(8, "Engineer audience named: %s" % ", ".join(s["audience_eng"][:3]))
    if len(s["tech_depth"]) >= 6:
        add(9, "High technical density (%d distinct technical terms: %s)"
               % (len(s["tech_depth"]), ", ".join(s["tech_depth"][:5])))
    elif len(s["tech_depth"]) >= 3:
        add(5, "Moderate technical density (%s)" % ", ".join(s["tech_depth"][:4]))

    # --- format: does the format allow real conversation?
    if s["format_network"]:
        add(7, "Conversation-first format: %s" % ", ".join(s["format_network"][:2]))
    if s["format_build"]:
        add(6, "Build/demo format - natural to show work and be evaluated: %s"
               % ", ".join(s["format_build"][:2]))
    if s["format_talks_only"] and not s["format_network"]:
        sub(6, "Talk/lecture format with no stated mixer - low chance of real conversation")

    # --- company presence. Roles are resolved in jobevents/companies.py; a venue
    #     or sponsor is real evidence of people in the room, a passing mention is not.
    cmap = ev.signals.get("company_roles") or {}
    strong = [(c, m["role"]) for c, m in cmap.items() if m["role"] != "mention"]
    if strong:
        top = sorted(strong, key=lambda x: {"venue": 4, "host": 3, "sponsor": 2,
                                            "speaker": 1}[x[1]], reverse=True)
        add(min(12, 5 + 3 * min(len(strong), 3)),
            "Companies with people likely in the room: %s"
            % ", ".join("%s (%s)" % (c.title(), r) for c, r in top[:3]))
    elif len(cmap) >= 2:
        add(3, "Tech companies mentioned but no stated involvement: %s"
               % ", ".join(list(cmap)[:3]))

    # --- attendance sweet spot. Small enough to talk, big enough to matter.
    n = ev.attendee_count
    if n is not None:
        if 40 <= n <= 400:
            add(7, "Attendance %d is in the sweet spot for real conversations" % n)
        elif 15 <= n < 40:
            add(3, "Attendance %d - small but workable, easier to reach the organiser" % n)
        elif 400 < n <= 900:
            add(2, "Attendance %d - large; good company presence, harder 1:1 access" % n)
        elif n > 900:
            sub(3, "Attendance %d - too crowded for meaningful 1:1 conversation" % n)
        elif n < 5:
            sub(4, "Only %d registered - may be brand new or may not happen" % n)

    # --- access & cost (budget is $0)
    if ev.is_free:
        add(5, "Free to attend")
    elif ev.price is not None and ev.price > 0:
        if ev.price <= 25:
            sub(2, "Ticket $%.0f - low but non-zero cost" % ev.price)
        elif ev.price <= 100:
            sub(8, "Ticket $%.0f - meaningful cost on a $0 budget" % ev.price)
        else:
            sub(16, "Ticket $%.0f - not affordable right now" % ev.price)
    if ev.sold_out:
        sub(18, "Sold out - would need a waitlist spot")
    if ev.requires_approval:
        sub(4, "Host approval required - attendance not guaranteed")

    # Travel and money are handled by jobevents/transit.py, which models
    # door-to-door time and fare from home rather than straight-line distance.
    # Its adjustment is applied in jobevents/enrich.py so the reason strings can
    # name the actual route.

    # --- investor / non-hiring drag
    if s["investor"] and cat not in ("F",):
        sub(5, "Investor/pitch vocabulary present (%s)" % ", ".join(s["investor"][:2]))
    if s["founder_only"] and cat != "C":
        sub(6, "Framed as founder/exec/invite-only - you may not be the intended audience")
    if s["nontech_biz"] and cat in ("B", "D"):
        sub(4, "Non-technical business content mixed in (%s)"
               % ", ".join(s["nontech_biz"][:2]))

    # --- eligibility friction (never silent: the report quotes the restriction)
    if s["elig_identity"]:
        sub(22, "Attendance appears restricted to a specific community/identity group "
                "(%s) - verify you are eligible before going"
                % ", ".join(s["elig_identity"][:3]))
    if s["elig_seniority"] and not s["elig_role_mismatch"]:
        sub(12, "Listing targets a seniority band above new-grad (%s)"
                % ", ".join(s["elig_seniority"][:2]))

    # --- profile fit (personalisation)
    fit = s["profile_fit"]
    if len(fit) >= 3:
        add(6, "Strong overlap with your background: %s" % ", ".join(list(fit)[:3]))
    elif len(fit) >= 1:
        add(3, "Overlaps your background: %s" % ", ".join(list(fit)[:2]))

    # A genuine, in-window recruiting event is the single most valuable format for
    # this user. HackerX-style organisers publish no attendance or price data, so
    # they collect none of the metadata bonuses. Floor category A so sparse
    # metadata cannot push a real hiring event below an ordinary tech meetup.
    if cat == "A" and not (s["elig_identity"] or s["elig_role_mismatch"]) and pts < 70:
        reasons.append("+%d  Floor for a verified recruiting-format event "
                       "(organiser publishes little metadata, format value stands)"
                       % (70 - pts))
        pts = 70

    # --- clamp to category ceiling, then to 0..100
    ceiling = CATEGORIES[cat][1]
    if pts > ceiling:
        pens.append("capped at %d by category %s ceiling" % (ceiling, cat))
        pts = ceiling
    pts = max(0, min(100, pts))
    return int(round(pts)), reasons, pens


def verdict(ev):
    """The answer to "should I go?", shown before the number."""
    if ev.gate:
        return "EXCLUDED"
    if ev.signals.get("elig_identity") or ev.signals.get("elig_role_mismatch"):
        return "CHECK ELIGIBILITY"
    if ev.score >= config.VERDICT_GO:
        return "GO"
    if ev.score >= config.VERDICT_WORTH:
        return "WORTH IT"
    if ev.score >= config.VERDICT_MAYBE:
        return "MAYBE"
    return "SKIP"


# --------------------------------------------------------------- 4. confidence
def confidence(ev, s, cat):
    """HIGH / MEDIUM / LOW + the reason it is not HIGH."""
    problems = []
    if s["desc_len"] < 200:
        problems.append("description is only %d chars - classification rests mostly on the title"
                        % s["desc_len"])
    if ev.lat is None:
        problems.append("no coordinates published; distance not verifiable")
    if not ev.verified:
        problems.append("event page not re-checked at report time")
    if ev.attendee_count is None:
        problems.append("attendance not published")
    elif ev.attendee_count == 0:
        problems.append("nobody has registered yet - the event may be brand new or "
                        "may not happen")
    if cat == "U":
        problems.append("classification is based on a title only")
    if s["elig_identity"] or s["elig_seniority"]:
        problems.append("listing restricts its audience - confirm you are eligible")
    if cat in ("A", "B") and not (s["hiring_strong"] or len(s["tech_depth"]) >= 3):
        problems.append("high category assigned on thin evidence")
    if len(ev.sources) == 1 and s["desc_len"] < 400:
        problems.append("single source, short listing - not corroborated anywhere else")

    if not problems:
        return "HIGH", []
    if len(problems) <= 2 and s["desc_len"] >= 200:
        return "MEDIUM", problems
    return "LOW", problems


# ------------------------------------------------------------------ 5. entry pt
def evaluate(ev, now, win_start, win_end):
    ev.gate = gate(ev, now, win_start, win_end)
    s = features.extract(ev)
    ev.signals = s
    cat, cat_reasons = categorize(ev, s)
    ev.category = cat
    if ev.gate:
        ev.score, ev.confidence = 0, "N/A"
        ev.reasons = cat_reasons
        return ev
    pts, reasons, pens = score(ev, s, cat)
    ev.score = pts
    ev.reasons = cat_reasons + reasons
    ev.penalties = pens
    ev.confidence, why = confidence(ev, s, cat)
    ev.verify_note = "; ".join(why)
    return ev
