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

import logging
from typing import Dict, Optional
import urllib

import flask

from dashlive.drm.playready import PlayReady
from dashlive.server import models

from .base import HTMLHandlerBase
from .decorators import login_required, uses_stream, current_stream
from .exceptions import CsrfFailureException

class ListStreams(HTMLHandlerBase):
    """
    View handler that provides a list of all media in the
    database.
    """
    decorators = [login_required(admin=True, html=True)]

    def get(self, **kwargs):
        """
        Get list of all streams
        """
        context = self.create_context(**kwargs)
        context['keys'] = models.Key.all(order_by=[models.Key.hkid])
        context['streams'] = [s.to_dict(with_collections=True) for s in models.Stream.all()]
        csrf_key = self.generate_csrf_cookie()
        context['csrf_tokens'] = {
            'files': self.generate_csrf_token('files', csrf_key),
            'kids': self.generate_csrf_token('keys', csrf_key),
            'streams': self.generate_csrf_token('streams', csrf_key),
            'upload': self.generate_csrf_token('upload', csrf_key),
        }
        context['drm'] = {
            'playready': {
                'laurl': PlayReady.TEST_LA_URL
            },
            'marlin': {
                'laurl': ''
            }
        }
        if self.is_ajax():
            result = {
                'keys': [k.toJSON(pure=True) for k in context['keys']]
            }
            for item in ['csrf_tokens', 'streams']:
                result[item] = context[item]
            return self.jsonify(result)
        return flask.render_template('media/index.html', **context)


class AddStream(HTMLHandlerBase):
    """
    handler for adding or removing a stream
    """
    decorators = [login_required(admin=True)]

    FIELDS = ['title', 'directory', 'marlin_la_url', 'playready_la_url']

    def get(self, error: Optional[str] = None):
        """
        Returns an HTML form to add a new stream
        """
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        context.update({
            'csrf_token': self.generate_csrf_token('streams', csrf_key),
            'model': models.Stream().to_dict(),
            "fields": [{
                "name": "title",
                "title": "Title",
                "type": "text",
                "maxlength": 100,
                "value": flask.request.args.get("title", ""),
            }, {
                "name": "directory",
                "title": "Directory",
                "type": "text",
                "pattern": "[A-Za-z0-9]+",
                "minlength": 3,
                "maxlength": 30,
                "value": flask.request.args.get("directory", ""),
            }, {
                "name": "marlin_la_url",
                "title": "Marlin LA URL",
                "type": "text",
                "value": flask.request.args.get("marlin_la_url", ""),
            }, {
                "name": "playready_la_url",
                "title": "PlayReady LA URL",
                "type": "text",
                "value": flask.request.args.get("playready_la_url", ""),
            }]
        })
        return flask.render_template('media/add_stream.html', **context)

    def post(self):
        """
        Adds a new stream using HTML form submission
        """
        return self.put()

    def put(self, **kwargs):
        """
        Adds a new stream
        """
        data = {}
        params = flask.request.json if self.is_ajax() else flask.request.form
        try:
            self.check_csrf('streams', params)
        except (ValueError, CsrfFailureException) as err:
            if self.is_ajax:
                return self.jsonify({'error': f'{err}'}, 401)
            return self.get(error=str(err))
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
        if not self.is_ajax():
            return flask.redirect(flask.url_for('list-streams'))
        result["id"] = st.pk
        result.update(data)
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('streams', csrf_key)
        return self.jsonify(result)


class EditStream(HTMLHandlerBase):
    """
    Handler that allows viewing and updating a stream
    """
    decorators = [uses_stream, login_required(html=True, admin=True)]

    def get(self, **kwargs):
        """
        Get information about a stream
        """
        context = self.create_context(**kwargs)
        csrf_key = context['csrf_key']
        result = current_stream.to_dict(with_collections=True, exclude={'media_files'})
        result.update({
            'csrf_tokens': {
                'files': self.generate_csrf_token('files', csrf_key),
                'kids': self.generate_csrf_token('keys', csrf_key),
                'upload': self.generate_csrf_token('upload', csrf_key),
                'streams': csrf_key,
            },
            'media_files': [],
        })
        kids: Dict[str, models.Key] = {}
        for mf in current_stream.media_files:
            result['media_files'].append(mf.toJSON(convert_date=False))
            for mk in mf.encryption_keys:
                kids[mk.hkid] = mk
        result['keys'] = [kids[hkid] for hkid in sorted(kids.keys())]
        if self.is_ajax():
            result['upload_url'] = context['upload_url']
            return self.jsonify(result)
        context.update(result)
        context['stream'] = result
        context['next'] = urllib.parse.quote_plus(
            flask.url_for('stream-edit', spk=current_stream.pk))
        return flask.render_template('media/stream.html', **context)

    def post(self, **kwargs):
        def str_or_none(value):
            if value is None:
                return None
            value = value.strip()
            if value == "":
                return None
            return value

        context = self.create_context(**kwargs)
        current_stream.title = flask.request.form['title']
        current_stream.prefix = flask.request.form['prefix']
        current_stream.marlin_la_url = str_or_none(flask.request.form['marlin_la_url'])
        current_stream.playready_la_url = str_or_none(flask.request.form['playready_la_url'])
        try:
            self.check_csrf('streams', flask.request.form)
        except (CsrfFailureException) as cfe:
            logging.debug("csrf check failed")
            logging.debug(cfe)
            context['error'] = "csrf check failed"
        if context['error'] is not None:
            return flask.render_template('media/stream.html', **context)
        models.db.session.commit()
        return flask.redirect(flask.url_for('list-streams'))

    def create_context(self, **kwargs):
        def str_or_none(value):
            if value is None:
                return ''
            return value

        context = super(EditStream, self).create_context(**kwargs)
        csrf_key = self.generate_csrf_cookie()
        context.update({
            'csrf_key': csrf_key,
            'csrf_token': self.generate_csrf_token('streams', csrf_key),
            'stream': current_stream,
            'model': current_stream,
            'submit_url': flask.url_for('stream-edit', spk=current_stream.pk),
            'upload_url': flask.url_for('upload-blob', spk=current_stream.pk),
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

class DeleteStream(HTMLHandlerBase):
    decorators = [uses_stream, login_required(html=True, admin=True)]

    def get(self, spk: int) -> flask.Response:
        """
        Returns HTML form to confirm if stream should be deleted
        """
        try:
            self.check_csrf('streams', flask.request.args)
        except (CsrfFailureException) as cfe:
            logging.debug("csrf check failed")
            logging.debug(cfe)
            url = flask.url_for('stream-edit', spk=spk)
            return flask.redirect(url)
        context = self.create_context()
        return flask.render_template('media/confirm_delete.html', **context)

    def delete(self, spk: int, **kwargs) -> flask.Response:
        """
        handler for deleting a stream
        """
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
            # TODO: investigate using sqlachemy events to delete mp4 files
            for mf in stream.media_files:
                mf.delete_file()
            models.db.session.delete(stream)
            models.db.session.commit()
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('streams', csrf_key)
        return self.jsonify(result)
