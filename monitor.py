"""
Live Odds Total Monitor v2 — expanded coverage

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
    for US sports / selected bookmakers. It often does NOT come back at
    sport level for hockey or overseas leagues. The script still asks for
    it and uses it when present, and logs when it's missing — it will not
    crash. Game totals (featured market) work for all leagues below.

COST — 1 credit per region per market per sport per run.
  Default here: regions=eu, markets=totals,team_totals = 2 credits/sport/run
  15 sports = 30 credits/run, 90/hour at 20-min polling = 2,160/day.
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
MARKETS = "totals,team_totals"
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
    {"key": "basketball_nba", "label": "NBA", "group": "big"},
    {"key": "basketball_ncaab", "label": "NCAAB Men", "group": "big"},
    {"key": "basketball_wncaab", "label": "WNCAAB Women", "group": "big"},
    {"key": "basketball_wnba", "label": "WNBA", "group": "big"},
    {"key": "basketball_euroleague", "label": "EuroLeague", "group": "big"},
    {"key": "basketball_nbl", "label": "NBL Australia", "group": "big"},
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
            return json.load(f)
    return {"pregame": {}, "alerted": []}


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
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return None, {}
    book = next((b for b in bookmakers if b["key"] == BOOKMAKER), bookmakers[0])
    game_total = None
    team_totals = {}
    for market in book.get("markets", []):
        if market["key"] == "totals":
            for outcome in market.get("outcomes", []):
                if outcome["name"] == "Over":
                    game_total = float(outcome["point"])
        elif market["key"] == "team_totals":
            for outcome in market.get("outcomes", []):
                if outcome["name"] == "Over":
                    team_name = outcome.get("description")
                    if team_name:
                        team_totals[team_name] = float(outcome["point"])
    return game_total, team_totals


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

    active = get_active_sports()
    leagues = LEAGUES
    if active is not None:
        skipped = [l["label"] for l in LEAGUES if l["key"] not in active]
        leagues = [l for l in LEAGUES if l["key"] in active]
        print(f"Active leagues: {[l['label'] for l in leagues]}")
        if skipped:
            print(f"Skipped (offseason, $0 cost): {skipped}")

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
            game_total, team_totals = extract_lines(event)
            if team_totals:
                n_with_tt += 1

            if now < commence_time:
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
                           pre.get("game_total"), game_total, thresholds, state, alerts)
                for team, live_tt in team_totals.items():
                    pre_tt = pre.get("team_totals", {}).get(team)
                    check_move(event_id, label, matchup, "team_total",
                               pre_tt, live_tt, thresholds, state, alerts, team=team)
        if events and n_with_tt == 0:
            print(f"  Note: {label} returned {len(events)} events but no team_totals "
                  f"from {BOOKMAKER} — expected for hockey/overseas (see header).")

    cutoff = now - timedelta(hours=24)
    state["pregame"] = {
        k: v for k, v in state["pregame"].items()
        if datetime.fromisoformat(v["commence_time"].replace("Z", "+00:00")) > cutoff
    }

    if alerts:
        subject = f"Live Total Alert ({len(alerts)} trigger{'s' if len(alerts) > 1 else ''})"
        body = "\n\n---\n\n".join(alerts)
        send_email(subject, body)
        print("Sent alerts:\n", body)
    save_state(state)


if __name__ == "__main__":
    run()
