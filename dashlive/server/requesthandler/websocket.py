#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import queue
import logging
from logging.handlers import QueueHandler, QueueListener
import time

from dashlive.utils.json_object import JsonObject
from dashlive.mpeg.dash.validator.options import ValidatorOptions
from dashlive.mpeg.dash.validator.basic import BasicDashValidator
from dashlive.mpeg.dash.validator.progress import Progress

from .ws_log_handler import WebsocketLogHandler

class WebsocketHandler(Progress):
    def __init__(self, sockio) -> None:
        super().__init__()
        self.sockio = sockio
        self.dash_log = logging.getLogger('DashValidator')
        self.dash_log.propagate = False
        self._aborted = False

    def connect(self) -> None:
        log_queue = queue.Queue(-1)
        self.queue_handler = QueueHandler(log_queue)
        self.dash_log.addHandler(self.queue_handler)
        self.listener = QueueListener(log_queue, WebsocketLogHandler(self.sockio))
        self.listener.start()

    def disconnect(self) -> None:
        self.listener.stop()
        self.dash_log.removeHandler(self.queue_handler)
        self.queue_handler = None
        self.listener = None

    def event_handler(self, data: JsonObject) -> None:
        if not isinstance(data, dict):
            return
        try:
            cmd = data['method']
        except KeyError as err:
            self.sockio.emit('log', f'Invalid command: {err}')
            return
        if cmd == 'hello':
            self.hello_cmd(data)
        elif cmd == 'validate':
            self.validate_cmd(data)
        elif cmd == 'cancel':
            self.cancel_cmd(data)

    def send_progress(self, pct: float, text: str) -> None:
        self.sockio.emit('progress', {'pct': round(pct), 'text': text})

    def aborted(self) -> bool:
        return self._aborted

    def hello_cmd(self, data) -> None:
        self.sockio.emit('hello', {'hello': 'world'})

    def validate_cmd(self, data) -> None:
        data['verbose'] = data.get('verbose', '').lower() == 'on'
        data['duration'] = int(data['duration'])
        self._aborted = False
        self.task = self.sockio.start_background_task(self.dash_validator_task, **data)

    def dash_validator_task(self,
                            method: str,
                            manifest: str,
                            duration: int,
                            verbose: bool) -> None:
        start_time = time.time()
        self.dash_log.info('Fetching manifest: %s', manifest)
        print('verbose', verbose)
        if verbose:
            self.dash_log.setLevel(logging.DEBUG)
        else:
            self.dash_log.setLevel(logging.INFO)
        opts = ValidatorOptions(
            verbose=verbose, duration=duration, log=self.dash_log,
            progress=self)
        dv = BasicDashValidator(manifest, opts)
        try:
            dv.load()
            self.dash_log.info('Starting stream validation...')
            dv.validate()
            duration = round(time.time() - start_time)
            self.dash_log.info(f'DASH validation complete after {duration} seconds')
            self.sockio.emit('progress', {'pct': 100, 'text': '', 'finished': True})
        except Exception as err:
            print(err)
            self.dash_log.error('%s', err)
            raise

    def cancel_cmd(self, data) -> None:
        self.sockio.emit('log', {
            'level': 'info',
            'text': 'Cancelled validation'
        })
        self._aborted = True
