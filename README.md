# Big Papa Games

Telegram username: `Big_PapaGamesBot`
Domain: `bigpapagames.com`

## Deployed foundation

- Host: `209.250.237.183`
- Code: `/opt/bigpapagames`
- Linux user and systemd service: `bigpapagames`
- Bind: `127.0.0.1:8020`
- Database: `/var/lib/bigpapagames/db.sqlite3`
- Environment: `/etc/bigpapagames.env` (root-only)
- Nginx: `/etc/nginx/sites-available/bigpapagames`
- ACME webroot: `/var/www/bigpapagames-acme`
- Pre-change nginx backup: `/root/nginx-before-bigpapagames-20260905-210943.tar.gz`

The Python standard-library service is a temporary infrastructure scaffold. `/`
returns project metadata, and `/healthz` checks the database. Games, Telegram
authentication, score validation, leaderboards, and bot integration are not yet implemented.

## Domain and HTTPS

GoDaddy DNS now points to the server. HTTPS is active for the apex and `www`;
HTTP and `www` redirect to `https://bigpapagames.com`. Certbot uses webroot renewal
and its timer is active. A deploy hook validates and reloads nginx after renewal.
HTTPS health and redirect checks passed on September 5, 2026.

## Pending bot integration

Store the new bot token securely in `/etc/bigpapagames.env` as `BOT_TOKEN`.
   Never commit or log it. Implement and verify bot integration before enabling it.

## Operations

```sh
systemctl is-active dad blackjackbot blackjack-admin nginx bigpapagames
curl --fail http://127.0.0.1:8020/healthz
journalctl -u bigpapagames -n 50 --no-pager
```

Do not modify the dad or blackjack application directories, databases, or secrets.
Back up nginx before changes; validate before reload. Check RAM and disk before
adding dependencies. Only restart `bigpapagames` for this project's deployments.
