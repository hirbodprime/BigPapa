# Big Papa Games · Papa Chop

A visual HTML5 tree-chopping game at **https://bigpapagames.com/play**, launched inside
Telegram from **@Big_PapaGamesBot**. Original canvas woodland and lumberjack art;
no framework or runtime dependencies beyond Python 3.12. The root domain now serves
a cartoon one-page introduction to the multi-game brand.

## Play

Send `/start` or `/play` to the bot, then tap **Play Papa Chop**. The persistent
**Play** menu opens the same Mini App. Tap left/right (or use arrow keys / A / D)
to chop. Avoid branches and keep the timer alive. A run ends after collision,
timeout, leaving the active page, 180 seconds, or 2,000 inputs.

Browser play saves a best score on that device. Telegram play uses signed
Telegram initData and saves a personal best to the global, in-game leaderboard.
Add the bot to a group and send `/play@Big_PapaGamesBot`. Its group button opens a
private bot deep link, then a player-specific Mini App launch button bound to that
group. Group runs count in both group and global rankings. Private runs count
only globally. **My bests** shows the player's latest 10 completed runs within
30 days and their personal best. Global/personal bests are retained indefinitely.

GAMEE-style inline game selection and native Telegram game cards have dormant
integration code but are not enabled: they require BotFather `/setinline` and
`/newgame`. Set `GAME_SHORT_NAME` only after registering the game. The current
group Play-button flow works without that registration.

## Power-ups and sound

- 50 logs within 15 seconds of the first chop unlocks green ×2.
- 350 total logs unlocks red ×3, regardless of time. This is the maximum tier.
- Harder timer: 4.2 seconds initially, a 5-second cap, and smaller per-swing time bonuses.
- Powers last for the current run and reset on restart.
- A swing cuts up to its multiplier in logs. Bonus cuts stop before danger; the
  first cut can still hit a branch. Time is awarded once per swing.
- Chopping audio is synthesized on the player's device, with a persistent mute
  preference. No sound files or server audio processing are needed.
- Rules version 3 rejects pre-upgrade unfinished runs; existing bests are retained.

## Brand assets

`docs/bot-profile-image-brief.md` contains the multi-game bot avatar brief.
`docs/homepage-art-prompt.md` records the generated homepage illustration prompt.
The homepage raster is an image_gen asset; the animated game character is canvas.

## Validation and limits

The server verifies Telegram signatures and login age, issues single-use runs,
replays timed inputs against server-generated branch patterns, and calculates
scores itself. Rejects wrong owners, reused/expired runs, impossible move timing,
and moves after a collision or expired timer. This limits score tampering but
cannot prevent automation or a bot playing an otherwise legal input sequence.

The bot receives authenticated HTTPS webhook updates and responds to `/start`,
`/play`, and `/help` in private and group chats. No background polling service is needed.

## Deployment

- Host: `209.250.237.183`
- Code: `/opt/bigpapagames`
- User/service: `bigpapagames`
- Bind: `127.0.0.1:8020`
- SQLite: `/var/lib/bigpapagames/db.sqlite3`
- Secrets: `/etc/bigpapagames.env` (root-only; `BOT_TOKEN`, `PUBLIC_URL`, `PORT`, `DATABASE_PATH`)
- Nginx: `/etc/nginx/sites-available/bigpapagames`
- Certificate webroot: `/var/www/bigpapagames-acme`

The local `.env` is ignored by Git. Never archive or log it. Deploy only explicitly
selected app/static/deploy files. Back up code and SQLite before deployment.
Restart only `bigpapagames`. Run `deploy/configure_bot.py` with the service
environment loaded to set bot commands, Play menu, description, and webhook.
It verifies the expected bot identity and does not print credentials.

GoDaddy DNS points to Vultr. HTTP and `www` redirect to the apex HTTPS domain.
Certbot renewal is scheduled; its deploy hook validates and reloads nginx.
The original nginx backup is `/root/nginx-before-bigpapagames-20260905-210943.tar.gz`.

## Local development and checks

```sh
DATABASE_PATH=/tmp/papa-chop-dev.sqlite3 PORT=8020 python3 app.py
python3 -m unittest discover -s tests -v
node --check static/game.js
node tests/test_game.cjs
```

The app does not automatically load `.env`. Browser practice works without a bot
token. Tests use a temporary database and a fake token, never production data.

```sh
systemctl is-active dad blackjackbot blackjack-admin nginx bigpapagames
curl --fail http://127.0.0.1:8020/healthz
journalctl -u bigpapagames -n 50 --no-pager
```

Do not modify the dad or blackjack applications, databases, or secrets. Check RAM
and disk before deployments. Back up nginx and run `nginx -t` before any reload.

Group Play messages now include a top-10 leaderboard. The newest Play message in
each group is updated after completed group runs; older pre-upgrade buttons create
a scoreboard on the first completed run. Group message delivery failures never
roll back a saved score. Sending `/play` creates a fresh current scoreboard.

## Papa Zombie

Papa Zombie is available at `/zombie`; `/games` is the shared game chooser.
See `docs/papa-zombie.md` for controls, prices, progression, and score validation.
The bot offers both games privately, `/zombie` and `/chop` commands, and separate
ranking messages for each game in groups. `/start` and `/play` show game choices first; selecting a game sends its play link
and, in groups, its ranking card.

Run `node tests/test_zombie.cjs` and `python3 -m unittest discover -s tests -q`.
