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
import json
import os

from google.appengine.api import datastore_errors, users
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.ndb.model import Key

from drm.playready import PlayReady
from mpeg import mp4
from mpeg.dash.representation import Representation
from server import models
from server.requesthandler.base import RequestHandlerBase
from server.requesthandler.exceptions import CsrfFailureException
from templates.factory import TemplateFactory
from templates.tags import dateTimeFormat
from utils.buffered_reader import BufferedReader
from utils.objects import flatten

class MediaHandler(RequestHandlerBase):
    class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
        def post(self, *args, **kwargs):
            is_ajax = self.request.get("ajax", "0") == "1"
            upload_files = self.get_uploads()
            logging.debug("uploaded file count: %d" % len(upload_files))
            if not users.is_current_user_admin():
                self.response.write('User is not an administrator')
                self.response.set_status(401)
                return
            result = {"error": "Unknown"}
            if is_ajax:
                self.response.content_type = 'application/json'
            if len(upload_files) == 0:
                if is_ajax:
                    result["error"] = "No files uploaded"
                    self.response.write(json.dumps(result))
                    return
                self.outer.get()
                return
            blob_info = upload_files[0]
            logging.debug("Filename: " + blob_info.filename)
            result["filename"] = blob_info.filename
            media_id, ext = os.path.splitext(blob_info.filename)
            try:
                self.outer.check_csrf('upload')
            except (CsrfFailureException) as cfe:
                logging.debug("csrf check failed")
                logging.debug(cfe)
                if is_ajax:
                    result["error"] = '{}: {:s}'.format(
                        cfe.__class__.__name__, cfe)
                    self.response.write(json.dumps(result))
                self.response.set_status(401)
                blob_info.delete()
                return
            try:
                context = self.outer.create_context(title='File %s uploaded' % (blob_info.filename),
                                                    blob=blob_info.key())
                mf = models.MediaFile.query(
                    models.MediaFile.name == blob_info.filename).get()
                if mf:
                    mf.delete()
                mf = models.MediaFile(
                    name=blob_info.filename, blob=blob_info.key())
                mf.put()
                context["mfid"] = mf.key.urlsafe()
                result = mf.toJSON()
                logging.debug("upload done " + context["mfid"])
                if is_ajax:
                    csrf_key = self.outer.generate_csrf_cookie()
                    result['upload_url'] = blobstore.create_upload_url(
                        self.outer.uri_for('uploadBlob'))
                    result['csrf'] = self.outer.generate_csrf_token(
                        "upload", csrf_key)
                    template = TemplateFactory.get_template('media_row.html')
                    context["media"] = mf
                    result["file_html"] = template.render(context)
                    self.response.write(json.dumps(result))
                else:
                    template = TemplateFactory.get_template('upload-done.html')
                    self.response.write(template.render(context))
                return
            except (KeyError) as e:
                if is_ajax:
                    result["error"] = '{:s} not found: {:s}'.format(
                        media_id, e)
                    self.response.write(json.dumps(result))
                else:
                    self.response.write(
                        '{:s} not found: {:s}'.format(media_id, e))
                self.response.set_status(404)
                blob_info.delete()

    def __init__(self, *args, **kwargs):
        super(MediaHandler, self).__init__(*args, **kwargs)
        self.upload_handler = self.UploadHandler()
        self.upload_handler.initialize(self.request, self.response)
        self.upload_handler.outer = self
        self.post = self.upload_handler.post

    def get(self, **kwargs):
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        context = self.create_context(**kwargs)
        if "mfid" in kwargs:
            return self.media_info(**kwargs)
        context['upload_url'] = blobstore.create_upload_url(
            self.uri_for('uploadBlob'))
        if self.is_https_request():
            context['upload_url'] = context['upload_url'].replace(
                'http://', 'https://')
        context['files'] = models.MediaFile.all()
        context['files'].sort(key=lambda i: i.name)
        context['keys'] = models.Key.all()
        context['keys'].sort(key=lambda i: i.hkid)
        context['streams'] = models.Stream.all()
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
        is_ajax = self.request.get("ajax", "0") == "1"
        if is_ajax:
            result = {}
            for item in ['csrf_tokens', 'files',
                         'streams', 'keys', 'upload_url']:
                result[item] = context[item]
            result = flatten(result)
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))
        else:
            template = TemplateFactory.get_template('media.html')
            self.response.write(template.render(context))

    def media_info(self, mfid, **kwargs):
        result = {"error": "unknown error"}
        try:
            try:
                mf = models.MediaFile.query(
                    models.Key.key == Key(urlsafe=mfid)).get()
            except datastore_errors.Error as err:
                logging.warning("MediaFile query error: %s", err)
                mf = None
            if not mf:
                self.response.write('{} not found'.format(mfid))
                self.response.set_status(404)
                return
            bi = blobstore.BlobInfo.get(mf.blob)
            info = {
                'size': bi.size,
                'creation': dateTimeFormat(bi.creation, "%H:%M:%S %d/%m/%Y"),
                'md5': bi.md5_hash,
            }
            result = {
                "representation": mf.rep,
                "name": mf.name,
                "key": mf.key.urlsafe(),
                "blob": info,
            }
            if self.request.params.get('index'):
                self.check_csrf('files')
                blob_reader = BufferedReader(
                    blobstore.BlobReader(mf.blob))
                atom = mp4.Wrapper(atom_type='wrap', position=0, size=mf.info.size, parent=None,
                                   children=mp4.Mp4Atom.create(blob_reader))
                rep = Representation.create(
                    filename=mf.name, atoms=atom.children)
                mf.representation = rep
                mf.put()
                result = {
                    "indexed": mfid,
                    "representation": mf.rep,
                }
        except (ValueError, CsrfFailureException) as err:
            result = {"error": str(err)}
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('files', csrf_key)
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))

    def delete(self, mfid, **kwargs):
        """
        handler for deleting a media blob
        """
        if not users.is_current_user_admin():
            self.response.write('User is not an administrator')
            self.response.set_status(401)
            return
        if not mfid:
            self.response.write('MediaFile ID missing')
            self.response.set_status(400)
            return
        result = {"error": "unknown error"}
        try:
            self.check_csrf('files')
            mf = models.MediaFile.query(
                models.Key.key == Key(urlsafe=mfid)).get()
            if not mf:
                self.response.write('{} not found'.format(mfid))
                self.response.set_status(404)
                return
            mf.delete()
            result = {"deleted": mfid}
        except (ValueError, CsrfFailureException) as err:
            result = {"error": str(err)}
        finally:
            csrf_key = self.generate_csrf_cookie()
            result["csrf"] = self.generate_csrf_token('files', csrf_key)
            self.response.content_type = 'application/json'
            self.response.write(json.dumps(result))
