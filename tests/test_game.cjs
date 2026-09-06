const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const nodes = new Map();
function element() {return {textContent:'', hidden:false,disabled:false,style:{},dataset:{},classList:{add(){},remove(){}},setAttribute(){},addEventListener(){},focus(){},replaceChildren(){},append(){},getContext(){return {}},innerHTML:''};}
const sandbox={console, Uint32Array, Math, AbortController,setTimeout,clearTimeout,AbortSignal,URLSearchParams,atob,
  document:{getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)},addEventListener(){},querySelector(){return element()},createElement:element},
  window:{matchMedia(){return {matches:false}},addEventListener(){}},
  localStorage:{getItem(){return null},setItem(){}},crypto:{getRandomValues(x){x[0]=42717;return x}},
  performance:{now(){return sandbox.now}},now:0,requestAnimationFrame(){}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync('static/game.js','utf8'),sandbox);
(async()=>{
  await vm.runInContext('start()',sandbox);
  assert.equal(vm.runInContext('mode',sandbox),'playing');
  for(let i=0;i<50;i++){
    sandbox.now=i*150; vm.runInContext('chop(tree[score]===1||tree[score+1]===1?2:1)',sandbox);
  }
  assert.equal(vm.runInContext('score',sandbox),50);
  assert.equal(vm.runInContext('power',sandbox),2);
  const seen=new Set([2]);
  for(let i=50;i<1000&&vm.runInContext('score',sandbox)<600;i++){
    sandbox.now+=65;vm.runInContext('chop(tree[score]===1||tree[score+1]===1?2:1)',sandbox);
    seen.add(vm.runInContext('power',sandbox));assert.equal(vm.runInContext('mode',sandbox),'playing');
  }
  assert.deepEqual([...seen],[2,3]);
  assert.ok(vm.runInContext('score',sandbox)>=600);
  const fixture=JSON.parse(vm.runInContext('JSON.stringify({seed:42717,moves,score,tree})',sandbox));
  if(process.argv.includes('--fixture'))fs.writeFileSync('/tmp/papa-chop-replay-fixture.json',JSON.stringify(fixture));
  sandbox.now+=100;vm.runInContext('tree[score]=1;chop(1)',sandbox);
  assert.equal(vm.runInContext('mode',sandbox),'over');
  assert.equal(nodes.get('result-score').textContent,fixture.score);
  await vm.runInContext('start()',sandbox);
  assert.equal(vm.runInContext('score',sandbox),0);assert.equal(vm.runInContext('power',sandbox),1);
  assert.equal(vm.runInContext('firstMove',sandbox),true);
  sandbox.now+=1000;vm.runInContext('chop(1)',sandbox);
  sandbox.now+=1;vm.runInContext('chop(1)',sandbox);
  assert.equal(vm.runInContext('moves.length',sandbox),1);
  sandbox.now+=7000;vm.runInContext('chop(1)',sandbox);
  assert.equal(vm.runInContext('mode',sandbox),'over');
  assert.equal(vm.runInContext('powerLevel(50,15001,1)',sandbox),1);
  assert.equal(vm.runInContext('powerLevel(349,60000,1)',sandbox),1);
  assert.equal(vm.runInContext('powerLevel(500,120000,1)',sandbox),3);
  console.log('Gameplay, all power tiers, reset, collision, input throttle, and timeout checks passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
