def login_html() -> str:
    return """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sign in</title>
<style>
:root{--bg:#ffe66d;--ink:#111;--paper:#fff;--accent:#7cf29a;--blue:#77b8ff}
*{box-sizing:border-box}
body{font-family:'Space Grotesk',Inter,system-ui,sans-serif;background:var(--bg);color:var(--ink);display:grid;place-items:center;min-height:100vh;margin:0;padding:20px}
.stack{width:min(94vw,420px)}
.card{background:var(--paper);border:4px solid var(--ink);border-radius:18px;padding:22px;box-shadow:8px 8px 0 var(--ink)}
.badge{display:inline-block;background:var(--blue);border:3px solid var(--ink);border-radius:999px;padding:5px 10px;font-weight:800;font-size:12px;transform:rotate(-2deg)}
h2{margin:10px 0 14px 0;font-size:34px;line-height:1}
label{font-weight:800;font-size:13px;display:block;margin:7px 0 6px}
input{width:100%;padding:12px 13px;border-radius:12px;border:3px solid var(--ink);background:#fff;color:#111;font-size:15px;outline:none;box-shadow:4px 4px 0 var(--ink)}
input:focus{transform:translate(-1px,-1px);box-shadow:6px 6px 0 var(--ink)}
button{width:100%;padding:12px;border-radius:12px;border:3px solid var(--ink);background:var(--accent);color:#111;font-weight:900;cursor:pointer;box-shadow:4px 4px 0 var(--ink);font-size:15px}
button:active{transform:translate(2px,2px);box-shadow:2px 2px 0 var(--ink)}
.err{min-height:22px;font-weight:700;color:#b00020}
.note{font-size:12px;font-weight:700;opacity:.85}
</style>
<link href='https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700;800&display=swap' rel='stylesheet'>
</head><body><div class='stack'><div class='card'>
<span class='badge'>ARX CONTROL</span><h2>Sign in</h2><div class='err' id='err'></div>
<label>Username</label><input id='u' placeholder='admin' autocomplete='username'/>
<label>Password</label><input id='p' type='password' placeholder='••••••••' autocomplete='current-password'/>
<button onclick='login()'>LET ME IN</button>
<p class='note'>Protected dashboard • brute-force lockout enabled</p>
</div></div>
<script>
async function login(){
 const username=document.getElementById('u').value;
 const password=document.getElementById('p').value;
 const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});
 const j=await r.json().catch(()=>({error:'login failed'}));
 if(r.ok){ location.href='/'; } else { document.getElementById('err').textContent=j.error||'Login failed'; }
}
document.getElementById('p').addEventListener('keydown',(e)=>{if(e.key==='Enter')login();});
</script></body></html>
"""


def dash_html() -> str:
    return """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>ARX Dashboard</title>
<link href='https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700;800&display=swap' rel='stylesheet'>
<style>
:root{--bg:#ffe66d;--ink:#101010;--paper:#fff;--mint:#7cf29a;--pink:#ff8fab;--blue:#77b8ff;--orange:#ffb347;--purple:#b29bff;--red:#ff7b7b}
*{box-sizing:border-box}
body{font-family:'Space Grotesk',Inter,system-ui,sans-serif;background:var(--bg);color:var(--ink);margin:0}
.wrap{max-width:1180px;margin:18px auto;padding:0 14px}
.card{background:var(--paper);border:4px solid var(--ink);border-radius:18px;padding:14px;margin-bottom:14px;box-shadow:8px 8px 0 var(--ink)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
@media(max-width:980px){.grid,.grid3{grid-template-columns:1fr}}
.btn{border:3px solid var(--ink);padding:10px 14px;border-radius:12px;font-weight:900;cursor:pointer;margin-right:8px;margin-top:8px;box-shadow:4px 4px 0 var(--ink);color:#111;background:#fff}
.btn:active{transform:translate(2px,2px);box-shadow:2px 2px 0 var(--ink)}
.start{background:var(--mint)}.stop{background:var(--red)}.restart{background:var(--blue)}.ghost{background:#fff}
.tag{display:inline-block;padding:5px 11px;border-radius:999px;border:3px solid var(--ink);font-weight:800;font-size:12px;box-shadow:3px 3px 0 var(--ink)}
.tag.status{background:var(--purple)}.tag.logs{background:var(--orange)}.tag.live{background:var(--pink)}
.k{font-weight:700;opacity:.9}.big{font-size:28px;font-weight:900;letter-spacing:.4px}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:13px}
pre{background:#fff;border:3px solid var(--ink);border-radius:12px;padding:10px;max-height:340px;overflow:auto;box-shadow:4px 4px 0 var(--ink);font-family:ui-monospace,Consolas,monospace;white-space:pre-wrap;word-break:break-word}
.tabs{display:flex;gap:8px;flex-wrap:wrap}.tab{padding:8px 12px;border:3px solid var(--ink);border-radius:999px;background:#fff;cursor:pointer;font-weight:800;box-shadow:3px 3px 0 var(--ink)}.tab.active{background:var(--mint)}
.panel{display:none}.panel.active{display:block}
input,select{width:100%;padding:10px;border-radius:10px;border:3px solid var(--ink);font-size:14px;background:#fff}
.small{font-size:12px;opacity:.85}.statusline{min-height:22px;font-weight:800}
.success{color:#0b7f35}.error{color:#b00020}.chip{display:inline-flex;align-items:center;gap:6px;border:2px solid var(--ink);border-radius:999px;padding:4px 10px;margin:4px;background:#fff;font-weight:700}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;border:2px solid var(--ink);margin:2px;font-size:12px;background:#fff}
#errorBanner{display:none;background:#fff;border:4px solid #b00020;color:#b00020;padding:10px;border-radius:12px;margin-bottom:12px;box-shadow:6px 6px 0 #b00020;font-weight:800}
</style></head><body><div class='wrap'>

<div id='errorBanner'></div>

<div class='card'><div style='display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap'>
<div><h2 style='margin:8px 0 0 0;font-size:32px'>ARX Dashboard</h2><div class='k'>Gemma-only Minecraft control panel</div></div>
<button class='btn ghost' onclick='logout()'>Logout</button></div></div>

<div class='card'><div class='tabs'>
<button class='tab active' data-tab='overview'>Overview</button>
<button class='tab' data-tab='players'>Players</button>
<button class='tab' data-tab='props'>Properties</button>
<button class='tab' data-tab='console'>Console</button>
</div></div>

<div id='panel-overview' class='panel active'>
  <div class='card'><span class='tag status'>MINECRAFT STATUS</span>
  <div class='big' id='status' style='margin-top:8px'>Loading...</div>
  <div id='wsState' class='k small'>WebSocket: connecting...</div>
  <div style='margin-top:10px'>
    <button class='btn start' onclick="act('start')">Start</button>
    <button class='btn stop' onclick="act('stop')">Stop</button>
    <button class='btn restart' onclick="act('restart')">Restart</button>
  </div></div>

  <div class='grid3'>
    <div class='card'><span class='tag' style='background:var(--mint)'>OLLAMA</span><div class='big' id='h_ollama' style='margin-top:8px'>...</div></div>
    <div class='card'><span class='tag' style='background:var(--blue)'>JAVA</span><div class='big' id='h_java' style='margin-top:8px'>...</div></div>
    <div class='card'><span class='tag' style='background:var(--pink)'>SERVER PING</span><div class='big' id='h_ping' style='margin-top:8px'>...</div></div>
  </div>
</div>

<div id='panel-players' class='panel'>
  <div class='card'><span class='tag'>PLAYER ACCESS</span>
    <div class='grid' style='margin-top:10px'>
      <div>
        <label>OP username</label>
        <input id='op_user' placeholder='PlayerName'>
        <div><button class='btn' onclick="opAction('add')">Add OP</button><button class='btn ghost' onclick="opAction('remove')">Remove OP</button></div>
        <div id='op_msg' class='statusline small'></div>
        <div class='small'><b>Known OPs</b></div><div id='op_list'></div>
      </div>
      <div>
        <label>Whitelist username</label>
        <input id='wl_user' placeholder='PlayerName'>
        <div><button class='btn' onclick="wlAction('add')">Add WL</button><button class='btn ghost' onclick="wlAction('remove')">Remove WL</button></div>
        <div id='wl_msg' class='statusline small'></div>
        <div class='small'><b>Whitelist</b></div><div id='wl_list'></div>
      </div>
    </div>
    <div class='small' style='margin-top:8px'><b>Online players:</b> <span id='online_players'></span></div>
  </div>
</div>

<div id='panel-props' class='panel'>
  <div class='card'><span class='tag'>SERVER PROPERTIES</span>
    <div class='grid' style='margin-top:10px'>
      <div><label>MOTD</label><input id='sp_motd'></div>
      <div><label>Max Players</label><input id='sp_max_players' type='number' min='1' max='500'></div>
      <div><label>Difficulty</label><select id='sp_difficulty'><option>peaceful</option><option>easy</option><option>normal</option><option>hard</option></select></div>
      <div><label>Spawn Protection</label><input id='sp_spawn_protection' type='number' min='0' max='64'></div>
      <div><label>PVP</label><select id='sp_pvp'><option>true</option><option>false</option></select></div>
      <div><label>Whitelist</label><select id='sp_whitelist'><option>true</option><option>false</option></select></div>
      <div><label>Online Mode</label><select id='sp_online_mode'><option>true</option><option>false</option></select></div>
    </div>
    <button class='btn' onclick='saveServerProps()'>Save Properties</button>
    <div id='spMsg' class='statusline small'></div>
  </div>
</div>

<div id='panel-console' class='panel'>
  <div class='card'><span class='tag live'>LIVE CONSOLE</span>
    <div style='display:flex;gap:8px;margin-top:10px'><input id='cmd' placeholder='say hello'><button class='btn' onclick='sendCmd()'>Send</button></div>
    <div id='cmdmsg' class='statusline small'></div>
    <pre id='console-window'>Connecting...</pre>
  </div>
</div>

<script>
let wsBackoffMs = 2000;

function st(id,m,ok=true){const e=document.getElementById(id); if(!e)return; e.textContent=m||''; e.className='statusline small '+(ok?'success':'error');}
function showError(msg){errorBanner.textContent=msg||'Unknown error'; errorBanner.style.display='block';}
function clearError(){errorBanner.style.display='none';}

function renderBadges(el, arr){
  const data = Array.isArray(arr) ? arr : [];
  el.innerHTML = data.length ? data.map(x=>`<span class='badge'>${x}</span>`).join('') : "<span class='small'>none</span>";
}

async function api(path, method='GET', body=null){
  let r;
  try{r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null});}
  catch(e){showError('Network error. Check server connection.'); throw e;}
  if(r.status===401){showError('Session expired. Redirecting to login...'); setTimeout(()=>location.href='/login',800); throw new Error('unauthorized');}
  const j=await r.json().catch(()=>({error:'request failed'}));
  if(!r.ok){showError(j.error||'request failed'); throw new Error(j.error||'request failed');}
  clearError();
  return j;
}

async function logout(){await api('/api/logout','POST'); location.href='/login';}

async function loadState(){
  const s=await api('/api/state');
  status.innerHTML=`<span style="color:${s.running?'#0b7f35':'#b00020'}">${s.running?'RUNNING':'STOPPED'}</span> | ${s.server_info.public} | ${s.server_info.players}`;
}

async function loadHealth(){
  try{const h=await api('/api/health/runtime'); h_ollama.textContent=h.ollama; h_java.textContent=h.java; h_ping.textContent=h.server_ping;}
  catch(_){h_ollama.textContent=h_java.textContent=h_ping.textContent='error';}
}

async function act(a){ try{ await api('/api/'+a,'POST'); await loadState(); }catch(e){ st('cmdmsg',e.message,false); } }

async function sendCmd(){
  try{ const r=await api('/api/console/send','POST',{command:cmd.value}); cmd.value=''; st('cmdmsg',r.message,true); }
  catch(e){ st('cmdmsg',e.message,false); }
}

async function loadPlayers(){
  try{
    const r = await api('/api/players');
    renderBadges(op_list, r.ops || []);
    renderBadges(wl_list, r.whitelist || []);
    const online = Array.isArray(r.online) ? r.online : [];
    online_players.textContent = online.length ? online.join(', ') : 'none';
  }catch(e){ st('op_msg',e.message,false); st('wl_msg',e.message,false); }
}

async function opAction(action){
  try{ await api('/api/players/op','POST',{action, username:op_user.value.trim(), sync_runtime:true}); st('op_msg',`OP ${action} ok`,true); await loadPlayers(); }
  catch(e){ st('op_msg',e.message,false); }
}

async function wlAction(action){
  try{ await api('/api/players/whitelist','POST',{action, username:wl_user.value.trim(), sync_runtime:true}); st('wl_msg',`Whitelist ${action} ok`,true); await loadPlayers(); }
  catch(e){ st('wl_msg',e.message,false); }
}

async function loadServerProps(){
  try{
    const r = await api('/api/server-properties');
    const p = r.properties || {};
    sp_motd.value = p['motd'] || '';
    sp_max_players.value = Number(p['max-players'] || 20);
    sp_difficulty.value = p['difficulty'] || 'easy';
    sp_spawn_protection.value = Number(p['spawn-protection'] || 16);
    sp_pvp.value = (p['pvp'] || 'true').toLowerCase();
    sp_whitelist.value = (p['white-list'] || 'false').toLowerCase();
    sp_online_mode.value = (p['online-mode'] || 'true').toLowerCase();
  }catch(e){ st('spMsg',e.message,false); }
}

async function saveServerProps(){
  try{
    await api('/api/server-properties','POST',{updates:{
      motd: sp_motd.value,
      'max-players': Number(sp_max_players.value),
      difficulty: sp_difficulty.value,
      'spawn-protection': Number(sp_spawn_protection.value),
      pvp: sp_pvp.value,
      'white-list': sp_whitelist.value,
      'online-mode': sp_online_mode.value,
    }});
    st('spMsg','Saved server.properties',true);
  }catch(e){ st('spMsg',e.message,false); }
}

async function ws(){
  try{
    const t=await api('/api/ws-ticket');
    const scheme=location.protocol==='https:'?'wss':'ws';
    const sock=new WebSocket(`${scheme}://${location.host}/ws?ticket=${encodeURIComponent(t.ticket)}`);
    wsState.textContent='WebSocket: connected'; wsState.style.color='#0b7f35'; wsBackoffMs=2000;
    sock.onmessage=(ev)=>{
      try{
        const m=JSON.parse(ev.data);
        if(m.type==='snapshot'){status.innerHTML=`<span style="color:${m.data.running?'#0b7f35':'#b00020'}">${m.data.running?'RUNNING':'STOPPED'}</span> | ${m.data.server_info.public} | ${m.data.server_info.players}`;}
        if(m.type==='log'&&m.chunk){const el=document.getElementById('console-window'); el.textContent += m.chunk; if(el.textContent.length>180000) el.textContent=el.textContent.slice(-140000); el.scrollTop=el.scrollHeight;}
      }catch(_){ }
    };
    sock.onclose=()=>{wsState.textContent=`WebSocket: reconnecting in ${Math.round(wsBackoffMs/1000)}s`; wsState.style.color='#9a6700'; const wait=wsBackoffMs; wsBackoffMs=Math.min(wsBackoffMs*2,15000); setTimeout(ws,wait);};
    sock.onerror=()=>{wsState.textContent='WebSocket: error'; wsState.style.color='#b00020';};
  }catch(_){ wsState.textContent='WebSocket: reconnecting'; wsState.style.color='#9a6700'; setTimeout(ws,Math.min(wsBackoffMs,15000)); wsBackoffMs=Math.min(wsBackoffMs*2,15000); }
}

document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active')); t.classList.add('active');
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('panel-'+t.dataset.tab).classList.add('active');
});

loadState(); loadHealth(); loadPlayers(); loadServerProps(); ws();
setInterval(loadHealth, 5000);
setInterval(loadPlayers, 7000);
</script></body></html>
"""
