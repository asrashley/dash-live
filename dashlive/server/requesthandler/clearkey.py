#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import binascii
from builtins import map
import base64
import json

import flask

from dashlive.server import models
from .base import RequestHandlerBase

class ClearkeyHandler(RequestHandlerBase):
    def post(self):
        def to_hex(data: bytes) -> str:
            return str(binascii.b2a_hex(data), 'ascii')
        result = {"error": None}
        req = flask.request.json
        try:
            kids = req["kids"]
        except KeyError:
            return self.jsonify('kids property missing', 400)
        try:
            kids = list(map(self.base64url_decode, kids))
            kids = [to_hex(k) for k in kids]
            keys = []
            for kid, key in models.Key.get_kids(kids).items():
                item = {
                    "kty": "oct",
                    "kid": self.base64url_encode(key.KID.raw),
                    "k": self.base64url_encode(key.KEY.raw)
                }
                keys.append(item)
            result = {
                "keys": keys,
                "type": req["type"]
            }
        except (TypeError, ValueError, KeyError) as err:
            result["error"] = f'Error: {err}'
        return self.jsonify(result)

    def base64url_encode(self, b: bytes) -> str:
        b = str(base64.b64encode(b), 'ascii')
        b = b.replace('+', '-')
        b = b.replace('/', '_')
        return b.replace('=', '')

    def base64url_decode(self, txt: str) -> bytes:
        txt = txt.replace('-', '+')
        txt = txt.replace('_', '/')
        padding = len(txt) % 4
        if padding == 2:
            txt += '=='
        elif padding == 3:
            txt += '='
        return base64.b64decode(txt)
