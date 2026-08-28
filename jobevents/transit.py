"""Door-to-door travel time, fare, and cost-of-attendance from home.

Why this exists: straight-line distance is a bad proxy for effort in the Bay Area.
From Broad St (Ocean View), downtown SF is 5.5 mi but ~35 min because Balboa Park
BART is an 0.8 mi walk away and the ride is fast. The Marina is a similar distance
and takes far longer because it means crossing town on Muni. Palo Alto is 27 mi and
close to two hours each way. A single distance penalty cannot express that.

This is a deterministic ESTIMATE, not a routing API (those cost money). It models:
  walk to the nearest rail station -> wait -> rail at an average speed that already
  includes station dwell -> walk to the venue, with a Muni fallback when rail does
  not serve either end. Every number below is labelled and tunable in one place.
"""
import math

from . import config

WALK_MPH = 3.0
BART_MPH = 30.0          # includes station dwell time
CALTRAIN_MPH = 35.0
MUNI_MPH = 8.5           # effective door-to-door surface transit speed
BART_WAIT_MIN = 7
CALTRAIN_WAIT_MIN = 14   # off-peak headways are long
MUNI_FIXED_MIN = 10      # walk to stop + wait
MAX_WALK_TO_STATION_MI = 1.15
# A venue further than this from a station still gets a rail route, with a local
# bus leg for the last mile. Without it, a Palo Alto venue 1.3 mi from Caltrain
# fell through to the Muni model and produced a nonsense 194-minute estimate.
MAX_CONNECT_MI = 3.5
CONNECT_BUS_MIN = 16
CONNECT_BUS_FARE = 2.75
# Pure surface transit is only credible inside the city.
MUNI_MAX_MI = 11.0

MUNI_FARE = 2.85         # Clipper single ride, 120-min transfers
BART_BASE, BART_PER_MI = 2.30, 0.20
CALTRAIN_BASE, CALTRAIN_PER_MI = 3.90, 0.09
HOME_TO_CALTRAIN_MIN = 32     # Broad St -> 4th & King via BART/Muni
HOME_TO_CALTRAIN_FARE = 2.85

# Last realistic ride home, in minutes since midnight.
LAST_RAIL_MIN = 24 * 60 + 15      # ~00:15
LAST_MUNI_MIN = 24 * 60 + 30

# (name, lat, lon) - stations relevant to a job search based in SF.
BART = [
    ("Balboa Park", 37.7215, -122.4477), ("Glen Park", 37.7332, -122.4337),
    ("24th St Mission", 37.7522, -122.4183), ("16th St Mission", 37.7650, -122.4197),
    ("Civic Center", 37.7796, -122.4137), ("Powell St", 37.7844, -122.4079),
    ("Montgomery St", 37.7894, -122.4014), ("Embarcadero", 37.7929, -122.3968),
    ("Daly City", 37.7063, -122.4692), ("Colma", 37.6847, -122.4661),
    ("South SF", 37.6640, -122.4440), ("San Bruno", 37.6376, -122.4162),
    ("Millbrae", 37.6000, -122.3866), ("West Oakland", 37.8046, -122.2951),
    ("12th St Oakland", 37.8033, -122.2718), ("19th St Oakland", 37.8087, -122.2686),
    ("MacArthur", 37.8288, -122.2670), ("Ashby", 37.8530, -122.2700),
    ("Downtown Berkeley", 37.8700, -122.2681), ("Fruitvale", 37.7748, -122.2241),
    ("Berryessa", 37.3684, -121.8746), ("Milpitas", 37.4100, -121.8913),
]
CALTRAIN = [
    ("SF 4th & King", 37.7766, -122.3947), ("22nd St", 37.7573, -122.3921),
    ("Millbrae", 37.5997, -122.3869), ("Burlingame", 37.5800, -122.3450),
    ("San Mateo", 37.5680, -122.3240), ("Hillsdale", 37.5378, -122.3000),
    ("Belmont", 37.5210, -122.2760), ("San Carlos", 37.5075, -122.2600),
    ("Redwood City", 37.4860, -122.2320), ("Menlo Park", 37.4545, -122.1820),
    ("Palo Alto", 37.4433, -122.1650), ("Mountain View", 37.3945, -122.0760),
    ("Sunnyvale", 37.3785, -122.0310), ("Santa Clara", 37.3530, -121.9360),
    ("San Jose Diridon", 37.3297, -121.9027),
]


def _mi(a_lat, a_lon, b_lat, b_lon):
    r = 3958.8
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _nearest(stations, lat, lon):
    best, bd = None, 1e9
    for name, sl, so in stations:
        d = _mi(lat, lon, sl, so)
        if d < bd:
            best, bd = (name, sl, so), d
    return best, bd


def _walk_min(mi):
    return mi / WALK_MPH * 60.0


def plan(lat, lon):
    """Return a one-way plan dict, or None if coordinates are unknown."""
    if lat is None or lon is None:
        return None
    hl, ho = config.HOME_LAT, config.HOME_LON

    (h_bart, hb_lat, hb_lon), h_bd = _nearest(BART, hl, ho)
    (d_bart, db_lat, db_lon), d_bd = _nearest(BART, lat, lon)
    (d_ct, ct_lat, ct_lon), d_ctd = _nearest(CALTRAIN, lat, lon)

    options = []

    def last_leg(dist_mi):
        """(minutes, fare, description) to cover the gap from station to venue."""
        if dist_mi <= MAX_WALK_TO_STATION_MI:
            return _walk_min(dist_mi), 0.0, "walk %.1f mi" % dist_mi
        return CONNECT_BUS_MIN, CONNECT_BUS_FARE, "local bus %.1f mi" % dist_mi

    # --- BART both ends (a bus finishes the trip if the venue is not walkable)
    if h_bd <= MAX_WALK_TO_STATION_MI and d_bd <= MAX_CONNECT_MI:
        rail = _mi(hb_lat, hb_lon, db_lat, db_lon)
        leg_min, leg_fare, leg_txt = last_leg(d_bd)
        mins = _walk_min(h_bd) + BART_WAIT_MIN + rail / BART_MPH * 60 + leg_min
        fare = max(BART_BASE, BART_BASE + BART_PER_MI * rail) + leg_fare
        options.append({
            "mode": "BART", "minutes": mins, "fare": fare,
            "detail": "walk %.1f mi to %s, BART to %s, %s"
                      % (h_bd, h_bart, d_bart, leg_txt),
            "last_ride_min": LAST_RAIL_MIN,
        })

    # --- Caltrain for the Peninsula (BART/Muni to 4th & King, then Caltrain)
    if d_ctd <= MAX_CONNECT_MI and d_ct != "SF 4th & King":
        rail = _mi(37.7766, -122.3947, ct_lat, ct_lon)
        if rail > 3:
            leg_min, leg_fare, leg_txt = last_leg(d_ctd)
            mins = (HOME_TO_CALTRAIN_MIN + CALTRAIN_WAIT_MIN
                    + rail / CALTRAIN_MPH * 60 + leg_min)
            fare = (HOME_TO_CALTRAIN_FARE + CALTRAIN_BASE
                    + CALTRAIN_PER_MI * rail + leg_fare)
            options.append({
                "mode": "BART+Caltrain", "minutes": mins, "fare": fare,
                "detail": "transit to 4th & King, Caltrain to %s, %s" % (d_ct, leg_txt),
                "last_ride_min": 23 * 60 + 45,
            })

    # --- Muni / surface transit, credible only within the city
    direct = _mi(hl, ho, lat, lon)
    if direct <= MUNI_MAX_MI:
        options.append({
            "mode": "Muni", "minutes": direct / MUNI_MPH * 60 + MUNI_FIXED_MIN,
            "fare": MUNI_FARE,
            "detail": "surface transit, ~%.1f mi across town" % direct,
            "last_ride_min": LAST_MUNI_MIN,
        })

    if not options:
        # Reachable by rail + a long connection, or genuinely awkward. Say so
        # rather than inventing a number.
        return {"mode": "hard to reach by transit",
                "minutes": int(direct / 12.0 * 60 + 40), "fare": 9.0,
                "detail": "%.1f mi with no station within %.1f mi of the venue - "
                          "check the route yourself" % (direct, MAX_CONNECT_MI),
                "last_ride_min": LAST_RAIL_MIN, "straight_line_mi": round(direct, 1),
                "uncertain": True}

    best = min(options, key=lambda o: o["minutes"])
    best["minutes"] = int(round(best["minutes"]))
    best["fare"] = round(best["fare"], 2)
    best["straight_line_mi"] = round(direct, 1)
    return best


def cost_of_attendance(ev):
    """Attach travel + money + time cost to an event. Returns a dict."""
    p = plan(ev.lat, ev.lon)
    ticket = 0.0 if ev.is_free else float(ev.price or 0.0)

    if not p:
        return {"known": False, "ticket": ticket,
                "note": "venue coordinates not published - travel cost unknown"}

    one_way = p["minutes"]
    round_trip = one_way * 2
    fares = p["fare"] * 2

    # Event duration, defaulting to a typical 2h evening meetup.
    dur = 120
    if ev.start and ev.end:
        d = (ev.end - ev.start).total_seconds() / 60.0
        if 15 <= d <= 12 * 60:
            dur = int(d)

    total_min = round_trip + dur
    total_cash = ticket + fares

    # Can he actually get home? Uses event end (or start + duration).
    late = ""
    end = ev.end or (ev.start + __import__("datetime").timedelta(minutes=dur)
                     if ev.start else None)
    if end:
        arrive = end.hour * 60 + end.minute + one_way
        if arrive > p["last_ride_min"]:
            late = ("ends too late to get home by %s - last ride is around %02d:%02d"
                    % (p["mode"], p["last_ride_min"] // 60 % 24, p["last_ride_min"] % 60))
        elif arrive > p["last_ride_min"] - 45:
            late = "tight connection home; check the last %s departure" % p["mode"]

    return {
        "known": True, "mode": p["mode"], "detail": p["detail"],
        "one_way_min": one_way, "round_trip_min": int(round_trip),
        "fare_round_trip": round(fares, 2), "ticket": round(ticket, 2),
        "total_cash": round(total_cash, 2), "event_minutes": dur,
        "total_minutes": int(total_min), "late_warning": late,
        "straight_line_mi": p["straight_line_mi"],
    }


def cost_penalty(cost, score_before):
    """Opportunity/cost adjustment. Returns (delta_points, [reason strings]).

    Deliberately expressed as points rather than a ratio so it stays comparable
    with every other term in the score, and so the reason can be printed.
    """
    if not cost.get("known"):
        return 0, []
    out, delta = [], 0
    rt = cost["round_trip_min"]
    cash = cost["total_cash"]

    # --- time
    if rt <= 50:
        delta += 4
        out.append("+4  %d min round trip by %s - cheap to attend, easy to leave early"
                   % (rt, cost["mode"]))
    elif rt <= 90:
        out.append("+0  %d min round trip by %s - normal for SF" % (rt, cost["mode"]))
    elif rt <= 140:
        delta -= 6
        out.append("-6  %d min round trip by %s - most of the evening is travel"
                   % (rt, cost["mode"]))
    else:
        delta -= 13
        out.append("-13  %d min round trip by %s - a whole evening for one event"
                   % (rt, cost["mode"]))

    # --- money, weighted heavily because the budget is $0
    if cash <= 6:
        delta += 3
        out.append("+3  $%.2f total (transit only, free entry)" % cash)
    elif cash <= 15:
        out.append("+0  $%.2f total" % cash)
    elif cash <= 40:
        delta -= 8
        out.append("-8  $%.2f total - real money on a $0 budget" % cash)
    else:
        delta -= 18
        out.append("-18  $%.2f total - hard to justify without a confirmed payoff" % cash)

    if cost.get("late_warning"):
        delta -= 5
        out.append("-5  %s" % cost["late_warning"])

    return delta, out
