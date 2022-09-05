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

import base64
import json

from .base import RequestHandlerBase
import models

class ClearkeyHandler(RequestHandlerBase):
    def post(self):
        result = {"error": "unknown error"}
        try:
            req = json.loads(self.request.body)
            kids = req["kids"]
            kids = map(self.base64url_decode, kids)
            kids = map(lambda k: k.encode('hex'), kids)
            keys = []
            for kid, key in models.Key.get_kids(kids).iteritems():
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
            result = {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            self.add_allowed_origins()
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))

    def base64url_encode(self, b):
        b = base64.b64encode(b)
        b = b.replace('+', '-')
        b = b.replace('/', '_')
        return b.replace('=', '')

    def base64url_decode(self, b):
        b = b.replace('-', '+')
        b = b.replace('_', '/')
        padding = len(b) % 4
        if padding == 2:
            b += '=='
        elif padding == 3:
            b += '='
        return base64.b64decode(b)
