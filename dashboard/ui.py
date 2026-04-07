def login_html() -> str:
    return """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ARX Dashboard Login</title>
<style>
body{font-family:Inter,system-ui,sans-serif;background:#0f172a;color:#e2e8f0;display:grid;place-items:center;min-height:100vh;margin:0}
.card{background:#111827;border:1px solid #334155;border-radius:12px;padding:24px;width:min(92vw,360px)}
input,button{width:100%;margin-top:10px;padding:10px;border-radius:8px;border:1px solid #334155}
button{background:#22c55e;color:#0b1020;font-weight:700;cursor:pointer}
.err{color:#fca5a5;min-height:20px}
</style></head><body>
<div class='card'><h3>ARX Sign in</h3><div id='err' class='err'></div>
<input id='u' placeholder='username' autocomplete='username'>
<input id='p' type='password' placeholder='password' autocomplete='current-password'>
<button onclick='login()'>Login</button></div>
<script>
async function login(){
  const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u.value,password:p.value})});
  const j=await r.json().catch(()=>({error:'login failed'}));
  if(r.ok){location.href='/';}else{err.textContent=j.error||'Login failed';}
}
p.addEventListener('keydown',e=>{if(e.key==='Enter')login();});
</script></body></html>
    """


def dash_html() -> str:
    return """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ARX — Gemma Minecraft Ops Dashboard</title>
<style>
body{font-family:Inter,system-ui,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:16px}
.card{background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px;margin-bottom:12px}
button{padding:8px 12px;margin-right:8px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;cursor:pointer}
.ok{color:#86efac}.bad{color:#fca5a5}.warn{color:#fcd34d}
#console-window{background:#000;padding:10px;border-radius:8px;max-height:52vh;overflow:auto;white-space:pre-wrap}
input,select{padding:8px;border-radius:8px;border:1px solid #334155;background:#0b1220;color:#e2e8f0}
input{width:70%}
#setupPanel{display:none}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.listbox{background:#020617;border:1px solid #334155;border-radius:8px;padding:8px;max-height:140px;overflow:auto}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid #334155;margin:2px;font-size:12px}
#errorBanner{display:none;background:#7f1d1d;border:1px solid #ef4444;color:#fecaca;padding:10px;border-radius:10px;margin-bottom:12px}
#wsState{font-size:12px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
</style></head><body>
<div id='errorBanner'></div>

<div class='card'><h2>ARX Ops Dashboard</h2><div id='status'>Loading...</div>
<div id='wsState' class='warn'>WebSocket: connecting...</div>
<button onclick="act('start')">Start</button><button onclick="act('stop')">Stop</button><button onclick="act('restart')">Restart</button>
<button onclick='logout()'>Logout</button></div>

<div id='setupPanel' class='card'>
  <h3>First-run Gemma Setup</h3>
  <p>Configure local inference/runtime tuning. These values are saved locally.</p>
  <div class='grid'>
    <div><label>Trigger</label><br><input id='cfg_trigger' style='width:100%' placeholder='gemma'></div>
    <div><label>Model</label><br><input id='cfg_model' style='width:100%' placeholder='gemma4:e2b'></div>
    <div><label>Context Size</label><br><input id='cfg_ctx' style='width:100%' type='number' min='1024' max='131072'></div>
    <div><label>Temperature</label><br><input id='cfg_temp' style='width:100%' type='number' min='0' max='2' step='0.05'></div>
    <div><label>Max Reply Chars</label><br><input id='cfg_max_reply' style='width:100%' type='number' min='80' max='500'></div>
    <div><label>Cooldown Seconds</label><br><input id='cfg_cooldown' style='width:100%' type='number' min='0' max='30' step='0.1'></div>
  </div>
  <div style='margin-top:10px'>
    <button onclick='saveSetup()'>Save Setup</button>
    <span id='setupMsg'></span>
  </div>
</div>

<div class='card'>
  <h3>Runtime Health</h3>
  <div id='health' class='grid'>
    <div>Ollama: <span id='h_ollama'>...</span></div>
    <div>tmux: <span id='h_tmux'>...</span></div>
    <div>Java: <span id='h_java'>...</span></div>
    <div>Server Ping: <span id='h_ping'>...</span></div>
  </div>
</div>

<div class='card'>
  <h3>Player Access (OP + Whitelist)</h3>
  <div class='grid'>
    <div>
      <label>OP username</label><br>
      <input id='op_user' style='width:100%' placeholder='PlayerName'>
      <div style='margin-top:8px'>
        <button onclick="opAction('add')">Add OP</button>
        <button onclick="opAction('remove')">Remove OP</button>
      </div>
      <div id='op_msg'></div>
      <div><b>Known OPs</b></div>
      <div id='op_list' class='listbox'></div>
    </div>
    <div>
      <label>Whitelist username</label><br>
      <input id='wl_user' style='width:100%' placeholder='PlayerName'>
      <div style='margin-top:8px'>
        <button onclick="wlAction('add')">Add Whitelist</button>
        <button onclick="wlAction('remove')">Remove Whitelist</button>
      </div>
      <div id='wl_msg'></div>
      <div><b>Whitelist</b></div>
      <div id='wl_list' class='listbox'></div>
    </div>
  </div>
  <div style='margin-top:10px'><b>Online players:</b> <span id='online_players'></span></div>
</div>

<div class='card'>
  <h3>Server Properties</h3>
  <div class='grid'>
    <div><label>MOTD</label><br><input id='sp_motd' style='width:100%'></div>
    <div><label>Max Players</label><br><input id='sp_max_players' style='width:100%' type='number' min='1' max='500'></div>
    <div><label>Difficulty</label><br><select id='sp_difficulty' style='width:100%'><option>peaceful</option><option>easy</option><option>normal</option><option>hard</option></select></div>
    <div><label>Spawn Protection</label><br><input id='sp_spawn_protection' style='width:100%' type='number' min='0' max='64'></div>
    <div><label>PVP</label><br><select id='sp_pvp' style='width:100%'><option>true</option><option>false</option></select></div>
    <div><label>Whitelist</label><br><select id='sp_whitelist' style='width:100%'><option>true</option><option>false</option></select></div>
    <div><label>Online Mode</label><br><select id='sp_online_mode' style='width:100%'><option>true</option><option>false</option></select></div>
  </div>
  <div style='margin-top:10px'>
    <button onclick='saveServerProps()'>Save Properties</button>
    <span id='spMsg'></span>
  </div>
</div>

<div class='card'><h3>Console</h3>
  <div><input id='cmd' placeholder='say hello'><button onclick='sendCmd()'>Send</button></div>
  <div id='cmdmsg'></div>
  <pre id='console-window'>Connecting...</pre>
</div>
<script>
let wsBackoffMs = 2000;

function showError(msg){
  errorBanner.textContent = msg || 'Unknown error';
  errorBanner.style.display = 'block';
}
function clearError(){ errorBanner.style.display = 'none'; }

async function api(path, method='GET', body=null){
  let r;
  try{
    r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null});
  }catch(e){
    showError('Network error. Check server connection.');
    throw e;
  }
  if(r.status===401){
    showError('Session expired. Redirecting to login...');
    setTimeout(()=>location.href='/login', 800);
    throw new Error('unauthorized');
  }
  const j=await r.json().catch(()=>({error:'request failed'}));
  if(!r.ok){
    showError(j.error||'request failed');
    throw new Error(j.error||'request failed');
  }
  clearError();
  return j;
}

async function loadState(){
  const s=await api('/api/state');
  status.innerHTML=`<span class='${s.running?'ok':'bad'}'>${s.running?'RUNNING':'STOPPED'}</span> | ${s.server_info.public} | ${s.server_info.players}`;
}

async function act(a){ try{ await api('/api/'+a,'POST'); await loadState(); }catch(e){ cmdmsg.textContent=e.message; } }
async function sendCmd(){ try{ const r=await api('/api/console/send','POST',{command:cmd.value}); cmd.value=''; cmdmsg.textContent=r.message; }catch(e){ cmdmsg.textContent=e.message; } }
async function logout(){ await api('/api/logout','POST'); location.href='/login'; }

async function loadSetup(){
  try{
    const cfg = await api('/api/setup/config');
    cfg_trigger.value = cfg.agent_trigger || 'gemma';
    cfg_model.value = cfg.gemma_model || 'gemma4:e2b';
    cfg_ctx.value = cfg.gemma_context_size || 8192;
    cfg_temp.value = cfg.gemma_temperature || 0.2;
    cfg_max_reply.value = cfg.gemma_max_reply_chars || 220;
    cfg_cooldown.value = cfg.gemma_cooldown_sec || 2.5;
    if(!cfg.setup_completed){
      setupPanel.style.display='block';
      setupMsg.textContent='Complete first-run setup to continue.';
      setupMsg.className='bad';
    }
  }catch(e){
    setupPanel.style.display='block';
    setupMsg.textContent=e.message;
    setupMsg.className='bad';
  }
}

async function saveSetup(){
  try{
    const updates = {
      agent_trigger: cfg_trigger.value,
      gemma_model: cfg_model.value,
      gemma_context_size: Number(cfg_ctx.value),
      gemma_temperature: Number(cfg_temp.value),
      gemma_max_reply_chars: Number(cfg_max_reply.value),
      gemma_cooldown_sec: Number(cfg_cooldown.value),
      setup_completed: true,
    };
    await api('/api/setup/config','POST',{updates});
    setupMsg.textContent='Saved.';
    setupMsg.className='ok';
    setupPanel.style.display='none';
  }catch(e){
    setupMsg.textContent=e.message;
    setupMsg.className='bad';
  }
}

async function loadHealth(){
  try{
    const h = await api('/api/health/runtime');
    h_ollama.textContent = h.ollama;
    h_tmux.textContent = h.tmux;
    h_java.textContent = h.java;
    h_ping.textContent = h.server_ping;
  }catch(e){
    h_ollama.textContent = h_tmux.textContent = h_java.textContent = h_ping.textContent = 'error';
  }
}

function renderBadges(el, arr){
  const data = Array.isArray(arr) ? arr : [];
  el.innerHTML = data.length ? data.map(x=>`<span class='badge'>${x}</span>`).join('') : "<span class='warn'>none</span>";
}

async function loadPlayers(){
  try{
    const r = await api('/api/players');
    renderBadges(op_list, r.ops || []);
    renderBadges(wl_list, r.whitelist || []);
    const online = Array.isArray(r.online) ? r.online : [];
    online_players.textContent = online.length ? online.join(', ') : 'none';
  }catch(e){
    op_msg.textContent = wl_msg.textContent = e.message;
    op_msg.className = wl_msg.className = 'bad';
  }
}

async function opAction(action){
  try{
    const username = op_user.value.trim();
    await api('/api/players/op','POST',{action, username, sync_runtime:true});
    op_msg.textContent = `OP ${action} ok`;
    op_msg.className = 'ok';
    await loadPlayers();
  }catch(e){
    op_msg.textContent = e.message;
    op_msg.className = 'bad';
  }
}

async function wlAction(action){
  try{
    const username = wl_user.value.trim();
    await api('/api/players/whitelist','POST',{action, username, sync_runtime:true});
    wl_msg.textContent = `Whitelist ${action} ok`;
    wl_msg.className = 'ok';
    await loadPlayers();
  }catch(e){
    wl_msg.textContent = e.message;
    wl_msg.className = 'bad';
  }
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
  }catch(e){
    spMsg.textContent = e.message;
    spMsg.className = 'bad';
  }
}

async function saveServerProps(){
  try{
    const updates = {
      motd: sp_motd.value,
      'max-players': Number(sp_max_players.value),
      difficulty: sp_difficulty.value,
      'spawn-protection': Number(sp_spawn_protection.value),
      pvp: sp_pvp.value,
      'white-list': sp_whitelist.value,
      'online-mode': sp_online_mode.value,
    };
    await api('/api/server-properties','POST',{updates});
    spMsg.textContent = 'Saved server.properties';
    spMsg.className = 'ok';
  }catch(e){
    spMsg.textContent = e.message;
    spMsg.className = 'bad';
  }
}

async function ws(){
  try{
    const t=await api('/api/ws-ticket');
    const scheme=location.protocol==='https:'?'wss':'ws';
    const sock=new WebSocket(`${scheme}://${location.host}/ws?ticket=${encodeURIComponent(t.ticket)}`);
    wsState.textContent='WebSocket: connected';
    wsState.className='ok';
    wsBackoffMs = 2000;
    sock.onmessage=(ev)=>{
      try{
        const m=JSON.parse(ev.data);
        if(m.type==='snapshot'){
          status.innerHTML=`<span class='${m.data.running?'ok':'bad'}'>${m.data.running?'RUNNING':'STOPPED'}</span> | ${m.data.server_info.public} | ${m.data.server_info.players}`;
        }
        if(m.type==='log'&&m.chunk){
          const el=document.getElementById('console-window');
          el.textContent += m.chunk;
          if(el.textContent.length>180000) el.textContent=el.textContent.slice(-140000);
          el.scrollTop=el.scrollHeight;
        }
      }catch(_){ }
    };
    sock.onclose=()=>{
      wsState.textContent=`WebSocket: reconnecting in ${Math.round(wsBackoffMs/1000)}s`;
      wsState.className='warn';
      const wait = wsBackoffMs;
      wsBackoffMs = Math.min(wsBackoffMs * 2, 15000);
      setTimeout(ws, wait);
    };
    sock.onerror=()=>{
      wsState.textContent='WebSocket: error';
      wsState.className='bad';
    };
  }catch(_){
    wsState.textContent='WebSocket: reconnecting';
    wsState.className='warn';
    setTimeout(ws, Math.min(wsBackoffMs, 15000));
    wsBackoffMs = Math.min(wsBackoffMs * 2, 15000);
  }
}

loadState();
loadSetup();
loadHealth();
loadPlayers();
loadServerProps();
ws();
setInterval(loadHealth, 5000);
setInterval(loadPlayers, 7000);
</script></body></html>
    """
