// USE_MOCK=true returns sample data from docs/api_contract.md. Set to false when the Hub API is ready.
const USE_MOCK=true,BASE='/api/v1',S=sessionStorage,OFF=['LIBRARY','ACCOUNTING','STUDENT_AFFAIRS'];
const DEF={LIBRARY:{status:'HOLD',reason:'UNPAID_FINES'},ACCOUNTING:{status:'CLEARED',reason:null},STUDENT_AFFAIRS:{status:'CLEARED',reason:null}};
const U={student:{user_id:1,username:'student',role:'student',office:null,student_id:'2023-59928',display_name:'Rhea B. Morales'},
staff:{user_id:2,username:'staff',role:'staff',office:'LIBRARY',student_id:null,display_name:'Library Staff'},
admin:{user_id:3,username:'admin',role:'admin',office:null,student_id:null,display_name:'Hub Admin'}};
const ST=[['MORALES, Rhea B.','2023-***28','AGRI','HOLD'],['NAVARRO, Mark D.','2026-***17','EDMATH','CLEARED'],['DELA CRUZ, Mark C.','2024-***81','IS','HOLD'],['MORALES, Paolo G.','2023-***51','EDMATH','CLEARED']].map(([name,student_id,program_code,overall])=>({name,student_id,program_code,overall}));
function mock(m,p,b){
const e=(s,t)=>{throw{status:s,message:t}},cl=()=>JSON.parse(S.cl||JSON.stringify(DEF)),ov=c=>OFF.every(o=>c[o].status==='CLEARED')?'CLEARED':'HOLD',u=U[(S.token||'').slice(5)];let r;
if(p==='/auth/login')return U[b.username]?{access_token:'mock-'+b.username,token_type:'Bearer',expires_in:1800,user:U[b.username]}:e(401,'Wrong username or password');
if(p.startsWith('/slips/'))return{valid:p.includes('/demo/'),reason:'SIGNATURE_MISMATCH',student_id:'2023-***28',overall:'CLEARED',issued_at:new Date(),expires_at:new Date(Date.now()+6048e5)};
if(!u)e(401,'Please sign in');
if(p==='/auth/me')return u;
if(p==='/deadline')return{final_deadline:'2026-12-14'};
if(p.startsWith('/clearance/summary'))return{total_students:40,cleared:12,hold:28};
if(r=p.match(/^\/clearance\/([^/]+)\/slip$/)){if(ov(cl())!=='CLEARED')e(409,'Not cleared yet');return{slip_id:'demo',issued_at:new Date(),expires_at:new Date(Date.now()+6048e5),verify_url:location.origin+'/verify.html?slip=demo',qr_png_base64:null}}
if(r=p.match(/^\/clearance\/([^/]+)\/offices\/(\w+)$/)){const c=cl();c[r[2]]={status:b.status,reason:b.status==='HOLD'?b.reason:null};S.cl=JSON.stringify(c);return{office:r[2],status:b.status}}
if(r=p.match(/^\/clearance\/([^/]+)$/)){const c=cl();return{student_id:r[1],overall:ov(c),offices:OFF.map(o=>({office:o,...c[o],updated_at:'2026-11-20T22:05:00+08:00'}))}}
if(p.startsWith('/students')){const q=new URLSearchParams(p.split('?')[1]).get('overall');return{data:ST.filter(x=>!q||x.overall===q)}}
if(p==='/affairs/records')return{ok:1};
if(p==='/imports/run')return{status:'RUNNING'};
if(p==='/imports')return{data:[{filename:'library_export_2026-11-20.xml',status:'ACCEPTED',accepted_rows:27,rejected_rows:2},{filename:'accounting_balances_2026-11-20.csv',status:'REJECTED',reject_reason:'HASH_MISMATCH',accepted_rows:0,rejected_rows:0}]};
if(p==='/audit-log?verify=true')return{chain_valid:true};
if(p==='/audit-log')return{data:[{ts:'2026-11-20T22:10:00+08:00',actor_role:'admin',action:'IMPORT_REJECTED',target_id:'accounting_balances'},{ts:'2026-11-20T22:05:00+08:00',actor_role:'staff',action:'SIGN_OFF',target_id:'2026-***17'}]};
if(p.startsWith('/reports/'))return new Blob(['student_id,overall\n2023-***28,HOLD\n']);
e(404,'Not found')}
async function api(m,p,b,raw){try{
if(USE_MOCK){await new Promise(r=>setTimeout(r,200));return mock(m,p,b)}
const r=await fetch(BASE+p,{method:m,headers:{'Content-Type':'application/json',...(S.token?{Authorization:'Bearer '+S.token}:{})},body:b?JSON.stringify(b):undefined});
if(raw&&r.ok)return r.blob();
const d=await r.json().catch(()=>({}));
if(!r.ok)throw{status:r.status,message:d.error?.message||'Something went wrong'};return d
}catch(x){if(x.status===401&&S.token){S.clear();location='index.html'}throw x.status?x:{status:0,message:'Cannot reach the server'}}}
