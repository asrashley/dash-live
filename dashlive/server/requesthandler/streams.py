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
from pathlib import Path
import urllib

import flask
from flask_login import current_user

from dashlive.drm.playready import PlayReady
from dashlive.server import models
from dashlive.utils.json_object import JsonObject

from .base import HTMLHandlerBase, DeleteModelBase
from .decorators import login_required, uses_stream, current_stream
from .exceptions import CsrfFailureException

class ListStreams(HTMLHandlerBase):
    """
    View handler that provides a list of all media in the
    database.
    """
    decorators = []

    def get(self, **kwargs):
        """
        Get list of all streams
        """
        context = self.create_context(**kwargs)
        context['keys'] = models.Key.all(order_by=[models.Key.hkid])
        context['streams'] = [s.to_dict(with_collections=True) for s in models.Stream.all()]
        context['user_can_modify'] = current_user.has_permission(models.Group.MEDIA)
        csrf_key = self.generate_csrf_cookie()
        context['csrf_tokens'] = {
            'files': self.generate_csrf_token('files', csrf_key),
            'kids': self.generate_csrf_token('keys', csrf_key),
            'streams': self.generate_csrf_token('streams', csrf_key),
        }
        if context['user_can_modify']:
            context['upload'] = self.generate_csrf_token('upload', csrf_key),
        context['drm'] = {
            'playready': {
                'laurl': PlayReady.TEST_LA_URL
            },
            'marlin': {
                'laurl': ''
            }
        }
        if self.is_ajax():
            exclude = set()
            if not current_user.has_permission(models.Group.MEDIA):
                exclude.add('key')
            result = {
                'keys': [k.toJSON(pure=True, exclude=exclude) for k in context['keys']]
            }
            for item in ['csrf_tokens', 'streams']:
                result[item] = context[item]
            return self.jsonify(result)
        return flask.render_template('media/index.html', **context)


class AddStream(HTMLHandlerBase):
    """
    handler for adding a stream
    """
    decorators = [login_required(permission=models.Group.MEDIA)]

    def get(self, error: str | None = None):
        """
        Returns an HTML form to add a new stream
        """
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        model = models.Stream()
        context.update({
            'csrf_token': self.generate_csrf_token('streams', csrf_key),
            'model': model.to_dict(),
            "fields": model.get_fields(**flask.request.args),
        })
        return flask.render_template('media/add_stream.html', **context)

    def post(self) -> flask.Response:
        """
        Adds a new stream using HTML form submission
        """
        return self.add_stream(flask.request.form)

    def put(self, **kwargs) -> flask.Response:
        """
        Adds a new stream using JSON API
        """
        return self.add_stream(flask.request.json)

    def add_stream(self, params) -> flask.Response:
        """
        Adds a new stream
        """
        data = {}
        try:
            self.check_csrf('streams', params)
        except (ValueError, CsrfFailureException) as err:
            if self.is_ajax():
                return self.jsonify({'error': f'{err}'}, 401)
            flask.flash(f'CSRF error: {err}', 'error')
            return self.get(error=str(err))
        for f in models.Stream.get_column_names(with_collections=False):
            data[f] = params.get(f)
            if data[f] == '':
                data[f] = None
        if 'prefix' in params:
            data['directory'] = params['prefix']
        result = {}
        st = models.Stream.get(directory=data['directory'])
        if st:
            models.db.session.delete(st)
        st = models.Stream(**data)
        st.add(commit=True)
        if not self.is_ajax():
            flask.flash(f'Added new stream "{data["title"]}"', 'success')
            return flask.redirect(flask.url_for('list-streams'))
        result["id"] = st.pk
        result.update(st.to_dict(with_collections=True))
        csrf_key = self.generate_csrf_cookie()
        result["csrf_token"] = self.generate_csrf_token('streams', csrf_key)
        return self.jsonify(result)


class EditStream(HTMLHandlerBase):
    """
    Handler that allows viewing and updating a stream
    """
    decorators = [uses_stream]

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
                'streams': context['csrf_token'],
            },
            'media_files': [],
        })
        if current_user.has_permission(models.Group.MEDIA):
            result['csrf_tokens']['upload'] = self.generate_csrf_token('upload', csrf_key)
        kids: dict[str, models.Key] = {}
        for mf in current_stream.media_files:
            result['media_files'].append(mf.toJSON(convert_date=False))
            for mk in mf.encryption_keys:
                kids[mk.hkid] = mk
        result['keys'] = [kids[hkid] for hkid in sorted(kids.keys())]
        if self.is_ajax():
            exclude = set()
            if current_user.has_permission(models.Group.MEDIA):
                result['upload_url'] = context['upload_url']
            else:
                exclude.add('key')
            result['keys'] = [k.toJSON(exclude=exclude, pure=True) for k in result['keys']]
            return self.jsonify(result)
        options = self.calculate_options(mode='vod')
        options.audioCodec = None
        options.textCodec = None
        clear_adaptation_sets = [self.calculate_video_adaptation_set(current_stream, options)]
        clear_adaptation_sets += self.calculate_audio_adaptation_sets(current_stream, options)
        clear_adaptation_sets += self.calculate_text_adaptation_sets(current_stream, options)
        enc_options = options.clone(
            drmSelection=['playready', 'marlin', 'clearkey'], encrypted=True)
        enc_adaptation_sets = [self.calculate_video_adaptation_set(current_stream, enc_options)]
        enc_adaptation_sets += self.calculate_audio_adaptation_sets(current_stream, enc_options)
        enc_adaptation_sets += self.calculate_text_adaptation_sets(current_stream, enc_options)
        if 'fragment' in flask.request.args:
            layout = 'fragment.html'
        else:
            layout = 'layout.html'
        context.update(result)
        context.update({
            'clear_adaptation_sets': clear_adaptation_sets,
            'encrypted_adaptation_sets': enc_adaptation_sets,
            'user_can_modify': current_user.has_permission(models.Group.MEDIA),
            'stream': result,
            'layout': layout,
            'next': urllib.parse.quote_plus(
                flask.url_for('view-stream', spk=current_stream.pk)),
        })
        return flask.render_template('media/stream.html', **context)

    @login_required(permission=models.Group.MEDIA)
    def post(self, **kwargs):
        def str_or_none(value):
            if value is None:
                return None
            value = value.strip()
            if value == "":
                return None
            return value

        context = self.create_context(**kwargs)
        context['error'] = None
        if self.is_ajax():
            params = flask.request.json
        else:
            params = flask.request.form
        current_stream.title = params['title']
        if models.MediaFile.count(stream=current_stream) == 0:
            current_stream.directory = params['directory']
        current_stream.marlin_la_url = str_or_none(params['marlin_la_url'])
        current_stream.playready_la_url = str_or_none(params['playready_la_url'])
        current_stream.timing_reference = None
        timing_reference = params.get('timing_ref', '')
        if timing_reference != '':
            mf = models.MediaFile.get(name=Path(timing_reference).stem)
            if not mf:
                return flask.make_response(
                    f'Invalid timing_reference "{timing_reference}"', 400)
            current_stream.set_timing_reference(mf.as_stream_timing_reference())
        try:
            self.check_csrf('streams', params)
        except (CsrfFailureException) as cfe:
            logging.debug("csrf check failed")
            logging.debug(cfe)
            context['error'] = "csrf check failed"
        if context['error'] is not None:
            context['csrf_tokens'] = {
                'files': self.generate_csrf_token('files', context['csrf_key']),
                'kids': self.generate_csrf_token('keys', context['csrf_key']),
                'streams': context['csrf_token'],
            }
            return flask.render_template('media/stream.html', **context)
        models.db.session.commit()
        if self.is_ajax():
            return self.jsonify(current_stream.toJSON())
        flask.flash(f'Saved changes to "{current_stream.title}"', 'success')
        return flask.redirect(flask.url_for('list-streams'))

    @login_required(permission=models.Group.MEDIA)
    def delete(self, **kwargs):
        """
        Delete a stream
        """
        models.db.session.delete(current_stream)
        models.db.session.commit()
        return flask.redirect(flask.url_for('list-streams'))

    def create_context(self, **kwargs):
        context = super().create_context(**kwargs)
        csrf_key = self.generate_csrf_cookie()
        context.update({
            'csrf_key': csrf_key,
            'csrf_token': self.generate_csrf_token('streams', csrf_key),
            'stream': current_stream,
            'model': current_stream,
            'submit_url': flask.url_for('view-stream', spk=current_stream.pk),
            'upload_url': flask.url_for('upload-blob', spk=current_stream.pk),
            "fields": current_stream.get_fields(),
        })
        if current_user.has_permission(models.Group.MEDIA):
            current_ref: str | None = None
            if current_stream.timing_reference:
                current_ref = current_stream.timing_reference.media_name
            options = [{
                'value': '',
                'title': '--Please choose a mediafile as the timing reference--',
                'selected': current_ref is None,
            }]
            for rep in current_stream.media_files:
                options.append({
                    'value': rep.name,
                    'title': rep.name,
                    'selected': rep.name == current_ref,
                })
            context['fields'].append({
                "name": "timing_ref",
                "title": "Timing reference",
                "type": "select",
                "options": options,
            })
        else:
            for fld in context['fields']:
                fld['disabled'] = True
        return context

class DeleteStream(DeleteModelBase):
    MODEL_NAME = 'stream'
    CSRF_TOKEN_NAME = 'streams'
    decorators = [
        uses_stream,
        login_required(html=True, permission=models.Group.MEDIA)]

    def get_model_dict(self) -> JsonObject:
        return current_stream.to_dict(with_collections=False)

    def get_cancel_url(self) -> str:
        return self.get_next_url_with_fallback(
            'view-stream', spk=current_stream.pk)

    def delete_model(self) -> JsonObject:
        result = {
            "deleted": current_stream.pk,
            "title": current_stream.title,
            "directory": current_stream.directory
        }
        models.db.session.delete(current_stream)
        models.db.session.commit()
        return result

    def get_next_url(self) -> str:
        return flask.url_for('list-streams')
