#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from concurrent.futures import Future
import queue
import logging
from logging.handlers import QueueHandler, QueueListener
import tempfile
import time
from typing import Optional

import flask

from dashlive.utils.json_object import JsonObject
from dashlive.management.populate import PopulateDatabase
from dashlive.management.backend_db import BackendDatabaseAccess
from dashlive.mpeg.dash.validator.concurrent_pool import ConcurrentWorkerPool
from dashlive.mpeg.dash.validator.options import ValidatorOptions
from dashlive.mpeg.dash.validator.basic import BasicDashValidator
from dashlive.mpeg.dash.validator.pool import WorkerPool
from dashlive.mpeg.dash.validator.progress import Progress
from dashlive.mpeg.dash.validator.requests_http_client import RequestsHttpClient
from dashlive.mpeg.dash.validator.validation_flag import ValidationFlag
from dashlive.server import models
from dashlive.server.asyncio_loop import asyncio_loop
from dashlive.server.thread_pool import pool_executor

from .ws_log_handler import WebsocketLogHandler

class ClientConnection(Progress):
    def __init__(self, sockio, session_id) -> None:
        super().__init__()
        self.sockio = sockio
        self.session_id = session_id
        self.dash_log = logging.getLogger('DashValidator')
        self.dash_log.propagate = False
        self._aborted = False
        self.tasks: set[Future] = set()
        self.tmpdir: Optional[tempfile.TemporaryDirectory] = None
        self.pool = ConcurrentWorkerPool(pool_executor)
        log_queue = queue.Queue(-1)
        self.queue_handler = QueueHandler(log_queue)
        self.dash_log.addHandler(self.queue_handler)
        self.listener = QueueListener(
            log_queue, WebsocketLogHandler(sockio, session_id))
        self.listener.start()

    def shutdown(self) -> None:
        self._aborted = True
        self.join_finished_tasks()
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.queue_handler:
            self.dash_log.removeHandler(self.queue_handler)
            self.queue_handler = None
        # if self.tmpdir:
        #     shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.tmpdir = None

    def event_handler(self, data: JsonObject) -> None:
        self.join_finished_tasks()
        if not isinstance(data, dict):
            return
        try:
            cmd = data['method']
        except KeyError as err:
            self.sockio.emit('log', {
                "level": "error",
                "test": f'Invalid command: {err}'
            }, to=flask.request.sid)
            return
        if cmd == 'validate':
            self.validate_cmd(data)
        elif cmd == 'cancel':
            self.cancel_cmd(data)
        elif cmd == 'done':
            self.join_finished_tasks()
        elif cmd == 'save':
            self.save_cmd(data)

    def emit(self, cmd, data) -> None:
        self.sockio.emit(cmd, data, to=self.session_id)

    def send_progress(self, pct: float, text: str) -> None:
        self.emit('progress', {'pct': round(pct), 'text': text})

    def aborted(self) -> bool:
        return self._aborted

    def validate_cmd(self, data) -> None:
        self._aborted = False
        for field in ['pretty', 'encrypted', 'media', 'save']:
            data[field] = data.get(field, '').lower() == 'on'
        if data.get('verbose', '').lower() == 'on':
            data['verbose'] = 1
        else:
            data['verbose'] = 0
        data['duration'] = int(data['duration'])
        self._aborted = False
        errs = {}
        if data['save']:
            if data['prefix'] == '':
                errs['prefix'] = 'Directory name is required'
            else:
                stream = models.Stream.get(directory=data['prefix'])
                if stream is not None:
                    errs['prefix'] = f'"{data["directory"]}" directory already exists'
            if data['title'] == '':
                errs['title'] = 'Title is required'
        if errs:
            self.emit('manifest-validation', errs)
            return
        upload_dir = flask.current_app.config['UPLOAD_FOLDER']
        if self.tmpdir is not None:
            self.emit('log', {
                'level': 'error',
                'text': 'Saving stream already in progress'
            })
            return
        self.tasks.add(asyncio_loop.run_coroutine(
            self.dash_validator_task, pool=self.pool, upload_dir=upload_dir, **data))

    def cancel_cmd(self, data) -> None:
        self.emit('log', {
            'level': 'info',
            'text': 'Cancelled validation'
        })
        self._aborted = True

    def save_cmd(self, data) -> None:
        self._aborted = False
        self.emit('log', {
            'level': 'info',
            'text': 'Creating stream'
        })
        del data['method']
        self.save_stream_task(**data)

    async def dash_validator_task(
            self, method: str, manifest: str, upload_dir: str, pool: WorkerPool,
            media: bool, **kwargs) -> None:
        if self.tmpdir is not None:
            self.emit('log', {
                'level': 'error',
                'text': 'Saving stream already in progress'
            })
            return
        start_time = time.time()
        opts = ValidatorOptions(log=self.dash_log, progress=self, pool=pool, **kwargs)
        if opts.save:
            self.tmpdir = tempfile.TemporaryDirectory(dir=upload_dir)
            opts.dest = self.tmpdir.name
        if opts.verbose:
            self.dash_log.setLevel(logging.DEBUG)
        else:
            self.dash_log.setLevel(logging.INFO)
        if not media:
            opts.verify &= ~ValidationFlag.MEDIA
        dv = BasicDashValidator(manifest, options=opts, http_client=RequestsHttpClient(opts))
        try:
            if not await dv.load():
                self.dash_log.error('loading manifest failed')
                return
            self.dash_log.debug('loading manifest complete')
            self.emit('manifest', {
                'text': dv.get_manifest_lines()
            })
            await dv.run()
            self.emit('codecs', sorted(list(dv.get_codecs())))
            if dv.has_errors():
                errs = [e.to_dict() for e in dv.get_errors()]
                self.dash_log.info('Found %d errors', len(errs))
                self.emit('manifest-errors', errs)
            duration = round(time.time() - start_time)
            txt = f'DASH validation complete after {duration:#5.1f} seconds'
            self.dash_log.info(txt)
            self.emit('progress', {
                'pct': 100,
                'text': txt,
                'finished': True
            })
            if opts.save:
                self.emit('script', {
                    'filename': dv.get_json_script_filename(),
                    'prefix': opts.prefix,
                    'title': opts.title,
                })
        except Exception as err:
            self.dash_log.error('%s', err)

    def save_stream_task(self, filename: str, prefix: str, title: str):
        bda = BackendDatabaseAccess()
        pd = PopulateDatabase(bda)
        bda.log = self.dash_log
        pd.log = self.dash_log
        self.dash_log.info(f'Adding new stream {prefix}: "{title}"')
        self.dash_log.debug('Installing %s', filename)
        pd.populate_database(filename)
        self.dash_log.info('Adding new stream complete')
        self.emit('progress', {
            'pct': 100,
            'text': f'Added stream "{title}" ({prefix}) to this server',
            'finished': True
        })

    def join_finished_tasks(self) -> None:
        done: set[Future] = set()
        for tsk in self.tasks:
            if not tsk.done():
                done.add(tsk)
        for tsk in done:
            self.tasks.remove(tsk)
        for tsk in done:
            try:
                tsk.result()
            except Exception as err:
                self.dash_log.error('Validation error: %s', err)


class WebsocketHandler:
    def __init__(self, sockio) -> None:
        self.sockio = sockio

    def connect(self) -> None:
        logging.debug('WebSocket connection %s', flask.request.sid)

    def disconnect(self) -> None:
        if 'websock_connection' in flask.g:
            if flask.g.websock_connection.session_id == flask.request.sid:
                con = flask.g.pop('websock_connection', None)
                if con:
                    con.shutdown()

    def event_handler(self, data: JsonObject) -> None:
        if 'method' not in data:
            self.sockio.emit('log', {
                "level": "error",
                "test": 'Invalid request - no method',
            }, to=flask.request.sid)
            return
        if 'websock_connection' not in flask.g:
            flask.g.websock_connection = ClientConnection(
                self.sockio, flask.request.sid)
        flask.g.websock_connection.event_handler(data)
