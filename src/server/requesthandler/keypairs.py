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

import json

from google.appengine.api import users

from server import models

from base import RequestHandlerBase
from drm.playready import PlayReady
from exceptions import CsrfFailureException

class KeyHandler(RequestHandlerBase):
    """handler for adding a key pair"""

    def put(self, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return

        kid = self.request.get('kid')
        key = self.request.get('key')
        result = {"error": "unknown error"}
        try:
            self.check_csrf('keys')
            kid = models.KeyMaterial(kid)
            computed = False
            if key:
                key = models.KeyMaterial(key)
            else:
                key = models.KeyMaterial(
                    raw=PlayReady.generate_content_key(kid.raw))
                computed = True
            keypair = models.Key.query(models.Key.hkid == kid.hex).get()
            if keypair:
                raise ValueError("Duplicate KID {}".format(kid.hex))
            keypair = models.Key(hkid=kid.hex, hkey=key.hex, computed=computed)
            keypair.put()
            result = {
                "key": key.hex,
                "kid": kid.hex,
                "computed": computed
            }
        except (ValueError, CsrfFailureException) as err:
            result = {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('keys', csrf_key)
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))

    """handler for deleting a key pair"""

    def delete(self, kid, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        if not kid:
            self.response.write('KID missing')
            self.response.set_status(400)
            return
        result = {"error": "unknown error"}
        try:
            self.check_csrf('keys')
            kid = models.KeyMaterial(hex=kid)
            keypair = models.Key.query(models.Key.hkid == kid.hex).get()
            if keypair:
                keypair.key.delete()
                result = {
                    "deleted": kid.hex,
                }
            else:
                result["error"] = 'KID {:s} not found'.format(kid)
        except (TypeError, ValueError, CsrfFailureException) as err:
            result = {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('keys', csrf_key)
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))
