"""Minimal Big Papa Games service; game endpoints will be added next."""
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DATABASE = os.environ.get("DATABASE_PATH", "/var/lib/bigpapagames/db.sqlite3")


def initialize():
    with sqlite3.connect(DATABASE) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        db.execute("INSERT OR IGNORE INTO schema_version VALUES (1)")


class Handler(BaseHTTPRequestHandler):
    server_version = "BigPapaGames"
    sys_version = ""

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            try:
                with sqlite3.connect(DATABASE, timeout=2) as db:
                    db.execute("SELECT version FROM schema_version").fetchone()
                status, data = 200, {"status": "ok"}
            except sqlite3.Error:
                status, data = 503, {"status": "unavailable"}
        elif path == "/":
            status, data = 200, {"name": "Big Papa Games", "status": "Coming soon", "bot": "https://t.me/Big_PapaGamesBot"}
        else:
            status, data = 404, {"error": "Not found"}
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    initialize()
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8020"))), Handler).serve_forever()
