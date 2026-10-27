// featured plate (if present): thumb shows instantly, swap to full-res when it loads
const fe=document.getElementById('featimg');
if(fe){const f=fe.closest('.feat').dataset.full,hi=new Image();hi.onload=()=>{fe.src=f};hi.src=f;}

// lightbox + link chips (shared)
const PHOTOS={{PHOTOS_JSON}};
const photoEls=[...document.querySelectorAll('[data-i]')];   // DOM order == visual reading order
const RICO='<svg class="ico" viewBox="0 0 20 20" fill="currentColor"><circle cx="10" cy="11" r="8" opacity=".18"/><path d="M16.7 8.9a1.5 1.5 0 10-2.2-1.3 8.4 8.4 0 00-3.9-1l.7-3.1 2.2.5a1.1 1.1 0 101.1-1.2 1.1 1.1 0 00-1 .6l-2.5-.6-.95 4.2a8.4 8.4 0 00-4 1A1.5 1.5 0 103.3 8.9a3 3 0 00-.05.6c0 2.9 3 5.2 6.75 5.2s6.75-2.3 6.75-5.2a3 3 0 00-.05-.6zM7 10.4a1.05 1.05 0 112.1 0 1.05 1.05 0 01-2.1 0zm5.85 2.9c-.85.85-3.55.9-3.85.9s-3-.05-3.85-.9a.35.35 0 01.5-.5c.6.6 2.85.65 3.35.65s2.75-.05 3.35-.65a.35.35 0 11.5.5zm-.7-1.85a1.05 1.05 0 110-2.1 1.05 1.05 0 010 2.1z"/></svg>';
const IGICO='<svg class="ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3.5" y="3.5" width="13" height="13" rx="4"/><circle cx="10" cy="10" r="3.2"/><circle cx="14" cy="6" r="1" fill="currentColor" stroke="none"/></svg>';
const PXICO='<svg class="ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="3" y="3" width="14" height="14" rx="3"/><circle cx="10" cy="10" r="3.1"/></svg>';
const lb=document.getElementById('lb'),lbi=document.getElementById('lbi'),lbtitle=document.getElementById('lbtitle'),lbmeta=document.getElementById('lbmeta'),lblinks=document.getElementById('lblinks'),lbalts=document.getElementById('lbalts');
const GROUPED=document.documentElement.dataset.groups==='1';   // feed: a tile may hold several frames of one scene
let idx=-1,curAr=1;
function chip(cls,ico,label,url){return url
  ?'<a class="lk '+cls+'" href="'+url+'" target="_blank" rel="noopener">'+ico+label+'</a>'
  :'';}   // no link, no chip
// derive the frame's TRUE dominant colour: a hue histogram weighted by saliency (saturation ×
// mid-tone), so a small vivid region (coral stairs, gold sky, a bird's brown) beats a big muddy
// sky. Emits the winning cluster's real hue/sat/light — warm, cool, or silver when desaturated.
function domGlow(img){try{if(!img||!img.complete||!img.naturalWidth)return null;
  var N=28,c=document.createElement('canvas');c.width=c.height=N;var x=c.getContext('2d');
  x.drawImage(img,0,0,N,N);var d=x.getImageData(0,0,N,N).data;
  var B=18,cw=new Array(B).fill(0),hh=new Array(B).fill(0),ss=new Array(B).fill(0),ll=new Array(B).fill(0),cn=new Array(B).fill(0);
  var totL=0,totS=0,pN=0;
  for(var k=0;k<d.length;k+=4){
    var R=d[k]/255,G=d[k+1]/255,Bb=d[k+2]/255,mx=Math.max(R,G,Bb),mn=Math.min(R,G,Bb),l=(mx+mn)/2;
    pN++;totL+=l;
    if(mx===mn)continue;
    var dd=mx-mn,s=l>0.5?dd/(2-mx-mn):dd/(mx+mn);
    totS+=s;
    if(s<0.16)continue;                               // drop washed-out fog/haze/sky so real colour regions compete
    var h=mx===R?(G-Bb)/dd+(G<Bb?6:0):mx===G?(Bb-R)/dd+2:(R-G)/dd+4;h*=60;
    var w=s*Math.max(0.3,1-Math.abs(l-0.5)*1.25);     // among genuinely-coloured pixels, compete by area×saturation
    var bi=Math.floor(h/360*B)%B;
    cw[bi]+=w;hh[bi]+=w*h;ss[bi]+=w*s;ll[bi]+=w*l;cn[bi]++;
  }
  var avgL=pN?totL/pN:0.5,avgS=pN?totS/pN:0;
  var sm=new Array(B);for(var i=0;i<B;i++)sm[i]=cw[i]+0.55*cw[(i+1)%B]+0.55*cw[(i+B-1)%B]; // smooth split clusters
  var best=-1,bv=0;for(var i=0;i<B;i++)if(sm[i]>bv){bv=sm[i];best=i;}
  var H=best>=0&&cw[best]>0?Math.round(((hh[best]/cw[best])%360+360)%360):216;
  if(H>=182&&H<=212)H=Math.round(H+(214-H)*0.45);          // nudge cyan-ish skies toward blue
  var clS=best>=0&&cw[best]>0?ss[best]/cw[best]:0;
  var frac=best>=0?cn[best]/pN:0;                            // how much of the frame is this colour
  var scale=Math.min(1,0.45+avgS*3.5)*Math.min(1,0.3+frac*6);// desaturated OR tiny-patch colour → toward silver
  var S=Math.round(Math.max(4,Math.min(68,clS*100*scale)));// cap so the glow is never garish
  var L=Math.round(Math.max(44,Math.min(72,(best>=0&&cw[best]>0?ll[best]/cw[best]:avgL)*100)));
  return 'hsl('+H+','+S+'%,'+L+'%)';
}catch(e){return null;}}
const GLOW_SAMPLED={darkroom:1,postcard:1};   // lightbox glow = photo's true dominant colour; cyanotype=fixed blue, lantern=fixed purple, others none
let curK=0,curFull='';
const LOADED=new Set();
function warm(u,cb){if(!u)return;if(LOADED.has(u)){cb&&cb();return;}const im=new Image();im.onload=()=>{LOADED.add(u);cb&&cb();};im.src=u;}
function fullAt(d){if(idx<0)return null;const p0=PHOTOS[+photoEls[idx].dataset.i],vs=GROUPED&&p0.v?p0.v:null;
  if(vs){const k=curK+d;if(k>=0&&k<vs.length)return PHOTOS[vs[k]].full;}
  const i=(idx+d+photoEls.length)%photoEls.length,q=PHOTOS[+photoEls[i].dataset.i];
  return GROUPED&&q.v?PHOTOS[q.v[d<0?q.v.length-1:0]].full:q.full;}
// sandboxed previews and some private modes refuse history/storage; never let that break the page
function setHash(u){try{history.replaceState(null,'',u);}catch(e){}}
function show(i,k){if(i<0||i>=photoEls.length)return;idx=i;k=k||0;curK=k;const el=photoEls[i],p0=PHOTOS[+el.dataset.i],timg=el.querySelector('img');
  const vs=GROUPED&&p0.v?p0.v:null,p=vs?PHOTOS[vs[k]]:p0,thumb=vs?p.th:timg.src;curAr=p.ar;
  if(GLOW_SAMPLED[document.documentElement.dataset.variant]){const _g=domGlow(timg);if(_g)document.documentElement.style.setProperty('--lbglow',_g);else document.documentElement.style.removeProperty('--lbglow');}
  curFull=p.full;lbi.onerror=()=>{lbi.onerror=null;lbi.src=thumb;};
  if(LOADED.has(p.full))lbi.src=p.full;else{lbi.src=thumb;warm(p.full,()=>{if(curFull===p.full)lbi.src=p.full;});}
  document.documentElement.classList.add('lb-lock');setTimeout(()=>{warm(fullAt(1));warm(fullAt(-1));},60);
  lbtitle.textContent=p.t;lbmeta.innerHTML=p.pl+'  &middot;  '+p.fn+(vs?'  &middot;  '+(k+1)+' of '+vs.length:'')+'  &middot;  '+(i+1)+' / '+photoEls.length;
  if(lbalts){lbalts.textContent='';lbalts.hidden=!vs;
    if(vs)vs.forEach((j,n)=>{const b=document.createElement('button');b.type='button';b.className='alt'+(n===k?' on':'');
      b.setAttribute('aria-pressed',n===k);b.setAttribute('aria-label','show '+PHOTOS[j].fn);b.title=PHOTOS[j].fn;
      const im=document.createElement('img');im.src=PHOTOS[j].th;im.alt='';b.append(im);
      b.addEventListener('click',e=>{e.stopPropagation();if(n!==k)show(i,n);});lbalts.append(b);});}
  let h='';p.r.forEach(s=>{h+=chip('reddit',RICO,s.s,s.url||('https://www.reddit.com/'+s.s));});
  h+=chip('ig',IGICO,'Instagram',p.ig);
  lblinks.innerHTML=h;
  lb.classList.remove('lb-side','lb-below');
  lb.classList.add(p.ar < innerWidth/innerHeight ? 'lb-side' : 'lb-below','open');
  if(p.id&&location.hash.slice(1)!==p.id)setHash('#'+p.id);}
// prev/next walks photo by photo: through every frame of a stack first, then on to the next tile
function step(d){const p0=PHOTOS[+photoEls[idx].dataset.i],vs=GROUPED&&p0.v?p0.v:null;
  if(vs){const k=curK+d;if(k>=0&&k<vs.length)return show(idx,k);}
  const i=(idx+d+photoEls.length)%photoEls.length,q=PHOTOS[+photoEls[i].dataset.i];
  show(i,d<0&&GROUPED&&q.v?q.v.length-1:0);}
addEventListener('resize',()=>{if(idx>=0&&lb.classList.contains('open')){const a=curAr;lb.classList.remove('lb-side','lb-below');lb.classList.add(a<innerWidth/innerHeight?'lb-side':'lb-below');}});
function close(){lb.classList.remove('open');document.documentElement.classList.remove('lb-lock');idx=-1;curFull='';lbi.src='';if(location.hash)setHash(location.pathname+location.search);}
// /photo#<camera-id> — permanent per-frame URL; the id is the camera filename stem
function openHash(){const id=decodeURIComponent(location.hash.slice(1)).replace(/^([A-Za-z]+\d+)[-._].*$/,'$1');if(!id)return;
  let k=photoEls.findIndex(el=>PHOTOS[+el.dataset.i].id===id),v=0;
  if(k<0&&GROUPED){const j=PHOTOS.findIndex(p=>p.id===id);              // a frame tucked behind its group's tile
    if(j>=0){k=photoEls.findIndex(el=>{const q=PHOTOS[+el.dataset.i];return q.v&&q.v.includes(j);});if(k>=0)v=PHOTOS[+photoEls[k].dataset.i].v.indexOf(j);}}
  if(k>=0){show(k,v);photoEls[k].scrollIntoView({block:'center'});}}
addEventListener('hashchange',openHash);addEventListener('load',openHash);
photoEls.forEach((el,i)=>el.addEventListener('click',()=>show(i)));
lb.addEventListener('click',e=>{if(e.target===lb||e.target.classList.contains('stage')||e.target===lbi)close();});
document.getElementById('lbprev').onclick=e=>{e.stopPropagation();step(-1);};
document.getElementById('lbnext').onclick=e=>{e.stopPropagation();step(1);};
document.getElementById('lbx').onclick=close;
addEventListener('keydown',e=>{if(!lb.classList.contains('open'))return;
  if(e.key==='Escape')close();else if(e.key==='ArrowLeft')step(-1);else if(e.key==='ArrowRight')step(1);});

// touch: swipe left/right for next/previous (the photo follows the finger), swipe down to close
(function(){let x0=null,y0=0,dx=0,dy=0,t0=0,axis='',busy=false;
  const EASE='cubic-bezier(.2,.75,.25,1)';
  const reset=()=>{lbi.style.transition='transform .24s '+EASE+', opacity .24s ease';lbi.style.transform='';lbi.style.opacity='';};
  lb.addEventListener('touchstart',e=>{if(busy||!lb.classList.contains('open')||e.touches.length!==1){x0=null;return;}
    x0=e.touches[0].clientX;y0=e.touches[0].clientY;dx=dy=0;axis='';t0=Date.now();lbi.style.transition='none';},{passive:true});
  lb.addEventListener('touchmove',e=>{if(x0===null)return;if(e.touches.length!==1){x0=null;reset();return;}
    dx=e.touches[0].clientX-x0;dy=e.touches[0].clientY-y0;
    if(!axis&&(Math.abs(dx)>8||Math.abs(dy)>8))axis=Math.abs(dx)>Math.abs(dy)?'x':'y';
    if(axis==='x'){e.preventDefault();lbi.style.transform='translate3d('+dx+'px,0,0)';lbi.style.opacity=String(1-Math.min(.35,Math.abs(dx)/innerWidth*.6));}
    else if(axis==='y'){e.preventDefault();const d=Math.max(0,dy);lbi.style.transform='translate3d(0,'+d+'px,0) scale('+(1-Math.min(.12,d/innerHeight*.3))+')';lbi.style.opacity=String(1-Math.min(.6,d/innerHeight));}},{passive:false});
  lb.addEventListener('touchend',()=>{if(x0===null)return;x0=null;const fast=Date.now()-t0<280;
    if(axis==='x'&&(Math.abs(dx)>innerWidth*.16||(fast&&Math.abs(dx)>35))){
      const d=dx<0?1:-1;busy=true;
      lbi.style.transition='transform .15s ease-in, opacity .15s ease-in';lbi.style.transform='translate3d('+(-d*innerWidth*.55)+'px,0,0)';lbi.style.opacity='0';
      setTimeout(()=>{lbi.style.transition='none';lbi.style.transform='translate3d('+(d*innerWidth*.3)+'px,0,0)';lbi.style.opacity='0';step(d);
        requestAnimationFrame(()=>requestAnimationFrame(()=>{reset();setTimeout(()=>{busy=false;},120);}));},150);}
    else if(axis==='y'&&(dy>innerHeight*.16||(fast&&dy>50))){reset();close();}
    else reset();});
  lb.addEventListener('touchcancel',()=>{x0=null;reset();});
})();

const root=document.documentElement,KEY='sadh-photos-theme';let saved=null;try{saved=localStorage.getItem(KEY);}catch(e){}if(saved)root.setAttribute('data-theme',saved);
document.getElementById('themebtn').onclick=()=>{const t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);try{localStorage.setItem(KEY,t);}catch(e){}};

// cursor-tracked light pool (any page that includes a .throwlight layer)
if(document.querySelector('.throwlight')&&!matchMedia('(prefers-reduced-motion:reduce)').matches){
  addEventListener('pointermove',e=>{root.style.setProperty('--throw-x',e.clientX+'px');root.style.setProperty('--throw-y',e.clientY+'px');},{passive:true});}

// local file:// support: rewrite root-relative asset and navigation paths when opened from disk
if(location.protocol==='file:'){
  const m=location.pathname.match(/^(.*\/_site)\//);
  const base=m?m[1]:location.pathname.replace(/\/index\.html$/,'').replace(/\/$/,'');
  const fixUrl=u=>(u&&u.startsWith('/')&&!u.startsWith('//'))?base+(u.endsWith('/')?u+'index.html':u):u;
  PHOTOS.forEach(p=>{p.full=fixUrl(p.full);p.th=fixUrl(p.th);});
  document.querySelectorAll('img[src^="/"]').forEach(im=>{im.setAttribute('src',fixUrl(im.getAttribute('src')));});
  document.querySelectorAll('a[href^="/"]').forEach(a=>{a.setAttribute('href',fixUrl(a.getAttribute('href')));});
}
