export const DEFAULT_APPEARANCE=Object.freeze({mode:'dark',accent:'#a477ff'});
export const ACCENT_PRESETS=['#a477ff','#65a8ff','#62ceb0','#ed87ae','#eda86c','#b5becf'];
export function normalizeAppearance(raw){return {mode:['dark','light','system'].includes(raw?.mode)?raw.mode:'dark',accent:/^#[a-f\d]{6}$/i.test(raw?.accent||'')?raw.accent.toLowerCase():DEFAULT_APPEARANCE.accent};}
function rgb(hex){return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));}
function hex(parts){return '#'+parts.map(x=>Math.round(x).toString(16).padStart(2,'0')).join('');}
function luminance(c){return rgb(c).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);}
export function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
export function themeTokens(raw,systemDark=false){const p=normalizeAppearance(raw);const dark=p.mode==='dark'||(p.mode==='system'&&systemDark);const surface=dark?'#232235':'#ffffff';let ink=p.accent;const target=dark?[255,255,255]:[0,0,0];const start=rgb(ink);for(let i=1;contrast(ink,surface)<4.5&&i<=100;i++)ink=hex(start.map((v,k)=>v+(target[k]-v)*i/100));return {...p,dark,ink,onAccent:contrast(p.accent,'#101018')>=contrast(p.accent,'#ffffff')?'#101018':'#ffffff'};}
export function applyAppearance(raw){const t=themeTokens(raw,matchMedia('(prefers-color-scheme: dark)').matches);const root=document.documentElement;root.dataset.theme=t.dark?'dark':'light';root.style.setProperty('--accent',t.accent);root.style.setProperty('--accent-ink',t.ink);root.style.setProperty('--on-accent',t.onAccent);return t;}
