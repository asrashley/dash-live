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
import datetime
import logging
from typing import cast, NamedTuple, TypedDict

import flask
from typing_extensions import deprecated
from flask_jwt_extended import jwt_required

from dashlive.mpeg.dash.content_role import ContentRole
from dashlive.mpeg.dash.timing import DashTiming
from dashlive.server import models
from dashlive.server.options.form_input_field import FormInputContext
from dashlive.server.options.repository import OptionsRepository
from dashlive.utils.date_time import from_isodatetime, timecode_to_timedelta
from dashlive.utils.timezone import UTC

from .base import HTMLHandlerBase, RequestHandlerBase, TemplateContext
from .csrf import CsrfTokenCollection
from .decorators import (
    csrf_token_required,
    current_mps,
    login_required,
    spa_handler,
    uses_multi_period_stream
)
from .utils import is_ajax, jsonify, jsonify_no_content

class PeriodJsonData(TypedDict):
    duration: str
    ordering: int
    parent: int
    pid: str
    pk: int | None
    start: str
    stream: int
    tracks: dict[int, str]


class MultiPeriodStreamData(TypedDict):
    pk: int | None
    name: str
    title: str
    periods: list[PeriodJsonData]


def process_period(mp_stream: models.MultiPeriodStream,
                   data: PeriodJsonData) -> str | None:
    """
    Create a period and its tracks from JSON data
    """
    period: models.Period | None = None
    new_period: bool = False

    defaults = OptionsRepository.get_default_options()
    options = OptionsRepository.convert_cgi_options(
        {"mode": "vod"}, defaults=defaults)
    if data['pk'] is not None:
        period = models.Period.get(pk=data['pk'])
    elif mp_stream.pk:
        period = models.Period.get(pid=data['pid'], parent=mp_stream)
    if period is None:
        period = models.Period(parent=mp_stream)
        new_period = True
    stream = models.Stream.get(pk=data['stream'])
    if stream is None:
        return f"Unknown stream {data['stream']} for period {data['pid']}"
    if stream.timing_reference is None:
        return f"No timing ref in stream {data['stream']} for period {data['pid']}"
    mf = stream.get_timing_reference_file()
    if mf is None:
        return f"Failed to find MediaFile for stream {stream.directory}"
    if mf.representation is None:
        return f"MediaFile {mf.name} in stream {stream.directory} needs indexing"
    now = datetime.datetime.now(tz=UTC())
    timing = DashTiming(now, stream.timing_reference, options)
    mf.representation.set_dash_timing(timing)
    period.stream = stream
    period.stream_pk = stream.pk
    period.ordering = data['ordering']
    period.pid = data['pid']
    if data['start'] in {"", "PT0S"}:
        period.start = datetime.timedelta()
    else:
        period.start = from_isodatetime(data['start'])
    mod_seg, start_tc, origin = mf.representation.get_segment_index(
        int(period.start.total_seconds() * mf.representation.timescale))
    period.start = timecode_to_timedelta(start_tc, mf.representation.timescale)
    if data['duration'] in {"", "PT0S"}:
        period.duration = stream.duration()
    else:
        period.duration = from_isodatetime(data['duration'])
    if new_period:
        models.db.session.add(period)
        models.db.session.flush()
    unused_tracks: set[int] = set()
    for trk in period.adaptation_sets:
        unused_tracks.add(trk.pk)
    for track_id, role_str in data['tracks'].items():
        adp: models.AdaptationSet | None = None
        role: ContentRole = ContentRole.from_string(role_str)
        if period.pk:
            adp = models.AdaptationSet.get(
                track_id=track_id, period=period)
        if adp:
            unused_tracks.remove(adp.pk)
            adp.role = role
        else:
            content_type: models.ContentType | None = models.ContentType.get(
                name='application')
            assert content_type is not None
            adp = models.AdaptationSet(
                period_pk=period.pk, track_id=track_id, role=role,
                content_type=content_type)
            stmt = models.db.select(models.MediaFile).filter(
                models.MediaFile.stream_pk == stream.pk,
                models.MediaFile.track_id == track_id,
                models.MediaFile.content_type is not None)
            for mf in models.db.session.execute(stmt).scalars():
                ct = models.ContentType.get(name=mf.content_type)
                if ct is not None:
                    adp.content_type = ct
                break
            models.db.session.add(adp)
    for pk in unused_tracks:
        adp = models.AdaptationSet.get(pk=pk)
        models.db.session.delete(adp)
    return None


def mps_as_dict(mps: models.MultiPeriodStream) -> MultiPeriodStreamData:
    model = mps.to_dict(with_collections=False)
    model['periods'] = []
    for period in mps.periods:
        p_js = period.to_dict()
        p_js['tracks'] = {}
        for adp in period.adaptation_sets:
            p_js['tracks'][adp.track_id] = adp.role.name.lower()
        model['periods'].append(p_js)
    return model


class ListStreamsTemplateContext(TemplateContext):
    csrf_tokens: CsrfTokenCollection
    streams: list[models.Stream]
    user_can_modify: bool


class ListStreams(HTMLHandlerBase):
    """
    View handler that provides a list of all multi-period streams
    in the database.
    """
    decorators = [spa_handler]

    def get(self) -> flask.Response:
        """
        Get list of all multi-period streams
        """
        if not is_ajax():
            logging.error('the spa_handler decorator should have handled this request')
            return jsonify_no_content(500)

        csrf_key = self.generate_csrf_cookie()
        csrf_tokens = CsrfTokenCollection(
            files=self.generate_csrf_token('files', csrf_key),
            kids=self.generate_csrf_token('keys', csrf_key),
            streams=self.generate_csrf_token('streams', csrf_key),
            upload=None)

        streams = cast(
            list[models.MultiPeriodStream], models.MultiPeriodStream.get_all())

        result = {
            'csrfTokens': csrf_tokens,
            'streams': [],
        }
        for s in streams:
            js = s.to_dict(with_collections=True)
            js['duration'] = s.total_duration()
            result['streams'].append(js)
        return jsonify(result)


class AddStream(HTMLHandlerBase):
    decorators = [
        login_required(permission=models.Group.MEDIA),
    ]

    @spa_handler
    def get(self) -> flask.Response:
        """
        GET will be handled by spa_handler
        """
        # fields = models.MultiPeriodStream().get_fields(**flask.request.args)
        # return self.generate_form(fields)
        return jsonify_no_content(404)

    def generate_form(self, fields: list[FormInputContext]) -> flask.Response:
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('streams', csrf_key)
        context = self.create_context(
            cancel_url=flask.url_for('list-mps'), csrf_token=csrf_token,
            fields=fields, form_id='add_mps_form')
        return flask.render_template('mps/add_stream.html', **context)

    def put(self) -> flask.Response:
        data: MultiPeriodStreamData = cast(
            MultiPeriodStreamData, flask.request.json)
        if not data:
            return jsonify_no_content(400)
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('streams', csrf_key)
        errors: list[str] = []
        for source, msg in models.MultiPeriodStream.validate_values(**data).items():
            errors.append(f"{source}: {msg}")
        if errors:
            return jsonify({
                "errors": errors,
                "csrf_token": csrf_token,
            })
        mp_stream = models.MultiPeriodStream.get(name=data["name"])
        if mp_stream is not None:
            errors.append(f'Stream {data["name"]} already exists')
        else:
            stream, errs = self.add_new_stream(data)
            errors += errs
        if not errors:
            models.db.session.commit()
            stream = models.MultiPeriodStream.get(name=data["name"])
        return jsonify({
            "success": not errors,
            "errors": errors,
            "model": mps_as_dict(stream) if stream else None,
        })

    def add_new_stream(self,
                       data: MultiPeriodStreamData
                       ) -> tuple[models.MultiPeriodStream, list[str]]:
        errors: list[str] = []
        stream = models.MultiPeriodStream(
            name=data["name"], title=data['title'])
        models.db.session.add(stream)
        models.db.session.flush()
        for period in data['periods']:
            err = process_period(stream, period)
            if err is not None:
                errors.push(err)
        return [stream, errors]


class ValidateStream(RequestHandlerBase):
    decorators = [
        login_required(permission=models.Group.MEDIA),
        csrf_token_required('streams', next_url=lambda: None),
    ]

    def post(self) -> flask.Response:
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('streams', csrf_key)
        errors = models.MultiPeriodStream.validate_values(**flask.request.json)
        return jsonify({
            'csrf_token': csrf_token,
            'errors': errors,
        })


class PeriodFormInputs(NamedTuple):
    pid: FormInputContext
    ordering: FormInputContext
    stream: FormInputContext
    start: FormInputContext
    duration: FormInputContext

class PeriodFormData:
    pid: str
    directory: str
    stream: models.Stream | None
    start: datetime.timedelta | None
    duration: datetime.timedelta | None
    ordering: int

    def __init__(self, prefix: str, data: dict[str, str]) -> None:
        self.directory = data[f'{prefix}_stream']
        self.pid = data[f'{prefix}_pid']
        self.ordering = int(data[f'{prefix}_ordering'], 10)
        self.stream = None
        if self.directory:
            self.stream = models.Stream.get(directory=self.directory)
        start = data[f'{prefix}_start']
        if start == '':
            self.start = None
        else:
            self.start = from_isodatetime(f'PT{start}')
        duration = data[f'{prefix}_duration']
        if duration == '':
            self.duration = None
        else:
            self.duration = from_isodatetime(f'PT{duration}')


class EditStream(HTMLHandlerBase):
    decorators = [
        # login_required(permission=models.Group.MEDIA),
        uses_multi_period_stream,
        spa_handler,
    ]

    def get(self, name: str) -> flask.Response:
        """
        Returns a form for editing an MP stream
        """
        if not is_ajax():
            logging.error('the spa_handler decorator should have handled this request')
            return jsonify_no_content(500)

        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('streams', csrf_key)
        model = mps_as_dict(current_mps)
        result = {
            'csrf_tokens': {
                'streams': csrf_token,
            },
            'model': model,
        }
        return jsonify(result)

    @csrf_token_required(
        'streams',
        optional=True,
        next_url=lambda: flask.url_for(
            'edit-mps', name=current_mps.name, **flask.request.json))
    @jwt_required(optional=True)
    def post(self, name: str) -> flask.Response:
        data = flask.request.json
        if not data:
            logging.waring('JSON payload missing')
            return jsonify_no_content(400)
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('streams', csrf_key)
        errors = models.MultiPeriodStream.validate_values(**data)
        if errors:
            return jsonify({
                'errors': errors,
                'csrf_token': csrf_token,
            })
        pk: int | None = None
        try:
            pk = data['pk']
        except KeyError as err:
            logging.waring('Primary key missing from JSON payload: %s', err)
            return jsonify({
                'errors': [
                    "Primary key missing from JSON payload",
                ],
                'csrf_token': csrf_token,
            })
        spa: bool = data.get('spa', False)
        if spa and isinstance(pk, int):
            return self.handle_spa_data(name, csrf_token)
        return self.handle_form_data(name, csrf_token)

    def handle_form_data(self, name: str, csrf_token: str) -> flask.Response:
        data = flask.request.json
        current_mps.name = data['name']
        current_mps.title = data['title']
        errors: list[str] = []
        for period in current_mps.periods:
            try:
                pfd = PeriodFormData(f'period_{period.pk}', data)
                if pfd.stream is not None:
                    period.stream = pfd.stream
                period.start = pfd.start
                period.duration = pfd.duration
                period.ordering = pfd.ordering
            except (ValueError, KeyError) as err:
                logging.warning(
                    'Invalid form data Period pk=%d: %s', period.pk, err)
                errors[f'period_{ period.pk }'] = 'Invalid form data'
        try:
            num_new_periods: int = int(data['num_new_periods'], 10)
        except (ValueError, KeyError) as err:
            logging.warning('Failed to parse num_new_periods field: %s', err)
            errors['num_new_periods'] = 'Failed to parse num_new_periods'
        for idx in range(num_new_periods):
            prefix: str = f'new_period_{idx}'
            if f'{prefix}_stream' not in data:
                logging.warning('Form data missing for %s', prefix)
                continue
            try:
                pfd = PeriodFormData(prefix, data)
                period = models.Period(
                    stream=pfd.stream, ordering=pfd.ordering, parent=current_mps,
                    start=pfd.start, duration=pfd.duration, pid=pfd.pid)
                models.db.session.add(period)
            except (ValueError, KeyError) as err:
                logging.warning(
                    'Invalid form data new Period %d: %s', idx, err)
                errors[f'new_period_{ idx }'] = 'Invalid form data'

        if not errors:
            flask.flash(f'Updated multi-period stream "{name}"', 'success')
            models.db.session.commit()
        return jsonify({
            'success': errors == {},
            'errors': errors,
            'csrf_token': csrf_token,
            'next': flask.url_for('list-mps'),
            **mps_as_dict(current_mps),
        })

    def handle_spa_data(self, name: str, csrf_token: str) -> flask.Response:
        data = flask.request.json
        current_mps.name = data['name']
        current_mps.title = data['title']
        errors: list[str] = []
        for period in data['periods']:
            err = process_period(current_mps, period)
            if err is not None:
                errors.push(err)
        if not errors:
            models.db.session.commit()
        return jsonify({
            'success': errors == [],
            'errors': errors,
            'csrfTokens': {
                'stream': csrf_token,
            },
            'model': mps_as_dict(current_mps),
        })

    @deprecated("the SPA handler should be used")
    def generate_form(self) -> flask.Response:
        fields = current_mps.get_fields(**flask.request.args)
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('streams', csrf_key)
        periods: dict[int, dict[str, FormInputContext]] = {}
        for period in current_mps.periods:
            periods[period.pk] = self.generate_period_fields(period)
        periods[-1] = self.generate_period_fields(None)
        context = self.create_context(
            cancel_url=flask.url_for('list-mps'), csrf_token=csrf_token,
            model=current_mps, period_fields=periods,
            fields=fields, form_id='edit_mps_form')
        return flask.render_template('mps/edit_stream.html', **context)

    @classmethod
    def generate_period_fields(
            cls, period: models.Period | None) -> PeriodFormInputs:
        if period is None:
            period = models.Period(pk=None, ordering=1000)
        ordering, pid, start, duration, stream = period.get_fields()
        return PeriodFormInputs(
            ordering=ordering, pid=pid, stream=stream, start=start,
            duration=duration)