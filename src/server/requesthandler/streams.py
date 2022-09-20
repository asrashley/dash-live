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
from google.appengine.ext.ndb.model import Key

from server import models

from .base import RequestHandlerBase
from .exceptions import CsrfFailureException

class StreamHandler(RequestHandlerBase):
    """
    handler for adding or removing a stream
    """

    FIELDS = ['title', 'prefix', 'marlin_la_url', 'playready_la_url']

    def put(self, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        data = {}
        for f in self.FIELDS:
            data[f] = self.request.get(f)
            if data[f] == '':
                data[f] = None
        result = {"error": "unknown error"}
        try:
            self.check_csrf('streams')
            st = models.Stream.query(
                models.Stream.prefix == data['prefix']).get()
            if st:
                raise ValueError("Duplicate prefix {prefix}".format(**data))
            st = models.Stream(**data)
            st.put()
            result = {
                "id": st.key.urlsafe()
            }
            result.update(data)
        except (ValueError, CsrfFailureException) as err:
            result = {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('streams', csrf_key)
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))

    """handler for deleting a stream"""

    def delete(self, id, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        if not id:
            self.response.write('Stream ID missing')
            self.response.set_status(400)
            return
        result = {"error": "unknown error"}
        try:
            self.check_csrf('streams')
            key = Key(urlsafe=id)
            st = key.get()
            if not st:
                self.response.write('Stream {:s} not found'.format(id))
                self.response.set_status(404)
                return
            key.delete()
            result = {
                "deleted": id,
                "title": st.title,
                "prefix": st.prefix
            }
        except (TypeError, ValueError, CsrfFailureException) as err:
            result = {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('streams', csrf_key)
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))
