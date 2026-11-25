"""
Live Odds Total Monitor v4.6 — expanded coverage + Q1 / halftime checkpoints
+ consensus-gated alerts (only alert when the move goes against the
pregame sharp consensus)

Football + Basketball (NFL, NCAAF, CFL, NBA, NCAAB, WNCAAB, WNBA,
EuroLeague, NBL Australia):
  Game total: alert when live moves NEAR 20 pts vs pregame
  Team total: alert when live moves NEAR 15 pts vs pregame

Hockey (NHL, AHL, Liiga, SHL, HockeyAllsvenskan):
  Game total: alert when live moves NEAR 3 goals vs pregame
  Team total: alert when live moves NEAR 3 goals vs pregame

"Nearly" is defined below so it actually triggers:
  Big sports:  game >= 18.0 (within 2 of 20), team >= 13.0 (within 2 of 15)
  Hockey:      game >= 2.5 (within 0.5 of 3), team >= 2.5 (within 0.5 of 3)
You get a NEAR alert first, then a second HIT alert if it reaches the
full 20 / 15 / 3. Change the *_NEAR values to make it stricter/looser.

Q1 / HALFTIME CHECKPOINTS (basketball only, v4):
  In addition to the NEAR/HIT alerts, the script emails you the live
  lines once at the end of the 1st quarter and once at halftime, per game:
    Pregame full-game total + team totals (already snapshotted)
    Live full-game total + team totals at the checkpoint
  The Odds API gives no game clock, so checkpoints are timed by elapsed
  real time since tipoff, caught on the next 20-minute poll:
    Quarter leagues (NBA, WNBA, WNCAAB, EuroLeague, NBL):
      Q1 end: 25-55 min after tipoff; Halftime: 55-95 min after tipoff
    Halves league (NCAAB Men — no quarters):
      Halftime only: 40-75 min after tipoff
  Each checkpoint is emailed once per game and saved in state.json under
  "checkpoints". The 20-minute polling stays on — it is how the script
  notices that a checkpoint window has been reached.

v4.1: the pregame Q1/H1 period totals (totals_q1, totals_h1, etc.) were
dropped — at 5 credits per game, once, they burned credits far too fast
on big slates (NCAAB alone is 30-50 games a night). The checkpoints
stay: they cost $0 extra, reusing the live totals already fetched.
Pregame team totals are back to 1 credit per event, once.

v4.3: the test-email run failed with UnicodeEncodeError: the
EMAIL_PASSWORD secret contained a non-breaking space (\\xa0), copied
in with the App Password from Google's display. The script now strips
all spaces / non-breaking spaces from the password (and trims the
sender/receiver). A failed email also no longer kills the whole run —
it is logged and the run carries on so state.json still updates.

v4.4 CREDIT SAVING: polling is every 30 minutes (was 20) and the script
only runs during game hours, 11:00–01:30 EST (16:00–06:30 UTC). Outside
those hours it exits immediately, $0 cost. That cuts the burn from
~1,000 credits/day to ~500/day, so 20,000 credits last ~38 days instead
of ~20. The alert checks themselves cost $0 extra — see below.
TEST_EMAIL bypasses the game-hours gate so you can test anytime.

v4.6 CONSENSUS-GATED ALERTS: a NEAR/HIT alert is now emailed only when
the live total move goes AGAINST the pregame sharp consensus — total
moved UP and the consensus is UNDER, or total moved DOWN and the
consensus is OVER — per element (game total and each team total).
Thresholds: big: game 18/20, team 13/15; hockey 2.5/3 (raised from
1.5/2 on 2026-11-25 at the user's request).
The consensus lives in the pregame analyses (models, AI projections,
money/bet splits, expert leans), not in The Odds API, so the pregame
analysis job publishes it as verdicts.json in the repo root and this
script reads it at run start. "Strong consensus" = at least 3 of the
4 signals agree on a direction, with none pointing the opposite way.
FAIL-OPEN: if verdicts.json is missing/corrupt, or a game has no
verdict, or the verdict is mixed/not strong, the alert goes out exactly
as before. A move that agrees with consensus is NOT emailed, but its
key is recorded in state.json under "suppressed" (NOT "alerted"), so
the matchup-analysis job — which reads "alerted" — skips it and you
get no email about a no-value move. Checkpoints (Q1/halftime) are
unchanged: they are routine lines, not alerts. Reading verdicts.json
costs $0 in Odds API credits (it is a local file, not an API call).
Hockey has no pregame verdicts published, so hockey alerts always
fail open and behave exactly as before.

WHY v3: The Odds API's sport-level /odds endpoint only supports
featured markets (h2h, spreads, totals). Asking it for team_totals
returns 422 INVALID_MARKET for every league and no data at all.
team_totals is an "additional market" that must be fetched one event
at a time via /sports/{sport}/events/{eventId}/odds — so v3 fetches
game totals at sport level, and team totals per event (see below).

COVERAGE LIMITS — checked against The Odds API's official sports list
(https://the-odds-api.com/sports-odds-data/sports-apis.html):
  * Overseas basketball on this API is ONLY EuroLeague + NBL Australia.
    There is NO key for Spain ACB, Italy Serie A, Germany BBL, Turkey BSL,
    China CBA, EuroCup, or a women's EuroLeague. WNCAAB/WNBA are the only
    women's basketball keys. If you need ACB etc., you need a different
    provider — The Odds API simply doesn't list them.
  * Other hockey on this API is ONLY Liiga (Finland), SHL + Allsvenskan
    (Sweden). There is NO DEL, Swiss NL, Czech Extraliga, or KHL key.
  * team_totals is an "additional market" per The Odds API docs, mainly
    for US sports / selected bookmakers. It often does NOT come back
    for hockey or overseas leagues, even per event. The script uses it
    when present, logs when it's missing, and does not crash.
    Game totals (featured market) work for all leagues below.

COST — 1 credit per region per market per sport/event per run.
  Game totals: markets=totals, regions=eu = 1 credit/sport/run.
  Team totals: 1 credit per event fetched, regions=eu, markets=team_totals.
    Pregame team totals are fetched ONCE per event (cached in state.json),
    so upcoming games cost ~1 credit each, once. Live games cost
    1 credit per live event per run, only while they are live.
  THE ALERT CHECKS COST $0 EXTRA: a NEAR/HIT check (game total near
    20 pts, team total near 15 pts, hockey game/team near 2 goals,
    up or down) is just a comparison of the totals already fetched
    in that run — no extra API call is made for it. The ~500 credits/day
    below IS the cost of checking those moves, every 30 minutes.
  Period totals (v4, dropped in v4.1): pregame Q1/H1 totals cost
    5 credits per basketball event, once — too fast on big slates.
    Checkpoints themselves cost $0 extra — they reuse the live totals
    already fetched that run.
  v4.4 burn (30-min polls, game hours 11:00–01:30 EST only):
    game totals ~11 leagues x ~29 runs/day = ~320/day;
    pregame team totals ~50/day; live team totals ~150/day;
    total ~500/day, so 20,000 credits last ~38 days.
  The script first calls /v4/sports (FREE) and only polls leagues that are
  currently active/in-season, so offseason leagues cost nothing.
  Still, running this 24/7 will burn through paid tiers fast. See README.
"""
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
import json
import os
import smtplib
import requests

API_KEY = os.environ["ODDS_API_KEY"]
# Gmail App Passwords are shown by Google in groups of 4 with spaces,
# and copying them can also bring in a non-breaking space (\xa0).
# Either one crashes smtp.login with UnicodeEncodeError, so strip them.
# (The stored secret can stay as-is; this cleans it at runtime.)
EMAIL_SENDER = os.environ["EMAIL_SENDER"].replace("\xa0", "").strip()
EMAIL_PASSWORD = "".join(os.environ["EMAIL_PASSWORD"].split())
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"].replace("\xa0", "").strip()

BOOKMAKER = "pinnacle"  # sharpest benchmark; fallback to first available
REGIONS = "eu"  # Pinnacle is EU. Use "us,eu" only if team totals are missing for US leagues — doubles cost.
MARKETS = "totals"  # sport-level endpoint: featured markets ONLY (h2h, spreads, totals)
TEAM_MARKETS = "team_totals"  # additional market: per-event endpoint ONLY, see fetch_team_totals()
# Game hours (v4.4 credit saving): only poll 11:00–01:30 EST,
# i.e. 16:00–06:30 UTC. Outside that, run() exits immediately ($0).
# TEST_EMAIL bypasses the gate so you can test anytime.
GAME_HOURS_START_MIN = 16 * 60       # 16:00 UTC = 11:00 EST
GAME_HOURS_END_MIN = 6 * 60 + 30     # 06:30 UTC = 01:30 EST (next day)
# Checkpoint windows, minutes of real time since tipoff (no game clock in the API).
# Quarters: Q1 ~25-55 min, halftime ~55-95 min. Halves (NCAAB Men): halftime ~40-75 min.
CHECKPOINTS_QUARTERS = {"q1": (25, 55), "h1": (55, 95)}
CHECKPOINTS_HALVES = {"h1": (40, 75)}
STATE_FILE = "state.json"
VERDICTS_FILE = "verdicts.json"  # v4.6: pregame sharp-consensus verdicts, published by the pregame analysis job (repo root, read at run start; missing/corrupt = fail open)
# The four consensus signals recorded per element in verdicts.json.
SIGNALS = ("models", "ai", "money", "experts")

# --- thresholds: (near, target) ---
BIG = {"game_near": 18.0, "game_target": 20.0, "team_near": 13.0, "team_target": 15.0}
HOCKEY = {"game_near": 2.5, "game_target": 3.0, "team_near": 2.5, "team_target": 3.0}

# group "big" = football/basketball, "hockey" = hockey
LEAGUES = [
    # --- American football ---
    {"key": "americanfootball_nfl", "label": "NFL", "group": "big"},
    {"key": "americanfootball_ncaaf", "label": "NCAAF", "group": "big"},
    {"key": "americanfootball_ncaaf_fcs", "label": "NCAAF FCS", "group": "big"},
    {"key": "americanfootball_cfl", "label": "CFL", "group": "big"},
    # --- Basketball: US + overseas (all The Odds API actually offers) ---
    # "periods": quarters = Q1 + halftime checkpoints; halves = halftime only
    {"key": "basketball_nba", "label": "NBA", "group": "big", "periods": "quarters"},
    {"key": "basketball_ncaab", "label": "NCAAB Men", "group": "big", "periods": "halves"},
    {"key": "basketball_wncaab", "label": "WNCAAB Women", "group": "big", "periods": "quarters"},
    {"key": "basketball_wnba", "label": "WNBA", "group": "big", "periods": "quarters"},
    {"key": "basketball_euroleague", "label": "EuroLeague", "group": "big", "periods": "quarters"},
    {"key": "basketball_nbl", "label": "NBL Australia", "group": "big", "periods": "quarters"},
    # --- Hockey ---
    {"key": "icehockey_nhl", "label": "NHL", "group": "hockey"},
    {"key": "icehockey_ahl", "label": "AHL", "group": "hockey"},
    {"key": "icehockey_liiga", "label": "Liiga Finland", "group": "hockey"},
    {"key": "icehockey_sweden_hockey_league", "label": "SHL Sweden", "group": "hockey"},
    {"key": "icehockey_sweden_allsvenskan", "label": "HockeyAllsvenskan Sweden", "group": "hockey"},
    # Add if you want it (Finnish 2nd tier, thin coverage):
    # {"key": "icehockey_mestis", "label": "Mestis Finland", "group": "hockey"},
]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            state.setdefault("pregame", {})
            state.setdefault("alerted", [])
            state.setdefault("checkpoints", {})
            state.setdefault("suppressed", [])
            return state
    return {"pregame": {}, "alerted": [], "checkpoints": {}, "suppressed": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_verdicts():
    """Load verdicts.json (v4.6): pregame sharp-consensus verdicts,
    published by the pregame analysis job. Returns {event_id: verdict}.
    Missing file, unreadable JSON, or wrong shape -> {} (fail open:
    alerts send exactly as before). Never raises."""
    try:
        with open(VERDICTS_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("verdicts.json not found — consensus gate off (fail open).")
        return {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"verdicts.json unreadable ({e}) — consensus gate off (fail open).")
        return {}
    if not isinstance(data, dict):
        print("verdicts.json is not an object — consensus gate off (fail open).")
        return {}
    verdicts = data.get("verdicts", {})
    if not isinstance(verdicts, dict):
        print("verdicts.json: 'verdicts' is not an object — consensus gate off (fail open).")
        return {}
    print(f"Loaded {len(verdicts)} verdict(s) from verdicts.json.")
    return verdicts


def strong_consensus(element_verdict):
    """Return 'under' or 'over' when an element verdict is a strong
    consensus, else None (mixed / missing / not strong -> fail open).
    Strong = at least 3 of the 4 signals agree on a direction, with
    none of the signals pointing the opposite way. Signals that are
    'mixed', 'not found', or missing do not count either way. If no
    signals are recorded, fall back to the published direction/strong
    fields; anything else is not strong."""
    if not isinstance(element_verdict, dict):
        return None
    signals = element_verdict.get("signals") or {}
    if isinstance(signals, dict) and signals:
        under = sum(1 for s in SIGNALS if signals.get(s) == "under")
        over = sum(1 for s in SIGNALS if signals.get(s) == "over")
        if under >= 3 and over == 0:
            return "under"
        if over >= 3 and under == 0:
            return "over"
        return None
    # No signals recorded: trust the publisher's direction/strong fields.
    if element_verdict.get("strong") and element_verdict.get("direction") in ("under", "over"):
        return element_verdict["direction"]
    return None


def send_email(subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.send_message(msg)


def get_active_sports():
    """Free endpoint — returns only in-season sport keys, so we don't
    pay credits polling offseason leagues."""
    try:
        resp = requests.get(
            "https://api.the-odds-api.com/v4/sports/",
            params={"apiKey": API_KEY},
            timeout=15,
        )
        if resp.status_code == 200:
            return {s["key"] for s in resp.json() if s.get("active")}
    except Exception as e:
        print(f"Could not fetch active sports list ({e}); polling all leagues.")
    return None  # None = unknown, poll everything


def extract_lines(event):
    """Returns (game_total, team_totals, period_totals).
    period_totals: {"totals_q1": float|None, "totals_h1": float|None,
                    "team_totals_q1": {team: float}, "team_totals_h1": {team: float}}"""
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return None, {}, {"totals_q1": None, "totals_h1": None,
                          "team_totals_q1": {}, "team_totals_h1": {}}
    book = next((b for b in bookmakers if b["key"] == BOOKMAKER), bookmakers[0])
    game_total = None
    team_totals = {}
    period = {"totals_q1": None, "totals_h1": None,
              "team_totals_q1": {}, "team_totals_h1": {}}
    for market in book.get("markets", []):
        key = market.get("key")
        outcomes = market.get("outcomes", [])
        if key == "totals":
            for outcome in outcomes:
                if outcome["name"] == "Over":
                    game_total = float(outcome["point"])
        elif key == "team_totals":
            for outcome in outcomes:
                if outcome["name"] == "Over":
                    team_name = outcome.get("description")
                    if team_name:
                        team_totals[team_name] = float(outcome["point"])
        elif key in ("totals_q1", "totals_h1"):
            for outcome in outcomes:
                if outcome["name"] == "Over":
                    period[key] = float(outcome["point"])
        elif key in ("team_totals_q1", "team_totals_h1"):
            for outcome in outcomes:
                if outcome["name"] == "Over":
                    team_name = outcome.get("description")
                    if team_name:
                        period[key][team_name] = float(outcome["point"])
    return game_total, team_totals, period


def fetch_team_totals(sport, event_id, failed_sports):
    """Fetch team_totals for ONE event via the per-event endpoint.

    The sport-level /odds endpoint rejects team_totals with 422, so this
    is the only way to get them. Costs 1 credit per call (1 region x
    1 market). Returns {} on any failure — the caller keeps game totals.
    failed_sports is a set used to log a sport's failure only once per run.
    """
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": TEAM_MARKETS,
        "oddsFormat": "american",
        "bookmakers": BOOKMAKER,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
    except Exception as e:
        if sport not in failed_sports:
            print(f"  team_totals request failed for {sport} ({e})")
            failed_sports.add(sport)
        return {}
    if resp.status_code != 200:
        if sport not in failed_sports:
            print(f"  team_totals not available for {sport}: "
                  f"{resp.status_code} {resp.text[:200]}")
            failed_sports.add(sport)
        return {}
    _, team_totals, _ = extract_lines(resp.json())
    return team_totals


def checkpoint_name(periods, elapsed_min):
    """Which checkpoint window are we in, if any? 'q1' / 'h1' / None.
    The API has no game clock, so this is elapsed real time since tipoff.
    """
    windows = CHECKPOINTS_QUARTERS if periods == "quarters" else (
        CHECKPOINTS_HALVES if periods == "halves" else {})
    for name, (lo, hi) in windows.items():
        if lo <= elapsed_min < hi:
            return name
    return None


def format_checkpoint(label, matchup, cp, pre, game_total, team_totals):
    """One checkpoint email block: live lines at Q1 end / halftime,
    vs the pregame full-game / team totals."""
    title = "End of 1st Quarter" if cp == "q1" else "Halftime"
    lines = [f"[{label}] {matchup}\n{title}"]
    pre_game = pre.get("game_total")
    if pre_game is not None and game_total is not None:
        lines.append(f"Game total: Pregame {pre_game} -> {title} {game_total} "
                     f"({game_total - pre_game:+.1f} pts)")
    elif game_total is not None:
        lines.append(f"Game total at {title}: {game_total}")
    for team, live_tt in (team_totals or {}).items():
        pre_tt = (pre.get("team_totals", {}) or {}).get(team)
        if pre_tt is not None:
            lines.append(f"Team total {team}: Pregame {pre_tt} -> {title} {live_tt} "
                         f"({live_tt - pre_tt:+.1f} pts)")
        else:
            lines.append(f"Team total {team} at {title}: {live_tt}")
    return "\n".join(lines)


def check_move(event_id, label, matchup, kind, pre_val, live_val, thresholds, state, alerts, team=None, verdicts=None):
    """kind = 'game_total' or 'team_total'. Alerts once at NEAR, once at HIT.
    If it jumps straight to HIT, send only HIT (and mark NEAR as seen).

    v4.6 consensus gate: an alert is emailed only when the move goes
    AGAINST the pregame sharp consensus for that element (UP + consensus
    UNDER, or DOWN + consensus OVER). If the move agrees with consensus,
    no email is sent; the key is recorded in state["suppressed"] (NOT
    state["alerted"]) so the matchup-analysis job skips it. No verdict,
    a mixed/not-strong verdict, or a missing verdicts.json -> fail open:
    the alert sends exactly as before."""
    if pre_val is None or live_val is None:
        return
    diff = live_val - pre_val
    adiff = abs(diff)
    near = thresholds["game_near" if kind == "game_total" else "team_near"]
    target = thresholds["game_target" if kind == "game_total" else "team_target"]
    unit = "pts" if thresholds is BIG else "goals"
    what = "GAME TOTAL" if kind == "game_total" else f"TEAM TOTAL ({team})"
    suffix = f"_{team}" if kind == "team_total" and team else ""
    if adiff >= target:
        level, key = "HIT", f"{event_id}_{kind}{suffix}_hit"
        near_key = f"{event_id}_{kind}{suffix}_near"
    elif adiff >= near:
        level, key = "NEAR", f"{event_id}_{kind}{suffix}_near"
        near_key = None
    else:
        return
    if key in state["alerted"] or key in state.get("suppressed", []):
        return
    direction = "UP" if diff > 0 else "DOWN"
    # Consensus gate (v4.6). Element keys in verdicts.json: "game_total"
    # or "team_total:<exact team name as in state.json team_totals>".
    # Any malformed verdict entry is treated as "no verdict" (fail open).
    element_key = kind if kind == "game_total" else f"team_total:{team}"
    event_verdict = (verdicts or {}).get(event_id)
    elements = event_verdict.get("elements", {}) if isinstance(event_verdict, dict) else {}
    element_verdict = elements.get(element_key) if isinstance(elements, dict) else None
    consensus = strong_consensus(element_verdict)
    if consensus is not None:
        against = ((direction == "UP" and consensus == "under")
                   or (direction == "DOWN" and consensus == "over"))
        if not against:
            # Move agrees with consensus: no value in alerting.
            state.setdefault("suppressed", [])
            if key not in state["suppressed"]:
                state["suppressed"].append(key)
            if near_key and near_key not in state["suppressed"]:
                state["suppressed"].append(near_key)
            print(f"  SUPPRESSED (consensus {consensus}): [{label}] {matchup} "
                  f"{what} {level} {direction} {adiff:.1f} {unit}")
            return
    alerts.append(
        f"[{label}] {matchup}\n"
        f"{what} {level} {target:g} — {direction} {adiff:.1f} {unit} | "
        f"Pregame: {pre_val} -> Live: {live_val}"
    )
    state["alerted"].append(key)
    if near_key:
        state["alerted"].append(near_key)
        # A NEAR that was suppressed earlier is subsumed by this HIT email.
        if near_key in state.get("suppressed", []):
            state["suppressed"].remove(near_key)


def in_game_hours(now):
    """True between 16:00 and 06:30 UTC (11:00–01:30 EST). Wraps midnight."""
    m = now.hour * 60 + now.minute
    if GAME_HOURS_START_MIN <= GAME_HOURS_END_MIN:
        return GAME_HOURS_START_MIN <= m < GAME_HOURS_END_MIN
    return m >= GAME_HOURS_START_MIN or m < GAME_HOURS_END_MIN


def feed_test():
    """One-off WNCAAB coverage test (v4.5). Set FEED_TEST=1 via the
    workflow's feed_test dispatch input. Queries basketball_wncaab totals
    with several bookmaker/region combos and emails the event counts.
    ~5-7 credits total, then exits: no normal polling, no state write.
    Answers: does Pinnacle/EU list WNCAAB at all, and which bookmaker/
    region does (US books price WNCAAB totals — The Odds API's own
    WNCAAB docs page queries regions=us and shows FanDuel)."""
    sport = "basketball_wncaab"
    combos = [
        ("current config: pinnacle / eu",
         {"bookmakers": "pinnacle", "regions": "eu"}),
        ("all bookmakers / us (no bookmaker filter)",
         {"regions": "us"}),
        ("all bookmakers / eu (no bookmaker filter)",
         {"regions": "eu"}),
        ("fanduel / us", {"bookmakers": "fanduel", "regions": "us"}),
        ("draftkings / us", {"bookmakers": "draftkings", "regions": "us"}),
    ]
    lines = ["WNCAAB feed test — basketball_wncaab, markets=totals\n"]
    first_us_event = None
    for name, extra in combos:
        params = {"apiKey": API_KEY, "regions": extra["regions"],
                  "markets": "totals", "oddsFormat": "american"}
        if "bookmakers" in extra:
            params["bookmakers"] = extra["bookmakers"]
        try:
            resp = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport}/odds/",
                params=params, timeout=15)
        except Exception as e:
            lines.append(f"{name}: request failed ({e})")
            print(lines[-1])
            continue
        if resp.status_code != 200:
            lines.append(f"{name}: HTTP {resp.status_code} {resp.text[:150]}")
            print(lines[-1])
            continue
        events = resp.json()
        books = sorted({b["key"] for ev in events
                        for b in ev.get("bookmakers", [])})
        with_totals = sum(
            1 for ev in events
            if any(m.get("key") == "totals"
                   for b in ev.get("bookmakers", [])
                   for m in b.get("markets", [])))
        sample = "; ".join(
            f"{ev['away_team']} @ {ev['home_team']}" for ev in events[:3])
        lines.append(
            f"{name}: {len(events)} events, {with_totals} with a totals "
            f"market; bookmakers seen: {', '.join(books) or 'none'}")
        if sample:
            lines.append(f"  e.g. {sample}")
        print(lines[-1])
        if first_us_event is None and extra["regions"] == "us" and events:
            first_us_event = events[0]["id"]
    # team_totals on one event, if any US event was found
    if first_us_event:
        for name, extra in [
                ("team_totals pinnacle / eu",
                 {"bookmakers": "pinnacle", "regions": "eu"}),
                ("team_totals fanduel / us",
                 {"bookmakers": "fanduel", "regions": "us"})]:
            params = {"apiKey": API_KEY, "regions": extra["regions"],
                      "markets": TEAM_MARKETS, "oddsFormat": "american",
                      "bookmakers": extra["bookmakers"]}
            try:
                resp = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport}/"
                    f"events/{first_us_event}/odds/",
                    params=params, timeout=15)
            except Exception as e:
                lines.append(f"{name}: request failed ({e})")
                print(lines[-1])
                continue
            if resp.status_code != 200:
                lines.append(f"{name}: HTTP {resp.status_code} "
                             f"{resp.text[:150]}")
                print(lines[-1])
                continue
            _, team_totals, _ = extract_lines(resp.json())
            lines.append(f"{name}: team_totals = {team_totals or 'none returned'}")
            print(lines[-1])
    else:
        lines.append("No US event found, so no team_totals test was possible.")
    lines.append("\nCost: ~5-7 credits for this one-off test.")
    lines.append("Reading the result: if 'pinnacle / eu' shows 0 events but "
                 "'all bookmakers / us' shows games, switch WNCAAB to a US "
                 "bookmaker (fanduel/draftkings) — note regions=us doubles "
                 "the per-run credit cost for that sport. If every combo "
                 "shows 0, WNCAAB lines post later in the day and the "
                 "morning freeze (game hours start 11:00 EST) is the cause.")
    try:
        send_email("WNCAAB Feed Test — which bookmaker lists WNCAAB totals",
                   "\n".join(lines))
        print("Sent feed test email.")
    except Exception as e:
        print(f"FEED TEST EMAIL FAILED: {type(e).__name__}: {e}")


def run():
    state = load_state()
    verdicts = load_verdicts()  # v4.6: {} when missing/corrupt -> fail open
    now = datetime.now(timezone.utc)
    alerts = []
    checkpoint_lines = []

    if os.environ.get("FEED_TEST") in ("1", "true", "True"):
        # One-off coverage test; bypasses the game-hours gate, then exits.
        feed_test()
        return

    if not in_game_hours(now) and os.environ.get("TEST_EMAIL") not in ("1", "true", "True"):
        print(f"Outside game hours (11:00-01:30 EST), skipping — $0 cost. "
              f"Now: {now.strftime('%H:%M UTC')}")
        return

    if os.environ.get("TEST_EMAIL") in ("1", "true", "True"):
        # Test mode: prove the email path works, even with no alerts.
        # Sent first, so a bad SMTP login shows up in the log right away.
        n_pregame = len(state.get("pregame", {}))
        sample = sorted(state.get("pregame", {}).values(),
                        key=lambda v: v.get("commence_time", ""))[:5]
        sample_lines = "\n".join(
            f"- {v.get('label')}: {v.get('matchup')} "
            f"(total {v.get('game_total')}, starts {v.get('commence_time')})"
            for v in sample) or "- (no games snapshotted yet)"
        try:
            send_email(
                "Live Odds Monitor — Test Email",
                "This is a test email from your Live Odds Total Monitor.\n"
                "If you can read this, the Gmail login and the receiver address work.\n\n"
                f"Games currently snapshotted in state.json: {n_pregame}\n"
                f"Alerts sent so far: {len(state.get('alerted', []))}\n"
                f"Alerts suppressed by consensus gate: {len(state.get('suppressed', []))}\n"
                f"Checkpoints recorded: {sum(len(v) for v in state.get('checkpoints', {}).values())}\n\n"
                "Next few games:\n" + sample_lines + "\n\n"
                "Normal emails only fire when a total moves NEAR/HIT or a Q1/halftime\n"
                "checkpoint is hit — a quiet day means no email, which is normal."
            )
            print("Sent test email.")
        except Exception as e:
            print(f"TEST EMAIL FAILED (run continues): {type(e).__name__}: {e}")

    active = get_active_sports()
    leagues = LEAGUES
    if active is not None:
        skipped = [l["label"] for l in LEAGUES if l["key"] not in active]
        leagues = [l for l in LEAGUES if l["key"] in active]
        print(f"Active leagues: {[l['label'] for l in leagues]}")
        if skipped:
            print(f"Skipped (offseason, $0 cost): {skipped}")

    failed_sports = set()  # sports whose team_totals failed, logged once per run
    for league in leagues:
        sport = league["key"]
        label = league["label"]
        thresholds = BIG if league["group"] == "big" else HOCKEY
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            "apiKey": API_KEY,
            "regions": REGIONS,
            "markets": MARKETS,
            "oddsFormat": "american",
            "bookmakers": BOOKMAKER,
        }
        resp = requests.get(url, params=params, timeout=15)
        print(f"{label}: {resp.status_code} "
              f"remaining={resp.headers.get('x-requests-remaining')} "
              f"used={resp.headers.get('x-requests-used')}")
        if resp.status_code != 200:
            print(f"Error fetching {sport}: {resp.status_code} {resp.text}")
            continue
        events = resp.json()
        n_with_tt = 0
        for event in events:
            event_id = event["id"]
            commence_time = datetime.fromisoformat(
                event["commence_time"].replace("Z", "+00:00")
            )
            matchup = f"{event['away_team']} @ {event['home_team']}"
            game_total, _, _ = extract_lines(event)

            if now < commence_time:
                # Pregame: fetch team totals ONCE per event and cache them.
                # On later runs the cached copy is reused — no repeat cost.
                # v4.1: period totals (Q1/H1) are NOT fetched — 5 credits
                # per game was too fast on big slates.
                existing = state["pregame"].get(event_id, {})
                team_totals = existing.get("team_totals") or {}
                if not team_totals:
                    team_totals = fetch_team_totals(sport, event_id, failed_sports)
                if team_totals:
                    n_with_tt += 1
                state["pregame"][event_id] = {
                    "matchup": matchup,
                    "sport": sport,
                    "label": label,
                    "group": league["group"],
                    "commence_time": event["commence_time"],
                    "game_total": game_total,
                    "team_totals": team_totals,
                }
                continue

            if event_id in state["pregame"]:
                pre = state["pregame"][event_id]
                check_move(event_id, label, matchup, "game_total",
                           pre.get("game_total"), game_total, thresholds, state, alerts,
                           verdicts=verdicts)
                # Live: team totals need a fresh per-event fetch (1 credit).
                team_totals = fetch_team_totals(sport, event_id, failed_sports)
                if team_totals:
                    n_with_tt += 1
                for team, live_tt in team_totals.items():
                    pre_tt = pre.get("team_totals", {}).get(team)
                    check_move(event_id, label, matchup, "team_total",
                               pre_tt, live_tt, thresholds, state, alerts, team=team,
                               verdicts=verdicts)
                # Q1 / halftime checkpoint (basketball only): record the
                # live lines once, in the first poll inside the window.
                # Costs $0 extra — reuses the live totals fetched above.
                elapsed = (now - commence_time).total_seconds() / 60
                cp = checkpoint_name(league.get("periods"), elapsed)
                if cp:
                    done = state["checkpoints"].setdefault(event_id, {})
                    if cp not in done:
                        done[cp] = {
                            "elapsed_min": round(elapsed),
                            "game_total": game_total,
                            "team_totals": team_totals,
                            "at": now.isoformat(),
                        }
                        checkpoint_lines.append(
                            format_checkpoint(label, matchup, cp, pre,
                                              game_total, team_totals))
        if events and n_with_tt == 0:
            print(f"  Note: {label} returned {len(events)} events but no team_totals "
                  f"from {BOOKMAKER} — expected for hockey/overseas (see header).")

    cutoff = now - timedelta(hours=24)
    state["pregame"] = {
        k: v for k, v in state["pregame"].items()
        if datetime.fromisoformat(v["commence_time"].replace("Z", "+00:00")) > cutoff
    }
    # Drop checkpoints for games that have been pruned from pregame.
    state["checkpoints"] = {
        k: v for k, v in state.get("checkpoints", {}).items()
        if k in state["pregame"]
    }
    # Drop suppressed keys for pruned games too. A suppressed key is
    # "{event_id}_{kind}..." so it belongs to a game still in "pregame".
    # "alerted" is intentionally never pruned (existing behaviour).
    state["suppressed"] = [
        k for k in state.get("suppressed", [])
        if any(k.startswith(eid + "_") for eid in state["pregame"])
    ]

    if alerts:
        subject = f"Live Total Alert ({len(alerts)} trigger{'s' if len(alerts) > 1 else ''})"
        body = "\n\n---\n\n".join(alerts)
        try:
            send_email(subject, body)
            print("Sent alerts:\n", body)
        except Exception as e:
            print(f"ALERT EMAIL FAILED (run continues): {type(e).__name__}: {e}")
    if checkpoint_lines:
        subject = (f"Q1 / Halftime Lines "
                   f"({len(checkpoint_lines)} checkpoint{'s' if len(checkpoint_lines) > 1 else ''})")
        body = "\n\n---\n\n".join(checkpoint_lines)
        try:
            send_email(subject, body)
            print("Sent checkpoints:\n", body)
        except Exception as e:
            print(f"CHECKPOINT EMAIL FAILED (run continues): {type(e).__name__}: {e}")
    save_state(state)


if __name__ == "__main__":
    run()
