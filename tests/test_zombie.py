import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import zombie

class ZombieTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.p=patch.object(app,'DATABASE',str(Path(self.temp.name)/'db'));self.p.start();app.initialize()
        self.now=1000;self.clock=patch('zombie.time.time',side_effect=lambda:self.now);self.clock.start()
    def tearDown(self):self.clock.stop();self.p.stop();self.temp.cleanup()
    def call(self,path,data,user=1,scope='private'):
        return zombie.handle(app,'/api/zombie/'+path,{'version':4,**data},user,'Player '+str(user),scope)
    def first_street(self,user=1,scope='private'):
        run=self.call('start',{},user,scope);state=zombie.create();ticks=0
        inputs=[]
        while state['mode']=='running':
            mask=1 if ticks%8==0 else 0
            for h in state['hazards']:
                if h['kind']=='bird':mask|=8
                elif 180<h['x']<260 and not h['warning']:mask|=2
            if inputs and inputs[-1][1]==mask:inputs[-1][0]+=1
            else:inputs.append([1,mask])
            zombie.step(state,mask);ticks+=1
            assert ticks<18000
        self.now+=ticks*.05+2
        data={'run':run['run'],'action':'combat','request':'combat-1','inputs':inputs}
        with patch.object(app,'refresh_zombie_card'):
            result=self.call('action',data,user,scope)
        self.assertEqual(result['state'],state)
        return run['run'],data,result
    def test_authoritative_shop_and_idempotent_purchase(self):
        run,data,result=self.first_street();self.assertEqual(result['state']['coins'],200)
        self.assertEqual(self.call('action',data),result)
        self.call('action',{'run':run,'action':'enter','request':'enter-1'})
        purchase={'run':run,'action':'buy','item':'smg','request':'buy-1','coins':99999}
        bought=self.call('action',purchase);self.assertEqual(bought['state']['coins'],50)
        self.assertEqual(self.call('action',purchase),bought)
        with self.assertRaises(ValueError):self.call('action',{'run':run,'action':'buy','item':'rifle','request':'buy-2'})
        self.assertEqual(app.leaderboard(),[])
        self.assertEqual(zombie.board(app)['players'][0]['score'],20)
    def test_hazards_require_correct_dodge(self):
        for kind,mask,safe in [('bird',8,True),('bird',0,False),('bird',2,False),('ground',8,False),('ground',0,False)]:
            s=zombie.create();s['hazards']=[dict(kind=kind,x=175,warning=0)]
            zombie.step(s,mask);self.assertEqual(s['hp'],5 if safe else 4)
        s=zombie.create();s.update(jump=9,hazards=[dict(kind='ground',x=175,warning=0)])
        zombie.step(s,0);self.assertEqual(s['hp'],5)
        s=zombie.create();s.update(hazardWait=1,enemies=[dict(id=1,kind='walker',hp=9,maxHp=9,x=500)])
        zombie.step(s,0);self.assertEqual((len(s['hazards']),len(s['enemies'])),(1,1))
        self.assertGreater(s['hazards'][0]['warning'],0)

    def test_tap_fire_and_single_enemy(self):
        s=zombie.create()
        for _ in range(40):
            zombie.step(s,1)
            self.assertLessEqual(len(s['enemies']),1)
        self.assertEqual(s['mag'],7)
        zombie.step(s,0);zombie.step(s,1)
        self.assertEqual(s['mag'],6)

    def test_store_requires_entry_and_limits_healing(self):
        s=zombie.create();s.update(mode='storefront',coins=1000,hp=1)
        with self.assertRaises(ValueError):zombie.buy(s,'heal')
        s['mode']='shop';zombie.buy(s,'heal')
        self.assertEqual(s['hp'],3)
        with self.assertRaises(ValueError):zombie.buy(s,'heal')
        zombie.resume(s);self.assertFalse(s['healed'])
        s['mode']='storefront';zombie.resume(s)
        self.assertEqual((s['wave'],s['mode']),(3,'running'))

    def test_duration_owner_and_scope(self):
        started=self.call('start',{},scope='group:-1')
        data={'run':started['run'],'action':'combat','inputs':[[1000,1]],'request':'fast'}
        with self.assertRaises(ValueError):self.call('action',data,scope='group:-1')
        self.now+=100
        with self.assertRaises(ValueError):self.call('action',data,user=2,scope='group:-1')
        with self.assertRaises(ValueError):self.call('action',data,scope='group:-2')
    def test_group_scores_do_not_mix(self):
        self.first_street(1,'group:-1');self.first_street(2,'group:-2')
        self.assertEqual([x['name'] for x in zombie.board(app,1,'group:-1','group')['players']],['Player 1'])
        self.assertEqual(len(zombie.board(app)['players']),2)
    def test_ammo_fallback_and_extra_life(self):
        s=zombie.create();s.update(gun='smg',ammo=0,enemies=[dict(id=1,kind='walker',hp=2,maxHp=2,x=500)]);zombie.step(s,1);self.assertEqual(s['gun'],'pistol')
        s=zombie.create();s.update(hp=1,lives=1,enemies=[dict(id=1,kind='walker',hp=2,maxHp=2,x=170)])
        zombie.step(s,0);self.assertEqual((s['hp'],s['lives'],s['mode']),(5,0,'running'))
    def test_illegal_input_and_combat_after_shop(self):
        run,_,_=self.first_street();self.now+=10
        for inputs in [[[1,99]],[[0,1]],[[1,True]],[[1,1]]]:
            with self.assertRaises(ValueError):self.call('action',{'run':run,'action':'combat','inputs':inputs,'request':'bad'})

if __name__=='__main__':unittest.main()
