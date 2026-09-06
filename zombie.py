"""Papa Zombie authoritative fixed-step simulation and persistence."""
import json
import secrets
import time

GUNS={'pistol':(1,8,8),'smg':(2,3,24),'shotgun':(4,12,6),'rifle':(7,6,10)}

def create():
    return dict(version=4,duck=False,hazards=[],hazardWait=90,hazardId=0,fireHeld=0,healed=False,wave=1,kills=0,waveKills=0,coins=0,hp=5,lives=0,lifeBuys=0,gun='pistol',owned=['pistol'],ammo=0,level=0,mag=8,reload=0,cooldown=0,jump=0,jumpWait=0,tick=0,spawn=12,nextId=1,enemies=[],mode='running')

def price(s,item):
    return dict(smg=150,shotgun=280,rifle=500,ammo=35+5*s['wave'],heal=55+10*s['wave'],upgrade=80*(s['level']+1)**2,life=300*2**s['lifeBuys']).get(item)

def buy(s,item):
    if s['mode']!='shop' or not isinstance(item,str):raise ValueError('Wait for the shop.')
    if item.startswith('equip:'):
        gun=item[6:]
        if gun not in s['owned']:raise ValueError('Buy this gun first.')
        s.update(gun=gun,mag=0,reload=1);return
    cost=price(s,item)
    if cost is None or s['coins']<cost:raise ValueError('Not enough coins.')
    if item in GUNS:
        if item in s['owned']:raise ValueError('Already owned.')
        s['owned'].append(item);s['gun']=item;s['ammo']+=40;s['mag']=0;s['reload']=1
    elif item=='ammo':
        if s['ammo']>=600:raise ValueError('Ammo stash full.')
        s['ammo']=min(600,s['ammo']+60)
    elif item=='heal':
        if s['hp']>=5 or s['healed']:raise ValueError('One first-aid kit per store.')
        s['healed']=True
        s['hp']=min(5,s['hp']+2)
    elif item=='upgrade':
        if s['level']>=5:raise ValueError('Fully upgraded.')
        s['level']+=1
    elif item=='life':
        if s['lives']:raise ValueError('Already carrying a life.')
        s['lives']=1;s['lifeBuys']+=1
    s['coins']-=cost

def resume(s):
    if s['mode'] not in ('shop','storefront'):raise ValueError('Not at a shop.')
    s['wave']+=1;s.update(hazards=[],hazardWait=100,duck=False,healed=False,fireHeld=0,waveKills=0,spawn=15,enemies=[],mode='running')

def step(s,input):
    if s['mode']!='running':return
    fire=bool(input&1) and not s['fireHeld'];s['fireHeld']=input&1
    s['tick']+=1
    for key in ('cooldown','jumpWait','jump'):s[key]=max(0,s[key]-1)
    if input&2 and s['jumpWait']==0:s['jump']=21;s['jumpWait']=38
    s['duck']=bool(input&8) and s['jump']==0
    damage,rate,mag=GUNS[s['gun']]
    if s['reload']>0:
        s['reload']-=1
        if s['reload']==0:s['mag']=mag if s['gun']=='pistol' else min(mag,s['ammo'])
    if input&4 and s['reload']==0 and s['mag']<mag:s['reload']=22
    s['spawn']-=1
    if s['spawn']<=0 and len(s['enemies'])<1:
        eid=s['nextId'];s['nextId']+=1
        kind='tank' if s['wave']>=3 and eid%7==0 else 'runner' if s['wave']>=2 and eid%4==0 else 'walker'
        hp=(2+int((s['wave']-1)*.65))*(3 if kind=='tank' else 1)
        s['enemies'].append(dict(id=eid,kind=kind,hp=hp,maxHp=hp,x=790));s['spawn']=max(6,18-s['wave'])
    if fire and s['reload']==0 and s['cooldown']==0:
        if s['gun']!='pistol' and s['ammo']<=0:
            s['gun']='pistol';damage,rate,mag=GUNS['pistol'];s['mag']=8
        if s['mag']<=0:s['reload']=22
        else:
            s['mag']-=1
            if s['gun']!='pistol':s['ammo']-=1
            s['cooldown']=rate
            for enemy in sorted((e for e in s['enemies'] if e['x']<=650),key=lambda e:e['x'])[:3 if s['gun']=='shotgun' else 1]:enemy['hp']-=damage+s['level']
    had_enemies=bool(s['enemies']);survivors=[]
    for e in s['enemies']:
        if e['hp']<=0:
            s['kills']+=1;s['waveKills']+=1;s['coins']+=10+(s['wave']//2)*2+(8 if e['kind']=='tank' else 3 if e['kind']=='runner' else 0);continue
        e['x']-=min(17,6+(s['wave']-1)//2)+(2 if e['kind']=='runner' else 0)
        if e['x']<=170:
            if s['jump']==0:s['hp']-=2 if e['kind']=='tank' else 1
            continue
        survivors.append(e)
    s['enemies']=survivors
    if had_enemies and not survivors and s['spawn']<12:s['spawn']=8+s['nextId']%4*2
    s['hazardWait']-=1
    if s['hazardWait']<=0 and not s['hazards']:
        s['hazardId']+=1
        s['hazards']=[dict(kind='bird' if s['hazardId']%2 else 'ground',x=790,warning=24)]
        s['hazardWait']=max(110,165-s['wave']*5)
    hazards=[]
    for h in s['hazards']:
        if h['warning']>0:h['warning']-=1
        else:h['x']-=min(16,11+s['wave']//3)
        if h['x']<=170:
            safe=s['duck'] if h['kind']=='bird' else 4<=s['jump']<=18
            if not safe:s['hp']-=1
        else:hazards.append(h)
    s['hazards']=hazards
    if s['hp']<=0:
        if s['lives']:s['lives']-=1;s.update(hp=5,enemies=[],hazards=[],spawn=35,hazardWait=100)
        else:s.update(hp=0,mode='dead');return
    if s['waveKills']>=20:s.update(mode='storefront',enemies=[],hazards=[],duck=False)

def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS zombie_runs(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,scope TEXT NOT NULL,state TEXT NOT NULL,updated REAL NOT NULL,request TEXT,created REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS zombie_run_user ON zombie_runs(user_id);
    CREATE TABLE IF NOT EXISTS zombie_scores(scope TEXT NOT NULL,user_id INTEGER NOT NULL,best INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(scope,user_id));
    CREATE TABLE IF NOT EXISTS zombie_cards(scope TEXT PRIMARY KEY,chat_id INTEGER NOT NULL,message_id INTEGER NOT NULL);''')

def board(app,user_id=0,scope='private',kind='global'):
    target=scope if kind=='group' and scope!='private' else 'global'
    with app.connect() as db:
        if kind=='personal':
            rows=db.execute("SELECT state,created FROM zombie_runs WHERE user_id=? ORDER BY created DESC LIMIT 10",(user_id,)).fetchall()
            players=[dict(name=time.strftime('%b %d · %H:%M UTC',time.gmtime(r['created'])),score=json.loads(r['state'])['kills']) for r in rows]
        else:players=[dict(r) for r in db.execute('SELECT p.name,z.best AS score FROM zombie_scores z JOIN players p ON p.id=z.user_id WHERE z.scope=? AND z.best>0 ORDER BY z.best DESC,z.user_id LIMIT 20',(target,))]
        row=db.execute("SELECT best FROM zombie_scores WHERE scope='global' AND user_id=?",(user_id,)).fetchone()
    return dict(players=players,best=row[0] if row else 0,group=scope!='private')

def handle(app,path,data,user_id,name,scope):
    if data.get('version')!=4:raise ValueError('Reload Papa Zombie.')
    if path.endswith('/leaderboard'):return board(app,user_id,scope,data.get('board','global'))
    now=time.time()
    with app.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if path.endswith('/start'):
            last=db.execute('SELECT MAX(created) FROM zombie_runs WHERE user_id=?',(user_id,)).fetchone()[0]
            if last and now-last<1:raise ValueError('Wait a moment before restarting.')
            db.execute('DELETE FROM zombie_runs WHERE updated<?',(now-30*86400,))
            db.execute('INSERT INTO players(id,name) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name',(user_id,name))
            run=secrets.token_urlsafe(24);s=create()
            db.execute('INSERT INTO zombie_runs VALUES (?,?,?,?,?,?,?)',(run,user_id,scope,json.dumps(s),now,None,now))
            return dict(run=run,state=s,group=scope!='private')
        run=data.get('run');request=data.get('request')
        if not isinstance(run,str) or not isinstance(request,str) or len(request)>80:raise ValueError('Invalid run.')
        row=db.execute('SELECT * FROM zombie_runs WHERE id=? AND user_id=? AND scope=?',(run,user_id,scope)).fetchone()
        if not row or now-row['updated']>86400:raise ValueError('Run expired.')
        s=json.loads(row['state'])
        if s.get('version')!=4:raise ValueError('Start a new run for the updated game.')
        if row['request']==request:return dict(run=run,state=s,group=scope!='private')
        action=data.get('action')
        if action=='combat':
            inputs=data.get('inputs')
            if not isinstance(inputs,list) or not 1<=len(inputs)<=2000:raise ValueError('Invalid inputs.')
            ticks=0
            for batch in inputs:
                if not isinstance(batch,list) or len(batch)!=2 or any(type(v)is not int for v in batch):raise ValueError('Invalid inputs.')
                count,mask=batch
                if not 1<=count<=18000 or not 0<=mask<=15:raise ValueError('Invalid inputs.')
                ticks+=count
                if ticks>18000 or ticks*50>(now-row['updated'])*1000+1500:raise ValueError('Invalid duration.')
                for _ in range(count):
                    if s['mode']!='running':raise ValueError('Run continued after combat ended.')
                    step(s,mask)
                if s['tick']*50>(now-row['created'])*1000+1500:
                    raise ValueError('Run is advancing faster than real time.')
        elif action=='enter':
            if s['mode']!='storefront':raise ValueError('No shop here.')
            s['mode']='shop'
        elif action=='buy':buy(s,data.get('item'))
        elif action=='continue':resume(s)
        else:raise ValueError('Unknown action.')
        db.execute('UPDATE zombie_runs SET state=?,updated=?,request=? WHERE id=?',(json.dumps(s),now,request,run))
        for key in set(('global',scope)):
            db.execute('INSERT INTO zombie_scores VALUES (?,?,?) ON CONFLICT(scope,user_id) DO UPDATE SET best=MAX(best,excluded.best)',(key,user_id,s['kills']))
    if action=='combat' and scope.startswith('group:'):
        try:app.refresh_zombie_card(scope)
        except Exception:pass
    return dict(run=run,state=s,group=scope!='private')
