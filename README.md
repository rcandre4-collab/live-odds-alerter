# Live Odds Total Monitor v2 — expanded

## What it watches

**Football + Basketball — game total near 20, team total near 15**
- NFL, NCAAF, NCAAF FCS, CFL
- NBA, NCAAB Men, WNCAAB Women, WNBA, EuroLeague, NBL Australia

**Hockey — game total near 2, team total near 2**
- NHL, AHL, Liiga (Finland), SHL (Sweden), HockeyAllsvenskan (Sweden)

"Nearly" means: big sports alert at **18+ pts** (game) / **13+ pts** (team), then again at the full 20 / 15. Hockey alerts at **1.5+ goals**, then again at the full 2. All thresholds are at the top of `monitor.py` — change `BIG` / `HOCKEY` to tune them.

Pregame lines are snapshotted before tipoff/kickoff/puck drop and saved in `state.json`. Live games are compared against that snapshot, and each move alerts once per level (NEAR, then HIT). Alerts go to your email via Gmail SMTP.

## Coverage limits — read this before you expect ACB, DEL, etc.

Checked against The Odds API's official sports list:

- **Overseas basketball:** the API only has **EuroLeague and NBL (Australia)**. There is no Spain ACB, Italy, Germany BBL, Turkey, China CBA, EuroCup, or women's EuroLeague key. The only women's basketball keys are WNBA and WNCAAB.
- **Other hockey:** the API only has **Liiga, SHL, and HockeyAllsvenskan** (plus thin Mestis, commented out in the script). There is no DEL, Swiss NL, Czech Extraliga, or KHL key.
- **Team totals:** The Odds API lists `team_totals` as an additional market, mainly for US sports / selected bookmakers. It often won't come back for hockey or overseas leagues at sport level. The script asks for it anyway, uses it when present, and logs when a league returns events but no team totals. Game totals work for all leagues listed.

If you need ACB / DEL / KHL, you'd need a second provider — The Odds API can't supply them.

## Credit math — this is the big problem with 15 leagues

1 credit per region per market. Default: `eu` × `totals,team_totals` = 2 credits per sport per run.

- 15 sports = **30 credits/run**
- Every 20 min = 90/hour, **2,160/day** if all 15 are in season (4x cheaper than 5-min polling)
- The script first calls `/v4/sports` (free) and only polls in-season leagues, so offseason leagues cost $0. That helps a lot in summer/winter, but in-season you'll still burn a paid tier fast.

To fit a budget, in `monitor.py`:
1. Comment out leagues you don't care about in `LEAGUES`
2. Or run only during game hours

The script prints `x-requests-remaining` / `x-requests-used` on every run so you can see burn in the Actions log.

## Hockey / basketball warning

Live totals naturally drift down as the clock runs down — a hockey total dropping 1.5 goals late in a scoreless game, or an NBA total dropping 18 points in the 4th quarter of a low-scoring game, is normal clock drift, not necessarily a sharp move. Expect hockey alerts to be frequent late in games.

## Setup (same as v1)

1. Free key at the-odds-api.com; Gmail App Password (Google Account → Security → 2-Step Verification → App passwords)
2. Private GitHub repo, upload `monitor.py` to the root and `.github/workflows/poll_odds.yml` to that exact path
3. Repo → Settings → Secrets and variables → Actions → add `ODDS_API_KEY`, `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVER`
4. Actions → Live Odds Total Monitor → Run workflow to test. It should create `state.json` with no errors.

## Files

- `monitor.py` — the monitor (v2, this file's logic)
- `.github/workflows/poll_odds.yml` — runs it every 20 minutes, commits `state.json`
