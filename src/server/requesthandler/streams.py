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
import logging

from google.appengine.api import users
from google.appengine.ext.ndb.model import Key

from server import models
from templates.factory import TemplateFactory

from .base import HTMLHandlerBase, RequestHandlerBase
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

class EditStreamHandler(HTMLHandlerBase):
    def get(self, key, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        if not key:
            self.response.write('Stream ID missing')
            self.response.set_status(400)
            return
        context = self.create_context(**kwargs)
        self.get_stream(key, context)
        template = TemplateFactory.get_template('edit-stream.html')
        self.response.write(template.render(context))

    def post(self, key, **kwargs):
        def str_or_none(value):
            if value is None:
                return None
            value = value.strip()
            if value == "":
                return None
            return value

        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        template = TemplateFactory.get_template('edit-stream.html')
        context = self.create_context(**kwargs)
        if not self.get_stream(key, context):
            self.response.write(template.render(context))
            return
        stream = context['stream']
        stream.title = self.request.params['title']
        stream.prefix = self.request.params['prefix']
        stream.marlin_la_url = str_or_none(self.request.params['marlin_la_url'])
        stream.playready_la_url = str_or_none(self.request.params['playready_la_url'])
        try:
            self.check_csrf('streams')
        except (CsrfFailureException) as cfe:
            logging.debug("csrf check failed")
            logging.debug(cfe)
            context['error'] = "csrf check failed"
        if context['error'] is not None:
            self.response.write(template.render(context))
            return
        stream.put()
        self.redirect(self.uri_for('media-index'))

    def create_context(self, **kwargs):
        context = super(EditStreamHandler, self).create_context(**kwargs)
        csrf_key = self.generate_csrf_cookie()
        context.update({
            'csrf_tokens': {
                'streams': self.generate_csrf_token('streams', csrf_key),
            },
            "error": None,
            "stream": None,
            "fields": [],
        })
        return context

    def get_stream(self, key, context):
        def str_or_none(value):
            if value is None:
                return ''
            return value

        try:
            db_key = Key(urlsafe=key)
            stream = db_key.get()
            if not stream:
                self.response.write('Stream {:s} not found'.format(key))
                self.response.set_status(404)
                return False
            context.update({
                'error': None,
                'stream': stream,
                "fields": [{
                    "name": "title",
                    "title": "Title",
                    "type": "text",
                    "value": stream.title,
                }, {
                    "name": "prefix",
                    "title": "Prefix",
                    "type": "text",
                    "value": stream.prefix,
                }, {
                    "name": "marlin_la_url",
                    "title": "Marlin LA URL",
                    "type": "text",
                    "value": str_or_none(stream.marlin_la_url),
                }, {
                    "name": "playready_la_url",
                    "title": "PlayReady LA URL",
                    "type": "text",
                    "value": str_or_none(stream.playready_la_url),
                }],
            })
            return True
        except (TypeError, ValueError) as err:
            context["error"] = '{}: {:s}'.format(err.__class__.__name__, err)
            return False
