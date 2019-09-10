
import base64
import binascii
import cookielib
import copy
import datetime
import hashlib
import hmac
import io
import json
import re
import logging
import md5
import os
import unittest
import uuid
import sys

#from google.appengine.api import memcache
from google.appengine.ext import ndb, testbed
from google.appengine.api import datastore, files, users
from google.appengine.api.files import file_service_stub
from google.appengine.api.blobstore import blobstore_stub, file_blob_storage
import jinja2
import webapp2
import webtest # if this import fails, "pip install WebTest"

import drm
import models
import mp4
import views
import utils
import manifests
import options
import routes
from media.segment import Representation

# convert App Engine's template syntax in to the Python string format syntax
for name,r in routes.routes.iteritems():
    r.template = re.sub(r':[^>]*>','}',r.template.replace('<','{'))

class GAETestCase(unittest.TestCase):
    def _init_blobstore_stub(self):
        blob_storage = file_blob_storage.FileBlobStorage('tmp', testbed.DEFAULT_APP_ID)
        blob_stub = blobstore_stub.BlobstoreServiceStub(blob_storage)
        file_stub = file_service_stub.FileServiceStub(blob_storage)
        self.testbed._register_stub('blobstore',blob_stub)
        self.testbed._register_stub('file',file_stub)

    def setUp(self):
        FORMAT = "%(filename)s:%(lineno)d %(message)s"
        #logging.basicConfig(format=FORMAT)
        #logging.getLogger().setLevel(logging.DEBUG)

        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_blobstore_stub()
        self.testbed.init_files_stub()
        #self._init_blobstore_stub()
        self.testbed.init_taskqueue_stub()
        self.testbed.init_channel_stub()
        self.testbed.init_memcache_stub()
        # Clear ndb's in-context cache between tests.
        # This prevents data from leaking between tests.
        ndb.get_context().clear_cache()
                                        
        #self.testbed.setup_env(USER_EMAIL='usermail@gmail.com',USER_ID='1', USER_IS_ADMIN='0')
        self.testbed.init_user_stub()
        self.wsgi = webapp2.WSGIApplication(routes.webapp_routes, debug=True)
        #app.router.add(Route(r'/discover/<service_type:[\w\-_\.]+>/', handler='views.SearchHandler', parent="search", title="Search by type"))
        self.app = webtest.TestApp(self.wsgi, cookiejar=cookielib.CookieJar(), extra_environ={
            'REMOTE_USER':'test@example.com',
            'REMOTE_ADDR':'10.10.0.1', 
            'HTTP_X_APPENGINE_COUNTRY':'zz',
            'HTTP_USER_AGENT':'Mozilla/5.0 (GAE Unit test) Gecko/20100101 WebTest/2.0',
        })
        self.auth = None
        self.uid="4d9cf5f4-4574-4381-9df3-1d6e7ca295ff"
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__),'templates')
            ),
            extensions=['jinja2.ext.autoescape'],
            trim_blocks=False,
        )
        self.templates.filters['base64'] = utils.toBase64
        self.xmlNamespaces = {
            'dash': 'urn:mpeg:dash:schema:mpd:2011',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'cenc': 'urn:mpeg:cenc:2013',
        }
        self.cgi_options = []
        drmloc = []
        for opt in options.options:
            if opt['name']=='drmloc':
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
                    if d[1]=='drm=none':
                        continue
                    for loc in drmloc:
                        if "pro" in loc and d[1]!='drm=playready' and d[1]!='drm=all':
                            continue
                        opts.append(d[1]+'-'+loc)
            self.cgi_options.append((opt["name"],opts))
        #print(self.cgi_options)

    def setup_media(self):
        for idx, rid in enumerate(["bbb_v6","bbb_v6_enc","bbb_v7","bbb_v7_enc",
                                   "bbb_a1", "bbb_a1_enc"]):
            filename = rid + ".mp4"
            src_filename = os.path.join(os.path.dirname(__file__), "fixtures", filename)
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
            mf = models.MediaFile(name=filename, rep=rep.toJSON(), blob=blob_key)
            mf.put()
        media_files = models.MediaFile.all()
        self.assertGreater(len(media_files), 0)
        for mf in media_files:
            r = mf["representation"]
            if r is None:
                continue
            if r.encrypted:
                mspr = drm.PlayReady(self.templates)
                for kid in r.kids:
                    key = binascii.b2a_hex(mspr.generate_content_key(kid.decode('hex')))
                    keypair = models.Key(hkid=kid, hkey=key, computed=True)
                    keypair.put()
        
    def tearDown(self):
        self.logoutCurrentUser()
        self.testbed.deactivate()
        
    def from_uri(self, name, **kwargs):
        try:
            absolute = kwargs["absolute"]
            del kwargs["absolute"]
        except KeyError:
            absolute = False
        uri = routes.routes[name].template.format(**kwargs)
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
            user_email = email,
            user_id = user_id,
            user_is_admin = is_admin,
            overwrite = True
        )
        os.environ['USER_EMAIL'] = email
        os.environ['USER_ID'] = user_id
        os.environ['USER_IS_ADMIN'] = is_admin
        self.user = users.get_current_user()

    def logoutCurrentUser(self):
        self.setCurrentUser('', '', False)
        
    def upload_blobstore_file(self, from_url, upload_url, form, field, filename, contents, content_type = "application/octet-stream"):
        session = datastore.Get(upload_url.split('/')[-1])
        #new_object = "/" + session["gs_bucket_name"] + "/" + str(uuid.uuid4())
        new_object = "/gs{:s}".format(uuid.uuid4())
        #self.storage_stub.store(new_object, type, contents)

        message = [
            "Content-Length: " + str(len(contents)),
            'Content-Disposition: form-data; name="{}"; filename="{}"'.format(field, filename),
            'Content-Type: {}'.format(content_type),
            "Content-MD5: " + base64.b64encode(md5.new(contents).hexdigest()),
            "X-AppEngine-Cloud-Storage-Object: /gs" + new_object.encode("ascii"),
            'X-AppEngine-Upload-Creation: 2019-07-17 16:19:55.531719',
            ''
        ]
        message = '\r\n'.join(message)
        cookies=[]
        for k,v in self.app.cookies.iteritems():
            cookies.append('{}={}'.format(k,v))
        headers = {
            "Cookie": '; '.join(cookies),
            "Referer": from_url,
        }
        upload_files = [(field, filename, message, "message/external-body; blob-key=\"encoded_gs_file:blablabla\"; access-type=\"X-AppEngine-BlobKey\"")]
        #upload_files = [(field, filename, message, 'fooooo')]
        logging.debug(message)
        return self.app.post(upload_url, params=form, headers=headers, upload_files=upload_files)


class TestHandlers(GAETestCase):
    def test_index_page(self):
        self.setup_media()
        page = views.MainPage()
        self.assertIsNotNone(getattr(page,'get',None))
        url = self.from_uri('home', absolute=True)
        self.logoutCurrentUser()
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        response.mustcontain('Log In', no='href="{}"'.format(self.from_uri('media-index')))
        for filename, manifest in manifests.manifest.iteritems():
            mpd_url = self.from_uri('dash-mpd-v2', manifest=filename, prefix='placeholder')
            mpd_url = mpd_url.replace('placeholder', '{directory}')
            response.mustcontain(mpd_url)
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        response.mustcontain('href="{}"'.format(self.from_uri('media-index')), no="Log In")
        response.mustcontain('Log Out')

        #self.setCurrentUser(is_admin=False)
        #response = self.app.get(url)
        #response.mustcontain('<a href="',mpd_url, no=routes.routes['upload'].title)
        
    def test_media_page(self):
        self.setup_media()
        page = views.MediaHandler()
        self.assertIsNotNone(getattr(page,'get',None))
        self.assertIsNotNone(getattr(page,'post',None))
        url = self.from_uri('media-index', absolute=True)

        # user must be logged in to use media page
        self.logoutCurrentUser()
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use media page
        self.setCurrentUser(is_admin=False)
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use media page
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)

    def validate_manifest(self, mpd_url, params, xml):
        mpd_type = xml.get("type", "static")
        period = xml.find('dash:Period', self.xmlNamespaces)
        self.assertIsNotNone(period, "Manifest does not have a Period element: "+mpd_url)
        mode = params.get("mode")
        if mode is None:
            if "vod_" in mpd_url:
                mode="vod"
            else:
                mode="live"
        else:
            mode = mode.split('=')[1]
        if mode=="live":
            self.assertEqual(mpd_type, "dynamic",
                             "MPD@type must be dynamic for live manifest: "+mpd_url)
            self.assertIsNotNone(xml.get("availabilityStartTime"),
                                 "MPD@availabilityStartTime must be present for live manifest: "+mpd_url)
            
            self.assertIsNone(xml.get("mediaPresentationDuration"),
                              "MPD@mediaPresentationDuration must not be present for live manifest: "+mpd_url)
        else:
            self.assertEqual(mpd_type, "static",
                             "MPD@type must be static for VOD manifest: "+mpd_url)
            duration = xml.get('mediaPresentationDuration')
            if duration is not None:
                self.assertTrue(duration.startswith('PT'),
                                'Invalid MPD@mediaPresentationDuration "{}": {}'.format(duration, mpd_url))
            else:
                self.assertIsNotNone(period.get("duration"),
                                     'If MPD@mediaPresentationDuration is not present, Period@duration must be present: '+mpd_url)
                duration = period.get("duration")
                self.assertTrue(duration.startswith('PT'),
                                'Invalid MPD@mediaPresentationDuration "{}": {}'.format(duration, mpd_url))
            self.assertIsNone(xml.get("minimumUpdatePeriod"),
                              "MPD@minimumUpdatePeriod must not be present for VOD manifest: "+mpd_url)
            self.assertIsNone(xml.get("availabilityStartTime"),
                              "MPD@availabilityStartTime must not be present for VOD manifest: "+mpd_url)
        
    def check_manifest(self, filename, indexes, tested):
        params = {}
        for idx, option in enumerate(self.cgi_options):
            name, values = option
            value = values[indexes[idx]]
            if value:
                params[name] = value
        # remove pointless combinations of options
        if params.get("mode", "mode=live") == "mode=live" and "vod_" in filename:
            return
        if params.get("mode", "mode=live") != "mode=live":
            if params.has_key("mup"):
                del params["mup"]
            if params.has_key("time"):
                del params["time"]
        cgi = params.values()
        url = self.from_uri('dash-mpd', manifest=filename)
        mpd_url = '{}?{}'.format(url, '&'.join(cgi))
        if mpd_url in tested:
            return
        #print(mpd_url)
        tested.add(mpd_url)
        response = self.app.get(mpd_url)
        self.assertEqual(response.status_int, 200)
        mpd = '{{{}}}mpd'.format(self.xmlNamespaces['dash'])
        xml = response.xml
        self.assertEqual(mpd, xml.tag.lower())
        self.validate_manifest(mpd_url, params, xml)

    def test_get_manifest(self):
        """Exhaustive test of every manifest with every combination of options.
        This test is _very_ slow, expect it to take several minutes!"""
        self.setup_media()
        self.logoutCurrentUser()
        pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreater(len(media_files), 0)
        # do a first pass check of every manifest with no CGI options
        for filename, manifest in manifests.manifest.iteritems():
            url = self.from_uri('dash-mpd', manifest=filename)
            response = self.app.get(url)
            self.assertEqual(response.status_int, 200)
            mpd = '{{{}}}mpd'.format(self.xmlNamespaces['dash'])
            self.assertEqual(mpd, response.xml.tag.lower())
            self.validate_manifest(url, {}, response.xml)

        # do the exhaustive check of every option with every manifest
        total_tests = len(manifests.manifest)
        count = 0
        for param in self.cgi_options:
            total_tests = total_tests * len(param[1])
        sys.stdout.write('\n')
        for filename, manifest in manifests.manifest.iteritems():
            tested = set([url])
            indexes = [0] * len(self.cgi_options)
            done = False
            while not done:
                #sys.stdout.write('{:s}\r'.format(indexes))
                sys.stdout.write('\r {:05.2f}%'.format(100.0 * float(count) / float(total_tests)))
                count += 1
                self.check_manifest(filename, indexes, tested)
                idx = 0
                while idx < len(self.cgi_options):
                    indexes[idx] += 1
                    if indexes[idx] < len(self.cgi_options[idx][1]):
                        break
                    indexes[idx] = 0
                    idx += 1
                if idx==len(self.cgi_options):
                    done=True
        sys.stdout.write('\n')

    def test_add_full_key_pair(self):
        self.assertEqual(len(models.Key.all()), 0)
        
        url = self.from_uri('key', absolute=True)

        request = {
            'kid': '1AB45440532C439994DC5C5AD9584BAC',
            'key': 'ccc0f2b3b279926496a7f5d25da692f6',
        }
        url = '{}?kid={}&key={}'.format(url, request['kid'], request['key'])

        # user must be logged in to use keys API
        self.logoutCurrentUser()
        response = self.app.put(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=False)
        response = self.app.put(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=True)
        response = self.app.put(url)
        self.assertEqual(response.status_int, 200)

        expected_result = {
            'kid': request['kid'].lower(),
            'key': request['key'].lower(),
            'computed': False
        }
        self.assertEqual(expected_result, response.json)

        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, expected_result['kid'])
        self.assertEqual(keys[0].hkey, expected_result['key'])
        self.assertEqual(keys[0].computed, False)

        url = self.from_uri('media-index', absolute=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(expected_result['kid'], expected_result['key'])        

    def test_add_computed_keys(self):
        self.assertEqual(len(models.Key.all()), 0)
        kid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower()
        url = '{}?kid={}'.format(self.from_uri('key', absolute=True), kid)
        self.setCurrentUser(is_admin=True)
        response = self.app.put(url)
        self.assertEqual(response.status_int, 200)
        expected_result = {
            'kid': kid,
            'key': base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
            'computed': True
        }
        self.assertEqual(expected_result, response.json)
        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, expected_result['kid'])
        self.assertEqual(keys[0].hkey, expected_result['key'])
        self.assertEqual(keys[0].computed, True)
        
    def test_delete_key(self):
        self.assertEqual(len(models.Key.all()), 0)

        kid='1AB45440532C439994DC5C5AD9584BAC'.lower()
        keypair = models.Key(hkid=kid,
                             hkey='ccc0f2b3b279926496a7f5d25da692f6',
                             computed=False)
        keypair.put()
        
        keypair = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower(),
                             hkey=base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                             computed=True)
        keypair.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('del-key', kid=kid, absolute=True)
        
        # user must be logged in to use keys API
        self.logoutCurrentUser()
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int,401)
        self.assertEqual(len(models.Key.all()), 2)
        
        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=False)
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int,401)
        self.assertEqual(len(models.Key.all()), 2)
        
        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=True)
        response = self.app.delete(url)
        self.assertEqual(response.status_int, 200)
        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, keypair.hkid)
        self.assertEqual(keys[0].hkey, keypair.hkey)
        self.assertEqual(keys[0].computed, keypair.computed)

        # try to delete a key that does not exist
        response = self.app.delete(url, status=404)

        url = self.from_uri('del-key', kid='invalid', absolute=True)
        try:
            binascii.unhexlify('invalid')
        except (TypeError) as err:
            expected_result = {
                'error': str(err)
            }
        response = self.app.delete(url)
        self.assertEqual(expected_result, response.json)
        
    def test_clearkey(self):
        self.assertEqual(len(models.Key.all()), 0)

        keypair1 = models.Key(hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
                             hkey='ccc0f2b3b279926496a7f5d25da692f6',
                             computed=False)
        keypair1.put()

        keypair2 = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower(),
                             hkey=base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                             computed=True)
        keypair2.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('clearkey', absolute=True)
        request = {
            "kids": [
                self.base64url_encode(keypair1.hkid),
                self.base64url_encode(keypair2.hkid),
            ],
            "type":"temporary",
        }
        
        # user does not need to be logged in to use clearkey
        self.logoutCurrentUser()
        response = self.app.post_json(url, request)
        expected_result = {
            "keys": [
                {
                    "kty": "oct",
                    "kid": self.base64url_encode(keypair1.hkid),
                    "k": self.base64url_encode(keypair1.hkey),
                },
                {
                    "kty": "oct",
                    "kid": self.base64url_encode(keypair2.hkid),
                    "k": self.base64url_encode(keypair2.hkey),
                },
            ],
            "type":"temporary",
        }
        # as the order of keys is not defined, sort both expected
        # and actual before the compare
        expected_result["keys"].sort(key=lambda k: k["kid"])
        actual_result = copy.deepcopy(response.json)
        actual_result["keys"].sort(key=lambda k: k["kid"])
        self.maxDiff = None
        self.assertEqual(expected_result, actual_result)

        # check with unknown KID
        request = {
            "kids": [
                self.base64url_encode(keypair1.hkid.replace('0','9')),
            ],
            "type":"temporary",
        }
        expected_result = {
            "keys": [],
            "type":"temporary",
        }
        response = self.app.post_json(url, request)
        self.assertEqual(expected_result, response.json)

    def test_clearkey_bad_request(self):
        self.assertEqual(len(models.Key.all()), 0)

        keypair1 = models.Key(hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
                             hkey='ccc0f2b3b279926496a7f5d25da692f6',
                             computed=False)
        keypair1.put()

        keypair2 = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower(),
                             hkey=base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                             computed=True)
        keypair2.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('clearkey', absolute=True)

        # user does not need to be logged in to use clearkey
        self.logoutCurrentUser()

        request = {
            "type":"temporary",
        }

        # check request without the kids parameter
        response = self.app.post_json(url, request)
        expected_result = {
            'error': "'kids'",
        }
        self.assertEqual(expected_result, response.json)

        # check request with invalid base64url encoding
        request = {
            "kids": [
                '*invalid base64*',
            ],
            "type":"temporary",
        }
        
        response = self.app.post_json(url, request)
        try:
            base64.b64decode('*invalid base64*')
        except (TypeError) as err:
            expected_result = {
                'error': str(err)
            }
        self.assertEqual(expected_result, response.json)

    def base64url_encode(self, value):
        #See https://tools.ietf.org/html/rfc7515#page-54
        if len(value) != 16:
            value = value.decode('hex')
        s = base64.b64encode(value) # Regular base64 encoder
        s = s.split('=')[0]         # Remove any trailing '='s
        s = s.replace('+', '-')     # 62nd char of encoding
        s = s.replace('/', '_')     # 63rd char of encoding
        return s


class BlobstoreTestHandlers(GAETestCase):
    def setUp(self):
        super(BlobstoreTestHandlers,self).setUp()
        self.wsgi.router.add(webapp2.Route(template=r'/_ah/upload/<blob_id:[\w\-_\.]+>', handler=views.MediaHandler, name="uploadBlob_ah"))
        routes.routes['uploadBlob_ah'] = routes.routes['uploadBlob']
        
    def test_upload_media_file(self):
        url = self.from_uri('media-index', absolute=True)
        blobURL = self.from_uri('uploadBlob', absolute=True)
        self.assertIsNotNone(blobURL)
        
        # not logged in, should return authentication error
        self.logoutCurrentUser()
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)

        # logged in as non-admin, should return authentication error
        self.setCurrentUser(is_admin=False)
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)

        # logged in as admin should succeed
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)

        form = response.forms['upload-form']
        form['file'] = webtest.Upload('bbb_v1.mp4', b'data', 'video/mp4')
        #form['media'] = 'V1'
        self.assertEqual(form.method, 'POST')
        self.logoutCurrentUser()
        # a POST from a non-logged in user should fail
        response = form.submit('submit', status=401)
        
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        upload_form = response.forms['upload-form']
        form = {
            "csrf_token": upload_form["csrf_token"].value,
            "submit": "submit",
        }
        response = self.upload_blobstore_file(url, response.forms['upload-form'].action, form,
                                              'file', 'bbb_v1.mp4', b'data', 'video/mp4')
        response.mustcontain('<h2>Upload complete</h2>')
        
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        response.mustcontain('bbb_v1.mp4')
        
if __name__ == '__main__':
    unittest.main()        
