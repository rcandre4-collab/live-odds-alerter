"""
Live Odds Total Monitor v4 — expanded coverage + Q1 / halftime checkpoints

Football + Basketball (NFL, NCAAF, CFL, NBA, NCAAB, WNCAAB, WNBA,
EuroLeague, NBL Australia):
  Game total: alert when live moves NEAR 20 pts vs pregame
  Team total: alert when live moves NEAR 15 pts vs pregame

Hockey (NHL, AHL, Liiga, SHL, HockeyAllsvenskan):
  Game total: alert when live moves NEAR 2 goals vs pregame
  Team total: alert when live moves NEAR 2 goals vs pregame

"Nearly" is defined below so it actually triggers:
  Big sports:  game >= 18.0 (within 2 of 20), team >= 13.0 (within 2 of 15)
  Hockey:      game >= 1.5 (within 0.5 of 2), team >= 1.5 (within 0.5 of 2)
You get a NEAR alert first, then a second HIT alert if it reaches the
full 20 / 15 / 2. Change the *_NEAR values to make it stricter/looser.

Q1 / HALFTIME CHECKPOINTS (basketball only, v4):
  In addition to the NEAR/HIT alerts, the script emails you the live
  lines once at the end of the 1st quarter and once at halftime, per game:
    Pregame full-game total + team totals (already snapshotted)
    Pregame Q1 total / H1 total and Q1/H1 team totals (period markets,
      fetched once per event, pregame only)
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
  Period totals (v4): pregame Q1/H1 totals + team Q1/H1 totals are fetched
    ONCE per basketball event with the pregame team-totals call:
    markets=team_totals,totals_q1,totals_h1,team_totals_q1,team_totals_h1
    = 5 credits per basketball event, once. Checkpoint snapshots themselves
    cost $0 extra — they reuse the live totals already fetched that run.
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
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

BOOKMAKER = "pinnacle"  # sharpest benchmark; fallback to first available
REGIONS = "eu"  # Pinnacle is EU. Use "us,eu" only if team totals are missing for US leagues — doubles cost.
MARKETS = "totals"  # sport-level endpoint: featured markets ONLY (h2h, spreads, totals)
TEAM_MARKETS = "team_totals"  # additional market: per-event endpoint ONLY, see fetch_team_totals()
# Pregame period markets (basketball only, per-event, fetched once per event):
PERIOD_MARKETS = "team_totals,totals_q1,totals_h1,team_totals_q1,team_totals_h1"
# Checkpoint windows, minutes of real time since tipoff (no game clock in the API).
# Quarters: Q1 ~25-55 min, halftime ~55-95 min. Halves (NCAAB Men): halftime ~40-75 min.
CHECKPOINTS_QUARTERS = {"q1": (25, 55), "h1": (55, 95)}
CHECKPOINTS_HALVES = {"h1": (40, 75)}
STATE_FILE = "state.json"

# --- thresholds: (near, target) ---
BIG = {"game_near": 18.0, "game_target": 20.0, "team_near": 13.0, "team_target": 15.0}
HOCKEY = {"game_near": 1.5, "game_target": 2.0, "team_near": 1.5, "team_target": 2.0}

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
            return state
    return {"pregame": {}, "alerted": [], "checkpoints": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


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


def fetch_event_markets(sport, event_id, failed_sports):
    """Pregame-only: fetch team totals + Q1/H1 period totals for ONE event.

    One call, markets=team_totals,totals_q1,totals_h1,team_totals_q1,
    team_totals_h1 = 5 credits, once per event (caller caches the result).
    Returns (team_totals, period_totals); both {} / empty on failure.
    """
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": PERIOD_MARKETS,
        "oddsFormat": "american",
        "bookmakers": BOOKMAKER,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
    except Exception as e:
        if sport not in failed_sports:
            print(f"  period markets request failed for {sport} ({e})")
            failed_sports.add(sport)
        return {}, {"totals_q1": None, "totals_h1": None,
                    "team_totals_q1": {}, "team_totals_h1": {}}
    if resp.status_code != 200:
        if sport not in failed_sports:
            print(f"  period markets not available for {sport}: "
                  f"{resp.status_code} {resp.text[:200]}")
            failed_sports.add(sport)
        return {}, {"totals_q1": None, "totals_h1": None,
                    "team_totals_q1": {}, "team_totals_h1": {}}
    _, team_totals, period = extract_lines(resp.json())
    return team_totals, period


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
    vs pregame, plus the pregame period total for that period."""
    title = "End of 1st Quarter" if cp == "q1" else "Halftime"
    period_key = "totals_q1" if cp == "q1" else "totals_h1"
    team_key = "team_totals_q1" if cp == "q1" else "team_totals_h1"
    period = pre.get("period_totals", {}) or {}
    lines = [f"[{label}] {matchup}\n{title}"]
    pre_game = pre.get("game_total")
    if pre_game is not None and game_total is not None:
        lines.append(f"Game total: Pregame {pre_game} -> {title} {game_total} "
                     f"({game_total - pre_game:+.1f} pts)")
    elif game_total is not None:
        lines.append(f"Game total at {title}: {game_total}")
    if period.get(period_key) is not None:
        lines.append(f"Pregame {title} total line: {period[period_key]}")
    for team, live_tt in (team_totals or {}).items():
        pre_tt = (pre.get("team_totals", {}) or {}).get(team)
        if pre_tt is not None:
            lines.append(f"Team total {team}: Pregame {pre_tt} -> {title} {live_tt} "
                         f"({live_tt - pre_tt:+.1f} pts)")
        else:
            lines.append(f"Team total {team} at {title}: {live_tt}")
        pre_period_tt = (period.get(team_key, {}) or {}).get(team)
        if pre_period_tt is not None:
            lines.append(f"  Pregame {title} team total line for {team}: {pre_period_tt}")
    return "\n".join(lines)


def check_move(event_id, label, matchup, kind, pre_val, live_val, thresholds, state, alerts, team=None):
    """kind = 'game_total' or 'team_total'. Alerts once at NEAR, once at HIT.
    If it jumps straight to HIT, send only HIT (and mark NEAR as seen)."""
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
    if key in state["alerted"]:
        return
    direction = "UP" if diff > 0 else "DOWN"
    alerts.append(
        f"[{label}] {matchup}\n"
        f"{what} {level} {target:g} — {direction} {adiff:.1f} {unit} | "
        f"Pregame: {pre_val} -> Live: {live_val}"
    )
    state["alerted"].append(key)
    if near_key:
        state["alerted"].append(near_key)


def run():
    state = load_state()
    now = datetime.now(timezone.utc)
    alerts = []
    checkpoint_lines = []

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
                # Pregame: fetch team totals + Q1/H1 period totals ONCE per
                # event and cache them. On later runs the cached copy is
                # reused — no repeat cost.
                existing = state["pregame"].get(event_id, {})
                team_totals = existing.get("team_totals") or {}
                period_totals = existing.get("period_totals") or {}
                if not team_totals or not period_totals:
                    team_totals, period_totals = fetch_event_markets(
                        sport, event_id, failed_sports)
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
                    "period_totals": period_totals,
                }
                continue

            if event_id in state["pregame"]:
                pre = state["pregame"][event_id]
                check_move(event_id, label, matchup, "game_total",
                           pre.get("game_total"), game_total, thresholds, state, alerts)
                # Live: team totals need a fresh per-event fetch (1 credit).
                team_totals = fetch_team_totals(sport, event_id, failed_sports)
                if team_totals:
                    n_with_tt += 1
                for team, live_tt in team_totals.items():
                    pre_tt = pre.get("team_totals", {}).get(team)
                    check_move(event_id, label, matchup, "team_total",
                               pre_tt, live_tt, thresholds, state, alerts, team=team)
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

    if alerts:
        subject = f"Live Total Alert ({len(alerts)} trigger{'s' if len(alerts) > 1 else ''})"
        body = "\n\n---\n\n".join(alerts)
        send_email(subject, body)
        print("Sent alerts:\n", body)
    if checkpoint_lines:
        subject = (f"Q1 / Halftime Lines "
                   f"({len(checkpoint_lines)} checkpoint{'s' if len(checkpoint_lines) > 1 else ''})")
        body = "\n\n---\n\n".join(checkpoint_lines)
        send_email(subject, body)
        print("Sent checkpoints:\n", body)
    save_state(state)


if __name__ == "__main__":
    run()
