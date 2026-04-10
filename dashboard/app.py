import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
import urllib.parse
import urllib.request

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .auth import check_login, client_key, is_locked, prune_attempts, register_failed_attempt, require_session
from .config import (
    APP_NAME,
    CSRF_ENABLED,
    PUBLIC_READ_ENABLED,
    PUBLIC_READ_TOKEN,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_SECRET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    _cache,
    _console_history,
    _console_policy,
    _scheduler,
    _ws_tickets,
    load_lockouts,
    now_ts,
    save_scheduler,
    state,
)
from .services.config_service import PropertiesService
from .services.log_analytics_service import AnalyticsService, LogService
from .services.player_service import PlayerService
from .services.plugin_service import PluginService
from .services.server_service import ServerService
from .services.snapshot_service import build_snapshot, get_snapshot
from .services.world_service import SeedService, WorldService
from .services.join_watcher_service import JoinWatcherService
from .services.op_assist_service import OpAssistService
from .ui import dash_html, login_html, public_html

logger = logging.getLogger(__name__)
BACKGROUND_TASK_CANCEL_TIMEOUT_SECONDS = 5.0


def _create_background_tasks() -> list[asyncio.Task]:
    return [
        asyncio.create_task(refresh_cache_loop()),
        asyncio.create_task(refresh_logs_loop()),
        asyncio.create_task(automation_loop()),
        asyncio.create_task(JoinWatcherService.run_loop(_on_player_join)),
        asyncio.create_task(OpAssistService.run_loop()),
    ]


async def _cancel_background_tasks(tasks: list[asyncio.Task]) -> None:
    if not tasks:
        return

    for task in tasks:
        task.cancel()

    done, pending = await asyncio.wait(
        tasks,
        timeout=BACKGROUND_TASK_CANCEL_TIMEOUT_SECONDS,
    )

    for task in done:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            task.result()

    if pending:
        logger.warning(
            "Timed out waiting for %d background task(s) to cancel",
            len(pending),
        )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from .config import ensure_dirs, load_scheduler

    ensure_dirs()
    load_scheduler()
    load_lockouts()
    # default preference: auto-start OFF (manual start only)
    state['auto_start'] = False

    tasks = _create_background_tasks()
    try:
        yield
    finally:
        await _cancel_background_tasks(tasks)


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 12,
    same_site=SESSION_COOKIE_SAMESITE,
    https_only=SESSION_COOKIE_SECURE,
)


async def _send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    def _send() -> None:
        qs = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': text})
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?{qs}"
        with urllib.request.urlopen(url, timeout=8) as _r:
            _r.read(64)

    try:
        await asyncio.to_thread(_send)
    except Exception:
        logger.debug("Failed to send telegram message", exc_info=True)


async def _on_player_join(username: str) -> None:
    await _send_telegram_message(f"{username} joined mc server")


def _require_csrf(request: Request) -> None:
    if not CSRF_ENABLED:
        return
    token_session = str(request.session.get('csrf_token', '') or '')
    headers = getattr(request, 'headers', None)
    token_header = ''
    if headers is not None:
        try:
            token_header = str(headers.get('x-csrf-token', '') or '')
        except Exception:
            token_header = ''
    if not token_session or not token_header or token_session != token_header:
        raise HTTPException(status_code=403, detail='CSRF token missing or invalid')


async def _parse_json_object(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid JSON payload')

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail='JSON body must be an object')

    return data


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get('user'):
        return RedirectResponse('/', status_code=302)
    return login_html()


@app.post('/api/login')
async def api_login(request: Request):
    data = await _parse_json_object(request)
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
    request.session['login_at'] = int(now)
    request.session['csrf_token'] = __import__('secrets').token_urlsafe(24)
    return {'ok': True}


@app.post('/api/logout')
async def api_logout(request: Request):
    require_session(request)
    _require_csrf(request)
    request.session.clear()
    return {'ok': True}


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get('user'):
        return RedirectResponse('/login', status_code=302)
    return dash_html()


@app.get('/public/{token}', response_class=HTMLResponse)
async def public_page(token: str):
    if not PUBLIC_READ_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if token != PUBLIC_READ_TOKEN:
        raise HTTPException(status_code=404, detail='Not found')
    return public_html()


@app.get('/api/state')
async def api_state(request: Request):
    require_session(request)
    return get_snapshot()


@app.get('/api/public/state/{token}')
async def api_public_state(token: str):
    if not PUBLIC_READ_ENABLED:
        return JSONResponse({'error': 'forbidden'}, status_code=403)
    if token != PUBLIC_READ_TOKEN:
        return JSONResponse({'error': 'forbidden'}, status_code=403)
    s = get_snapshot()
    return {
        'running': s['running'],
        'server_info': s['server_info'],
        'metrics': s['metrics'],
    }


@app.post('/api/start')
async def api_start(request: Request):
    require_session(request)
    _require_csrf(request)
    return {'ok': True, 'message': ServerService.start()}


@app.post('/api/stop')
async def api_stop(request: Request):
    require_session(request)
    _require_csrf(request)
    return {'ok': True, 'message': ServerService.stop()}


@app.post('/api/restart')
async def api_restart(request: Request):
    require_session(request)
    _require_csrf(request)
    return {'ok': True, 'message': ServerService.restart()}


@app.post('/api/toggle/{name}')
async def api_toggle(name: str, request: Request):
    require_session(request)
    _require_csrf(request)
    if name not in ('auto_start', 'auto_stop'):
        return JSONResponse({'ok': False, 'error': 'unknown toggle'}, status_code=400)
    state[name] = not bool(state[name])
    state['last_action'] = f'toggle:{name}'
    state['last_status_note'] = f'{name} -> {state[name]}'
    return {'ok': True, 'name': name, 'value': state[name]}


@app.get('/api/ws-ticket')
async def api_ws_ticket(request: Request):
    require_session(request)
    ticket = __import__('secrets').token_urlsafe(24)
    _ws_tickets[ticket] = now_ts() + 30
    return {'ticket': ticket}


@app.get('/api/csrf')
async def api_csrf(request: Request):
    require_session(request)
    token = str(request.session.get('csrf_token', '') or '')
    if not token:
        token = __import__('secrets').token_urlsafe(24)
        request.session['csrf_token'] = token
    return {'csrf_token': token, 'enabled': CSRF_ENABLED}


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
        from .config import LOG_FILE
        if LOG_FILE.exists():
            # Stream from the start of current log so console panel is populated immediately.
            log_offset = 0
        while True:
            await ws.send_json({'type': 'snapshot', 'data': get_snapshot()})
            diff = LogService.diff_from(log_offset)
            log_offset = diff['next_offset']
            if diff['chunk']:
                await ws.send_json({'type': 'log', 'chunk': diff['chunk']})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


@app.post('/api/console/send')
async def api_console_send(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    command = str(data.get('command', '')).strip()
    tier = str(data.get('tier', _console_policy.get('tier', 'safe'))).strip().lower()
    if tier not in ('safe', 'moderate', 'admin'):
        return JSONResponse({'error': 'Invalid tier'}, status_code=400)
    _console_policy['tier'] = tier
    res = ServerService.send_console_command(command, tier=tier)
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'failed')}, status_code=400)
    return {'ok': True, 'message': res.get('message', 'sent')}


@app.get('/api/console/history')
async def api_console_history(request: Request):
    require_session(request)
    return {'history': list(_console_history), 'tier': _console_policy.get('tier', 'safe')}


@app.get('/api/players/state')
async def api_players_state(request: Request):
    require_session(request)
    props = PropertiesService.read_all()
    snap = get_snapshot()
    return {
        'ops': PlayerService.list_ops(),
        'whitelist': PlayerService.list_whitelist(),
        'banned': PlayerService.list_banned(),
        'whitelist_enabled': props.get('white-list', 'false'),
        'online_players': snap.get('server_info', {}).get('player_names', []),
        'online_count': snap.get('server_info', {}).get('players_online', 0),
    }


@app.post('/api/players/action')
async def api_players_action(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    action = str(data.get('action', '')).strip()
    name = str(data.get('name', '')).strip()
    reason = str(data.get('reason', '')).strip()

    if action not in ('op', 'deop', 'whitelist_add', 'whitelist_remove', 'ban', 'pardon', 'kick'):
        return JSONResponse({'error': 'Unsupported action'}, status_code=400)

    try:
        name = PlayerService.validate_name(name)
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=400)

    cmd = {
        'op': f'op {name}',
        'deop': f'deop {name}',
        'whitelist_add': f'whitelist add {name}',
        'whitelist_remove': f'whitelist remove {name}',
        'ban': f'ban {name} {reason}'.strip(),
        'pardon': f'pardon {name}',
        'kick': f'kick {name} {reason}'.strip(),
    }[action]

    res = ServerService.send_console_command(cmd, tier='admin')
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'failed')}, status_code=400)
    return {'ok': True, 'message': f'{action} sent for {name}'}


@app.post('/api/players/whitelist/toggle')
async def api_whitelist_toggle(request: Request):
    require_session(request)
    _require_csrf(request)
    props = PropertiesService.read_all()
    enabled = props.get('white-list', 'false').lower() == 'true'
    new_val = 'false' if enabled else 'true'
    props['white-list'] = new_val
    props['enforce-whitelist'] = new_val
    PropertiesService.write_all(props)

    if ServerService.is_running():
        ServerService.send_console_command(f'whitelist {"on" if new_val=="true" else "off"}', tier='admin')

    return {'ok': True, 'message': f'Whitelist now {new_val}'}


@app.get('/api/properties')
async def api_properties(request: Request):
    require_session(request)
    return {'values': PropertiesService.get_editable_view(), 'schema': PropertiesService.ALLOWED_EDIT_KEYS}


@app.post('/api/properties')
async def api_properties_save(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    updates = data.get('updates') or {}
    if not isinstance(updates, dict):
        return JSONResponse({'error': 'updates must be object'}, status_code=400)

    try:
        clean = PropertiesService.validate_updates(updates)
    except ValueError as e:
        return JSONResponse({'error': str(e)}, status_code=400)

    props = PropertiesService.read_all()
    props.update(clean)
    PropertiesService.write_all(props)
    return {'ok': True, 'message': f'Applied {len(clean)} property changes'}


@app.get('/api/seed')
async def api_seed(request: Request):
    require_session(request)
    return {'seed': SeedService.get_seed()}


@app.post('/api/seed/generate')
async def api_seed_generate(request: Request):
    require_session(request)
    _require_csrf(request)
    return {'seed': SeedService.random_seed()}


@app.post('/api/seed/apply')
async def api_seed_apply(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    res = SeedService.apply_seed(data.get('seed', ''))
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'failed')}, status_code=400)
    return res


@app.get('/api/world/backups')
async def api_world_backups(request: Request):
    require_session(request)
    return {'items': WorldService.list_backups()}


@app.post('/api/world/backup')
async def api_world_backup(request: Request):
    require_session(request)
    _require_csrf(request)
    res = WorldService.create_backup()
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'backup failed')}, status_code=400)
    return {'ok': True, 'message': f"Backup created: {res['name']}", 'backup': res}


@app.post('/api/world/reset')
async def api_world_reset(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    return WorldService.reset_world(with_backup=bool(data.get('with_backup', True)), new_seed=data.get('new_seed', None))


@app.post('/api/world/restore')
async def api_world_restore(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    res = WorldService.restore_backup(str(data.get('name', '')).strip())
    if not res.get('ok'):
        payload = {'error': res.get('error', 'restore failed')}
        if 'details' in res:
            payload['details'] = res['details']
        return JSONResponse(payload, status_code=400)
    return res


@app.get('/api/world/download-url')
async def api_world_download_url(request: Request):
    require_session(request)
    res = WorldService.create_backup()
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'download failed')}, status_code=400)
    return {'url': f"/api/world/download/{res['name']}"}


@app.get('/api/world/download/{name}')
async def api_world_download(name: str, request: Request):
    require_session(request)
    backup_path = WorldService._resolve_backup_path(name)
    if backup_path is None:
        raise HTTPException(status_code=400, detail='Invalid file')
    if not backup_path.exists() or not backup_path.is_file():
        raise HTTPException(status_code=404, detail='Not found')
    return FileResponse(path=str(backup_path), filename=backup_path.name, media_type='application/zip')


@app.post('/api/world/upload-b64')
async def api_world_upload_b64(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    res = WorldService.upload_world_zip_b64(str(data.get('archive_b64', '')), str(data.get('filename', 'uploaded-world.zip')))
    if not res.get('ok'):
        payload = {'error': res.get('error', 'upload failed')}
        if 'details' in res:
            payload['details'] = res['details']
        return JSONResponse(payload, status_code=400)
    return res


@app.post('/api/world/upload')
async def api_world_upload(request: Request, file: UploadFile = File(...)):
    require_session(request)
    _require_csrf(request)
    max_upload_bytes = WorldService.MAX_UPLOAD_BYTES
    chunk_size = 1024 * 1024
    raw = bytearray()

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        if len(raw) + len(chunk) > max_upload_bytes:
            return JSONResponse(
                {'error': f'Upload too large (max {max_upload_bytes // (1024 * 1024)} MB)'},
                status_code=400,
            )
        raw.extend(chunk)

    res = WorldService.upload_world_zip_bytes(bytes(raw), file.filename or 'uploaded-world.zip')
    if not res.get('ok'):
        payload = {'error': res.get('error', 'upload failed')}
        if 'details' in res:
            payload['details'] = res['details']
        return JSONResponse(payload, status_code=400)
    return res


@app.get('/api/scheduler')
async def api_scheduler_get(request: Request):
    require_session(request)
    return _scheduler


@app.post('/api/scheduler')
async def api_scheduler_set(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    try:
        restart_minutes = int(data.get('restart_minutes', 0) or 0)
        backup_minutes = int(data.get('backup_minutes', 0) or 0)
    except Exception:
        return JSONResponse({'error': 'Invalid schedule values'}, status_code=400)

    if restart_minutes < 0 or backup_minutes < 0:
        return JSONResponse({'error': 'Schedule values must be >= 0'}, status_code=400)
    if restart_minutes > 10080 or backup_minutes > 10080:
        return JSONResponse({'error': 'Schedule values too large (max 10080 minutes)'}, status_code=400)

    _scheduler['restart_minutes'] = restart_minutes
    _scheduler['backup_minutes'] = backup_minutes
    save_scheduler()
    return {'ok': True, 'message': 'Schedule saved', 'scheduler': _scheduler}


@app.get('/api/analytics')
async def api_analytics(request: Request):
    require_session(request)
    return AnalyticsService.summary(hours=6)


@app.get('/api/plugins/catalog')
async def api_plugins_catalog(request: Request):
    require_session(request)
    return {'items': PluginService.catalog()}


@app.get('/api/plugins/staged')
async def api_plugins_staged(request: Request):
    require_session(request)
    return {'items': PluginService.staged()}


@app.post('/api/plugins/stage')
async def api_plugins_stage(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    res = PluginService.stage_from_catalog(str(data.get('id', '')))
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'failed')}, status_code=400)
    return res


@app.post('/api/plugins/remove')
async def api_plugins_remove(request: Request):
    require_session(request)
    _require_csrf(request)
    data = await _parse_json_object(request)
    res = PluginService.remove_staged(str(data.get('file', '')))
    if not res.get('ok'):
        return JSONResponse({'error': res.get('error', 'failed')}, status_code=400)
    return res


async def refresh_cache_loop():
    import psutil

    psutil.cpu_percent(interval=None)
    while True:
        try:
            _cache['snapshot'] = build_snapshot()
            _cache['updated_at'] = now_ts()
        except Exception:
            logger.exception("refresh_cache_loop iteration failed")
        await asyncio.sleep(3)


async def refresh_logs_loop():
    while True:
        try:
            _cache['logs'] = LogService.tail(140)
        except Exception:
            logger.exception("refresh_logs_loop iteration failed")
        await asyncio.sleep(8)


async def automation_loop():
    first_cycle = True
    while True:
        try:
            now = now_ts()
            for t, exp in list(_ws_tickets.items()):
                if exp < now:
                    _ws_tickets.pop(t, None)

            s = get_snapshot()
            running = s['running']
            players_online = s['server_info']['players_online']

            # Auto-start intentionally disabled: dashboard must never start MC automatically.
            # Server start should only happen via explicit manual action (API/start button).

            if state['auto_stop'] and running:
                if players_online == 0:
                    if state['no_player_since'] is None:
                        state['no_player_since'] = now
                        state['last_status_note'] = 'No players detected, shutdown timer started'
                    elif now - state['no_player_since'] > 300:
                        ServerService.stop()
                        state['last_status_note'] = 'Auto-stop triggered after 5m with no players'
                        state['no_player_since'] = None
                else:
                    state['no_player_since'] = None

            rmin = int(_scheduler.get('restart_minutes', 0) or 0)
            if rmin > 0 and running:
                last = float(_scheduler.get('last_restart_at', 0) or 0)
                if now - last >= rmin * 60:
                    ServerService.send_console_command('say [Dashboard] Scheduled restart in 10 seconds', tier='admin', unsafe_ok=True)
                    await asyncio.sleep(10)
                    ServerService.restart()
                    _scheduler['last_restart_at'] = now_ts()
                    save_scheduler()

            bmin = int(_scheduler.get('backup_minutes', 0) or 0)
            if bmin > 0:
                lastb = float(_scheduler.get('last_backup_at', 0) or 0)
                if now - lastb >= bmin * 60:
                    WorldService.create_backup()
                    _scheduler['last_backup_at'] = now_ts()
                    save_scheduler()

            first_cycle = False
        except Exception:
            logger.exception("automation_loop iteration failed")
        await asyncio.sleep(15)



