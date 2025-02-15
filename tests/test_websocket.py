import asyncio
from dataclasses import dataclass
from pathlib import Path
import sched
import time
from typing import ClassVar
from unittest import TestCase, main as unittest_main
from unittest.mock import Mock, patch, ANY

from flask_socketio import SocketIO
from pyfakefs.fake_filesystem_unittest import TestCaseMixin as PyfakefsTestCaseMixin

from dashlive.mpeg.dash.validator.errors import (
    ErrorSource,
    StackFrameJson,
    ValidationError,
    ValidationErrorJson,
)
from dashlive.mpeg.dash.validator.options import ValidatorOptions
from dashlive.mpeg.dash.validator.progress import Progress
from dashlive.mpeg.dash.validator.requests_http_client import RequestsHttpClient
from dashlive.server.requesthandler.websocket import ClientConnection, ValidatorSettings
from dashlive.server.asyncio_loop import AsyncLoopOwner, AsyncioLoop

from .mixins.mixin import TestCaseMixin


@dataclass(slots=True, kw_only=True)
class FakeStackFrame:
    filename: str
    lineno: int
    module: str

    def to_dict(self) -> StackFrameJson:
        rv: StackFrameJson = {
            "filename": self.filename,
            "line": self.lineno,
            "module": self.module,
        }
        return rv


class FakeValidator:
    MANIFEST_LINES: ClassVar[list[str]] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<MPD>",
        '<Period duration="PT0S" />',
        "</MPD>",
    ]
    CODECS: ClassVar[set[str]] = {"avc3.640028", "mp4a.40.2"}
    errors: list[ValidationErrorJson] = []
    finished: bool = False
    increment: float = 0.5
    load_return: bool = True
    manifest: str
    num_run_steps: int = 40
    options: ValidatorOptions
    run_return: bool = True
    todo: int = 40

    def __init__(
        self, manifest: str, options: ValidatorOptions, http_client: RequestsHttpClient
    ) -> None:
        self.manifest = manifest
        self.options = options

    async def load(self) -> bool:
        return self.load_return

    def get_manifest_lines(self) -> list[str]:
        return FakeValidator.MANIFEST_LINES

    def get_codecs(self) -> set[str]:
        return FakeValidator.CODECS

    async def run(self) -> bool:
        progress: Progress = self.options.progress
        assert progress is not None
        self.todo = self.num_run_steps
        progress.add_todo(self.todo)
        while not progress.aborted() and not self.finished:
            await asyncio.sleep(0.025)
            progress.inc()
            self.todo -= 1
            if self.todo == 0:
                self.finished = True
                progress.finished("DASH validation complete")
        return self.run_return

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def get_errors(self) -> list[ValidationErrorJson]:
        return self.errors


class FakeLoop(AsyncLoopOwner):
    started: bool = False
    scheduler = sched.scheduler(time.time, time.sleep)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        if not self.started:
            return
        self.started = False
        self.scheduler.run(blocking=True)

    def run_coroutine(self, fn, args, **kwargs) -> asyncio.Future:
        self.scheduler.enter(0.1, fn, argument=args, kwargs=kwargs)


class TestServerOptions(TestCaseMixin, PyfakefsTestCaseMixin, TestCase):
    SRC_DIR: ClassVar[Path] = Path(__file__).parent.parent.parent.absolute()
    upload_dir: str
    loop: AsyncLoopOwner

    good_settings: ValidatorSettings = {
        "duration": 10,
        "encrypted": False,
        "manifest": "http://unit.test.local/manifest.mpd",
        "media": True,
        "prefix": "",
        "pretty": True,
        "save": False,
        "title": "",
        "verbose": False,
    }

    def setUp(self) -> None:
        super().setUp()
        self.fake = None
        drive: str = self.SRC_DIR.drive
        self.setUpPyfakefs()
        self.upload_dir = f"{drive}/upload"
        self.loop = AsyncioLoop()

    def tearDown(self) -> None:
        super().tearDown()
        self.loop.stop()

    def test_create_and_shutdown(self) -> None:
        socket_mock = Mock(spec=SocketIO)
        conn = ClientConnection(self.loop, socket_mock, "abc123", self.upload_dir)
        self.assertFalse(conn.aborted())
        conn.shutdown()
        self.assertTrue(conn.aborted())

    def test_invalid_command_missing_method(self) -> None:
        socket_mock = Mock(spec=SocketIO)
        conn = ClientConnection(self.loop, socket_mock, "abc123", self.upload_dir)
        conn.event_handler({})
        socket_mock.emit.assert_called_with(
            "log", {"level": "error", "test": "method parameter missing"}, to="abc123"
        )
        conn.shutdown()

    def test_invalid_command(self) -> None:
        socket_mock = Mock(spec=SocketIO)
        conn = ClientConnection(self.loop, socket_mock, "abc123", self.upload_dir)
        conn.event_handler({"method": "not.a.command"})
        socket_mock.emit.assert_called_with(
            "log",
            {"level": "error", "test": 'Invalid command: "not.a.command"'},
            to="abc123",
        )
        conn.shutdown()

    def test_start_with_invalid_settings(self) -> None:
        socket_mock = Mock(spec=SocketIO)
        conn = ClientConnection(self.loop, socket_mock, "abc123", self.upload_dir)
        settings: ValidatorSettings = {
            **self.good_settings,
            "duration": 0,
            "manifest": "",
        }
        conn.event_handler(
            {
                "method": "validate",
                **settings,
            }
        )
        errs: dict[str, str] = {
            "manifest": "A manifest URL is required",
            "duration": "Invalid duration 0",
        }
        socket_mock.emit.assert_called_with("validate-errors", errs, to="abc123")
        conn.shutdown()

    @patch("dashlive.server.requesthandler.websocket.BasicDashValidator", spec=True)
    def test_start(self, bdv_mock) -> None:
        bdv_mock.return_value.load.return_value = True
        bdv_mock.return_value.has_errors.return_value = True
        bdv_mock.return_value.get_manifest_lines.return_value = (
            FakeValidator.MANIFEST_LINES
        )
        bdv_mock.return_value.get_codecs.return_value = FakeValidator.CODECS
        errs: list[ValidationError] = [
            ValidationError(
                assertion=FakeStackFrame(
                    filename="adaptation_set.py", lineno=123, module="AdaptationSet"
                ),
                source=ErrorSource.ELEMENT,
                location=[12, 15],
                msg="a validation error message",
                clause="1.2.3",
            ),
        ]
        bdv_mock.return_value.get_errors.return_value = errs
        socket_mock = Mock(spec=SocketIO)
        self.loop.start()
        conn = ClientConnection(self.loop, socket_mock, "abc123", self.upload_dir)
        conn.event_handler(
            {
                "method": "validate",
                **self.good_settings,
            }
        )
        conn.wait_for_all_tasks(10)
        bdv_mock.assert_called_with(
            self.good_settings["manifest"], options=ANY, http_client=ANY
        )
        kwargs = bdv_mock.mock_calls[0][2]
        options: ValidatorOptions = kwargs["options"]
        self.assertIsInstance(options, ValidatorOptions)
        self.assertEqual(options.duration, 10)
        self.assertEqual(options.verbose, 0)
        self.assertEqual(options.pretty, True)
        bdv_mock.return_value.load.assert_awaited()
        bdv_mock.return_value.run.assert_awaited()
        bdv_mock.return_value.get_errors.assert_called()
        finished_emitted: bool = False
        for emit in socket_mock.emit.call_args_list:
            cmd: str
            data: dict | list[str]
            self.assertDictEqual(emit.kwargs, {"to": "abc123"})
            self.assertEqual(len(emit.args), 2)
            cmd, data = emit.args
            self.assertIn(
                cmd,
                {
                    "codecs",
                    "finished",
                    "log",
                    "manifest",
                    "manifest-errors",
                    "progress",
                },
            )
            if cmd == "codecs":
                self.assertListEqual(data, sorted(list(FakeValidator.CODECS)))
            elif cmd == "finished":
                self.assertFalse(data["aborted"])
                finished_emitted = True
            elif cmd == "manifest":
                self.assertListEqual(data["text"], FakeValidator.MANIFEST_LINES)
            elif cmd == "manifest-errors":
                self.assertListEqual(data, [e.to_dict() for e in errs])
        self.assertTrue(finished_emitted)
        conn.shutdown()

    @patch("dashlive.server.requesthandler.websocket.BasicDashValidator", spec=True)
    def test_load_fails(self, bdv_mock) -> None:
        bdv_mock.return_value.load.return_value = False
        socket_mock = Mock(spec=SocketIO)
        self.loop.start()
        conn = ClientConnection(self.loop, socket_mock, "abc123", self.upload_dir)
        conn.event_handler(
            {
                "method": "validate",
                **self.good_settings,
            }
        )
        conn.wait_for_all_tasks(10)
        bdv_mock.return_value.load.assert_awaited()
        bdv_mock.return_value.run.assert_not_awaited()
        conn.shutdown()

    @patch("dashlive.server.requesthandler.websocket.BasicDashValidator", spec=True)
    def test_cancel(self, bdv_mock) -> None:
        fake: FakeValidator | None = None

        def create_fake(
            manifest: str, options: ValidatorOptions, http_client: RequestsHttpClient
        ) -> FakeValidator:
            nonlocal fake
            fake = FakeValidator(manifest, options, http_client)
            return fake

        bdv_mock.side_effect = create_fake
        socket_mock = Mock(spec=SocketIO)
        self.loop.start()
        conn = ClientConnection(self.loop, socket_mock, "abc123", self.upload_dir)
        conn.event_handler(
            {
                "method": "validate",
                **self.good_settings,
            }
        )
        timeout: int = 10
        while fake is None and timeout > 0:
            time.sleep(0.1)
            timeout -= 1
        self.assertIsNotNone(fake, "BasicDashValidator was not called before timeout")
        while fake.todo > 35:
            # print(f"while <5 {fake.todo}")
            time.sleep(0.01)
        conn.event_handler(
            {
                "method": "cancel",
            }
        )
        conn.wait_for_all_tasks(10)
        self.assertTrue(fake.options.progress.aborted())
        self.assertGreater(fake.todo, 0)
        conn.shutdown()


if __name__ == "__main__":
    unittest_main()
