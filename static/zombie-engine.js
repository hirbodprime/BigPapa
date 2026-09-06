/* Deterministic 20 Hz simulation, mirrored by zombie.py for score verification. */
(function(root){
'use strict';
const GUNS={pistol:{name:'Sidekick',damage:1,rate:8,mag:8},smg:{name:'Street Sweeper',damage:2,rate:3,mag:24},shotgun:{name:'Boomstick',damage:4,rate:12,mag:6},rifle:{name:'Nightfall',damage:7,rate:6,mag:10}};
function create(){return {version:4,duck:false,hazards:[],hazardWait:90,hazardId:0,fireHeld:0,healed:false,wave:1,kills:0,waveKills:0,coins:0,hp:5,lives:0,lifeBuys:0,gun:'pistol',owned:['pistol'],ammo:0,level:0,mag:8,reload:0,cooldown:0,jump:0,jumpWait:0,tick:0,spawn:12,nextId:1,enemies:[],mode:'running'};}
function price(s,item){return ({smg:150,shotgun:280,rifle:500,ammo:35+5*s.wave,heal:55+10*s.wave,upgrade:80*(s.level+1)**2,life:300*2**s.lifeBuys})[item];}
function buy(s,item){
 if(s.mode!=='shop')throw Error('Wait for the shop.');
 if(item.startsWith('equip:')){const gun=item.slice(6);if(!s.owned.includes(gun))throw Error('Buy this gun first.');s.gun=gun;s.mag=0;s.reload=1;return;}
 const cost=price(s,item);if(!Number.isFinite(cost)||s.coins<cost)throw Error('Not enough coins.');
 if(GUNS[item]){if(s.owned.includes(item))throw Error('Already owned.');s.owned.push(item);s.gun=item;s.ammo+=40;s.mag=0;s.reload=1;}
 else if(item==='ammo'){if(s.ammo>=600)throw Error('Ammo stash is full.');s.ammo=Math.min(600,s.ammo+60);}
 else if(item==='heal'){if(s.hp>=5||s.healed)throw Error('One first-aid kit per store.');s.healed=true;s.hp=Math.min(5,s.hp+2);}
 else if(item==='upgrade'){if(s.level>=5)throw Error('Fully upgraded.');s.level++;}
 else if(item==='life'){if(s.lives)throw Error('One spare life at a time.');s.lives=1;s.lifeBuys++;}
 s.coins-=cost;
}
function resume(s){if(!['shop','storefront'].includes(s.mode))throw Error('Not at a shop.');s.wave++;s.hazards=[];s.hazardWait=100;s.duck=false;s.healed=false;s.fireHeld=0;s.waveKills=0;s.spawn=15;s.enemies=[];s.mode='running';}
function step(s,input){
 if(s.mode!=='running')return;
 const fire=!!(input&1)&&!s.fireHeld;s.fireHeld=input&1;
 s.tick++;s.cooldown=Math.max(0,s.cooldown-1);s.jumpWait=Math.max(0,s.jumpWait-1);s.jump=Math.max(0,s.jump-1);
 if((input&2)&&s.jumpWait===0){s.jump=21;s.jumpWait=38;}
 s.duck=!!(input&8)&&s.jump===0;
 let gun=GUNS[s.gun];
 if(s.reload>0){s.reload--;if(s.reload===0)s.mag=s.gun==='pistol'?gun.mag:Math.min(gun.mag,s.ammo);}
 if((input&4)&&s.reload===0&&s.mag<gun.mag){s.reload=22;}
 s.spawn--;
 if(s.spawn<=0&&s.enemies.length<1){
  const id=s.nextId++,kind=s.wave>=3&&id%7===0?'tank':s.wave>=2&&id%4===0?'runner':'walker';
  const hp=(2+Math.floor((s.wave-1)*.65))*(kind==='tank'?3:1);
  s.enemies.push({id,kind,hp,maxHp:hp,x:790});s.spawn=Math.max(6,18-s.wave);
 }
 if(fire&&s.reload===0&&s.cooldown===0){
  if(s.gun!=='pistol'&&s.ammo<=0){s.gun='pistol';gun=GUNS.pistol;s.mag=8;}
  if(s.mag<=0){s.reload=22;}
  else{
   s.mag--;if(s.gun!=='pistol')s.ammo--;s.cooldown=gun.rate;
   const targets=s.enemies.filter(e=>e.x<=650).sort((a,b)=>a.x-b.x).slice(0,s.gun==='shotgun'?3:1);
   for(const enemy of targets)enemy.hp-=gun.damage+s.level;
  }
 }
 const hadEnemies=s.enemies.length>0;let survivors=[];
 for(const e of s.enemies){
  if(e.hp<=0){s.kills++;s.waveKills++;s.coins+=10+Math.floor(s.wave/2)*2+(e.kind==='tank'?8:e.kind==='runner'?3:0);continue;}
  e.x-=Math.min(17,6+Math.floor((s.wave-1)/2))+(e.kind==='runner'?2:0);
  if(e.x<=170){if(s.jump===0)s.hp-=e.kind==='tank'?2:1;continue;}
  survivors.push(e);
 }
 s.enemies=survivors;if(hadEnemies&&!survivors.length&&s.spawn<12)s.spawn=8+s.nextId%4*2;
 s.hazardWait--;
 if(s.hazardWait<=0&&!s.hazards.length){s.hazardId++;s.hazards=[{kind:s.hazardId%2?'bird':'ground',x:790,warning:24}];s.hazardWait=Math.max(110,165-s.wave*5);}
 const hazards=[];
 for(const h of s.hazards){
  if(h.warning>0)h.warning--;else h.x-=Math.min(16,11+Math.floor(s.wave/3));
  if(h.x<=170){const safe=h.kind==='bird'?s.duck:s.jump>=4&&s.jump<=18;if(!safe)s.hp--;}
  else hazards.push(h);
 }
 s.hazards=hazards;
 if(s.hp<=0){if(s.lives){s.lives--;s.hp=5;s.enemies=[];s.hazards=[];s.hazardWait=100;s.spawn=35;}else{s.hp=0;s.mode='dead';return;}}
 if(s.waveKills>=20){s.mode='storefront';s.enemies=[];s.hazards=[];s.duck=false;}
}
const api={GUNS,create,price,buy,resume,step};if(typeof module!=='undefined')module.exports=api;else root.ZombieEngine=api;
})(typeof globalThis!=='undefined'?globalThis:this);
