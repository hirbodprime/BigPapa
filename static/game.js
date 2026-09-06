'use strict';
const $ = id => document.getElementById(id);
const canvas = $('forest'), ctx = canvas.getContext('2d');
const tg = window.Telegram?.WebApp;
const initData = tg?.initData || '';
const launch = new URLSearchParams(window.location?.hash?.slice(1) || '').get('launch') || '';
const ranked = Boolean(initData || launch);
let groupPlay = false, boardScope = 'global';
try { groupPlay = Boolean(launch) && JSON.parse(atob(launch.split('.')[0].replace(/-/g,'+').replace(/_/g,'/'))).scope !== 'private'; } catch {}
boardScope = groupPlay ? 'group' : 'global';
$('tab-group').hidden = !groupPlay;
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let best = 0;
try { best = Number(localStorage.getItem('papa-chop-best')) || 0; } catch {}
$('best').textContent = best;
if (ranked) $('identity').textContent = groupPlay ? 'Group challenge · Group + global rankings' : 'Telegram player · Compete on the leaderboard';
try { tg?.ready(); tg?.expand(); tg?.setHeaderColor('#171c30'); tg?.setBackgroundColor('#171c30'); if(tg?.isVersionAtLeast('7.7')) tg.disableVerticalSwipes(); } catch {}

function makeTree(seed) {
  const result = [0, 0]; let state = seed >>> 0;
  for (let i = 2; i < 6010; i++) {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    result.push(result.at(-1) ? 0 : (state % 5 === 0 ? 0 : 1 + state % 2));
  }
  return result;
}
let tree = makeTree(42717), score = 0, energy = 4200, side = 1;
let mode = 'ready', moves = [], run = null, started = 0, lastStamp = -100, lastFrame = 0;
let firstMove = true, animation = 0, particles = [], bump = 0, elapsed = 0, saving = false;
let audio, sound = true;
try { sound = localStorage.getItem('papa-chop-sound') !== 'off'; } catch {}
let power = 1, choppedThisSwing = 1;
const axeColors = ['#e4eeee', '#e4eeee', '#91f65d', '#ff625c'];
const W = 480, H = 570, floor = 488, segment = 74;

async function api(path, payload) {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...payload, initData, launch, rules: 3}), signal: controller.signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not connect. Try again.');
    return data;
  } finally { clearTimeout(timer); }
}
function tone(frequency = 160, length = .045) {
  if (!sound) return;
  try {
    audio ||= new (window.AudioContext || window.webkitAudioContext)();
    if (audio.state === 'suspended') audio.resume();
    const osc = audio.createOscillator(), gain = audio.createGain();
    osc.type = 'triangle'; osc.frequency.setValueAtTime(frequency, audio.currentTime);
    osc.frequency.exponentialRampToValueAtTime(45, audio.currentTime + length);
    gain.gain.setValueAtTime(.10, audio.currentTime); gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + length);
    osc.connect(gain); gain.connect(audio.destination); osc.start(); osc.stop(audio.currentTime + length);
  } catch {}
}
$('sound').innerHTML = `♪ <span>${sound ? 'ON' : 'OFF'}</span>`;
$('sound').setAttribute('aria-pressed', String(sound));
$('sound').setAttribute('aria-label', sound ? 'Mute sound' : 'Enable sound');
$('sound').onclick = () => {
  sound = !sound; $('sound').innerHTML = `♪ <span>${sound ? 'ON' : 'OFF'}</span>`;
  $('sound').setAttribute('aria-pressed', String(sound)); $('sound').setAttribute('aria-label', sound ? 'Mute sound' : 'Enable sound'); tone(400);
  try { localStorage.setItem('papa-chop-sound', sound ? 'on' : 'off'); } catch {}
};
function chopSound(strength) {
  if (!sound) return;
  try {
    audio ||= new (window.AudioContext || window.webkitAudioContext)();
    if (audio.state === 'suspended') audio.resume();
    const duration = .09, samples = Math.floor(audio.sampleRate * duration);
    const buffer = audio.createBuffer(1, samples, audio.sampleRate), wave = buffer.getChannelData(0);
    for (let i=0;i<samples;i++) wave[i] = (Math.random()*2-1)*Math.exp(-i/(samples*.15));
    const noise=audio.createBufferSource(), filter=audio.createBiquadFilter(), gain=audio.createGain();
    noise.buffer=buffer; filter.type='lowpass'; filter.frequency.value=1100+strength*180; gain.gain.value=.30;
    noise.connect(filter);filter.connect(gain);gain.connect(audio.destination);noise.start();
    const knock=audio.createOscillator(), body=audio.createGain();
    knock.type='triangle';knock.frequency.setValueAtTime(210-strength*20,audio.currentTime);
    knock.frequency.exponentialRampToValueAtTime(65,audio.currentTime+.08);
    body.gain.setValueAtTime(.22,audio.currentTime);body.gain.exponentialRampToValueAtTime(.001,audio.currentTime+.10);
    knock.connect(body);body.connect(audio.destination);knock.start();knock.stop(audio.currentTime+.11);
  } catch {}
}
async function start() {
  if (mode === 'loading' || saving) return;
  mode = 'loading'; $('start').disabled = true; $('start').textContent = 'GETTING THE AXE…';
  try {
    let seed = crypto.getRandomValues(new Uint32Array(1))[0];
    if (ranked) {
      const data = await api('/api/start', {}); if(data.rules !== 3) throw new Error('Please reload the game.'); groupPlay = data.group; $('tab-group').hidden = !groupPlay; run = data.run; seed = data.seed; best = data.best;
      $('best').textContent = best;
    }
    tree = makeTree(seed); score = 0; energy = 4200; side = 1; moves = []; firstMove = true;
    elapsed = 0; lastStamp = -100; particles = []; animation = 0; bump = 0; power = 1; choppedThisSwing = 1; updatePower(0);
    $('score').textContent = '0'; $('level').textContent = 'TAP A SIDE TO START';
    $('overlay').hidden = true; $('leaders').disabled = true; mode = 'playing'; $('hint').textContent = 'TAP LEFT / RIGHT · OR USE ← → KEYS';
    $('left').focus({preventScroll: true});
  } catch (error) {
    mode = 'ready'; $('save-status').textContent = error.name === 'AbortError' ? 'Connection timed out. Tap to retry.' : error.message;
  } finally {
    $('start').disabled = false; $('start').innerHTML = 'LET’S CHOP <span>→</span>';
  }
}
$('start').onclick = start;
function emitChips(which) {
  if (reduced) return;
  for (let i = 0; i < 9; i++) particles.push({x:240, y:floor-32, vx:(which === 1 ? 1 : -1)*(3+Math.random()*6), vy:-2-Math.random()*5, life:1, size:3+Math.random()*6});
}
function powerLevel(logs, stamp, current) {
  if (logs >= 350) return 3;
  if (logs >= 50 && stamp <= 15000) return Math.max(2, current);
  return current;
}
function swing(pattern, logs, which, strength) {
  if (pattern[logs] === which) return {score: logs, dead: true};
  for (let step = 0; step < strength; step++) {
    if (step && (pattern[logs] === which || pattern[logs + 1] === which)) break;
    logs++;
    if (pattern[logs] === which) return {score: logs, dead: true};
  }
  return {score: logs, dead: false};
}
function updatePower(stamp) {
  const oldPower = power;
  power = powerLevel(score, stamp, power);
  const label = ['','CLASSIC ×1','GREEN ×2','RED ×3'][power];
  $('power-badge').textContent = label;
  $('power-badge').dataset.level = power;
  $('power-hint').textContent = power === 3 ? 'MAX POWER · Up to 3 logs per swing' : power === 2 ? `${Math.max(0,350-score)} logs to RED ×3` : stamp <= 15000 ? `50 logs in 15s for GREEN ×2 · ${Math.max(0,15-stamp/1000).toFixed(1)}s left` : `${Math.max(0,350-score)} logs to RED ×3 · Try again for green`;
  if (power > oldPower) {
    $('power-toast').textContent = `${label} UNLOCKED!`;
    $('power-toast').classList.remove('show'); void $('power-toast').offsetWidth; $('power-toast').classList.add('show');
    tone(400 + power * 100, .16);
    try { if(tg?.isVersionAtLeast('6.1')) tg.HapticFeedback.notificationOccurred('success'); } catch {}
  }
}
function chop(which) {
  if (mode !== 'playing') return;
  const now = performance.now();
  if (firstMove) { started = now; firstMove = false; lastFrame = now; }
  const stamp = Math.round(now - started);
  if (stamp - lastStamp < 55) return;
  if (moves.length) energy -= stamp - lastStamp;
  if (energy <= 0 || stamp > 180000) return end('Time’s up!', 'Keep a rhythm. Every chop adds time.');
  lastStamp = stamp; moves.push([which, stamp]); side = which;
  const outcome = swing(tree, score, which, power);
  choppedThisSwing = outcome.score - score; score = outcome.score;
  if (choppedThisSwing) {
    energy = Math.min(5000, energy + Math.max(75, 310 - score * .6));
    animation = 1; bump = reduced ? 0 : 4 + power; emitChips(which); chopSound(power);
    try { if(tg?.isVersionAtLeast('6.1')) tg.HapticFeedback.impactOccurred('light'); } catch {}
  }
  $('score').textContent = score;
  $('level').textContent = score >= 350 ? 'RED AXE · MAX POWER' : score >= 50 ? 'BIG CHOP ENERGY' : 'FRESH CUTS';
  if (outcome.dead) return end('Branch happens.', 'Switch sides before a branch reaches Papa.');
  updatePower(stamp);
  if (moves.length >= 2000) end('Legendary run!', 'Two thousand swings. That’s a whole forest.');
}
async function end(title, copy) {
  if (mode !== 'playing') return;
  mode = 'over'; $('leaders').disabled = false; tone(80, .22);
  $('panel-tag').textContent = 'TAKE A BREATHER'; $('panel-title').textContent = title; $('panel-copy').textContent = copy;
  $('result').hidden = false; $('result-score').textContent = score;
  $('start').innerHTML = 'CHOP AGAIN <span>↻</span>'; $('overlay').hidden = false;
  $('flash').classList.remove('hit'); void $('flash').offsetWidth; $('flash').classList.add('hit');
  try { if(tg?.isVersionAtLeast('6.1')) tg.HapticFeedback.notificationOccurred('error'); } catch {}
  if (ranked && run && moves.length) {
    saving = true; $('start').disabled = true; $('save-status').textContent = 'Saving your run…';
    try {
      const data = await api('/api/finish', {run, moves});
      best = data.best; $('best').textContent = best;
      $('save-status').textContent = `Saved · Personal best ${best} · Rank #${data.rank}`;
    } catch (error) {
      $('save-status').textContent = 'Score not saved. Check your connection and try a new run.';
    } finally { saving = false; $('start').disabled = false; }
  } else {
    const isBest = score > best; best = Math.max(score, best); $('best').textContent = best;
    try { localStorage.setItem('papa-chop-best', String(best)); } catch {}
    $('save-status').textContent = isBest ? 'New device best! Play in Telegram to join the rankings.' : 'Device best saved. Open from Telegram for ranked play.';
  }
}
for (const [id, which] of [['left',1], ['right',2]]) {
  $(id).addEventListener('pointerdown', e => { if(e.button && e.button !== 0) return; e.preventDefault(); chop(which); });
  $(id).addEventListener('click', e => { if(e.detail === 0) chop(which); });
}
canvas.addEventListener('pointerdown', e => { e.preventDefault(); const r = canvas.getBoundingClientRect(); chop(e.clientX < r.left + r.width/2 ? 1 : 2); });
window.addEventListener('keydown', e => {
  if ($('leaderboard').open) return;
  const which = ['ArrowLeft','a','A'].includes(e.key) ? 1 : ['ArrowRight','d','D'].includes(e.key) ? 2 : 0;
  if (which) {e.preventDefault(); if(!e.repeat) chop(which);}
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden && mode === 'playing' && !firstMove) end('Taking a break?', 'Start a fresh run when you’re ready.');
});

async function loadLeaders() {
  $('board-status').textContent = 'Loading scores…'; $('ranks').replaceChildren(); $('refresh-leaders').disabled = true;
  for(const type of ['global','group','personal']) $('tab-'+type).setAttribute('aria-pressed',String(boardScope===type));
  $('board-title').textContent = boardScope === 'personal' ? 'Your bests' : boardScope === 'group' ? 'Group bests' : 'Top choppers';
  $('board-sub').textContent = boardScope === 'personal' ? 'Your recent runs' : boardScope === 'group' ? 'Only runs started from this group’s Play button' : 'All-time · All Telegram players';
  try {
    let data;
    if(ranked) {
      data = await api('/api/leaderboard', {board:boardScope});
      groupPlay = data.group; $('tab-group').hidden = !groupPlay;
    } else {
      if(boardScope==='personal') {
        $('board-status').textContent = `Your device best: ${best}. Open the bot to save your personal run history.`;return;
      }
      const response = await fetch('/api/leaderboard', {signal: AbortSignal.timeout(10000)});
      if (!response.ok) throw new Error(); data = await response.json();
    }
    for (const player of data.players) {
      const li = document.createElement('li'), name = document.createElement('span'), value = document.createElement('strong');
      name.textContent = player.name; value.textContent = player.score; li.append(name, value); $('ranks').append(li);
    }
    $('board-status').textContent = boardScope==='personal' ? `Personal best ${data.best} · Global rank #${data.rank} · Latest 10 runs from the last 30 days` : data.players.length ? 'Chop your way to the top.' : 'The forest is quiet. Set the first score!';
  } catch { $('board-status').textContent = 'Scores are unavailable right now. Try refreshing.'; }
  finally { $('refresh-leaders').disabled = false; }
}
for(const type of ['global','group','personal']) $('tab-'+type).onclick = () => {boardScope=type;loadLeaders();};
$('leaders').onclick = () => { if(mode === 'playing') return; $('leaderboard').showModal(); loadLeaders(); };
$('close-leaders').onclick = () => $('leaderboard').close();
$('refresh-leaders').onclick = loadLeaders;
$('leaderboard').addEventListener('click', e => {if(e.target === $('leaderboard')) {const r=e.target.getBoundingClientRect(); if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom) e.target.close();}});

// Original canvas game art: a layered woodland, timber, and an animated lumberjack.
function rect(x,y,w,h,color) {ctx.fillStyle=color;ctx.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));}
function poly(points,color) {ctx.fillStyle=color;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fill();}
function ellipse(x,y,rx,ry,color) {ctx.fillStyle=color;ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);ctx.fill();}
function pine(x,y,s,color) {
  rect(x-5*s,y,10*s,80*s,color);
  for(let j=0;j<3;j++) poly([[x,y-125*s+j*35*s],[x-(38+j*7)*s,y-42*s+j*35*s],[x+(38+j*7)*s,y-42*s+j*35*s]],color);
}
function background(t) {
  const sky=ctx.createLinearGradient(0,0,0,H);sky.addColorStop(0,'#79c9cf');sky.addColorStop(.65,'#c6e8be');sky.addColorStop(1,'#e0e7a4');ctx.fillStyle=sky;ctx.fillRect(0,0,W,H);
  ellipse(390,87,42,42,'#f9efad');ellipse(390,87,52,52,'#f9efad22');
  for(let i=0;i<4;i++) {const x=(i*159+22+(reduced?0:t*.002))%640-80;rect(x,70+i%2*48,75,11,'#ffffff55');rect(x+20,61+i%2*48,38,10,'#ffffff55');}
  poly([[0,277],[75,187],[147,246],[264,151],[353,239],[408,207],[480,266],[480,440],[0,440]],'#8ebbb1');
  poly([[208,201],[264,151],[309,201],[280,190],[266,181],[246,196]],'#d5e1cb');
  for(let i=0;i<9;i++) pine(i*65-20,329+(i%3)*13,.85,'#70a99b');
  for(let i=0;i<7;i++) pine(i*89-25,388+(i%2)*20,1.15,'#438b7c');
  for(const [x,y,s] of [[-12,419,1.9],[468,430,1.7],[77,405,1],[388,433,1]]) pine(x,y,s,'#286c61');
  poly([[0,443],[74,435],[153,451],[227,439],[344,449],[422,431],[480,445],[480,H],[0,H]],'#6f9e59');
  rect(0,486,W,84,'#365e42');rect(0,486,W,8,'#add575');rect(0,494,W,7,'#517d45');
  for(let i=0;i<30;i++){const x=(i*73)%480,y=510+(i*17)%57;rect(x,y,4+i%4*3,3,i%2?'#466c45':'#294f3c');}
  for(let i=0;i<16;i++){let x=i*33;rect(x,478-(i%3)*5,3,9,'#aecb77');rect(x+4,483-(i%3)*5,3,5,'#83b564');}
  ellipse(245,497,112,13,'#183d3d55');
  // Stump and small woodland mushrooms.
  rect(195,476,90,20,'#86553d');ellipse(240,476,45,10,'#efc587');ellipse(240,476,31,6,'#b48455');ellipse(240,476,24,4,'#e5b977');
  for(const [x,y] of [[44,470],[417,479]]){rect(x-2,y-2,5,12,'#f2d7ae');ellipse(x,y-3,11,6,'#e58055');rect(x-5,y-6,3,3,'#ffe6af');}
}
function logPiece(y,branch,index) {
  rect(195,y,90,segment+1,'#9a603d');rect(199,y,17,segment+1,'#ba7b49');rect(216,y,40,segment+1,'#b17141');rect(267,y,18,segment+1,'#704b36');
  rect(202,y+segment-4,80,4,'#805035');rect(207,y+10+(index%3)*4,5,22,'#d09758');rect(241,y+24,5,31,'#875032');rect(256,y+9,4,18,'#d19051');
  if(index%3===1){ellipse(228,y+39,9,14,'#8d5736');ellipse(228,y+39,4,8,'#b9804a');}
  if(branch){
    const left=branch===1;
    ctx.save();if(!left){ctx.translate(480,0);ctx.scale(-1,1);}
    poly([[198,y+42],[157,y+40],[143,y+24],[108,y+24],[108,y+12],[150,y+12],[170,y+27],[198,y+27]],'#784d36');
    rect(112,y+12,36,5,'#b27e4d');rect(147,y+6,10,22,'#855537');rect(149,y+6,4,14,'#b6824c');rect(168,y+28,29,5,'#b5814e');
    ctx.restore();
  }
}
function papa(){window.PapaMascot.draw(ctx,{x:side===1?145:335,y:floor,side,animation,reduced,power});}
function draw(now) {
  const delta=Math.min(40,now-(lastFrame||now));lastFrame=now;
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,W,H);ctx.save();
  if(bump>0){ctx.translate(Math.sin(now*.08)*bump,0);bump=Math.max(0,bump-delta*.05);}
  background(now);
  const drop=reduced?0:animation*segment*Math.min(choppedThisSwing,2);
  for(let i=8;i>=0;i--) logPiece(floor-segment*(i+1)-drop,tree[score+i]||0,score+i);
  papa();
  if(!reduced) for(const p of particles){p.x+=p.vx*delta/16;p.y+=p.vy*delta/16;p.vy+=.25*delta/16;p.life-=delta/500;ctx.globalAlpha=Math.max(0,p.life);rect(p.x,p.y,p.size,p.size*.65,'#f3c785');}ctx.globalAlpha=1;
  particles=particles.filter(p=>p.life>0);animation=Math.max(0,animation-delta/120);ctx.restore();
  let remaining=energy;
  if(mode==='playing'&&!firstMove){elapsed=now-started;remaining-=Math.max(0,elapsed-lastStamp);if(remaining<=0||elapsed>180000)end('Time’s up!','Keep a rhythm. Every chop adds time.');}
  const percent=Math.max(0,Math.min(100,remaining/50));$('time-fill').style.width=`${percent}%`;$('time-fill').style.background=percent<25?'#ff795d':'#d6fa57';
  if(Math.floor(now/250)!==Math.floor((now-delta)/250)) {
    document.querySelector('.time-track').setAttribute('aria-valuenow',String(Math.round(percent)));
    if(mode==='playing') updatePower(firstMove ? 0 : Math.round(elapsed));
  }
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);
