'use strict';
window.PapaMascot=(()=>{
function drawWeapon(ctx,kind,x,y,scale=1){
 ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);
 const r=(x,y,w,h,c)=>{ctx.fillStyle=c;ctx.fillRect(x,y,w,h);};
 if(kind==='pistol'){r(0,-7,40,13,'#84919a');r(4,4,12,23,'#293544');r(29,-10,7,3,'#dce6dd');}
 if(kind==='smg'){r(0,-8,53,17,'#657980');r(43,-4,17,6,'#222f3e');r(17,8,10,26,'#4c6470');r(-15,-5,16,10,'#9eaeb0');r(4,-12,19,4,'#a3bfbe');}
 if(kind==='shotgun'){r(-18,-3,30,16,'#a76a3d');r(8,-8,72,6,'#b0b7ae');r(8,-1,72,6,'#596a73');r(35,5,26,10,'#c08650');r(5,10,9,14,'#6c442e');}
 if(kind==='rifle'){r(-19,-2,25,14,'#668778');r(1,-7,60,14,'#526c6b');r(56,-3,25,6,'#b6c8bf');r(20,-19,25,8,'#171f32');r(25,-11,6,6,'#6f8e8a');r(20,7,12,23,'#3b504e');}
 ctx.restore();
}
function draw(ctx,options={}) {
  const {x=0,y=0,side=1,animation=0,reduced=false,power=1,weapon='axe',flash=0,walk=0,crouch=false}=options;
  const axeColors=['','#e4eeee','#91f65d','#ff625c'];
  const rect=(x,y,w,h,c)=>{ctx.fillStyle=c;ctx.fillRect(Math.round(x),Math.round(y),w,h);};
  const ellipse=(x,y,rx,ry,c)=>{ctx.fillStyle=c;ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);ctx.fill();};
  const poly=(points,c)=>{ctx.fillStyle=c;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fill();};
  ctx.save();ctx.translate(x,y);if(side===2)ctx.scale(-1,1);
  if(crouch)ctx.scale(1,.48);
  const stride=Math.sin(walk)*.34;
  const swinging = animation > .45;
  ctx.translate(0,reduced?0:-Math.sin(animation*Math.PI)*4);
  ellipse(-3,0,42,8,'#203c3d55');
  // Broad silhouette, oversized purple jacket, dark trousers, bright sneakers.
  for(const side of [-1,1]){ctx.save();ctx.translate(side*16,-33);ctx.rotate(side*stride);rect(-12,0,24,30,'#252a38');rect(-15,24,32,12,'#eee5c9');rect(-15,21,32,10,'#6445a1');rect(-5,23,17,3,'#e8be55');ctx.restore();}
  ellipse(-2,-60,39,36,'#393448');rect(-40,-81,77,43,'#393448');
  rect(-12,-91,30,62,'#252c3b');rect(-17,-83,6,48,'#debd62');rect(18,-83,5,48,'#debd62');
  poly([[-40,-67],[-20,-78],[-19,-56],[-32,-44]],'#397c79');poly([[24,-78],[37,-68],[35,-43],[24,-54]],'#397c79');
  poly([[-35,-56],[-22,-58],[-28,-45]],'#d99a63');poly([[24,-54],[34,-50],[27,-39]],'#cba766');
  rect(-35,-39,69,9,'#56428b');rect(-35,-83,17,8,'#71618a');rect(23,-82,13,8,'#71618a');
  // Rounded cheeks and sunglasses keep the friendly Biggie-inspired face readable.
  ellipse(-1,-108,28,27,'#935b35');rect(-24,-124,46,28,'#995f36');
  ellipse(-26,-108,6,8,'#b47845');ellipse(23,-108,5,8,'#a76a3b');
  rect(-25,-119,49,5,'#e8c25f');rect(-23,-117,20,13,'#182834');rect(2,-117,20,13,'#182834');rect(-5,-114,9,4,'#192832');
  rect(-19,-115,10,3,'#516674');rect(6,-115,10,3,'#516674');ellipse(1,-100,8,4,'#b67b49');
  rect(-9,-95,21,3,'#493326');rect(10,-97,6,3,'#493326');rect(-6,-88,20,4,'#342925');
  // Tilted crown and gold chain.
  ctx.save();ctx.translate(-3,-130);ctx.rotate(-.14);
  poly([[-27,0],[-30,-23],[-15,-13],[-4,-30],[8,-14],[25,-25],[25,0]],'#efbd47');
  rect(-27,-3,52,8,'#d29730');rect(-22,-1,42,3,'#ffe092');rect(-8,-13,7,8,'#8e55b7');ctx.restore();
  ctx.strokeStyle='#ebc455';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(-14,-87);ctx.quadraticCurveTo(0,-53,20,-84);ctx.stroke();
  ellipse(4,-65,8,9,'#efc35a');ellipse(4,-65,4,5,'#c68f32');
  if(weapon!=='axe'){
    rect(20,-72,29,20,'#393448');rect(44,-69,16,16,'#a66a3c');
    drawWeapon(ctx,weapon,51,-72,1);
    if(flash){poly([[125,-76],[146,-88],[140,-73],[154,-65],[125,-64]],'#ffda7f');}
    ctx.restore();return;
  }
  ctx.save();ctx.translate(20,-62);ctx.rotate(swinging?.6:-.45);
  rect(-3,-6,28,20,'#7854b6');rect(23,-4,16,16,'#a66a3c');
  rect(34,-44,8,81,'#6d4b37');rect(36,-43,3,78,'#d8a961');
  if(power===3){
    ctx.shadowColor='#180d23';ctx.shadowBlur=24;ctx.shadowOffsetX=5;ctx.shadowOffsetY=7;
    poly([[34,-48],[65,-55],[81,-32],[67,-6],[35,-16]],'#411b32');
    ctx.shadowOffsetX=0;ctx.shadowOffsetY=0;
  }
  if(power>1){ctx.shadowColor=power===3?'#b51f41':axeColors[power];ctx.shadowBlur=reduced?0:14;}
  poly([[39,-44],[63,-49],[74,-32],[64,-12],[39,-20]],axeColors[power]);
  ctx.shadowBlur=0;
  poly([[63,-49],[74,-32],[64,-12],[61,-18],[68,-32],[59,-45]],power===1?'#a3b9bd':power===2?'#3fa950':'#c8344b');
  rect(33,-42,11,20,'#b79244');rect(36,-39,4,14,'#f5d477');
  ctx.restore();ctx.restore();
}
return {draw,drawWeapon};})();
