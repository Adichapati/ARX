import asyncio
import secrets

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .auth import check_login, client_key, is_locked, prune_attempts, register_failed_attempt, require_session
from .config import (
    APP_NAME,
    PUBLIC_READ_ENABLED,
    PUBLIC_READ_TOKEN,
    SESSION_SECRET,
    _cache,
    _ws_tickets,
    ensure_dirs,
    now_ts,
    state,
)
from .services.config_service import ConfigService
from .services.log_service import LogService
from .services.op_assist_service import OpAssistService
from .services.server_service import ServerService
from .ui import dash_html, login_html

app = FastAPI(title=APP_NAME)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 12,
    same_site='lax',
    https_only=False,
)


def build_snapshot() -> dict:
    q = ServerService.mc_query()
    running = ServerService.is_running()
    return {
        'running': running,
        'server_info': {
            'public': 'online' if q['online'] else 'offline',
            'version': q['version'],
            'players': f"{q['players_online']}/{q['players_max']}",
            'player_names': q.get('player_names', []),
        },
        'status_note': state.get('last_status_note', ''),
    }


def get_snapshot() -> dict:
    if _cache.get('snapshot') is None:
        _cache['snapshot'] = build_snapshot()
        _cache['updated_at'] = now_ts()
    return _cache['snapshot']


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get('user'):
        return RedirectResponse('/', status_code=302)
    return login_html()


@app.post('/api/login')
async def api_login(request: Request):
    data = await request.json()
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    now = now_ts()
    key = client_key(request, username or 'unknown')
    prune_attempts(key, now)
    if is_locked(key, now):
        return JSONResponse({'error': 'Too many failed attempts. Try again later.'}, status_code=429)
    if not check_login(username, password):
        register_failed_attempt(key, now)
        return JSONResponse({'error': 'Invalid username or password'}, status_code=401)
    request.session['user'] = username
    return {'ok': True}


@app.post('/api/logout')
async def api_logout(request: Request):
    request.session.clear()
    return {'ok': True}


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get('user'):
        return RedirectResponse('/login', status_code=302)
    return dash_html()


@app.get('/api/state')
async def api_state(request: Request):
    require_session(request)
    return get_snapshot()


@app.get('/api/public/state/{token}')
async def api_public_state(token: str):
    if not PUBLIC_READ_ENABLED:
        raise HTTPException(status_code=404, detail='Not enabled')
    if token != PUBLIC_READ_TOKEN:
        return JSONResponse({'error': 'forbidden'}, status_code=403)
    s = get_snapshot()
    return {'running': s['running'], 'server_info': s['server_info']}


@app.post('/api/start')
async def api_start(request: Request):
    require_session(request)
    return {'ok': True, 'message': ServerService.start()}


@app.post('/api/stop')
async def api_stop(request: Request):
    require_session(request)
    return {'ok': True, 'message': ServerService.stop()}


@app.post('/api/restart')
async def api_restart(request: Request):
    require_session(request)
    return {'ok': True, 'message': ServerService.restart()}


@app.get('/api/setup/config')
async def api_setup_get(request: Request):
    require_session(request)
    return ConfigService.load_arx_runtime_config()


@app.post('/api/setup/config')
async def api_setup_set(request: Request):
    require_session(request)
    data = await request.json()
    updates = data.get('updates') or {}
    if not isinstance(updates, dict):
        return JSONResponse({'error': 'updates must be object'}, status_code=400)
    try:
        clean = ConfigService.validate_runtime_updates(updates)
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=400)
    cfg = ConfigService.save_arx_runtime_config(clean)
    return {'ok': True, 'config': cfg}

@app.post('/api/console/send')
async def api_console_send(request: Request):
    require_session(request)
    data = await request.json()
    command = str(data.get('command', '')).strip()
    res = ServerService.send_console_command(command)
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'failed')}, status_code=400)
    return {'ok': True, 'message': res.get('message', 'sent')}


@app.get('/api/ws-ticket')
async def api_ws_ticket(request: Request):
    require_session(request)
    t = secrets.token_urlsafe(24)
    _ws_tickets[t] = now_ts() + 30
    return {'ticket': t}


@app.websocket('/ws')
async def ws_feed(ws: WebSocket):
    ticket = ws.query_params.get('ticket', '')
    exp = _ws_tickets.pop(ticket, 0)
    if not exp or exp < now_ts():
        await ws.close(code=4401)
        return

    await ws.accept()
    log_offset = 0
    try:
        while True:
            await ws.send_json({'type': 'snapshot', 'data': get_snapshot()})
            d = LogService.diff_from(log_offset)
            log_offset = d['next_offset']
            if d['chunk']:
                await ws.send_json({'type': 'log', 'chunk': d['chunk']})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


async def snapshot_loop():
    while True:
        try:
            _cache['snapshot'] = build_snapshot()
            _cache['updated_at'] = now_ts()
        except Exception:
            pass
        await asyncio.sleep(3)


@app.on_event('startup')
async def on_startup():
    ensure_dirs()
    ConfigService.ensure_eula()
    asyncio.create_task(snapshot_loop())
    asyncio.create_task(OpAssistService.run_loop())
