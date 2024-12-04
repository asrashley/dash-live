############################################################################
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
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import cast, TypedDict
import urllib

import flask
from flask_login import current_user

from dashlive.drm.playready import PlayReady
from dashlive.drm.system import DrmSystem
from dashlive.mpeg.dash.adaptation_set import AdaptationSet
from dashlive.server import models
from dashlive.server.manifests import default_manifest
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.drm_options import DrmSelection
from dashlive.server.requesthandler.navbar import NavBarItem
from dashlive.server.routes import Route
from dashlive.utils.json_object import JsonObject
from dashlive.utils.objects import flatten

from .base import HTMLHandlerBase, DeleteModelBase, TemplateContext
from .csrf import CsrfTokenCollection
from .decorators import login_required, uses_stream, current_stream
from .exceptions import CsrfFailureException
from .manifest_context import ManifestContext
from .utils import is_ajax, jsonify

@dataclass(slots=True, kw_only=True)
class DrmLicenseContext:
    laurl: str

class ListStreamsTemplateContext(TemplateContext):
    csrf_tokens: CsrfTokenCollection
    drm: dict[str, DrmLicenseContext]
    keys: list[models.Key]
    streams: list[models.Stream]
    user_can_modify: bool

class ListStreams(HTMLHandlerBase):
    """
    View handler that provides a list of all media in the
    database.
    """
    decorators = []

    def get(self) -> flask.Response:
        """
        Get list of all streams
        """
        user_can_modify: bool = current_user.has_permission(models.Group.MEDIA)

        csrf_key = self.generate_csrf_cookie()
        upload: str | None = None
        if user_can_modify:
            upload = self.generate_csrf_token('upload', csrf_key),
        csrf_tokens = CsrfTokenCollection(
            files=self.generate_csrf_token('files', csrf_key),
            kids=self.generate_csrf_token('keys', csrf_key),
            streams=self.generate_csrf_token('streams', csrf_key),
            upload=upload)

        keys = models.Key.all(order_by=[models.Key.hkid])
        streams = models.Stream.all()

        if is_ajax():
            exclude: set[str] = set()
            if not current_user.has_permission(models.Group.MEDIA):
                exclude.add('key')
            result = {
                'keys': [
                    k.toJSON(pure=True, exclude=exclude) for k in keys
                ],
                'csrf_tokens': csrf_tokens,
                'streams': [],
            }
            for stream in streams:
                jss: JsonObject = stream.to_dict(with_collections=True)
                jss['duration'] = stream.duration()
                if flask.request.args.get('details', '0') == '1':
                    media_files: list[JsonObject] = []
                    for mf in stream.media_files:
                        media_files.append(mf.to_dict(
                            with_collections=False, exclude={'rep', 'blob'}))
                    jss['media_files'] = media_files
                result['streams'].append(jss)
            return jsonify(result)

        context = cast(ListStreamsTemplateContext, self.create_context(
            csrf_tokens=csrf_tokens,
            drm={
                'playready': DrmLicenseContext(laurl=PlayReady.TEST_LA_URL),
                'marlin': DrmLicenseContext(laurl=''),
            },
            keys=keys,
            streams=streams,
            title='All DASH streams',
            user_can_modify=user_can_modify))
        return flask.render_template('media/index.html', **context)


class AddStreamTemplateContext(TemplateContext):
    csrf_token: str
    model: models.Stream
    fields: list[JsonObject]

class AddStream(HTMLHandlerBase):
    """
    handler for adding a stream
    """
    decorators = [login_required(permission=models.Group.MEDIA)]

    def get(self, error: str | None = None) -> flask.Response:
        """
        Returns an HTML form to add a new stream
        """
        csrf_key = self.generate_csrf_cookie()
        model = models.Stream()
        context = cast(AddStreamTemplateContext, self.create_context(
            title='Add new stream',
            csrf_token=self.generate_csrf_token('streams', csrf_key),
            model=model.to_dict(),
            fields=model.get_fields(**flask.request.args)))
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

    def add_stream(self, params: dict[str, str]) -> flask.Response:
        """
        Adds a new stream
        """
        data = {}
        try:
            self.check_csrf('streams', params)
        except (ValueError, CsrfFailureException) as err:
            if is_ajax():
                return jsonify({'error': f'{err}'}, 401)
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
        if not is_ajax():
            flask.flash(f'Added new stream "{data["title"]}"', 'success')
            return flask.redirect(flask.url_for('list-streams'))
        result["id"] = st.pk
        result.update(st.to_dict(with_collections=True))
        csrf_key = self.generate_csrf_cookie()
        result["csrf_token"] = self.generate_csrf_token('streams', csrf_key)
        return jsonify(result)


class EditStreamTemplateContext(TemplateContext):
    clear_adaptation_sets: list[AdaptationSet]
    csrf_key: str
    csrf_token: str
    csrf_tokens: CsrfTokenCollection | None
    encrypted_adaptation_sets: list[AdaptationSet]
    error: str | None
    has_file_errors: bool
    keys: list[models.Key]
    layout: str
    media_files: list[models.MediaFile]
    next: str
    stream: models.Stream
    upload_url: str
    user_can_modify: bool

class StreamTimingReferenceAjaxResponse(TypedDict):
    media_name: str
    media_duration: int
    num_media_segments: int
    segment_duration: int
    timescale: int

class StreamAjaxResponse(TypedDict):
    """
    The JSON response that describes a stream
    """
    defaults: JsonObject | None
    directory: str
    keys: list[JsonObject]
    marlin_la_url: str | None
    media_files: []
    pk: int
    playready_la_url: str | None
    timing_ref: StreamTimingReferenceAjaxResponse | None
    title: str

class ViewStreamAjaxResponse(StreamAjaxResponse):
    """
    The JSON response to a GET request to the EditStream handler
    """
    upload_url: str
    csrf_tokens: CsrfTokenCollection


class EditStream(HTMLHandlerBase):
    """
    Handler that allows viewing and updating a stream
    """
    decorators = [uses_stream]

    def get(self, spk: int) -> flask.Response:
        """
        Get information about a stream
        """
        context = self.create_context(current_stream.title, True)
        stream = current_stream.to_dict(
            with_collections=True, exclude={'media_files'})
        stream.update({
            'media_files': [],
            'duration': current_stream.duration(),
        })
        kids: dict[str, models.Key] = {}
        has_file_errors: bool = False
        for mf in current_stream.media_files:
            stream['media_files'].append(mf)
            for mk in mf.encryption_keys:
                kids[mk.hkid] = mk
            if mf.errors:
                has_file_errors = True
        context['has_file_errors'] = has_file_errors
        context['keys'] = [kids[hkid] for hkid in sorted(kids.keys())]
        if is_ajax():
            exclude: set[str] = set()
            result: ViewStreamAjaxResponse = {
                **stream,
                'csrf_tokens': context['csrf_tokens'],
                'upload_url': context['upload_url'],
                'media_files': [
                    mf.toJSON(convert_date=False) for mf in stream['media_files']
                ],
            }
            if not current_user.has_permission(models.Group.MEDIA):
                del result['upload_url']
                exclude.add('key')
            result['keys'] = [
                k.toJSON(exclude=exclude, pure=True) for k in context['keys']
            ]
            return jsonify(result)
        options = self.calculate_options('vod', flask.request.args)
        options.audioCodec = 'any'
        options.textCodec = None
        options.drmSelection = []
        mc = ManifestContext(
            options=options, stream=current_stream, multi_period=None,
            manifest=default_manifest)
        clear_adaptation_sets = [mc.video] + mc.audio_sets + mc.text_sets
        drmSelection = DrmSelection.from_string(','.join(DrmSystem.values()))
        enc_options = options.clone(drmSelection=drmSelection)
        mc = ManifestContext(
            options=enc_options, stream=current_stream, multi_period=None,
            manifest=default_manifest)
        enc_adaptation_sets = [mc.video] + mc.audio_sets + mc.text_sets
        if 'fragment' in flask.request.args:
            layout = 'fragment.html'
        else:
            layout = 'layout.html'
        context.update({
            'clear_adaptation_sets': clear_adaptation_sets,
            'encrypted_adaptation_sets': enc_adaptation_sets,
            'user_can_modify': current_user.has_permission(models.Group.MEDIA),
            'stream': stream,
            'layout': layout,
            'next': urllib.parse.quote_plus(
                flask.url_for('view-stream', spk=current_stream.pk)),
        })
        return flask.render_template('media/stream.html', **context)

    @login_required(permission=models.Group.MEDIA)
    def post(self, spk: int) -> flask.Response:
        def str_or_none(value: str | None) -> str | None:
            if value is None:
                return None
            value = value.strip()
            if value == "":
                return None
            return value

        if is_ajax():
            params = flask.request.json
        else:
            params = flask.request.form
        current_stream.title = params['title']
        context = self.create_context(current_stream.title, False)
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
            context['csrf_tokens'] = CsrfTokenCollection(
                files=self.generate_csrf_token('files', context['csrf_key']),
                kids=self.generate_csrf_token('keys', context['csrf_key']),
                streams=context['csrf_token'],
                upload=None)
            return flask.render_template('media/stream.html', **context)
        models.db.session.commit()
        if is_ajax():
            return jsonify(current_stream.toJSON())
        flask.flash(f'Saved changes to "{current_stream.title}"', 'success')
        return flask.redirect(flask.url_for('list-streams'))

    @login_required(permission=models.Group.MEDIA)
    def delete(self, spk: int) -> flask.Response:
        """
        Delete a stream
        """
        models.db.session.delete(current_stream)
        models.db.session.commit()
        flask.flash(f'Deleted stream "{current_stream.title}"', 'success')
        if is_ajax():
            return jsonify({
                'success': True,
                'message': f'Deleted {current_stream.title}',
            })
        return flask.redirect(flask.url_for('list-streams'))

    def create_context(self,
                       title: str | None,
                       all_csrf_tokens: bool) -> EditStreamTemplateContext:
        context = super().create_context(title=title)
        csrf_key = self.generate_csrf_cookie()
        context.update({
            'csrf_key': csrf_key,
            'csrf_token': self.generate_csrf_token('streams', csrf_key),
            'error': None,
            'stream': current_stream,
            'model': current_stream,
            'submit_url': flask.url_for('view-stream', spk=current_stream.pk),
            'upload_url': flask.url_for('upload-blob', spk=current_stream.pk),
            "fields": current_stream.get_fields(),
        })

        if all_csrf_tokens:
            upload: str | None = None
            if current_user.has_permission(models.Group.MEDIA):
                upload = self.generate_csrf_token('upload', csrf_key)
            csrf_tokens = CsrfTokenCollection(
                files=self.generate_csrf_token('files', csrf_key),
                kids=self.generate_csrf_token('keys', csrf_key),
                streams=self.generate_csrf_token('streams', csrf_key),
                upload=upload)
            context['csrf_tokens'] = csrf_tokens

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
            if current_stream.defaults is None:
                value = ''
            else:
                value = current_stream.defaults

            context['fields'].append({
                "name": "defaults",
                "title": "Stream defaults",
                "link_title": "Edit stream's default options",
                "type": "link",
                "value": value,
                "href": flask.url_for("edit-stream-defaults", spk=current_stream.pk)
            })
        else:
            for fld in context['fields']:
                fld['disabled'] = True
        return context

    def get_breadcrumbs(self, route: Route) -> list[NavBarItem]:
        crumbs: list[NavBarItem] = super().get_breadcrumbs(route)
        crumbs[-1].title = current_stream.directory
        return crumbs


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

class EditStreamDefaults(HTMLHandlerBase):
    """
    Handler that allows viewing and updating a stream's default options
    """
    decorators = [uses_stream]

    def get(self, spk: int) -> flask.Response:
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        context['csrf_token'] = self.generate_csrf_token('streams', csrf_key)
        defaults = OptionsRepository.get_default_options()
        if current_stream.defaults is None:
            options = defaults
        else:
            options = defaults.clone(**current_stream.defaults)
        field_choices = {
            'representation': [
                dict(value=mf.name, title=mf.name) for mf in current_stream.media_files],
            'audio_representation': [
                dict(value=mf.name, title=mf.name) for mf in models.MediaFile.search(
                    stream=current_stream, content_type='audio')],
            'text_representation': [
                dict(value=mf.name, title=mf.name) for mf in models.MediaFile.search(
                    stream=current_stream, content_type='text')],
        }
        for name in ['representation', 'audio_representation', 'text_representation']:
            field_choices[name].insert(0, {
                'title': '--',
                'value': '',
            })
        context['field_groups'] = options.generate_input_field_groups(
            field_choices,
            exclude={'mode', 'clockDrift', 'dashjsVersion', 'marlin.licenseUrl',
                     'audioErrors', 'manifestErrors', 'textErrors', 'videoErrors',
                     'playready.licenseUrl', 'shakaVersion', 'failureCount',
                     'videoCorruption', 'videoCorruptionFrameCount',
                     'videoPlayer', 'updateCount', 'utcValue'})
        context['stream'] = current_stream
        return flask.render_template('media/stream_defaults.html', **context)

    def post(self, spk: int) -> flask.Response:
        try:
            self.check_csrf('streams', flask.request.form)
        except (ValueError, CsrfFailureException) as err:
            if is_ajax():
                return jsonify({'error': f'{err}'}, 401)
            flask.flash(f'CSRF error: {err}', 'error')
            return self.get(spk)
        defaults = OptionsRepository.get_default_options()
        form = {**flask.request.form}
        del form['csrf_token']
        drms = []
        for name in DrmSystem.values():
            if flask.request.form.get(f'drm_{name}', '') != 'on':
                continue
            loc = flask.request.form.get(f'{name}__drmloc', 'all')
            drms.append(f'{name}-{loc}')
        form['drm'] = ','.join(drms)
        form['events'] = ','.join(flask.request.form.getlist('events'))
        opts = OptionsRepository.convert_cgi_options(form, defaults=defaults)
        current_stream.defaults = flatten(opts.remove_default_values(defaults))
        models.db.session.commit()
        flask.flash('Saved stream defaults', 'success')
        return flask.redirect(flask.url_for('view-stream', spk=current_stream.pk))

    def get_breadcrumbs(self, route: Route) -> list[NavBarItem]:
        crumbs: list[NavBarItem] = super().get_breadcrumbs(route)
        crumbs.insert(-1, NavBarItem(
            title=current_stream.directory,
            href=flask.url_for('view-stream', spk=current_stream.pk)))
        return crumbs
