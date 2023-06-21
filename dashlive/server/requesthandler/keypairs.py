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

from __future__ import absolute_import
import binascii
import json

import flask
from flask_login import current_user

from dashlive.drm.playready import PlayReady
from dashlive.server import models

from .base import RequestHandlerBase
from .decorators import login_required
from .exceptions import CsrfFailureException

class KeyHandler(RequestHandlerBase):
    """
    Provides a JSON API to add and remove encryption keys
    """

    decorators = [login_required(admin=True)]
    
    def put(self, **kwargs):
        """
        handler for adding a key pair
        """

        # TODO: support JSON payload
        kid = flask.request.args.get('kid')
        key = flask.request.args.get('key')
        if kid is None:
            return self.jsonify({'error': 'KID is required'}, 400)
        result = {"error": None}
        try:
            self.check_csrf('keys', flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            result = {
                "error": f'CSRF failure: {err}'
            }
        if result['error'] is None:
            kid = models.KeyMaterial(kid)
            computed = False
            if key:
                key = models.KeyMaterial(key)
            else:
                key = models.KeyMaterial(
                    raw=PlayReady.generate_content_key(kid.raw))
                computed = True
            keypair = models.Key.get(hkid=kid.hex)
            if keypair:
                result['error'] = f"Duplicate KID {kid.hex}"
            else:
                keypair = models.Key(hkid=kid.hex, hkey=key.hex, computed=computed)
                keypair.add(commit=True)
                result = {
                    "key": key.hex,
                    "kid": kid.hex,
                    "computed": computed
                }
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('keys', csrf_key)
        return self.jsonify(result)

    def delete(self, kid, **kwargs):
        """
        handler for deleting a key pair
        """

        if not kid:
            return self.jsonify({'error': 'KID missing'}, 400)
        try:
            self.check_csrf('keys', flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            return self.jsonify({'error': 'CSRF failure'}, 400)
        result = {"error": None}
        try:
            kid = models.KeyMaterial(hex=kid)
        except (binascii.Error) as err:
            return self.jsonify({'error': f'{err}'}, 400)
        keypair = models.Key.get(hkid=kid.hex)
        if not keypair:
            return self.jsonify_no_content(404)
        result = {
            "deleted": kid.hex,
        }
        models.db.session.delete(keypair)
        models.db.session.commit()
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('keys', csrf_key)
        return self.jsonify(result)
