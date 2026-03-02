"""Web dashboard HTML — single-page, inline CSS+JS, token auth via localStorage."""

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minion Network</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,system-ui,sans-serif;background:#0d1117;color:#c9d1d9;padding:12px;font-size:14px}
h1{font-size:1.3em;color:#58a6ff;margin-bottom:8px;display:flex;align-items:center;gap:8px}
h1 span{font-size:.6em;color:#8b949e;font-weight:normal}
h2{font-size:1em;color:#8b949e;margin:16px 0 6px;text-transform:uppercase;letter-spacing:.5px;font-weight:600}
.grid{display:grid;grid-template-columns:1fr;gap:8px}
@media(min-width:768px){.grid{grid-template-columns:1fr 1fr}}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#8b949e;font-weight:600;padding:4px 8px;border-bottom:1px solid #30363d;white-space:nowrap}
td{padding:4px 8px;border-bottom:1px solid #21262d;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
.status-green{color:#3fb950}
.status-yellow{color:#d29922}
.status-red{color:#f85149}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}
.dot-green{background:#3fb950}
.dot-yellow{background:#d29922}
.dot-red{background:#f85149}
.msg{font-size:12px;padding:6px 8px;border-bottom:1px solid #21262d}
.msg-from{color:#58a6ff;font-weight:600}
.msg-to{color:#8b949e}
.msg-time{color:#484f58;font-size:11px;float:right}
.msg-content{color:#c9d1d9;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stats{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px}
.stat{text-align:center}
.stat-num{font-size:1.8em;font-weight:700;line-height:1}
.stat-label{font-size:.7em;color:#8b949e;text-transform:uppercase}
#error{color:#f85149;font-size:12px;margin-top:4px;display:none}
.empty{color:#484f58;padding:12px;text-align:center;font-style:italic}
#login{display:flex;justify-content:center;align-items:center;min-height:80vh;flex-direction:column;gap:12px}
#login h1{font-size:1.5em;margin-bottom:4px}
#login input{background:#161b22;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;padding:10px 14px;font-size:15px;width:280px;outline:none}
#login input:focus{border-color:#58a6ff}
#login button{background:#238636;color:#fff;border:none;border-radius:6px;padding:10px 24px;font-size:14px;cursor:pointer;font-weight:600}
#login button:hover{background:#2ea043}
#login .login-err{color:#f85149;font-size:13px;min-height:20px}
.logout{font-size:11px;color:#484f58;cursor:pointer;margin-left:auto}
.logout:hover{color:#f85149}
#app{display:none}
</style>
</head>
<body>

<div id="login">
  <h1>Minion Network</h1>
  <input id="token-input" type="password" placeholder="Cluster token" autofocus>
  <button onclick="tryLogin()">Connect</button>
  <div class="login-err" id="login-err"></div>
</div>

<div id="app">
  <h1>Minion Network <span id="clock"></span> <span class="logout" onclick="logout()">logout</span></h1>
  <div id="error"></div>
  <div class="stats" id="stats"></div>
  <div class="grid">
    <div>
      <h2>Agents</h2>
      <div class="card" id="agents"><div class="empty">loading...</div></div>
    </div>
    <div>
      <h2>Messages (last 20)</h2>
      <div class="card" id="messages"><div class="empty">loading...</div></div>
    </div>
  </div>
</div>

<script>
const STALE_MIN=5*60*1000,DEAD_MIN=15*60*1000;
let token='';
let refreshTimer=null;

function getToken(){return localStorage.getItem('minion_token')||'';}
function setToken(t){localStorage.setItem('minion_token',t);}
function clearToken(){localStorage.removeItem('minion_token');}

function authHeaders(){
  const h={};
  if(token)h['Authorization']='Bearer '+token;
  return h;
}

async function tryLogin(){
  const input=document.getElementById('token-input');
  const t=input.value.trim();
  if(!t){document.getElementById('login-err').textContent='Token required';return;}
  try{
    const r=await fetch('/who',{headers:{'Authorization':'Bearer '+t}});
    if(r.status===401){
      document.getElementById('login-err').textContent='Invalid token';
      return;
    }
    token=t;
    setToken(t);
    showApp();
  }catch(e){
    document.getElementById('login-err').textContent='Connection failed: '+e.message;
  }
}

function showApp(){
  document.getElementById('login').style.display='none';
  document.getElementById('app').style.display='block';
  refresh();
  if(refreshTimer)clearInterval(refreshTimer);
  refreshTimer=setInterval(refresh,2000);
}

function logout(){
  clearToken();
  token='';
  if(refreshTimer)clearInterval(refreshTimer);
  document.getElementById('app').style.display='none';
  document.getElementById('login').style.display='flex';
  document.getElementById('token-input').value='';
  document.getElementById('login-err').textContent='';
}

// Enter key on token input
document.getElementById('token-input').addEventListener('keydown',e=>{
  if(e.key==='Enter')tryLogin();
});

function age(ts){
  if(!ts)return Infinity;
  return Date.now()-new Date(ts).getTime();
}
function fmtAge(ms){
  if(ms===Infinity)return'never';
  const s=Math.floor(ms/1000);
  if(s<60)return s+'s';
  const m=Math.floor(s/60);
  if(m<60)return m+'m';
  return Math.floor(m/60)+'h '+m%60+'m';
}
function statusClass(ts){
  const a=age(ts);
  if(a<STALE_MIN)return'green';
  if(a<DEAD_MIN)return'yellow';
  return'red';
}
function esc(s){
  if(!s)return'';
  const d=document.createElement('div');
  d.textContent=s;
  return d.innerHTML;
}

async function refresh(){
  try{
    const opts={headers:authHeaders()};
    const[agR,msgR]=await Promise.all([
      fetch('/who',opts).then(r=>{if(r.status===401){logout();throw new Error('unauthorized');}return r.json();}),
      fetch('/messages/recent',opts).then(r=>r.ok?r.json():{messages:[]}).catch(()=>({messages:[]}))
    ]);
    const agents=agR.agents||[];
    const msgs=msgR.messages||[];

    // Stats
    const total=agents.length;
    const active=agents.filter(a=>age(a.last_seen)<STALE_MIN).length;
    const stale=agents.filter(a=>{const a2=age(a.last_seen);return a2>=STALE_MIN&&a2<DEAD_MIN}).length;
    const dead=agents.filter(a=>age(a.last_seen)>=DEAD_MIN).length;
    document.getElementById('stats').innerHTML=
      `<div class="stat"><div class="stat-num">${total}</div><div class="stat-label">Total</div></div>`+
      `<div class="stat"><div class="stat-num status-green">${active}</div><div class="stat-label">Active</div></div>`+
      `<div class="stat"><div class="stat-num status-yellow">${stale}</div><div class="stat-label">Stale</div></div>`+
      `<div class="stat"><div class="stat-num status-red">${dead}</div><div class="stat-label">Dead</div></div>`;

    // Agents table
    if(agents.length===0){
      document.getElementById('agents').innerHTML='<div class="empty">No agents registered</div>';
    }else{
      let h='<table><tr><th></th><th>Name</th><th>Class</th><th>Host</th><th>Last Seen</th></tr>';
      for(const a of agents){
        const sc=statusClass(a.last_seen);
        h+=`<tr><td><span class="dot dot-${sc}"></span></td>`+
           `<td>${esc(a.name)}</td>`+
           `<td>${esc(a.agent_class)}</td>`+
           `<td>${esc(a.host||a.project_path||'')}</td>`+
           `<td class="status-${sc}">${fmtAge(age(a.last_seen))}</td></tr>`;
      }
      h+='</table>';
      document.getElementById('agents').innerHTML=h;
    }

    // Messages
    if(msgs.length===0){
      document.getElementById('messages').innerHTML='<div class="empty">No messages yet</div>';
    }else{
      let h='';
      for(const m of msgs.slice(-20).reverse()){
        const t=m.timestamp?new Date(m.timestamp).toLocaleTimeString():'';
        const preview=(m.content||'').substring(0,120);
        h+=`<div class="msg">`+
           `<span class="msg-time">${esc(t)}</span>`+
           `<span class="msg-from">${esc(m.from_agent)}</span>`+
           ` \\u2192 <span class="msg-to">${esc(m.to_agent)}</span>`+
           `<div class="msg-content">${esc(preview)}</div></div>`;
      }
      document.getElementById('messages').innerHTML=h;
    }
    document.getElementById('error').style.display='none';
  }catch(e){
    if(e.message==='unauthorized')return;
    const el=document.getElementById('error');
    el.textContent='Connection error: '+e.message;
    el.style.display='block';
  }
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
}

// Auto-login if token in localStorage
token=getToken();
if(token){showApp();}
</script>
</body>
</html>
"""
