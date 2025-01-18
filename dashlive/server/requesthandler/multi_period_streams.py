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
from flask_jwt_extended import jwt_required

from dashlive.mpeg.dash.content_role import ContentRole
from dashlive.mpeg.dash.timing import DashTiming
from dashlive.server import models
from dashlive.server.models.adaptation_set import AdaptationSetJson
from dashlive.server.options.form_input_field import FormInputContext
from dashlive.server.options.repository import OptionsRepository
from dashlive.utils.date_time import from_isodatetime, timecode_to_timedelta
from dashlive.utils.json_object import JsonObject
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

class TracksItemPayload:
    track_id: int
    role: ContentRole
    lang: str | None
    encrypted: bool

    def __init__(self, track_id: int, role: str, lang: str | None = None,
                 encrypted: bool = False, **kwargs) -> None:
        self.track_id = track_id
        self.role = ContentRole.from_string(role)
        self.lang = lang
        self.encrypted = encrypted

class TracksJsonPayload(TypedDict):
    track_id: int
    role: str
    lang: str | None = None
    encrypted: bool = False

class PeriodJsonData(TypedDict):
    duration: str
    encrypted: bool
    lang: str | None
    ordering: int
    parent: int
    pid: str
    pk: int | None
    start: str
    stream: int
    tracks: list[TracksJsonPayload]


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
    unused_tracks: set[int] = set()
    for trk in period.adaptation_sets:
        unused_tracks.add(trk.pk)

    for tkd in data['tracks']:
        tip: TracksItemPayload = TracksItemPayload(**tkd)
        adp: models.AdaptationSet | None = None
        if period.pk:
            adp = models.AdaptationSet.get(
                track_id=tip.track_id, period=period)
        if adp:
            unused_tracks.remove(adp.pk)
            adp.role = tip.role
            adp.encrypted = tip.encrypted
            adp.lang = tip.lang
        else:
            content_type: models.ContentType | None = models.ContentType.get(
                name='application')
            assert content_type is not None
            adp = models.AdaptationSet(
                period=period, track_id=tip.track_id, role=tip.role, lang=tip.lang,
                content_type=content_type, encrypted=tip.encrypted)
            stmt = models.db.select(models.MediaFile).filter(
                models.MediaFile.stream_pk == stream.pk,
                models.MediaFile.track_id == tip.track_id,
                models.MediaFile.content_type is not None)
            for mf in models.db.session.execute(stmt).scalars():
                ct: models.ContentType | None = models.ContentType.get(name=mf.content_type)
                if ct is not None:
                    adp.content_type = ct
                break
            models.db.session.add(adp)
    for pk in unused_tracks:
        adp = models.AdaptationSet.get(pk=pk)
        models.db.session.delete(adp)
    return None


def mps_as_dict(mps: models.MultiPeriodStream) -> MultiPeriodStreamData:
    model: MultiPeriodStreamData = mps.to_dict(with_collections=False)
    model['periods'] = []
    for period in mps.periods:
        p_js = period.to_dict()
        tracks: list[AdaptationSetJson] = []
        for adp in period.adaptation_sets:
            tk: AdaptationSetJson = adp.to_dict(exclude={'period_pk', 'content_type'})
            tk['content_type'] = adp.content_type.name
            tk['codec_fourcc'] = adp.codec_fourcc()
            tracks.append(tk)
        p_js['tracks'] = tracks
        model['periods'].append(p_js)
    return model


class ListStreamsTemplateContext(TemplateContext):
    csrfTokens: CsrfTokenCollection
    streams: list[models.Stream]
    user_can_modify: bool


class ListStreams(HTMLHandlerBase):
    """
    View handler that provides a list of all multi-period streams
    in the database.
    """
    decorators = [
        spa_handler,  # must be the last decorator so that it called before the others
    ]

    def get(self) -> flask.Response:
        """
        Get list of all multi-period streams
        """
        if not is_ajax():
            logging.error('the spa_handler decorator should have handled this request')
            return jsonify_no_content(500)

        streams: list[JsonObject] = []
        for s in models.MultiPeriodStream.get_all():
            js = s.to_dict(with_collections=True)
            js['duration'] = s.total_duration()
            streams.append(js)
        return jsonify(streams)


class AddStream(HTMLHandlerBase):
    decorators = [
        login_required(permission=models.Group.MEDIA),
    ]

    @spa_handler
    def get(self) -> flask.Response:
        """
        GET will be handled by spa_handler
        """
        return jsonify_no_content(404)

    @jwt_required()
    @csrf_token_required('streams')
    def put(self) -> flask.Response:
        data: MultiPeriodStreamData = cast(
            MultiPeriodStreamData, flask.request.get_json())
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
        stream: models.MultiPeriodStream | None = models.MultiPeriodStream.get(name=data["name"])
        if stream is not None:
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
            name=data["name"], title=data['title'], options=data.get('options'))
        models.db.session.add(stream)
        models.db.session.flush()
        for period in data['periods']:
            err = process_period(stream, period)
            if err is not None:
                errors.append(err)
        return [stream, errors]


class ValidateStream(RequestHandlerBase):
    decorators = [
        csrf_token_required('streams'),
        jwt_required()
    ]

    def post(self) -> flask.Response:
        errors = models.MultiPeriodStream.validate_values(**flask.request.json)
        return jsonify({
            'errors': errors,
        })


class PeriodFormInputs(NamedTuple):
    pid: FormInputContext
    ordering: FormInputContext
    stream: FormInputContext
    start: FormInputContext
    duration: FormInputContext

class EditStream(HTMLHandlerBase):
    decorators = [
        uses_multi_period_stream,
        jwt_required(),
        spa_handler,
    ]

    def get(self, mps_name: str) -> flask.Response:
        """
        Returns details of an MP stream
        """
        if not is_ajax():
            logging.error('the spa_handler decorator should have handled this request')
            return jsonify_no_content(500)

        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('streams', csrf_key)
        model = mps_as_dict(current_mps)
        result = {
            'csrfTokens': {
                'streams': csrf_token,
            },
            'model': model,
        }
        return jsonify(result)

    @csrf_token_required('streams')
    def post(self, mps_name: str) -> flask.Response:
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
        return self.process_json_body(mps_name, csrf_token)

    @csrf_token_required('streams')
    def delete(self, mps_name: str) -> flask.Response:
        logging.info('Deleting MultiPeriodStream: %s', mps_name)
        models.db.session.delete(current_mps)
        models.db.session.commit()
        return jsonify_no_content(204)

    def process_json_body(self, name: str, csrf_token: str) -> flask.Response:
        data = flask.request.json
        current_mps.name = data['name']
        current_mps.title = data['title']
        current_mps.options = data.get('options')
        errors: list[str] = []
        with models.db.session.no_autoflush:
            for period in data['periods']:
                err: str | None = process_period(current_mps, period)
                if err is not None:
                    errors.push(err)
            if not errors:
                models.db.session.flush()
                models.db.session.commit()
        return jsonify({
            'success': errors == [],
            'errors': errors,
            'csrfTokens': {
                'stream': csrf_token,
            },
            'model': mps_as_dict(current_mps),
        })
