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

import datetime
import html
import logging
from pathlib import Path
from typing import cast

import flask
from flask_login import current_user
from langcodes import tag_is_valid
from werkzeug.datastructures import FileStorage

from dashlive.mpeg import mp4
from dashlive.server import models
from dashlive.server.models.error_reason import ErrorReason
from dashlive.server.routes import Route
from dashlive.utils.buffered_reader import BufferedReader
from dashlive.utils.date_time import timecode_to_timedelta
from dashlive.utils.files import generate_new_filename
from dashlive.utils.json_object import JsonObject
from dashlive.utils.timezone import UTC

from .base import HTMLHandlerBase, RequestHandlerBase, DeleteModelBase
from .decorators import (
    uses_media_file, current_media_file, login_required,
    uses_stream, current_stream, csrf_token_required
)
from .exceptions import CsrfFailureException
from .template_context import TemplateContext
from .utils import is_ajax, jsonify, jsonify_no_content

class UploadHandler(RequestHandlerBase):
    decorators = [uses_stream, login_required(permission=models.Group.MEDIA)]

    def post(self, spk: int) -> flask.Response:
        if 'file' not in flask.request.files:
            return self.return_error('File not specified')
        if len(flask.request.files) == 0:
            return self.return_error('No files uploaded')
        blob_info = flask.request.files['file']
        logging.debug("Filename: " + blob_info.filename)
        if blob_info.filename == '':
            return self.return_error('Filename not specified')
        try:
            self.check_csrf('upload', flask.request.form)
        except (CsrfFailureException) as cfe:
            logging.debug("csrf check failed")
            logging.debug(cfe)
            # TODO: check if uploaded file needs to be deleted
            return self.return_error(str(cfe))
        return self.save_file(blob_info, current_stream)

    def return_error(self, error: str) -> flask.Response:
        logging.warning('Upload error: %s', error)
        if is_ajax():
            result = {"error": error}
            return jsonify(result)
        flask.flash(error)
        return flask.redirect(flask.url_for('list-streams'))

    def save_file(self, file_upload: FileStorage,
                  stream: models.Stream) -> flask.Response:
        logging.debug("File %s uploaded", file_upload.filename)
        mf = stream.add_file(file_upload, commit=True)
        result = mf.toJSON()
        result['blob']['created'] = datetime.datetime.now()
        logging.debug("upload done %s", mf.name)
        context = self.create_context(
            title=f'File {mf.name} uploaded',
            media=result,
            stream=current_stream)
        if is_ajax():
            csrf_key = self.generate_csrf_cookie()
            result['upload_url'] = flask.url_for('upload-blob', spk=stream.pk)
            result['csrf_token'] = self.generate_csrf_token(
                "upload", csrf_key)
            result["file_html"] = flask.render_template('media/media_row.html', **context)
            return jsonify(result)
        flask.flash(f'Uploaded file {mf.name}', 'success')
        return flask.render_template('upload-done.html', **context)


class MediaInfoContext(TemplateContext):
    duration_tc: int | None
    duration_time: datetime.timedelta | None
    mediafile: models.MediaFile
    segment_duration: datetime.timedelta | None
    stream: models.Stream
    user_can_modify: bool

class MediaInfo(HTMLHandlerBase):
    """
    View handler that provides details about one media file
    """
    decorators = [uses_media_file, uses_stream]

    def get(self, spk: int, mfid: int) -> flask.Response:
        mf = current_media_file
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('files', csrf_key)
        user_can_modify: bool = current_user.has_permission(models.Group.MEDIA)
        if is_ajax():
            result = {
                "representation": mf.rep,
                "name": mf.name,
                "key": mf.pk,
                "blob": mf.blob.to_dict(exclude={'mediafile'}),
                "csrf_token": csrf_token,
                "user_can_modify": user_can_modify,
            }
            return jsonify(result)
        context = cast(MediaInfoContext, self.create_context(
            title=f'Media file: {mf.name}',
            stream=current_stream,
            mediafile=mf,
            csrf_token=csrf_token,
            duration_tc=None,
            duration_time=None,
            segment_duration=None,
            user_can_modify=user_can_modify))
        if mf.representation:
            context['duration_tc'] = mf.representation.mediaDuration
            context['duration_time'] = timecode_to_timedelta(
                mf.representation.mediaDuration, mf.representation.timescale)
            context['segment_duration'] = timecode_to_timedelta(
                mf.representation.segment_duration, mf.representation.timescale)
        return flask.render_template('media/media_info.html', **context)

    def get_breadcrumbs(self, route: Route) -> list[dict[str, str]]:
        breadcrumbs = super().get_breadcrumbs(route)
        breadcrumbs.insert(-1, {
            'title': current_stream.directory,
            'href': flask.url_for('view-stream', spk=current_stream.pk),
        })
        breadcrumbs[-1]['title'] = current_media_file.name
        return breadcrumbs

    @login_required(permission=models.Group.MEDIA, html=True)
    def delete(self, spk: int, mfid: int) -> flask.Response:
        """
        handler for deleting a media blob
        """
        result = {"error": None}
        status = 200
        try:
            self.check_csrf('files', flask.request.args)
        except CsrfFailureException as err:
            result["error"] = str(err)
        if result["error"] is None:
            mf = models.MediaFile.get(pk=mfid)
            if not mf:
                result["error"] = f'{mfid} not found'
                status = 404
        if result["error"] is None:
            result.update(mf.toJSON())
            models.db.session.delete(mf)
            models.db.session.commit()
            result["deleted"] = mfid
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('files', csrf_key)
        return jsonify(result, status=status)


class EditMediaContext(TemplateContext):
    form_id: str
    model: models.MediaFile
    fields: dict[str, JsonObject]
    error: str | None
    cancel_url: str
    validation: str


class EditMedia(HTMLHandlerBase):
    """
    View handler that allows editing one media file
    """
    decorators = [
        uses_media_file,
        uses_stream,
        login_required(permission=models.Group.MEDIA),
    ]

    @classmethod
    def next_url(cls, spk: int, **kwargs) -> str:
        return flask.url_for('view-stream', spk=current_stream.pk)

    def get(self, spk: int, mfid: int) -> flask.Response:
        mf = current_media_file
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('files', csrf_key)
        error: str | None = None
        if mf.errors:
            errs: set[str] = {err.reason.name for err in mf.errors}
            error = f'{ mf.name } has errors: { " ,".join(errs) }'
        context = cast(EditMediaContext, self.create_context(
            form_id='edit_media',
            title=f'Edit file: {mf.name}',
            model=mf,
            cancel_url=flask.url_for('media-info', spk=spk, mfid=mfid),
            csrf_token=csrf_token,
            error=error,
            fields=mf.get_fields(**flask.request.args),
            validation='was-validated'))
        return flask.render_template('media/edit_media.html', **context)

    @csrf_token_required(service='files', next_url=next_url)
    def post(self, spk: int, mfid: int) -> flask.Response:
        mf = current_media_file
        current_values: dict[str, str | int] = {
            'track_id': mf.track_id,
            'lang': mf.representation.lang,
        }
        fields: dict[str, str | int] = {
            'track_id': int(flask.request.form['track_id'], 10),
            'lang': flask.request.form.get('lang', current_values['lang']),
        }
        if fields == current_values:
            flask.flash('No file changes to apply')
            return flask.redirect(
                flask.url_for('media-info', spk=spk, mfid=mfid))
        abs_path = models.MediaFile.absolute_path(mf.stream.directory)
        filename = Path(mf.blob.filename)
        new_name = generate_new_filename(abs_path, filename.stem, filename.suffix)

        def modify_atoms(wrap: mp4.Wrapper) -> bool:
            modified = False
            moov = wrap.find_child('moov')
            moof = wrap.find_child('moof')
            if moov is not None:
                trak = moov.trak
                if trak.tkhd.track_id != fields['track_id']:
                    trak.tkhd.track_id = fields['track_id']
                    moov.mvex.trex.track_id = fields['track_id']
                    moov.mvhd.next_track_id = fields['track_id'] + 1
                    modified = True
                if trak.mdia.mdhd.language != fields['lang']:
                    trak.mdia.mdhd.language = fields['lang']
                    modified = True
                if modified:
                    trak.tkhd.modification_time = datetime.datetime.now(tz=UTC())
            elif moof is not None:
                if moof.traf.tfhd.track_id != fields['track_id']:
                    moof.traf.tfhd.track_id = fields['track_id']
                    modified = True
            return modified

        old_blob_name = mf.blob.filename
        if not mf.modify_media_file(new_name, modify_atoms):
            flask.flash(f'Failed to create new MP4 file {new_name.name}')
            url = flask.url_for(
                'edit-media', spk=spk, mfid=mfid, **fields)
            return flask.redirect(url)
        flask.flash(f'Replaced MP4 file {old_blob_name} with {new_name.name}')
        models.db.session.commit()
        return flask.redirect(
            flask.url_for('media-info', spk=mf.stream.pk, mfid=mf.pk))

    def get_breadcrumbs(self, route: Route) -> list[dict[str, str]]:
        breadcrumbs = super().get_breadcrumbs(route)
        breadcrumbs.insert(-1, {
            'title': current_stream.directory,
            'href': flask.url_for('view-stream', spk=current_stream.pk),
        })
        breadcrumbs[-1] = {
            'title': current_media_file.name,
            'active': False,
            'href': flask.url_for(
                'media-info', spk=current_stream.pk, mfid=current_media_file.pk),
        }
        breadcrumbs.append({
            'title': 'edit',
            'active': True,
        })
        return breadcrumbs


class DeleteMedia(DeleteModelBase):
    MODEL_NAME = 'mediafile'
    CSRF_TOKEN_NAME = 'files'
    decorators = [
        uses_media_file,
        uses_stream,
        login_required(html=True, permission=models.Group.MEDIA)]

    def get_model_dict(self) -> JsonObject:
        js = current_media_file.to_dict(with_collections=False)
        js['title'] = current_media_file.blob.filename
        return js

    def get_cancel_url(self) -> str:
        return flask.url_for(
            'media-info',
            spk=current_media_file.stream.pk,
            mfid=current_media_file.pk)

    def delete_model(self) -> JsonObject:
        result = {
            "deleted": current_media_file.pk,
            "title": current_media_file.name,
            "stream": current_stream.title,
        }
        models.db.session.delete(current_media_file)
        models.db.session.commit()
        return result

    def get_next_url(self) -> str:
        return flask.url_for(
            'view-stream',
            spk=current_stream.pk)


class IndexMediaFile(HTMLHandlerBase):
    """
    View handler that indexes a file to find its fragments and
    media information
    """
    decorators = [uses_media_file, login_required(permission=models.Group.MEDIA)]

    def get(self, mfid: str) -> flask.Response:
        result = {"errors": []}
        try:
            self.check_csrf('files', flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            result["errors"].append(html.escape(f'{err}'))
            return jsonify(result, status=401)

        mf = current_media_file
        if mf.parse_media_file():
            models.db.session.commit()
            result.update({
                "indexed": mf.pk,
                "representation": mf.rep,
            })
            codecs: set[str] = set()
            for mfiles in models.MediaFile.search(
                    stream_pk=mf.stream_pk, track_id=mf.track_id):
                if mfiles.codec_fourcc is not None:
                    codecs.add(mfiles.codec_fourcc)
            if len(codecs) > 1:
                details = (
                    f'Track ID {mf.track_id} used for multiple codecs ' +
                    f'{" ,".join(codecs)}')
                err = models.MediaFileError(
                    media_pk=mf.pk,
                    reason=ErrorReason.DUPLICATE_TRACK_IDS,
                    details=details)
                models.db.session.add(err)
                result['errors'].append(details)
        else:
            result['errors'].append('Failed to parse media file')
        for err in mf.errors:
            result['errors'].append(f'{err.reason.name}: {err.details}')
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('files', csrf_key)
        return jsonify(result)


class MediaSegmentList(HTMLHandlerBase):
    decorators = [uses_media_file, uses_stream]

    def get(self, spk: int, mfid: int) -> flask.Response:
        context = self.create_context()
        start = 0
        segments = []
        for seg in current_media_file.representation.segments:
            item = {
                'start': start,
                'start_time': datetime.timedelta(
                    seconds=(start / float(current_media_file.representation.timescale))),
                'size': seg.size,
                'position': seg.pos,
                'duration': seg.duration,
            }
            if segments:
                if seg.duration is None:
                    item['duration'] = current_media_file.representation.segment_duration
                item['duration_time'] = datetime.timedelta(
                    seconds=(item['duration'] / float(current_media_file.representation.timescale)))
                start += item['duration']
            else:
                item.update({
                    'duration': '',
                    'duration_time': None,
                    'start': '',
                    'start_time': None,
                })
            segments.append(item)
        if is_ajax():
            return jsonify({
                'stream': current_stream.to_dict(with_collections=False),
                'mediafile': current_media_file.to_dict(
                    with_collections=False, exclude={'representation', 'rep'}),
                'segments': segments,
            })
        context.update({
            'stream': current_stream,
            'mediafile': current_media_file,
            'segments': segments,
        })
        return flask.render_template('media/segment_list.html', **context)

    def get_breadcrumbs(self, route: Route) -> list[dict[str, str]]:
        crumbs = super().get_breadcrumbs(route)
        stream_crumb = {
            'title': current_stream.directory,
            'href': flask.url_for('view-stream', spk=current_stream.pk),
        }
        crumbs.insert(-1, stream_crumb)
        media_info = {
            'title': current_media_file.name,
            'href': flask.url_for(
                'media-info', spk=current_stream.pk, mfid=current_media_file.pk),
        }
        crumbs.insert(-1, media_info)
        return crumbs


class MediaSegmentInfo(HTMLHandlerBase):
    """
    Handler for showing details about one segment in an MP4 file
    """

    decorators = [uses_media_file, uses_stream]

    def get(self, spk: int, mfid: int, segnum: int) -> flask.Response:
        context = self.create_context()
        if segnum == 0:
            context['breadcrumbs'][-1]['title'] = 'Init Segment'
        else:
            context['breadcrumbs'][-1]['title'] = f'Segment {segnum}'
        frag = current_media_file.representation.segments[int(segnum)]
        options = mp4.Options(lazy_load=False)
        if current_media_file.representation.encrypted:
            options.iv_size = current_media_file.representation.iv_size
        with current_media_file.open_file(start=frag.pos, buffer_size=16384) as reader:
            src = BufferedReader(
                reader, offset=frag.pos, size=frag.size, buffersize=16384)
            atom = mp4.Mp4Atom.load(src, options=options, use_wrapper=True)
        exclude = {'parent', 'options'}
        atoms = [ch.toJSON(exclude=exclude) for ch in atom.children]
        for ch in atoms:
            self.filter_atom(ch)
        if is_ajax():
            return jsonify({
                'segmentNumber': segnum,
                'atoms': atoms,
                'media': current_media_file.to_dict(
                    with_collections=False, exclude={'stream', 'blob', 'representation', 'rep'}),
                'stream': current_stream.to_dict(
                    with_collections=False, exclude={'media_files'}),
            })

        def value_has_children(obj) -> bool:
            if not obj:
                return False
            if not isinstance(obj, list):
                return False
            if not isinstance(obj[0], dict):
                return False
            if '_type' in obj[0]:
                return True
            return False

        context['next_id_value'] = 1

        def create_id() -> str:
            rv = f'id{context["next_id_value"]}'
            context['next_id_value'] += 1
            return rv

        context.update({
            'segnum': segnum,
            'atoms': atoms,
            'mediafile': current_media_file,
            'stream': current_stream,
            'value_has_children': value_has_children,
            'create_id': create_id,
            'object_name': self.object_name,
        })
        return flask.render_template('media/segment_info.html', **context)

    def get_breadcrumbs(self, route: Route) -> list[dict[str, str]]:
        crumbs = super().get_breadcrumbs(route)
        stream_crumb = {
            'title': current_stream.directory,
            'href': flask.url_for('view-stream', spk=current_stream.pk),
        }
        crumbs.insert(-1, stream_crumb)
        media_info = {
            'title': current_media_file.name,
            'href': flask.url_for(
                'media-info', spk=current_stream.pk, mfid=current_media_file.pk),
        }
        crumbs.insert(-1, media_info)
        all_segments = {
            'title': 'Segments',
            'href': flask.url_for(
                'list-media-segments', spk=current_stream.pk,
                mfid=current_media_file.pk),
        }
        crumbs.insert(-1, all_segments)
        return crumbs

    @staticmethod
    def object_name(obj: str | JsonObject) -> str:
        if isinstance(obj, str):
            return obj.split('.')[-1]
        if 'atom_type' in obj:
            return obj['atom_type']
        return obj['_type'].split('.')[-1]

    def filter_object(self, obj: JsonObject) -> None:
        if 'children' in obj:
            if obj['children'] is None:
                del obj['children']
            else:
                for ch in obj['children']:
                    self.filter_object(ch)
        if 'data' not in obj:
            return
        if obj['data'] is None:
            del obj['data']
            return
        if isinstance(obj['data'], dict):
            try:
                obj['data'] = obj['data']['b64']
            except KeyError:
                obj['data'] = obj['data']['hx']
        if len(obj['data']) > 63:
            obj['data'] = '...'

    def filter_atom(self, atom: JsonObject) -> None:
        self.filter_object(atom)
        if 'children' in atom:
            if atom['children'] is None:
                del atom['children']
            else:
                for ch in atom['children']:
                    self.filter_atom(ch)
        if 'descriptors' in atom:
            if atom['descriptors'] is None:
                del atom['descriptors']
            else:
                for dsc in atom['descriptors']:
                    self.filter_object(dsc)


class ValidateMediaChanges(HTMLHandlerBase):
    """
    Handler used for form validation when editing a media file
    """
    decorators = [
        uses_media_file,
        uses_stream,
        login_required(permission=models.Group.MEDIA),
    ]

    def post(self, spk: int, mfid: int) -> flask.Response:
        if not is_ajax():
            return flask.make_response('Invalid request', 400)
        data = flask.request.json
        try:
            lang = data['lang']
            track_id = int(data['track_id'], 10)
        except (KeyError, ValueError):
            return jsonify_no_content(400)
        errors: dict[str, str] = {
            "lang": '',
            "track_id": '',
        }
        if not tag_is_valid(lang):
            errors["lang"] = f'"{lang}" is not a valid BCP-47 language tag'
        codecs: set(str) = set()
        if current_media_file.codec_fourcc is not None:
            codecs.add(current_media_file.codec_fourcc)
        for item in models.MediaFile.search(
                stream_pk=current_media_file.stream_pk, track_id=track_id):
            if item.codec_fourcc is not None:
                codecs.add(item.codec_fourcc)
        if len(codecs) > 1:
            codecs.remove(current_media_file.codec_fourcc)
            track_names: list[str] = []
            for item in models.MediaFile.search(
                    stream_pk=current_media_file.stream_pk, track_id=track_id):
                if item.codec_fourcc in codecs:
                    track_names.append(f'"{item.name}"')
            errors['track_id'] = (
                f'Track ID {track_id} is already in use for {" ".join(codecs)} ' +
                f'tracks {", ".join(track_names)}')
        return jsonify(dict(errors=errors))
