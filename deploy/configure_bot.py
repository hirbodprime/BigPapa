"""Run on the server with the protected environment loaded. Never prints secrets."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


def configure():
    me = app.telegram('getMe', {})
    if me.get('username','').lower() != 'big_papagamesbot':
        raise RuntimeError('Unexpected bot identity; configuration stopped.')
    app.telegram('setMyCommands', {'commands': [
        {'command':'start','description':'Welcome to Big Papa Games'},
        {'command':'play','description':'Choose a game'},
        {'command':'zombie','description':'Play Papa Zombie'},
        {'command':'chop','description':'Play Papa Chop'},
        {'command':'help','description':'How to play'}]})
    app.telegram('setMyDescription', {'description':'Little games. Big smiles. Play Papa Chop or survive the streets in Papa Zombie. Personal bests, group challenges, and global rankings.'})
    app.telegram('setMyShortDescription', {'short_description':'🎮 Papa Chop + Papa Zombie. Quick games, big smiles, friendly competition.'})
    app.telegram('setChatMenuButton', {'menu_button': {'type':'web_app','text':'Games 🎮','web_app':{'url':app.PUBLIC_URL+'/games'}}})
    app.telegram('setWebhook', {'url':app.PUBLIC_URL+'/api/telegram', 'secret_token':app.WEBHOOK_SECRET,
                                'allowed_updates':['message','callback_query','inline_query'],'max_connections':4})
    info=app.telegram('getWebhookInfo', {})
    if info.get('url') != app.PUBLIC_URL+'/api/telegram':
        raise RuntimeError('Webhook did not match.')
    print('Configured @'+me['username']+' with Play menu, commands, and HTTPS webhook.')
    print('Pending updates:',info.get('pending_update_count',0))
    print('Inline mode enabled:', me.get('supports_inline_queries', False))
    print('Game short name configured:', bool(app.GAME_SHORT_NAME))


if __name__ == '__main__':
    try: configure()
    except Exception:
        raise SystemExit('Bot configuration failed. Details withheld to protect credentials.')
