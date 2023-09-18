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
import hashlib
import logging
from pathlib import Path

import flask
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation
from dashlive.server import models
from dashlive.server.routes import Route
from dashlive.utils.buffered_reader import BufferedReader
from dashlive.utils.json_object import JsonObject

from .base import HTMLHandlerBase, RequestHandlerBase
from .decorators import (
    uses_media_file, current_media_file, login_required,
    uses_stream, current_stream
)
from .exceptions import CsrfFailureException

class UploadHandler(RequestHandlerBase):
    decorators = [uses_stream, login_required(permission=models.Group.MEDIA)]

    def post(self, spk, **kwargs):
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
        if self.is_ajax():
            result = {"error": error}
            return self.jsonify(result)
        flask.flash(error)
        return flask.redirect(flask.url_for('list-streams'))

    def save_file(self, file_upload: FileStorage,
                  stream: models.Stream) -> flask.Response:
        logging.debug("File %s uploaded", file_upload.filename)
        filename = Path(secure_filename(file_upload.filename))
        upload_folder = Path(flask.current_app.config['UPLOAD_FOLDER']) / stream.directory
        logging.debug('upload_folder="%s"', upload_folder)
        if not upload_folder.exists():
            upload_folder.mkdir(parents=True)
        abs_filename = upload_folder / filename
        mf = models.MediaFile.get(name=filename.stem)
        if mf:
            mf.delete_file()
            mf.delete()
        blob = models.Blob.get_one(filename=filename.name)
        if blob:
            blob.delete_file(upload_folder)
            blob.delete()
        file_upload.save(abs_filename)
        blob = models.Blob(
            filename=filename.name,
            size=abs_filename.stat().st_size,
            content_type=file_upload.mimetype)
        with abs_filename.open('rb') as src:
            digest = hashlib.file_digest(src, 'sha1')
            blob.sha1_hash = digest.hexdigest()
        models.db.session.add(blob)
        mf = models.MediaFile(
            name=filename.stem, stream=stream, blob=blob,
            content_type=file_upload.mimetype)
        models.db.session.add(mf)
        models.db.session.commit()
        mf = models.MediaFile.get(name=filename.stem, stream=stream)
        result = mf.toJSON()
        result['blob']['created'] = datetime.datetime.now()
        logging.debug("upload done %s", abs_filename)
        context = self.create_context(
            title=f'File {filename.name} uploaded',
            media=result)
        context['stream'] = current_stream
        if self.is_ajax():
            csrf_key = self.generate_csrf_cookie()
            result['upload_url'] = flask.url_for('upload-blob', spk=stream.pk)
            result['csrf_token'] = self.generate_csrf_token(
                "upload", csrf_key)
            result["file_html"] = flask.render_template('media/media_row.html', **context)
            return self.jsonify(result)
        flask.flash(f'Uploaded file {filename.stem}', 'success')
        return flask.render_template('upload-done.html', **context)


class MediaInfo(HTMLHandlerBase):
    """
    View handler that provides details about one media file
    """
    decorators = [uses_media_file, uses_stream]

    def get(self, spk: int, mfid: int) -> flask.Response:
        mf = current_media_file
        csrf_key = self.generate_csrf_cookie()
        csrf_token = self.generate_csrf_token('files', csrf_key)
        if self.is_ajax():
            result = {
                "representation": mf.rep,
                "name": mf.name,
                "key": mf.pk,
                "blob": mf.blob.to_dict(exclude={'mediafile'}),
                "csrf_token": csrf_token,
            }
            return self.jsonify(result)
        context = self.create_context()
        context.update({
            'stream': current_stream,
            'mediafile': mf,
            "csrf_token": csrf_token,
            "duration": None,
            "segment_duration": None,
        })
        if mf.representation:
            context['duration'] = datetime.timedelta(seconds=(
                mf.representation.mediaDuration / float(mf.representation.timescale)))
            context['segment_duration'] = datetime.timedelta(seconds=(
                mf.representation.segment_duration / float(mf.representation.timescale)))
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
    def delete(self, mfid, **kwargs):
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
        return self.jsonify(result, status=status)


class IndexMediaFile(HTMLHandlerBase):
    """
    View handler that indexes a file to find its fragments and
    media information
    """
    decorators = [uses_media_file, login_required(permission=models.Group.MEDIA)]

    def get(self, mfid: str) -> flask.Response:
        result = {"error": None}
        status = 200
        try:
            self.check_csrf('files', flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            result = {"error": str(err)}
            status = 401
        if result["error"] is None:
            mf = current_media_file
            with mf.open_file() as src:
                atom = mp4.Wrapper(
                    atom_type='wrap', position=0, size=mf.blob.size,
                    parent=None, children=mp4.Mp4Atom.load(src))
            rep = Representation.load(filename=mf.name, atoms=atom.children)
            mf.representation = rep
            mf.encryption_keys = []
            for kid in rep.kids:
                key_model = models.Key.get(hkid=kid.hex)
                if key_model is None:
                    key = models.KeyMaterial(
                        raw=PlayReady.generate_content_key(kid.raw))
                    key_model = models.Key(hkid=kid.hex, hkey=key.hex, computed=True)
                    key_model.add()
                mf.encryption_keys.append(key_model)
            mf.content_type = rep.content_type
            mf.bitrate = rep.bitrate
            mf.encrypted = rep.encrypted
            if rep.bitrate:
                # bitrate cannot be None, therefore don't commit if
                # Representation class failed to discover the
                # bitrate
                models.db.session.commit()
            result = {
                "indexed": mf.pk,
                "representation": mf.rep,
            }
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('files', csrf_key)
        return self.jsonify(result, status=status)


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
        if self.is_ajax():
            return self.jsonify({
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
        options = mp4.Options(cache_encoded=True)
        if current_media_file.representation.encrypted:
            options.iv_size = current_media_file.representation.iv_size
        with current_media_file.open_file(start=frag.pos, buffer_size=16384) as reader:
            src = BufferedReader(
                reader, offset=frag.pos, size=frag.size, buffersize=16384)
            atom = mp4.Wrapper(
                atom_type='wrap', children=mp4.Mp4Atom.load(src, options=options))
        exclude = {'parent', 'options'}
        atoms = [ch.toJSON(exclude=exclude) for ch in atom.children]
        for ch in atoms:
            self.filter_atom(ch)
        if self.is_ajax():
            return self.jsonify({
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
