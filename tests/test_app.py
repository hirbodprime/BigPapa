import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import app


class GameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbpatch = patch.object(app, 'DATABASE', str(Path(self.temp.name) / 'test.sqlite3'))
        self.tokenpatch = patch.object(app, 'BOT_TOKEN', 'test-token')
        self.dbpatch.start(); self.tokenpatch.start(); app.initialize()

    def tearDown(self):
        self.dbpatch.stop(); self.tokenpatch.stop(); self.temp.cleanup()

    def login(self, **changes):
        data = {'user': json.dumps({'id': 123, 'first_name': 'Test'}), 'auth_date': str(int(time.time()))}
        data.update(changes)
        secret = hmac.new(b'WebAppData', b'test-token', hashlib.sha256).digest()
        data['hash'] = hmac.new(secret, '\n'.join(f'{k}={v}' for k,v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
        return urlencode(data)

    def test_telegram_auth_and_tampering(self):
        self.assertEqual(app.authenticate(self.login()), (123, 'Test'))
        with self.assertRaises(ValueError): app.authenticate(self.login().replace('Test', 'Fake'))
        with self.assertRaises(ValueError): app.authenticate(self.login(auth_date='1'))
        with self.assertRaises(ValueError): app.authenticate(self.login() + '&auth_date=1')

    def test_tree_always_has_a_safe_side(self):
        for seed in [0, 1, 42717, 0xffffffff]:
            tree = app.branches(seed)
            self.assertEqual(tree[:2], [0,0])
            for a,b in zip(tree,tree[1:]): self.assertFalse(a and b)

    def test_replay_valid_run_and_collision(self):
        seed=42717; tree=app.branches(seed)
        moves=[[2 if 1 in (tree[i],tree[i+1]) else 1,i*150] for i in range(40)]
        self.assertEqual(app.replay(seed,moves), (40,5850))
        fatal=[[1,0]]
        fatal.append([tree[2],150])
        self.assertEqual(app.replay(seed,fatal)[0],2)
        with self.assertRaises(ValueError):app.replay(seed,fatal+[[1,300]])

    def test_reject_fast_and_expired_moves(self):
        for moves in [[[1,0],[2,1]],[[1,0],[2,7000]],[[True,0]],[[1,-1]],[[1,0.1]],[]]:
            with self.assertRaises(ValueError): app.replay(1,moves)

    def test_score_ownership_reuse_and_leaderboard(self):
        run=app.begin_run(123,'A <test>')
        with self.assertRaises(ValueError):app.finish_run(456,run['run'],[[1,0]])
        result=app.finish_run(123,run['run'],[[1,0]])
        self.assertEqual(result, {'score':1,'best':1,'rank':1})
        with self.assertRaises(ValueError):app.finish_run(123,run['run'],[[1,0]])
        self.assertEqual(app.leaderboard(),[{'name':'A <test>','score':1}])

    def test_reject_future_run(self):
        run=app.begin_run(123,'Test')
        tree=app.branches(run['seed'])
        moves=[[2 if 1 in (tree[i],tree[i+1]) else 1,i*200] for i in range(30)]
        with self.assertRaises(ValueError):app.finish_run(123,run['run'],moves)

    def test_power_thresholds_and_safe_bonus_chops(self):
        self.assertEqual(app.power_level(49,10000,1),1)
        self.assertEqual(app.power_level(50,15000,1),2)
        self.assertEqual(app.power_level(50,15001,1),1)
        self.assertEqual(app.power_level(100,30000,2),2)
        self.assertEqual(app.power_level(349,60000,1),1)
        self.assertEqual(app.power_level(350,120000,1),3)
        self.assertEqual(app.swing([0,0,0,0,0,0],0,1,4),(4,False))
        self.assertEqual(app.swing([0,0,1,0,0],0,1,4),(1,False))
        self.assertEqual(app.swing([0,1,0],0,1,2),(1,True))
        self.assertEqual(app.swing([1,0,0],0,1,4),(0,True))

    def test_group_rankings_are_isolated(self):
        first=app.begin_run(123,'Player A','group:one')
        app.finish_run(123,first['run'],[[1,0]],'group:one')
        second=app.begin_run(456,'Player B','group:two')
        pattern=app.branches(second['seed'])
        which=2 if pattern[2]==1 else 1
        app.finish_run(456,second['run'],[[1,0],[which,100]],'group:two')
        self.assertEqual(app.scoped_leaderboard(123,'group:one','group')['players'],[{'name':'Player A','score':1}])
        self.assertEqual(app.scoped_leaderboard(456,'group:two','group')['players'],[{'name':'Player B','score':2}])
        self.assertEqual(len(app.leaderboard()),2)
        self.assertEqual(len(app.scoped_leaderboard(123,'private','personal')['players']),1)
        with self.assertRaises(ValueError): app.scoped_leaderboard(123,'private','group')

    def test_group_bot_launch_binds_player_and_group(self):
        with patch.object(app,'telegram',return_value={}) as api:
            app.bot_update({'update_id':1,'message':{'text':'/chop','chat':{'id':-42,'type':'supergroup','title':'Friends'}}})
            button=api.call_args.args[1]['reply_markup']['inline_keyboard'][0][0]
            parameter=button['url'].split('start=')[1]
            app.bot_update({'update_id':2,'message':{'text':'/start '+parameter,'from':{'id':123,'first_name':'A'},'chat':{'id':123,'type':'private'}}})
            url=api.call_args.args[1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url']
            launch=url.split('#launch=')[1]
            user,name,scope,context=app.identity({'launch':launch})
            self.assertEqual((user,name,scope,context),(123,'A','group:-42',{}))
            with self.assertRaises(ValueError): app.identity({'launch':launch[:-1]+'z'})
            self.assertEqual(app.group_invite({'id':-42}),parameter[2:])
            run=app.begin_run(user,name,scope)
            with self.assertRaises(ValueError):app.finish_run(user,run['run'],[[1,0]],'group:-43')

    def test_start_chooses_before_sending_link(self):
        with patch.object(app,'telegram',return_value={}) as api:
            chat={'id':123,'type':'private'}
            app.bot_update({'update_id':100,'message':{'text':'/start','chat':chat}})
            buttons=api.call_args.args[1]['reply_markup']['inline_keyboard']
            self.assertEqual([r[0]['callback_data'] for r in buttons],['choose:chop','choose:zombie'])
            app.bot_update({'update_id':101,'callback_query':{'id':'pick','data':'choose:zombie','message':{'chat':chat}}})
            self.assertEqual(api.call_args.args[0],'sendMessage')
            self.assertTrue(api.call_args.args[1]['reply_markup']['inline_keyboard'][0][0]['web_app']['url'].endswith('/zombie'))

    def test_previous_rules_cannot_submit(self):
        run=app.begin_run(123,'A')
        with app.connect() as db:db.execute('UPDATE runs SET rules=1 WHERE id=?',(run['run'],))
        with self.assertRaises(ValueError):app.finish_run(123,run['run'],[[1,0]])

    def test_group_message_updates_with_own_rankings(self):
        with patch.object(app,'telegram',return_value={'message_id':77}) as api:
            app.post_group_card({'id':-42,'type':'supergroup','title':'Friends'})
            self.assertIn('No scores yet',api.call_args.args[1]['text'])
            run=app.begin_run(123,'Alice','group:-42')
            app.finish_run(123,run['run'],[[1,0]],'group:-42')
            method,payload=api.call_args.args
            self.assertEqual(method,'editMessageText')
            self.assertEqual((payload['chat_id'],payload['message_id']),(-42,77))
            self.assertIn('1. Alice — 1 logs',payload['text'])
            other=app.begin_run(456,'Bob','group:-43')
            app.finish_run(456,other['run'],[[1,0]],'group:-43')
            self.assertNotIn('Bob',app.group_card_payload('group:-42')['text'])

    def test_old_group_button_creates_scoreboard_on_finish(self):
        app.group_invite({'id':-99,'title':'Old group'})
        with patch.object(app,'telegram',return_value={'message_id':88}) as api:
            run=app.begin_run(123,'Alice','group:-99')
            app.finish_run(123,run['run'],[[1,0]],'group:-99')
            self.assertEqual(api.call_args.args[0],'sendMessage')
            self.assertEqual(api.call_args.args[1]['chat_id'],-99)
            self.assertIn('Alice',api.call_args.args[1]['text'])


if __name__=='__main__':unittest.main()
