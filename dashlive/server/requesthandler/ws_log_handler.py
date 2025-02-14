#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging

from flask_socketio import SocketIO

class WebsocketLogHandler(logging.Handler):
    sock: SocketIO
    session_id: str

    def __init__(self, sock: SocketIO, session_id: str, level=logging.NOTSET) -> None:
        super().__init__(level)
        self.sock = sock
        self.session_id = session_id

    def emit(self, record: logging.LogRecord) -> None:
        msg: str = record.getMessage()
        self.sock.emit('log', {
            'level': record.levelname.lower(),
            'text': msg
        }, to=self.session_id)
