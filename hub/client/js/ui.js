const $=s=>document.querySelector(s);
// h('div',{class:'x'},child...) builds elements with textContent only (never innerHTML).
const h=(t,a={},...c)=>{const e=document.createElement(t);for(const k in a){const v=a[k];if(v===false||v==null)continue;k.startsWith('on')?e.addEventListener(k.slice(2),v):e.setAttribute(k,v===true?'':v)}c.flat().forEach(x=>{if(x!=null&&x!==false)e.append(x.nodeType?x:String(x))});return e};
const themeBtn=c=>{const b=h('button',{class:'btn alt',type:'button','aria-label':'Switch light or dark mode'}),set=t=>{document.documentElement.dataset.theme=t;try{localStorage.theme=t}catch(e){}b.textContent=c?(t==='dark'?'☀':'☾'):(t==='dark'?'☀ Light':'☾ Dark')};set(document.documentElement.dataset.theme||'light');b.onclick=()=>set(document.documentElement.dataset.theme==='dark'?'light':'dark');return b};
document.querySelectorAll('[data-themebtn]').forEach(e=>e.replaceChildren(themeBtn()));
const REASON={UNRETURNED_BOOKS:'You still have unreturned library books. Return them at the Library.',UNPAID_FINES:'You have an unpaid library fine. Settle it at the Library.',BALANCE_DUE:'You have an unpaid balance. Visit the Accounting office.',NO_ACCOUNTING_RECORD:"We can't find your payment record yet. Visit the Accounting office.",AFFAIRS_OUTSTANDING:'You have an unreturned item or pending requirement at Student Affairs.',ON_LOA:'You are on leave of absence, so clearance is not available.',NEEDS_REVIEW:'The office is checking a problem with your record. Please check back soon.'};
const badge=s=>h('span',{class:'badge '+(s==='CLEARED'?'ok':'hold')},s==='CLEARED'?'✓ CLEARED':'! HOLD');
const fmt=d=>d?new Date(d).toLocaleString('en-PH',{dateStyle:'medium',timeStyle:'short'}):'';
const office=o=>o.replace('_',' ');
function toast(t){const e=$('#toast');e.textContent=t;e.hidden=false;setTimeout(()=>e.hidden=true,3000)}
async function guard(roles){let u;try{u=await api('GET','/auth/me')}catch{location='index.html';return}
if(!roles.includes(u.role)){location='index.html';return}
$('#bar').replaceChildren(h('b',{},'DNSC e-Clearance'),h('nav',{class:'nav','aria-label':'Main'},...(NAV[u.role]||[]).map(([t,hr])=>h('a',{href:hr,'aria-current':hr===location.pathname.split('/').pop()?'page':false},t))),h('div',{class:'tools'},themeBtn(),bell(u),profileMenu(u)));return u}

const NAV={student:[['My clearance','student.html']],staff:[['Staff desk','staff.html'],['Reports','reports.html']],admin:[['Staff desk','staff.html'],['Reports','reports.html'],['Admin','admin.html']]};
const initials=n=>n.split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();
function profileMenu(u){const m=h('div',{class:'menu',hidden:true}),b=h('button',{class:'who-btn','aria-haspopup':'true','aria-expanded':'false',onclick:()=>{m.hidden=!m.hidden;b.setAttribute('aria-expanded',String(!m.hidden))}},h('span',{class:'av'},initials(u.display_name)),h('span',{class:'nm'},u.display_name),'▾'),w=h('div',{class:'prof'},b,m);
const close=()=>{m.hidden=true;b.setAttribute('aria-expanded','false')};
m.append(h('div',{class:'mh'},h('b',{},u.display_name),h('span',{class:'muted'},u.role+(u.office?' · '+office(u.office):'')+(u.student_id?' · '+u.student_id:''))),h('a',{href:'profile.html'},'My profile'),h('button',{class:'btn alt',onclick:()=>{S.clear();location='index.html'}},'Sign out'));
document.addEventListener('click',e=>{if(!w.contains(e.target))close()});document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});return w}

const STEP={UNRETURNED_BOOKS:'Return the borrowed books to the Library.',UNPAID_FINES:'Pay your library fine at the Library.',BALANCE_DUE:'Settle your balance at the Accounting office.',NO_ACCOUNTING_RECORD:'Visit the Accounting office so they can confirm your payment record.',AFFAIRS_OUTSTANDING:'Return the borrowed item or finish the pending requirement at Student Affairs.',ON_LOA:'Contact the Registrar about your enrollment status.',NEEDS_REVIEW:'Wait while the office checks your record. No action is needed from you yet.'};
const ref=(p,x)=>p+'-'+String(x).replace(/\D/g,'').slice(-5);
async function notes(u){const n=[],nm=u.display_name;
if(u.role==='student'){const [c,d]=await Promise.all([api('GET','/clearance/'+u.student_id),api('GET','/deadline')]);
c.offices.filter(o=>o.status!=='CLEARED').forEach(o=>{const on=office(o.office),why=REASON[o.reason]||o.reason;
n.push({t:on+' clearance is on hold',d:why,body:'Dear '+nm+',\n\nYour clearance at the '+on+' office is currently on hold.\n\nReason:\n'+why+'\n\nWhat happens next:\n1. '+(STEP[o.reason]||'Visit the '+on+' office.')+'\n2. The office updates your record. Your status changes once they sign off or the next import runs.\n3. Check your dashboard again to see the new status.\n\nThank you for your patience.\n\nReference: '+ref('CLR-'+o.office.slice(0,3),u.student_id)})});
if(c.overall==='CLEARED')n.push({t:'Congratulations! You are cleared',d:'Your clearance slip is ready.',body:'Dear '+nm+',\n\nCongratulations! Every office has signed off your clearance.\n\nWhat happens next:\n1. Open your dashboard and tap "Get my clearance slip".\n2. Show the QR code to the staff member who asks for it.\n3. Submit your clearance on or before '+d.final_deadline+'.\n\nThank you.\n\nReference: '+ref('CLR-ALL',u.student_id)});
n.push({t:'Deadline: '+d.final_deadline,d:'Clearance closes on '+d.final_deadline+'.',body:'Dear '+nm+',\n\nThis is a reminder that the clearance period closes on '+d.final_deadline+'. The date already skips weekends and Philippine public holidays.\n\nWhat to do:\n1. Check which offices are still on hold.\n2. Resolve them before the deadline.\n3. Get your clearance slip once every office is cleared.\n\nThank you.'})}
else{const s=await api('GET','/clearance/summary');
n.push({t:s.hold+' students on hold',d:s.cleared+' of '+s.total_students+' are cleared.',body:'Hello '+nm+',\n\n'+s.hold+' of '+s.total_students+' students are on hold, and '+s.cleared+' are cleared.\n\nWhat to do:\n1. Open the Staff desk and filter by On hold.\n2. Check the records for your office.\n3. Sign off students whose issues are resolved.\n\nThank you.'});
if(u.role==='admin'){const r=await api('GET','/imports');r.data.filter(i=>i.status==='REJECTED').forEach(i=>{const why=i.reject_reason||'unknown';
n.push({t:'Import rejected',d:i.filename+' ('+why+')',body:'Hello '+nm+',\n\nThe file '+i.filename+' was rejected ('+why+'). None of its rows were imported.\n\nWhat happens next:\n1. Check whether the file changed after it was signed.\n2. Ask the office to export and sign it again.\n3. Run the import again. The rejection is recorded in the audit log.\n\nReference: '+ref('IMP',i.filename)})})}}
return n}
const BELL='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>';
function bell(u){const key='seen_'+u.username,id=i=>i.t+'|'+i.d;let items=[],tab='all';
const seenSet=()=>{try{return new Set(JSON.parse(localStorage[key]||'[]'))}catch(e){return new Set()}},save=s=>{try{localStorage[key]=JSON.stringify([...s])}catch(e){}};
const dot=h('span',{class:'dot',hidden:true}),list=h('div',{class:'notes'}),tabs=h('div',{class:'tabs',role:'tablist'}),
mk=h('button',{class:'linkbtn',onclick:()=>{const s=seenSet();items.forEach(i=>s.add(id(i)));save(s);draw()}},'Mark all as read'),
lv=h('div',{},h('div',{class:'row'},h('span',{class:'nh'},'Notifications'),mk),tabs,list),dv=h('div',{hidden:true}),m=h('div',{class:'menu',hidden:true},lv,dv),
b=h('button',{class:'btn bellb','aria-label':'Notifications','aria-haspopup':'true','aria-expanded':'false'},new DOMParser().parseFromString(BELL,'image/svg+xml').documentElement,dot),w=h('div',{class:'prof'},b,m);
const back=()=>{m.classList.remove('detail');dv.hidden=true;lv.hidden=false},close=()=>{m.hidden=true;b.setAttribute('aria-expanded','false');back()},
show=i=>{m.classList.add('detail');lv.hidden=true;dv.hidden=false;dv.replaceChildren(h('div',{class:'row'},h('h2',{},i.t),h('button',{class:'x','aria-label':'Close',onclick:close},'✕')),h('button',{class:'linkbtn',onclick:back},'‹ All notifications'),h('div',{class:'msg'},i.body))};
const read=i=>{const z=seenSet();z.add(id(i));save(z);draw();show(i)};
function draw(){const s=seenSet(),un=items.filter(i=>!s.has(id(i)));dot.hidden=!un.length;
tabs.replaceChildren(...[['all','All'],['unread','Unread']].map(([k,t])=>h('button',{role:'tab','aria-selected':String(tab===k),onclick:()=>{tab=k;draw()}},t)));
const shown=tab==='all'?items:un;
list.replaceChildren(...(shown.length?shown.map(i=>h('div',{class:'note'+(s.has(id(i))?'':' unread'),tabindex:0,onclick:()=>read(i),onkeydown:e=>{if(e.key==='Enter')read(i)}},h('b',{},i.t),h('span',{class:'muted'},i.d))):[h('p',{class:'muted'},tab==='all'?"You're all caught up.":'No unread notifications.')]))}
b.onclick=()=>{m.hidden=!m.hidden;b.setAttribute('aria-expanded',String(!m.hidden));if(!m.hidden)back()};
document.addEventListener('click',e=>{if(!e.composedPath().includes(w))close()});document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
draw();notes(u).then(r=>{items=r;draw()}).catch(()=>{});return w}
