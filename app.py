"""Big Papa Games: lightweight Telegram Mini App and validated game scores."""
import zombie
import sys
import base64
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

DATABASE = os.environ.get('DATABASE_PATH', '/var/lib/bigpapagames/db.sqlite3')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PUBLIC_URL = os.environ.get('PUBLIC_URL', 'https://bigpapagames.com').rstrip('/')
GAME_URL = PUBLIC_URL + '/play'
STATIC = Path(__file__).parent / 'static'
WEBHOOK_SECRET = hmac.new(BOT_TOKEN.encode(), b'bigpapagames-webhook-v1', hashlib.sha256).hexdigest()
GROUP_CARD_LOCK = threading.Lock()
MAX_MOVES = 2000
RULES_VERSION = 3
GAME_SHORT_NAME = os.environ.get("GAME_SHORT_NAME", "")
LAUNCH_KEY = hmac.new(BOT_TOKEN.encode(), b"papa-game-launch-v1", hashlib.sha256).digest()


@contextmanager
def connect():
    db = sqlite3.connect(DATABASE, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
          CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
          INSERT OR IGNORE INTO schema_version VALUES (1);
          CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, best INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, seed INTEGER NOT NULL,
            created REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
          CREATE INDEX IF NOT EXISTS runs_user ON runs(user_id, created);
          CREATE INDEX IF NOT EXISTS players_best ON players(best DESC);
          CREATE TABLE IF NOT EXISTS updates (id INTEGER PRIMARY KEY, created REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS group_cards (scope TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS group_invites (token TEXT PRIMARY KEY, scope TEXT NOT NULL UNIQUE, title TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS group_scores (scope TEXT NOT NULL, user_id INTEGER NOT NULL, best INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(scope,user_id));
        ''')
        zombie.initialize(db)
        if 'rules' not in {row['name'] for row in db.execute('PRAGMA table_info(runs)')}:
            db.execute('ALTER TABLE runs ADD COLUMN rules INTEGER NOT NULL DEFAULT 1')
        columns = {row['name'] for row in db.execute('PRAGMA table_info(runs)')}
        for name, definition in [('scope', "TEXT NOT NULL DEFAULT 'private'"), ('context', "TEXT NOT NULL DEFAULT '{}'"), ('result_score', 'INTEGER')]:
            if name not in columns:
                db.execute(f'ALTER TABLE runs ADD COLUMN {name} {definition}')


def authenticate(raw, now=None):
    if not BOT_TOKEN or not isinstance(raw, str) or len(raw) > 12000:
        raise ValueError('Open the game from the Telegram bot to save scores.')
    pairs = parse_qsl(raw, keep_blank_values=True)
    data = dict(pairs)
    if len(data) != len(pairs):
        raise ValueError('Invalid Telegram login.')
    supplied = data.pop('hash', '')
    check = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
    secret = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise ValueError('Invalid Telegram login.')
    age = (now or time.time()) - int(data.get('auth_date', '0'))
    if age < -30 or age > 86400:
        raise ValueError('Please close and reopen the game in Telegram.')
    user = json.loads(data.get('user', '{}'))
    if type(user.get('id')) is not int or user['id'] <= 0:
        raise ValueError('Invalid Telegram player.')
    return user['id'], str(user.get('first_name', 'Player'))[:40]


def encode_launch(user, scope, context):
    payload = {'id': user['id'], 'name': str(user.get('first_name', 'Player'))[:40],
               'scope': scope, 'context': context, 'issued': int(time.time())}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    signature = hmac.new(LAUNCH_KEY, encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + '.' + signature


def identity(data):
    launch = data.get('launch')
    if launch:
        if not BOT_TOKEN or not isinstance(launch, str) or len(launch) > 4096:
            raise ValueError('Invalid game launch.')
        encoded, signature = launch.rsplit('.', 1)
        expected = hmac.new(LAUNCH_KEY, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError('Invalid game launch.')
        payload = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        age = time.time() - payload['issued']
        if age < -30 or age > 86400:
            raise ValueError('Reopen the game from its Telegram card.')
        if data.get('initData'):
            actual_id, _ = authenticate(data['initData'])
            if actual_id != payload['id']:
                raise ValueError('Open your own group game button.')
        return payload['id'], payload['name'], payload['scope'], payload['context']
    user_id, name = authenticate(data.get('initData'))
    return user_id, name, 'private', {}


def branches(seed, count=MAX_MOVES * 3 + 10):
    tree = [0, 0]
    state = seed & 0xffffffff
    for _ in range(2, count):
        state = (1664525 * state + 1013904223) & 0xffffffff
        tree.append(0 if tree[-1] else (0 if state % 5 == 0 else 1 + state % 2))
    return tree


def power_level(score, stamp, current):
    if score >= 350:
        return 3
    if score >= 50 and stamp <= 15000:
        return max(2, current)
    return current


def swing(tree, score, side, power):
    """First chop can collide; automatic bonus chops stop before danger."""
    if tree[score] == side:
        return score, True
    for step in range(power):
        if step and (tree[score] == side or tree[score + 1] == side):
            break
        score += 1
        if tree[score] == side:
            return score, True
    return score, False


def replay(seed, moves):
    if not isinstance(moves, list) or not 1 <= len(moves) <= MAX_MOVES:
        raise ValueError('Invalid run length.')
    tree = branches(seed)
    score, energy, previous, dead, power = 0, 4200, 0, False, 1
    for i, move in enumerate(moves):
        if not isinstance(move, list) or len(move) != 2:
            raise ValueError('Invalid move.')
        side, stamp = move
        if type(side) is not int or side not in (1, 2) or type(stamp) is not int:
            raise ValueError('Invalid move.')
        if stamp < 0 or stamp > 180000 or (i == 0 and stamp != 0) or (i and stamp - previous < 45):
            raise ValueError('Invalid move timing.')
        if dead:
            raise ValueError('Run continued after game over.')
        energy -= stamp - previous
        previous = stamp
        if energy <= 0:
            raise ValueError('Run continued after time ran out.')
        old_score = score
        score, dead = swing(tree, score, side, power)
        if score > old_score:
            # Time is awarded once per input, not per automatically chopped log.
            energy = min(5000, energy + max(75, 310 - score * .6))
        if not dead:
            power = power_level(score, stamp, power)
    return score, previous


def leaderboard():
    with connect() as db:
        return [dict(row) for row in db.execute(
            'SELECT name, best AS score FROM players WHERE best > 0 ORDER BY best DESC, id ASC LIMIT 20')]


def begin_run(user_id, name, scope='private', context=None):
    now = time.time()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        last = db.execute('SELECT MAX(created) FROM runs WHERE user_id=?', (user_id,)).fetchone()[0]
        if last and now - last < 1:
            raise ValueError('One moment—then try again.')
        db.execute('DELETE FROM runs WHERE created < ?', (now - 30 * 86400,))
        db.execute('DELETE FROM updates WHERE created < ?', (now - 86400,))
        db.execute('INSERT INTO players(id,name) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name', (user_id, name))
        db.execute('UPDATE runs SET used=1 WHERE user_id=? AND used=0', (user_id,))
        run_id, seed = secrets.token_urlsafe(24), secrets.randbits(32)
        db.execute('INSERT INTO runs(id,user_id,seed,created,rules,scope,context) VALUES (?,?,?,?,?,?,?)', (run_id, user_id, seed, now, RULES_VERSION, scope, json.dumps(context or {})))
        best = db.execute('SELECT best FROM players WHERE id=?', (user_id,)).fetchone()[0]
    return {'run': run_id, 'seed': seed, 'best': best, 'rules': RULES_VERSION, 'group': scope != 'private'}


def finish_run(user_id, run_id, moves, scope='private'):
    if not isinstance(run_id, str):
        raise ValueError('Invalid run.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        run = db.execute('SELECT * FROM runs WHERE id=? AND user_id=?', (run_id, user_id)).fetchone()
        if not run or run['used'] or run['rules'] != RULES_VERSION or run['scope'] != scope or time.time() - run['created'] > 240:
            raise ValueError('This run has expired or was already saved.')
        score, elapsed = replay(run['seed'], moves)
        if elapsed > (time.time() - run['created']) * 1000 + 1500:
            raise ValueError('Invalid run duration.')
        db.execute('UPDATE runs SET used=1,result_score=? WHERE id=?', (score,run_id))
        db.execute('UPDATE players SET best=MAX(best,?) WHERE id=?', (score, user_id))
        best = db.execute('SELECT best FROM players WHERE id=?', (user_id,)).fetchone()[0]
        rank = db.execute('SELECT COUNT(*)+1 FROM players WHERE best>?', (best,)).fetchone()[0]
        db.execute('INSERT INTO group_scores(scope,user_id,best) VALUES (?,?,?) ON CONFLICT(scope,user_id) DO UPDATE SET best=MAX(best,excluded.best)', (scope,user_id,score))
        scope_best = db.execute('SELECT best FROM group_scores WHERE scope=? AND user_id=?', (scope,user_id)).fetchone()[0]
        context = json.loads(run['context'])
    if context:
        try:
            telegram('setGameScore', {'user_id':user_id, 'score':scope_best, **context})
        except Exception:
            # In-game scores remain durable if Telegram declines an unchanged score
            # or a card has been deleted. A later finish retries the current best.
            logging.info('Telegram card score not updated; in-game score saved.')
    if scope.startswith('group:'):
        try:
            refresh_group_card(scope)
        except Exception:
            logging.info('Group message update failed; score remains saved.')
    return {'score': score, 'best': best, 'rank': rank}


def scoped_leaderboard(user_id, scope, board):
    with connect() as db:
        best_row = db.execute('SELECT best FROM players WHERE id=?', (user_id,)).fetchone()
        best = best_row[0] if best_row else 0
        rank = db.execute('SELECT COUNT(*)+1 FROM players WHERE best>?', (best,)).fetchone()[0]
        if board == 'personal':
            players = [{'name': time.strftime('%b %d · %H:%M UTC', time.gmtime(row['created'])), 'score': row['result_score']}
                       for row in db.execute('SELECT created,result_score FROM runs WHERE user_id=? AND result_score IS NOT NULL ORDER BY created DESC LIMIT 10', (user_id,))]
        elif board == 'group':
            if scope == 'private':
                raise ValueError('Open a game card in a group for group rankings.')
            players = [dict(row) for row in db.execute('SELECT p.name,g.best AS score FROM group_scores g JOIN players p ON p.id=g.user_id WHERE g.scope=? AND g.best>0 ORDER BY g.best DESC,g.user_id LIMIT 20', (scope,))]
        else:
            players = leaderboard()
    return {'players':players, 'best':best, 'rank':rank, 'group':scope != 'private'}


def telegram(method, payload):
    req = urllib.request.Request('https://api.telegram.org/bot' + BOT_TOKEN + '/' + method,
                                 data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=12) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram request failed')
    return result['result']


def group_invite(chat):
    scope = 'group:' + str(chat['id'])
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT token FROM group_invites WHERE scope=?', (scope,)).fetchone()
        if existing:
            return existing['token']
        token = secrets.token_urlsafe(16)
        db.execute('INSERT INTO group_invites VALUES (?,?,?)', (token,scope,str(chat.get('title','Your group'))[:100]))
    return token


def group_card_payload(scope):
    with connect() as db:
        invite = db.execute('SELECT token FROM group_invites WHERE scope=?', (scope,)).fetchone()
        rows = db.execute('SELECT p.name,g.best FROM group_scores g JOIN players p ON p.id=g.user_id WHERE g.scope=? AND g.best>0 ORDER BY g.best DESC,g.user_id LIMIT 10', (scope,)).fetchall()
    if not invite:
        raise ValueError('Unknown group.')
    lines = ['🪓 PAPA CHOP', '🏆 Group leaderboard', '']
    if rows:
        for index,row in enumerate(rows,1):
            name = ' '.join(row['name'].split())[:40]
            lines.append(f'{index}. {name} — {row["best"]} logs')
    else:
        lines.append('No scores yet. Be the first to chop!')
    lines += ['', 'Top 10 · Best score per player in this group',
              'Play below to compete. Rankings update after each group run.',
              '', 'Tap Play, then Start in the private bot chat.']
    return {'text':'\n'.join(lines),'reply_markup':{'inline_keyboard':[[{
        'text':'🪓 Play for this group','url':'https://t.me/Big_PapaGamesBot?start=g_'+invite['token']}]]}}


def refresh_group_card(scope):
    # Serialize edits so concurrent finishes cannot overwrite a newer ranking.
    with GROUP_CARD_LOCK:
        with connect() as db:
            card = db.execute('SELECT chat_id,message_id FROM group_cards WHERE scope=?',(scope,)).fetchone()
        if card:
            telegram('editMessageText', {**dict(card), **group_card_payload(scope)})
        else:
            # Existing group buttons predate message tracking. Create their first
            # scoreboard when a player finishes a run from one of those buttons.
            with connect() as db:
                invite = db.execute('SELECT 1 FROM group_invites WHERE scope=?', (scope,)).fetchone()
            if invite:
                chat_id = int(scope.split(':',1)[1])
                sent = telegram('sendMessage', {'chat_id':chat_id, **group_card_payload(scope)})
                with connect() as db:
                    db.execute('INSERT INTO group_cards VALUES (?,?,?)', (scope,chat_id,sent['message_id']))


def post_group_card(chat):
    group_invite(chat)
    scope = 'group:' + str(chat['id'])
    with GROUP_CARD_LOCK:
        sent = telegram('sendMessage', {'chat_id':chat['id'],**group_card_payload(scope)})
        if isinstance(sent,dict) and type(sent.get('message_id')) is int:
            with connect() as db:
                db.execute('INSERT INTO group_cards VALUES (?,?,?) ON CONFLICT(scope) DO UPDATE SET chat_id=excluded.chat_id,message_id=excluded.message_id', (scope,chat['id'],sent['message_id']))


def zombie_card_payload(scope):
    with connect() as db:
        invite=db.execute('SELECT token FROM group_invites WHERE scope=?',(scope,)).fetchone()
        rows=db.execute('SELECT p.name,z.best FROM zombie_scores z JOIN players p ON p.id=z.user_id WHERE z.scope=? AND z.best>0 ORDER BY z.best DESC,z.user_id LIMIT 10',(scope,)).fetchall()
    lines=['🧟 PAPA ZOMBIE','🏆 Group leaderboard','']
    lines += [f'{i}. {" ".join(row["name"].split())[:40]} — {row["best"]} kills' for i,row in enumerate(rows,1)] or ['No scores yet. Own the first spot!']
    lines += ['','Endless streets · Shop every 20 kills','Tap Play, then Start in the private bot chat.']
    return {'text':'\n'.join(lines),'reply_markup':{'inline_keyboard':[[{'text':'🧟 Play Papa Zombie','url':'https://t.me/Big_PapaGamesBot?start=z_'+invite['token']}]]}}


def post_zombie_card(chat):
    group_invite(chat);scope='group:'+str(chat['id'])
    with GROUP_CARD_LOCK:
        sent=telegram('sendMessage',{'chat_id':chat['id'],**zombie_card_payload(scope)})
        if isinstance(sent,dict) and type(sent.get('message_id')) is int:
            with connect() as db:db.execute('INSERT INTO zombie_cards VALUES (?,?,?) ON CONFLICT(scope) DO UPDATE SET message_id=excluded.message_id',(scope,chat['id'],sent['message_id']))


def refresh_zombie_card(scope):
    with GROUP_CARD_LOCK:
        with connect() as db:card=db.execute('SELECT chat_id,message_id FROM zombie_cards WHERE scope=?',(scope,)).fetchone()
        if card:telegram('editMessageText',{**dict(card),**zombie_card_payload(scope)})


def game_choices(chat_id):
    telegram('sendMessage',{'chat_id':chat_id,'text':'🎮 Big Papa Games\nChoose a game:',
        'reply_markup':{'inline_keyboard':[[{'text':'🪓 Papa Chop','callback_data':'choose:chop'}],[{'text':'🧟 Papa Zombie','callback_data':'choose:zombie'}]]}})


def send_game_link(chat_id,game):
    title='🧟 Papa Zombie' if game=='zombie' else '🪓 Papa Chop'
    url=PUBLIC_URL+'/zombie' if game=='zombie' else GAME_URL
    telegram('sendMessage',{'chat_id':chat_id,'text':title+'\nTap Play to launch your game.',
        'reply_markup':{'inline_keyboard':[[{'text':'▶ Play '+title,'web_app':{'url':url}}]]}})


def bot_update(update):
    update_id = update.get('update_id')
    if type(update_id) is not int:
        return
    with connect() as db:
        if db.execute('SELECT 1 FROM updates WHERE id=?', (update_id,)).fetchone():
            return
    if 'inline_query' in update:
        query = update['inline_query']
        search = query.get('query', '').strip().lower()
        results = []
        if GAME_SHORT_NAME and (not search or search in 'papa chop timber tree chopping'):
            results.append({'type':'game','id':'papachop','game_short_name':GAME_SHORT_NAME})
        telegram('answerInlineQuery', {'inline_query_id':query['id'], 'results':results, 'cache_time':30})
    elif 'callback_query' in update:
        query = update['callback_query']
        if query.get('data') in ('choose:chop','choose:zombie'):
            game=query['data'].split(':')[1]
            telegram('answerCallbackQuery',{'callback_query_id':query['id']})
            chat=query['message']['chat']
            if chat['type']=='private':send_game_link(chat['id'],game)
            elif game=='zombie':post_zombie_card(chat)
            else:post_group_card(chat)
        elif not GAME_SHORT_NAME or query.get('game_short_name') != GAME_SHORT_NAME:
            telegram('answerCallbackQuery', {'callback_query_id':query['id'],'text':'This game is not available yet.'})
        else:
            message = query.get('message', {})
            if query.get('inline_message_id'):
                context = {'inline_message_id':query['inline_message_id']}
                scope = 'chat:' + query['chat_instance']
            else:
                context = {'chat_id':message['chat']['id'],'message_id':message['message_id']}
                scope = 'private' if message['chat']['type']=='private' else 'chat:' + query['chat_instance']
            launch = encode_launch(query['from'], scope, context)
            telegram('answerCallbackQuery', {'callback_query_id':query['id'],'url':GAME_URL+'#launch='+launch})
    else:
        message = update.get('message', {})
        raw_command = message.get('text', '').split(' ', 1)[0].lower()
        if '@' in raw_command and raw_command.split('@',1)[1] != 'big_papagamesbot':
            return
        command = raw_command.split('@')[0]
        if command not in ('/start','/play','/help','/zombie','/chop'):
            return
        chat = message.get('chat', {})
        if chat.get('type') in ('group','supergroup'):
            if command=='/zombie':post_zombie_card(chat)
            elif command=='/chop':post_group_card(chat)
            else:game_choices(chat['id'])
        elif chat.get('type') == 'private':
            parameter = message.get('text','').split(' ',1)[1].strip() if ' ' in message.get('text','') else ''
            is_zombie = command == '/zombie' or parameter.startswith('z_') or parameter == 'zombie'
            invite = None
            if command == '/start' and parameter.startswith(('g_','z_')):
                with connect() as db:
                    invite = db.execute('SELECT scope,title FROM group_invites WHERE token=?', (parameter[2:],)).fetchone()
                if not invite:
                    telegram('sendMessage', {'chat_id':chat['id'],'text':'That group link is no longer available. Send /play in your group to get a new one.'})
                    return
            if invite:
                launch = encode_launch(message['from'], invite['scope'], {})
                url = (PUBLIC_URL+'/zombie' if is_zombie else GAME_URL)+'#launch='+launch
                text = ('🧟 Papa Zombie' if is_zombie else '🪓 Papa Chop')+' · '+invite['title']+'\n\nYour score goes to this game’s group and global rankings. Tap Play to begin!'
                buttons = [[{'text':('🧟 Play Zombie' if is_zombie else '🪓 Play Chop'), 'web_app':{'url':url}}]]
                telegram('sendMessage', {'chat_id':chat['id'],'text':text,'reply_markup':{'inline_keyboard':buttons}})
            elif command in ('/zombie','/chop') or parameter in ('zombie','papachop'):
                send_game_link(chat['id'],'zombie' if is_zombie else 'chop')
            else:
                game_choices(chat['id'])
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO updates VALUES (?,?)', (update_id,time.time()))


class Handler(BaseHTTPRequestHandler):
    server_version = 'BigPapaGames'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, *_):
        pass  # Never log request bodies, Telegram initData, or credential-bearing URLs.

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if 'json' in content_type or 'html' in content_type else 'public, max-age=300')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == '/healthz':
                with connect() as db:
                    db.execute('SELECT version FROM schema_version').fetchone()
                return self.respond(200, {'status': 'ok'})
            if path == '/api/zombie/leaderboard':
                return self.respond(200,zombie.board(sys.modules[__name__]))
            if path == '/api/leaderboard':
                return self.respond(200, {'players': leaderboard()})
            assets = {'/mascot.js':('mascot.js','text/javascript; charset=utf-8'), '/zombie':('zombie.html','text/html; charset=utf-8'), '/zombie/':('zombie.html','text/html; charset=utf-8'), '/zombie.js':('zombie.js','text/javascript; charset=utf-8'), '/zombie-engine.js':('zombie-engine.js','text/javascript; charset=utf-8'), '/zombie.css':('zombie.css','text/css; charset=utf-8'), '/games':('games.html','text/html; charset=utf-8'), '/games.js':('games.js','text/javascript; charset=utf-8'), '/': ('index.html', 'text/html; charset=utf-8'),
                      '/play': ('play.html', 'text/html; charset=utf-8'), '/play/': ('play.html', 'text/html; charset=utf-8'),
                      '/game.js': ('game.js', 'text/javascript; charset=utf-8'), '/home.js': ('home.js', 'text/javascript; charset=utf-8'),
                      '/home.css': ('home.css', 'text/css; charset=utf-8'), '/papa-world.png': ('papa-world.png', 'image/png'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8'), '/favicon.svg': ('favicon.svg', 'image/svg+xml')}
            if path in assets:
                filename, mime = assets[path]
                return self.respond(200, (STATIC / filename).read_bytes(), mime)
            self.respond(404, {'error': 'Not found'})
        except (OSError, sqlite3.Error):
            self.respond(503, {'error': 'Temporarily unavailable'})

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ('/api/zombie/start','/api/zombie/action','/api/zombie/leaderboard','/api/start', '/api/finish', '/api/leaderboard', '/api/telegram'):
            return self.respond(404, {'error': 'Not found'})
        if path == '/api/telegram':
            if not BOT_TOKEN or not hmac.compare_digest(self.headers.get('X-Telegram-Bot-Api-Secret-Token', ''), WEBHOOK_SECRET):
                return self.respond(403, {'error': 'Forbidden'})
        elif self.headers.get('Origin') not in (None, PUBLIC_URL):
            return self.respond(403, {'error': 'Forbidden origin'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536:
                return self.respond(413, {'error': 'Request too large'})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Invalid request.')
            if path == '/api/telegram':
                bot_update(data)
                return self.respond(200, {'ok': True})
            user_id, name, scope, context = identity(data)
            if path.startswith('/api/zombie/'):
                return self.respond(200,zombie.handle(sys.modules[__name__],path,data,user_id,name,scope))
            if data.get('rules') != RULES_VERSION:
                raise ValueError('Reload the game to use the current rules.')
            if path == '/api/leaderboard':
                result = scoped_leaderboard(user_id, scope, data.get('board', 'global'))
            elif path == '/api/start':
                result = begin_run(user_id, name, scope, context)
            else:
                result = finish_run(user_id, data.get('run'), data.get('moves'), scope)
            self.respond(200, result)
        except (ValueError, TypeError, KeyError):
            self.respond(400, {'error': 'Could not validate this run. Reopen the game in Telegram and try again.'})
        except Exception:
            logging.error('Request failed on %s (details withheld)', path)
            self.respond(503, {'error': 'Connection interrupted. Please try again.'})


if __name__ == '__main__':
    initialize()
    ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('PORT', '8020'))), Handler).serve_forever()
