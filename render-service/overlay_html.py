OVERLAY_HTML = """<!doctype html><html><head><meta charset=utf-8><style>
html,body{margin:0;background:transparent;width:720px;height:1280px;overflow:hidden;font-family:'DejaVu Sans',sans-serif}
#logo{position:absolute;left:510px;top:50px;width:180px;height:180px;filter:drop-shadow(0 12px 28px rgba(0,0,0,.45));transform-origin:center;opacity:0}
#cap{position:absolute;left:40px;right:40px;bottom:230px;display:flex;justify-content:center}
#card{background:rgba(18,18,22,.86);border-radius:34px;padding:26px 34px;direction:rtl;text-align:center;line-height:1.55;font-size:54px;font-weight:700;color:#fff;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.w{display:inline-block;margin:0 7px;opacity:.55;transition:none}
.w.on{opacity:1;color:#FF8A3D}
.w.done{opacity:1;color:#fff}
</style></head><body><div id=logo></div><div id=cap><div id=card></div></div>
<script>
const LOGOS=__LOGOS__;const W=__WORDS__;const PH=__PHRASES__;
const logo=document.getElementById('logo'),card=document.getElementById('card');
let lastPh=-1;
function ease(x){x=Math.min(1,Math.max(0,x));return 1-Math.pow(1-x,3)}
function back(x){x=Math.min(1,Math.max(0,x));const c=1.70158,c3=c+1;return 1+c3*Math.pow(x-1,3)+c*Math.pow(x-1,2)}
window.setT=function(t){
  let pi=PH.findIndex(p=>t>=p.s-0.05&&t<p.e+0.25);
  if(pi!==lastPh){lastPh=pi;card.innerHTML=pi<0?'':PH[pi].idx.map(i=>`<span class=w id=w${i}>${W[i].w}</span>`).join('');card.parentElement.style.display=pi<0?'none':'flex'}
  if(pi>=0)PH[pi].idx.forEach(i=>{const e=document.getElementById('w'+i);if(!e)return;const w=W[i];e.className='w '+(t>=w.s&&t<w.e?'on':(t>=w.e?'done':''));
    if(t>=w.s&&t<w.s+0.18){e.style.transform='scale('+(1+0.25*(1-(t-w.s)/0.18))+')'}else e.style.transform=''});
  let op=0,sc=0;
  for(const w of W){if(!w.logo)continue;const a=w.s-0.05,d=1.7;if(t>=a&&t<a+d){const k=t-a;sc=back(k/0.35);op=Math.min(1,k/0.12)*Math.min(1,(d-k)/0.25);logo.innerHTML=LOGOS[w.logo]}}
  logo.style.opacity=op;logo.style.transform='scale('+sc+') rotate('+((1-Math.min(1,sc))*-12)+'deg)';
};
</script></body></html>"""
