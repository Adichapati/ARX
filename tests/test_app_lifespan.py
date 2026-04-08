import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import dashboard.app as app_module


class AppLifespanTests(unittest.TestCase):
    def test_lifespan_runs_startup_and_cancels_background_tasks_on_shutdown(self):
        async def exercise() -> None:
            started = {
                "refresh_cache": False,
                "refresh_logs": False,
                "automation": False,
                "join_watcher": False,
                "op_assist": False,
            }
            cancelled = {name: False for name in started}
            task_refs: dict[str, asyncio.Task] = {}
            hold_open = asyncio.Event()

            def make_loop(name: str):
                async def _loop(*_args, **_kwargs):
                    started[name] = True
                    task_refs[name] = asyncio.current_task()
                    try:
                        await hold_open.wait()
                    except asyncio.CancelledError:
                        cancelled[name] = True
                        raise

                return _loop

            old_auto_start = app_module.state.get("auto_start")

            try:
                with (
                    patch("dashboard.config.ensure_dirs") as ensure_dirs,
                    patch("dashboard.config.load_scheduler") as load_scheduler,
                    patch.object(app_module, "refresh_cache_loop", new=make_loop("refresh_cache")),
                    patch.object(app_module, "refresh_logs_loop", new=make_loop("refresh_logs")),
                    patch.object(app_module, "automation_loop", new=make_loop("automation")),
                    patch.object(app_module.JoinWatcherService, "run_loop", new=make_loop("join_watcher")),
                    patch.object(app_module.OpAssistService, "run_loop", new=make_loop("op_assist")),
                ):
                    app_module.state["auto_start"] = True

                    async with app_module.app.router.lifespan_context(app_module.app):
                        await asyncio.sleep(0)
                        await asyncio.sleep(0)

                        ensure_dirs.assert_called_once_with()
                        load_scheduler.assert_called_once_with()
                        self.assertFalse(app_module.state["auto_start"])
                        self.assertTrue(all(started.values()), f"not started: {started}")

                    await asyncio.sleep(0)
                    self.assertTrue(all(cancelled.values()), f"not cancelled: {cancelled}")
            finally:
                app_module.state["auto_start"] = old_auto_start
                leftovers = [t for t in task_refs.values() if t is not None and not t.done()]
                for task in leftovers:
                    task.cancel()
                if leftovers:
                    await asyncio.gather(*leftovers, return_exceptions=True)

        asyncio.run(exercise())

    def test_cancel_background_tasks_times_out_without_hanging(self):
        async def exercise() -> None:
            stop = asyncio.Event()

            async def _stubborn_loop() -> None:
                while not stop.is_set():
                    try:
                        await asyncio.sleep(3600)
                    except asyncio.CancelledError:
                        # Simulate a misbehaving task that ignores cancellation.
                        continue

            task = asyncio.create_task(_stubborn_loop())
            await asyncio.sleep(0)
            try:
                with patch("dashboard.app.logger") as mock_logger:
                    await app_module._cancel_background_tasks([task])
                    mock_logger.warning.assert_called_once_with(
                        "Timed out waiting for %d background task(s) to cancel",
                        1,
                    )
            finally:
                stop.set()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        with patch("dashboard.app.BACKGROUND_TASK_CANCEL_TIMEOUT_SECONDS", 0.01):
            asyncio.run(exercise())

    def test_send_telegram_message_runs_urlopen_in_thread(self):
        async def exercise() -> None:
            class _Response:
                def read(self, *_args, **_kwargs):
                    return b"ok"

            class _Ctx:
                def __enter__(self):
                    return _Response()

                def __exit__(self, *_args):
                    return False

            with (
                patch("dashboard.app.TELEGRAM_BOT_TOKEN", "token"),
                patch("dashboard.app.TELEGRAM_CHAT_ID", "chat"),
                patch("dashboard.app.asyncio.to_thread", new=AsyncMock()) as to_thread,
                patch("dashboard.app.urllib.request.urlopen", return_value=_Ctx()) as urlopen,
            ):
                await app_module._send_telegram_message("hello")

                to_thread.assert_awaited_once()
                target = to_thread.await_args.args[0]
                self.assertTrue(callable(target))
                target()
                urlopen.assert_called_once()

        asyncio.run(exercise())
