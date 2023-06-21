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

import flask
from flask_login import current_user, login_required

from dashlive.server import models

from .base import HTMLHandlerBase, RequestHandlerBase
from .decorators import login_required, uses_stream, current_stream
from .exceptions import CsrfFailureException

class StreamHandler(RequestHandlerBase):
    """
    handler for adding or removing a stream
    """
    decorators = [login_required(admin=True)]

    FIELDS = ['title', 'directory', 'marlin_la_url', 'playready_la_url']

    def put(self, **kwargs):
        """
        Adds a new stream
        """
        data = {}
        params = flask.request.json if self.is_ajax() else flask.request.form
        try:
            self.check_csrf('streams', params)
        except (ValueError, CsrfFailureException) as err:
            return self.jsonify({'error': f'{err}'}, 401)
        for f in self.FIELDS:
            data[f] = params.get(f)
            if data[f] == '':
                data[f] = None
        if 'prefix' in params:
            data['directory'] = params['prefix']
        result = {"error": None}
        st = models.Stream.get(directory=data['directory'])
        if st:
            models.db.session.delete(st)
        st = models.Stream(**data)
        st.add(commit=True)
        result["id"] = st.pk
        result.update(data)
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('streams', csrf_key)
        return self.jsonify(result)


    def delete(self, spk, **kwargs):
        """
        handler for deleting a stream
        """
        if not spk:
            return self.jsonify('Stream primary key missing', status=400)
        result = {"error": None}
        try:
            self.check_csrf('streams', flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            result = {
                "error": f'CSRF failure: {err}'
            }
        if result['error'] is None:
            stream = models.Stream.get(pk=spk)
            if not stream:
                return self.jsonify_no_content(404)
            result = {
                "deleted": stream.pk,
                "title": stream.title,
                "directory": stream.directory
            }
            models.db.session.delete(stream)
            models.db.session.commit()
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('streams', csrf_key)
        return self.jsonify(result)


class EditStreamHandler(HTMLHandlerBase):
    decorators = [uses_stream, login_required(html=True, admin=True)]

    def get(self, **kwargs):
        context = self.create_context(**kwargs)
        return flask.render_template('edit-stream.html', **context)

    def post(self, **kwargs):
        def str_or_none(value):
            if value is None:
                return None
            value = value.strip()
            if value == "":
                return None
            return value

        context = self.create_context(**kwargs)
        stream = context['stream']
        stream.title = self.request.params['title']
        stream.prefix = self.request.params['prefix']
        stream.marlin_la_url = str_or_none(self.request.params['marlin_la_url'])
        stream.playready_la_url = str_or_none(self.request.params['playready_la_url'])
        try:
            self.check_csrf('streams', flask.request.form)
        except (CsrfFailureException) as cfe:
            logging.debug("csrf check failed")
            logging.debug(cfe)
            context['error'] = "csrf check failed"
        if context['error'] is not None:
            return flask.render_template('edit-stream.html', **context)
        db.session.commit()
        return flask.redirect(flask.url_for('media-list'))

    def create_context(self, **kwargs):
        def str_or_none(value):
            if value is None:
                return ''
            return value

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
        context.update({
            'error': None,
            'stream': current_stream,
            "fields": [{
                "name": "title",
                "title": "Title",
                "type": "text",
                "value": current_stream.title,
            }, {
                "name": "directory",
                "title": "Directory",
                "type": "text",
                "value": current_stream.directory,
            }, {
                "name": "marlin_la_url",
                "title": "Marlin LA URL",
                "type": "text",
                "value": str_or_none(current_stream.marlin_la_url),
            }, {
                "name": "playready_la_url",
                "title": "PlayReady LA URL",
                "type": "text",
                "value": str_or_none(current_stream.playready_la_url),
            }],
        })
        return context
