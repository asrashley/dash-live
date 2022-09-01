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

from __future__ import print_function
import base64
import binascii
import cookielib
import io
import logging
import md5
import os
import unittest
import urllib
import uuid
import sys

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from segment import Representation
from mixins import TestCaseMixin
import routes
import options
import utils
import views
import mp4
import models
from drm.playready import PlayReady

from google.appengine.ext import ndb, testbed
from google.appengine.api import files, users
from google.appengine.api.files import file_service_stub
from google.appengine.api.blobstore import blobstore_stub, file_blob_storage
import jinja2
import webapp2
import webtest  # if this import fails, "pip install WebTest"

class GAETestBase(TestCaseMixin, unittest.TestCase):
    # duration of media in test/fixtures directory (in seconds)
    MEDIA_DURATION = 40

    def _init_blobstore_stub(self):
        blob_storage = file_blob_storage.FileBlobStorage(
            'tmp', testbed.DEFAULT_APP_ID)
        blob_stub = blobstore_stub.BlobstoreServiceStub(blob_storage)
        file_stub = file_service_stub.FileServiceStub(blob_storage)
        self.testbed._register_stub('blobstore', blob_stub)
        self.testbed._register_stub('file', file_stub)

    def setUp(self):
        # FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        # logging.basicConfig(format=FORMAT)
        # logging.getLogger('dash').setLevel(logging.INFO)

        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_blobstore_stub()
        self.testbed.init_files_stub()
        # self._init_blobstore_stub()
        self.testbed.init_taskqueue_stub()
        # self.testbed.init_channel_stub()
        self.testbed.init_memcache_stub()
        # Clear ndb's in-context cache between tests.
        # This prevents data from leaking between tests.
        ndb.get_context().clear_cache()

        # self.testbed.setup_env(USER_EMAIL='usermail@gmail.com',USER_ID='1', USER_IS_ADMIN='0')
        self.testbed.init_user_stub()
        self.wsgi = webapp2.WSGIApplication(routes.webapp_routes, debug=True)
        # app.router.add(Route(r'/discover/<service_type:[\w\-_\.]+>/',
        #  handler='views.SearchHandler', parent="search", title="Search by type"))
        self.app = webtest.TestApp(self.wsgi, cookiejar=cookielib.CookieJar(), extra_environ={
            'REMOTE_USER': 'test@example.com',
            'REMOTE_ADDR': '10.10.0.1',
            'HTTP_X_APPENGINE_COUNTRY': 'zz',
            'HTTP_USER_AGENT': 'Mozilla/5.0 (GAE Unit test) Gecko/20100101 WebTest/2.0',
        })
        self.wsgi.router.add(
            webapp2.Route(
                template=r'/_ah/upload/<blob_id:[\w\-_\.]+>',
                handler=views.MediaHandler,
                name="uploadBlob_ah"))
        routes.routes['uploadBlob_ah'] = routes.routes['uploadBlob']
        self.auth = None
        self.uid = "4d9cf5f4-4574-4381-9df3-1d6e7ca295ff"
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__), 'templates')
            ),
            extensions=['jinja2.ext.autoescape'],
            trim_blocks=False,
        )
        self.templates.filters['base64'] = utils.toBase64
        self.cgi_options = []
        drmloc = []
        for opt in options.options:
            if opt['name'] == 'drmloc':
                for loc in opt['options']:
                    if loc[1]:
                        drmloc.append(loc[1].split('=')[1])
        for opt in options.options:
            # the MSE option is exluded from the list as it does not change
            # anything in the manifest responses
            if opt['name'] in ['mse', 'drmloc']:
                continue
            opts = map(lambda o: o[1], opt['options'])
            if opt['name'] == 'drm':
                for d in opt['options']:
                    if d[1] == 'drm=none':
                        continue
                    for loc in drmloc:
                        if "pro" in loc and d[1] != 'drm=playready' and d[1] != 'drm=all':
                            continue
                        opts.append(d[1] + '-' + loc)
            self.cgi_options.append((opt["name"], opts))
        # print(self.cgi_options)

    def setup_media(self):
        bbb = models.Stream(
            title='Big Buck Bunny', prefix='bbb',
            marlin_la_url='ms3://localhost/marlin/bbb',
            playready_la_url=PlayReady.TEST_LA_URL
        )
        bbb.put()
        for idx, rid in enumerate(["bbb_v6", "bbb_v6_enc", "bbb_v7", "bbb_v7_enc",
                                   "bbb_a1", "bbb_a1_enc", "bbb_a2"]):
            filename = rid + ".mp4"
            src_filename = os.path.join(
                os.path.dirname(__file__), "fixtures", filename)
            src = io.open(src_filename, mode="rb", buffering=16384)
            atoms = mp4.Mp4Atom.create(src)
            src.seek(0)
            data = src.read()
            src.close()
            blob_filename = files.blobstore.create(mime_type='video/mp4')
            with files.open(blob_filename, 'ab') as dest:
                dest.write(data)
            files.finalize(blob_filename)
            blob_key = files.blobstore.get_blob_key(blob_filename)
            rep = Representation.create(filename, atoms)
            self.assertAlmostEqual(rep.mediaDuration,
                                   self.MEDIA_DURATION * rep.timescale,
                                   delta=(rep.timescale / 10),
                                   msg='Invalid duration for {}. Expected {} got {}'.format(
                                       filename, self.MEDIA_DURATION * rep.timescale,
                                       rep.mediaDuration))
            mf = models.MediaFile(
                name=filename,
                rep=rep.toJSON(),
                blob=blob_key)
            mf.put()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for mf in media_files:
            r = mf.representation
            if r is None:
                continue
            if r.encrypted:
                mspr = PlayReady(self.templates)
                for kid in r.kids:
                    key = binascii.b2a_hex(
                        mspr.generate_content_key(
                            kid.decode('hex')))
                    keypair = models.Key(hkid=kid, hkey=key, computed=True)
                    keypair.put()

    def tearDown(self):
        self.logoutCurrentUser()
        self.testbed.deactivate()
        if hasattr(TestCaseMixin, "_orig_assert_true"):
            TestCaseMixin._assert_true = TestCaseMixin._orig_assert_true
            del TestCaseMixin._orig_assert_true

    def from_uri(self, name, absolute=False, params=None, **kwargs):
        uri = routes.routes[name].formatTemplate.format(**kwargs)
        if params is not None:
            uri += '?' + urllib.urlencode(params)
        if absolute and not uri.startswith("http"):
            uri = 'http://testbed.example.com' + uri
        return uri

    def setCurrentUser(self, email=None, user_id=None, is_admin=False):
        if email is None:
            email = 'test@example.com'
        if user_id is None:
            user_id = 'test'
        is_admin = '1' if is_admin else '0'
        self.testbed.setup_env(
            user_email=email,
            user_id=user_id,
            user_is_admin=is_admin,
            overwrite=True
        )
        os.environ['USER_EMAIL'] = email
        os.environ['USER_ID'] = user_id
        os.environ['USER_IS_ADMIN'] = is_admin
        self.user = users.get_current_user()

    def logoutCurrentUser(self):
        self.setCurrentUser('', '', False)

    def upload_blobstore_file(self, from_url, upload_url, form, field,
                              filename, contents, content_type="application/octet-stream"):
        # session = datastore.Get(upload_url.split('/')[-1])
        # new_object = "/" + session["gs_bucket_name"] + "/" + str(uuid.uuid4())
        new_object = "/gs{:s}".format(uuid.uuid4())
        # self.storage_stub.store(new_object, type, contents)

        message = [
            "Content-Length: " + str(len(contents)),
            'Content-Disposition: form-data; name="{}"; filename="{}"'.format(
                field, filename),
            'Content-Type: {}'.format(content_type),
            "Content-MD5: " + base64.b64encode(md5.new(contents).hexdigest()),
            "X-AppEngine-Cloud-Storage-Object: /gs" +
            new_object.encode("ascii"),
            'X-AppEngine-Upload-Creation: 2019-07-17 16:19:55.531719',
            ''
        ]
        message = '\r\n'.join(message)
        cookies = []
        for k, v in self.app.cookies.iteritems():
            cookies.append('{}={}'.format(k, v))
        headers = {
            "Cookie": '; '.join(cookies),
            "Referer": from_url,
        }
        upload_files = [
            (field,
             filename,
             message,
             "message/external-body; blob-key=\"encoded_gs_file:blablabla\"; access-type=\"X-AppEngine-BlobKey\"")]
        # upload_files = [(field, filename, message, 'fooooo')]
        logging.debug(message)
        return self.app.post(upload_url, params=form,
                             headers=headers, upload_files=upload_files)

    def progress(self, pos, total):
        if pos == 0:
            sys.stdout.write('\n')
        sys.stdout.write(
            '\r {:05.2f}%'.format(
                100.0 *
                float(pos) /
                float(total)))
        if pos == total:
            sys.stdout.write('\n')
        sys.stdout.flush()
