# Live Odds Total Monitor v4.5 — expanded + Q1 / halftime checkpoints + WNCAAB feed test

## What it watches

**Football + Basketball — game total near 20, team total near 15**
- NFL, NCAAF, NCAAF FCS, CFL
- NBA, NCAAB Men, WNCAAB Women, WNBA, EuroLeague, NBL Australia

**Hockey — game total near 2, team total near 2**
- NHL, AHL, Liiga (Finland), SHL (Sweden), HockeyAllsvenskan (Sweden)

"Nearly" means: big sports alert at **18+ pts** (game) / **13+ pts** (team), then again at the full 20 / 15. Hockey alerts at **1.5+ goals**, then again at the full 2. All thresholds are at the top of `monitor.py` — change `BIG` / `HOCKEY` to tune them.

Pregame lines are snapshotted before tipoff/kickoff/puck drop and saved in `state.json`. Live games are compared against that snapshot, and each move alerts once per level (NEAR, then HIT). Alerts go to your email via Gmail SMTP.

## Test email (v4.2)

Normal emails only fire when a total moves NEAR/HIT or a Q1/halftime checkpoint is hit — so on a quiet day you get nothing, and that doesn't mean email is broken. To test the email path itself:

1. Update `.github/workflows/poll_odds.yml` in the repo to the version in this folder (GitHub won't let the app create workflow files, so replace it by hand, like the first time).
2. Actions → Live Odds Total Monitor → Run workflow → tick **send_test_email** → Run workflow.
3. You should get an email titled "Live Odds Monitor — Test Email" listing the games currently snapshotted. If it doesn't arrive, check spam, then check that `EMAIL_RECEIVER` is the right address and `EMAIL_PASSWORD` is a 16-character Gmail App Password (not your normal Gmail password).

v4.3: the first test run failed with `UnicodeEncodeError` because the `EMAIL_PASSWORD` secret contained a non-breaking space, copied in with the App Password from Google's display. The script now strips all spaces from the password at runtime, so you don't need to re-enter the secret — but if you do re-enter it, paste the 16 characters with no spaces. A failed email also no longer kills the whole run; it is logged and the run carries on.

## Q1 / halftime checkpoints (basketball only, v4)

For each basketball game you also get one email at the end of the 1st quarter and one at halftime, with:
- Pregame full-game total and team totals
- Live full-game total and team totals at that checkpoint, with the move vs pregame

The Odds API gives no game clock, so checkpoints are timed by elapsed real time since tipoff, caught on the next 20-minute poll: quarter leagues (NBA, WNBA, WNCAAB, EuroLeague, NBL) — Q1 at 25–55 min, halftime at 55–95 min; NCAAB Men plays halves, so halftime only, at 40–75 min. Football and hockey get no checkpoints. Each checkpoint is emailed once per game and saved in `state.json` under `checkpoints`. The checkpoints cost $0 extra — they reuse the live totals already fetched that run.

v4.1: the pregame Q1/H1 period totals were dropped — at 5 credits per game, once, they burned credits far too fast on big slates (NCAAB alone is 30–50 games a night). Pregame team totals are back to 1 credit per event, once.

## Coverage limits — read this before you expect ACB, DEL, etc.

Checked against The Odds API's official sports list:

- **Overseas basketball:** the API only has **EuroLeague and NBL (Australia)**. There is no Spain ACB, Italy, Germany BBL, Turkey, China CBA, EuroCup, or women's EuroLeague key. The only women's basketball keys are WNBA and WNCAAB.
- **Other hockey:** the API only has **Liiga, SHL, and HockeyAllsvenskan** (plus thin Mestis, commented out in the script). There is no DEL, Swiss NL, Czech Extraliga, or KHL key.
- **Team totals:** The Odds API lists `team_totals` as an additional market, mainly for US sports / selected bookmakers. It is **not** available at sport level — asking the sport-level `/odds` endpoint for it returns 422 INVALID_MARKET for every league. v3 fetches game totals at sport level and team totals one event at a time via `/events/{eventId}/odds`. It often still won't come back for hockey or overseas leagues, even per event. The script uses it when present, and logs when a league returns events but no team totals. Game totals work for all leagues listed.

If you need ACB / DEL / KHL, you'd need a second provider — The Odds API can't supply them.

## Credit math — this is the big problem with 15 leagues

1 credit per region per market. Game totals: `eu` × `totals` = 1 credit per sport per run.

**The alert checks cost $0 extra.** A NEAR/HIT check — game total near 20 pts, team total near 15 pts (football/basketball), hockey game/team total near 2 goals, up or down — is just a comparison of the totals already fetched in that run. No extra API call is made for it. So the burn below *is* the cost of checking those moves.

- v4.4 (30-minute polls, game hours 11:00–01:30 EST only): game totals ~11 leagues × ~29 runs/day = ~320/day; pregame team totals ~50/day; live team totals ~150/day; **total ~500/day, so 20,000 credits last ~38 days**.
- v4.5 (WNCAAB feed test only, no change to normal polling): `FEED_TEST=1` (workflow `feed_test` dispatch input) queries `basketball_wncaab` totals with several bookmaker/region combos — current config (pinnacle/eu), all books/us, all books/eu, fanduel/us, draftkings/us — plus a team_totals check on one event, and emails the event counts. ~5–7 credits, one-off. WNCAAB was found missing from state.json on 2026-11-23 (188 pregame games, 0 WNCAAB) even though it is configured; the test shows whether Pinnacle/EU lists WNCAAB at all or a US bookmaker is needed (regions=us doubles that sport's per-run cost).
- Before v4.4 (20-minute polls, 24/7): 15 sports = **15 credits/run** for game totals, 45/hour, **1,080/day** if all 15 are in season, plus team totals — roughly 1,000/day total, so 20,000 credits lasted ~20 days.
- Period totals (v4, dropped in v4.1): 5 credits per event, once, for the pregame Q1/H1 + team Q1/H1 lines — too fast on big slates. Checkpoints themselves cost $0 extra.
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

- `monitor.py` — the monitor (v4.4, this file's logic)
- `.github/workflows/poll_odds.yml` — runs it every 30 minutes, game hours only (the script also exits outside 11:00–01:30 EST), commits `state.json`
