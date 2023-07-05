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

from builtins import str
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

from .base import HTMLHandlerBase, RequestHandlerBase
from .decorators import (
    uses_media_file, current_media_file, login_required,
    uses_stream, current_stream
)
from .exceptions import CsrfFailureException

class UploadHandler(RequestHandlerBase):
    decorators = [uses_stream, login_required(admin=True)]

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
        if self.is_ajax():
            result = {"error": error}
            return self.jsonify(result)
        flask.flash(error)
        logging.warning('Upload error: %s', error)
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
        if self.is_ajax():
            csrf_key = self.generate_csrf_cookie()
            result['upload_url'] = flask.url_for('upload-blob', spk=stream.pk)
            result['csrf_token'] = self.generate_csrf_token(
                "upload", csrf_key)
            result["file_html"] = flask.render_template('media/media_row.html', **context)
            return self.jsonify(result)
        return flask.render_template('upload-done.html', **context)


class MediaInfo(HTMLHandlerBase):
    """
    View handler that provides details about one media file
    """
    decorators = [uses_media_file, login_required(admin=True, html=True)]

    def get(self, mfid: int) -> flask.Response:
        result = {"error": None}
        mf = current_media_file
        result = {
            "representation": mf.rep,
            "name": mf.name,
            "key": mf.pk,
            "blob": mf.blob.to_dict(exclude={'mediafile'}),
        }
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('files', csrf_key)
        return self.jsonify(result)

    @uses_media_file
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

class MediaIndex(HTMLHandlerBase):
    """
    View handler that indexes a file to find its fragments and
    media information
    """
    decorators = [uses_media_file, login_required(admin=True)]

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
            models.db.session.commit()
            result = {
                "indexed": mf.pk,
                "representation": mf.rep,
            }
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('files', csrf_key)
        return self.jsonify(result, status=status)
