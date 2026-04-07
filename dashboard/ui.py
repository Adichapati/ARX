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
.ok{color:#86efac}.bad{color:#fca5a5}
#console-window{background:#000;padding:10px;border-radius:8px;max-height:52vh;overflow:auto;white-space:pre-wrap}
input,select{padding:8px;border-radius:8px;border:1px solid #334155;background:#0b1220;color:#e2e8f0}
input{width:70%}
#setupPanel{display:none}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
</style></head><body>
<div class='card'><h2>ARX Ops Dashboard</h2><div id='status'>Loading...</div>
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

<div class='card'><h3>Console</h3>
  <div><input id='cmd' placeholder='say hello'><button onclick='sendCmd()'>Send</button></div>
  <div id='cmdmsg'></div>
  <pre id='console-window'>Connecting...</pre>
</div>
<script>
async function api(path, method='GET', body=null){
  const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null});
  if(r.status===401){location.href='/login'; throw new Error('unauthorized');}
  const j=await r.json().catch(()=>({error:'request failed'}));
  if(!r.ok) throw new Error(j.error||'request failed');
  return j;
}
async function loadState(){
  const s=await api('/api/state');
  status.innerHTML=`<span class='${s.running?'ok':'bad'}'>${s.running?'RUNNING':'STOPPED'}</span> | ${s.server_info.public} | ${s.server_info.players}`;
}
async function act(a){try{await api('/api/'+a,'POST'); await loadState();}catch(e){cmdmsg.textContent=e.message;}}
async function sendCmd(){try{const r=await api('/api/console/send','POST',{command:cmd.value}); cmd.value=''; cmdmsg.textContent=r.message;}catch(e){cmdmsg.textContent=e.message;}}
async function logout(){await api('/api/logout','POST'); location.href='/login';}

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
    const r = await api('/api/setup/config','POST',{updates});
    setupMsg.textContent='Saved.';
    setupMsg.className='ok';
    setupPanel.style.display='none';
  }catch(e){
    setupMsg.textContent=e.message;
    setupMsg.className='bad';
  }
}

async function ws(){
  try{
    const t=await api('/api/ws-ticket');
    const scheme=location.protocol==='https:'?'wss':'ws';
    const sock=new WebSocket(`${scheme}://${location.host}/ws?ticket=${encodeURIComponent(t.ticket)}`);
    sock.onmessage=(ev)=>{
      try{
        const m=JSON.parse(ev.data);
        if(m.type==='snapshot'){status.innerHTML=`<span class='${m.data.running?'ok':'bad'}'>${m.data.running?'RUNNING':'STOPPED'}</span> | ${m.data.server_info.public} | ${m.data.server_info.players}`;}
        if(m.type==='log'&&m.chunk){
          const el=document.getElementById('console-window');
          el.textContent += m.chunk;
          if(el.textContent.length>150000) el.textContent=el.textContent.slice(-120000);
          el.scrollTop=el.scrollHeight;
        }
      }catch(_){ }
    };
    sock.onclose=()=>setTimeout(ws,2000);
  }catch(_){setTimeout(ws,2000)}
}
loadState(); loadSetup(); ws();
</script></body></html>
    """
