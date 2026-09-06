const E=require('../static/zombie-engine.js'),assert=require('node:assert/strict'),fs=require('node:fs');
const s=E.create(),events=[];
for(let wave=1;wave<=8;wave++){
 let count=0,inputs=[];while(s.mode==='running'&&count<18000){let mask=count%8===0?1:0;for(const h of s.hazards){if(h.kind==='bird')mask|=8;else if(h.x>180&&h.x<260&&!h.warning)mask|=2;}if(inputs.length&&inputs.at(-1)[1]===mask)inputs.at(-1)[0]++;else inputs.push([1,mask]);E.step(s,mask);count++;}
 assert.equal(s.mode,'storefront',`street ${wave}`);assert.ok(s.waveKills>=20);events.push({action:'combat',inputs,state:structuredClone(s)});
 s.mode='shop';events.push({action:'enter',state:structuredClone(s)});
 for(const item of [wave===1?'smg':wave===3?'rifle':'upgrade','heal','ammo']){
  try{E.buy(s,item);events.push({action:'buy',item,state:structuredClone(s)});}catch{}
 }
 E.resume(s);events.push({action:'continue',state:structuredClone(s)});
}
const empty=E.create();empty.coins=0;empty.mode='shop';assert.throws(()=>E.buy(empty,'rifle'));
empty.coins=10000;E.buy(empty,'life');assert.equal(empty.lives,1);assert.throws(()=>E.buy(empty,'life'));
const dead=E.create();for(let i=0;i<18000&&dead.mode==='running';i++)E.step(dead,0);assert.equal(dead.mode,'dead');
const fallback=E.create();fallback.gun='smg';fallback.ammo=0;fallback.enemies=[{id:1,kind:'walker',hp:2,maxHp:2,x:500}];E.step(fallback,1);assert.equal(fallback.gun,'pistol');
fs.writeFileSync('/tmp/zombie-fixtures.json',JSON.stringify(events));console.log('Eight streets, purchases, progression, death, and ammo fallback passed.');
