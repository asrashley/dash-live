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

import base64
import binascii
import copy
import os
import sys
import unittest
import urllib

import webtest

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path

from gae_base import GAETestBase
from server import models

class TestRestApi(GAETestBase):
    def test_add_stream(self):
        self.assertEqual(len(models.Stream.all()), 0)
        request = {
            'title': 'Big Buck Bunny',
            'prefix': 'bbb',
            'marlin_la_url': 'ms3://unit.test/bbb.sas',
            'playready_la_url': ''
        }
        params = []
        for k, v in request.iteritems():
            params.append('{0}={1}'.format(k, urllib.quote(v)))
        url = self.from_uri('stream', absolute=True)
        url = '{0}?{1}'.format(url, '&'.join(params))

        # user must be logged in to use stream API
        self.logoutCurrentUser()
        response = self.app.put(url, status=401)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=False)
        response = self.app.put(url, status=401)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=True)

        # request should fail due to lack of CSRF token
        response = self.app.put(url)
        self.assertTrue("error" in response.json)
        self.assertIn("CsrfFailureException", response.json["error"])

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        streams_table = media.html.find(id="streams")
        request['csrf_token'] = streams_table.get('data-csrf')
        url += '&csrf_token=' + request['csrf_token']
        response = self.app.put(url)
        expected_result = copy.deepcopy(request)
        expected_result['playready_la_url'] = None
        del expected_result['csrf_token']
        expected_result['csrf'] = response.json["csrf"]
        expected_result['id'] = response.json["id"]
        self.assertEqual(expected_result, response.json)

        streams = models.Stream.all()
        self.assertEqual(len(streams), 1)
        for k, v in request.iteritems():
            if k == 'csrf_token':
                continue
            self.assertEqual(getattr(streams[0], k), expected_result[k],
                             'Field {0}: expected "{1}" got "{2}"'.format(k, getattr(streams[0], k),
                                                                          expected_result[k]))

        url = self.from_uri('media-index', absolute=True)
        response = self.app.get(url)
        response.mustcontain(
            expected_result['title'],
            expected_result['prefix'])

    def test_delete_stream(self):
        self.assertEqual(len(models.Stream.all()), 0)

        bbb = models.Stream(title='Big Buck Bunny', prefix='bbb')
        bbb.put()
        tears = models.Stream(title='Tears of Steel', prefix='tears')
        tears.put()
        self.assertEqual(len(models.Stream.all()), 2)

        url = self.from_uri('del-stream', id=bbb.key.urlsafe(), absolute=True)

        # user must be logged in to use stream API
        self.logoutCurrentUser()
        response = self.app.delete(url, status=401)
        self.assertEqual(len(models.Stream.all()), 2)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=False)
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int, 401)
        self.assertEqual(len(models.Stream.all()), 2)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=True)

        # request without CSRF token should fail
        response = self.app.delete(url)
        self.assertTrue("error" in response.json)
        self.assertIn("CsrfFailureException", response.json["error"])
        self.assertEqual(len(models.Stream.all()), 2)

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        streams_table = media.html.find(id="streams")
        csrf_url = url + '?csrf_token=' + streams_table.get('data-csrf')

        response = self.app.delete(csrf_url)
        streams = models.Stream.all()
        self.assertEqual(len(streams), 1)
        next_csrf_token = response.json["csrf"]

        # try to re-use a CSRF token
        reuse_url = self.from_uri(
            'del-stream',
            id=tears.key.urlsafe(),
            absolute=True)
        reuse_url += '?csrf_token=' + streams_table.get('data-csrf')
        response = self.app.delete(reuse_url)
        self.assertTrue("error" in response.json)
        self.assertIn("CsrfFailureException", response.json["error"])

        # try to delete a stream that does not exist
        response = self.app.delete(
            url + '?csrf_token=' + next_csrf_token, status=404)

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
        self.assertEqual(response.status_int, 401)

        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=False)
        response = self.app.put(url, status=401)
        self.assertEqual(response.status_int, 401)

        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=True)

        # request should fail due to lack of CSRF token
        response = self.app.put(url)
        self.assertTrue("error" in response.json)
        self.assertIn("CsrfFailureException", response.json["error"])

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        keys_table = media.html.find(id="keys")
        url += '&csrf_token=' + keys_table.get('data-csrf')
        response = self.app.put(url)
        expected_result = {
            'kid': request['kid'].lower(),
            'key': request['key'].lower(),
            'computed': False,
            'csrf': response.json["csrf"],
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
        kid = '01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower()
        url = '{}?kid={}'.format(self.from_uri('key', absolute=True), kid)
        self.setCurrentUser(is_admin=True)
        response = self.app.put(url)
        # request without CSRF token should fail
        self.assertTrue("error" in response.json)
        self.assertIn("CsrfFailureException", response.json["error"])

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        keys_table = media.html.find(id="keys")
        url += '&csrf_token=' + keys_table.get('data-csrf')
        response = self.app.put(url)
        expected_result = {
            'kid': kid,
            'key': base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
            'computed': True,
            'csrf': response.json["csrf"],
        }
        self.assertEqual(expected_result, response.json)
        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, expected_result['kid'])
        self.assertEqual(keys[0].hkey, expected_result['key'])
        self.assertEqual(keys[0].computed, True)

    def test_delete_key(self):
        self.assertEqual(len(models.Key.all()), 0)

        kid = '1AB45440532C439994DC5C5AD9584BAC'.lower()
        keypair = models.Key(hkid=kid,
                             hkey='ccc0f2b3b279926496a7f5d25da692f6',
                             computed=False)
        keypair.put()

        keypair = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower(),
                             hkey=base64.b64decode(
                                 'GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                             computed=True)
        keypair.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('del-key', kid=kid, absolute=True)

        # user must be logged in to use keys API
        self.logoutCurrentUser()
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int, 401)
        self.assertEqual(len(models.Key.all()), 2)

        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=False)
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int, 401)
        self.assertEqual(len(models.Key.all()), 2)

        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=True)

        # request without CSRF token should fail
        response = self.app.delete(url)
        self.assertTrue("error" in response.json)
        self.assertIn("CsrfFailureException", response.json["error"])

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        keys_table = media.html.find(id="keys")
        csrf_url = url + '?csrf_token=' + keys_table.get('data-csrf')

        response = self.app.delete(csrf_url)
        self.assertEqual(response.status_int, 200)
        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, keypair.hkid)
        self.assertEqual(keys[0].hkey, keypair.hkey)
        self.assertEqual(keys[0].computed, keypair.computed)
        next_csrf_token = response.json["csrf"]

        # try to re-use a CSRF token
        response = self.app.delete(csrf_url)
        self.assertTrue("error" in response.json)
        self.assertIn("CsrfFailureException", response.json["error"])

        # try to delete a key that does not exist
        response = self.app.delete(url + '?csrf_token=' + next_csrf_token)
        self.assertTrue("error" in response.json)
        self.assertIn("not found", response.json["error"])
        next_csrf_token = response.json["csrf"]

        url = self.from_uri('del-key', kid='invalid', absolute=True)
        try:
            binascii.unhexlify('invalid')
        except (TypeError) as err:
            expected_result = {
                'error': '{}: {:s}'.format(err.__class__.__name__, err)
            }
        response = self.app.delete(url + '?csrf_token=' + next_csrf_token)
        expected_result["csrf"] = response.json["csrf"]
        self.assertEqual(expected_result, response.json)

    def test_clearkey(self):
        self.assertEqual(len(models.Key.all()), 0)

        keypair1 = models.Key(hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
                              hkey='ccc0f2b3b279926496a7f5d25da692f6',
                              computed=False)
        keypair1.put()

        keypair2 = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower(),
                              hkey=base64.b64decode(
                                  'GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                              computed=True)
        keypair2.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('clearkey', absolute=True)
        request = {
            "kids": [
                self.base64url_encode(keypair1.hkid),
                self.base64url_encode(keypair2.hkid),
            ],
            "type": "temporary",
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
            "type": "temporary",
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
                self.base64url_encode(keypair1.hkid.replace('0', '9')),
            ],
            "type": "temporary",
        }
        expected_result = {
            "keys": [],
            "type": "temporary",
        }
        response = self.app.post_json(url, request)
        self.assertEqual(expected_result, response.json)

    def test_clearkey_bad_request(self):
        self.assertEqual(len(models.Key.all()), 0)

        keypair1 = models.Key(hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
                              hkey='ccc0f2b3b279926496a7f5d25da692f6',
                              computed=False)
        keypair1.put()

        keypair2 = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower(),
                              hkey=base64.b64decode(
                                  'GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                              computed=True)
        keypair2.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('clearkey', absolute=True)

        # user does not need to be logged in to use clearkey
        self.logoutCurrentUser()

        request = {
            "type": "temporary",
        }

        # check request without the kids parameter
        response = self.app.post_json(url, request)
        expected_result = {
            'error': "KeyError: 'kids'",
        }
        self.assertEqual(expected_result, response.json)

        # check request with invalid base64url encoding
        request = {
            "kids": [
                '*invalid base64*',
            ],
            "type": "temporary",
        }

        response = self.app.post_json(url, request)
        try:
            base64.b64decode('*invalid base64*')
        except (TypeError) as err:
            expected_result = {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        self.assertEqual(expected_result, response.json)

    def base64url_encode(self, value):
        # See https://tools.ietf.org/html/rfc7515#page-54
        if len(value) != 16:
            value = value.decode('hex')
        s = base64.b64encode(value)  # Regular base64 encoder
        s = s.split('=')[0]         # Remove any trailing '='s
        s = s.replace('+', '-')     # 62nd char of encoding
        s = s.replace('/', '_')     # 63rd char of encoding
        return s

    def test_upload_media_file(self):
        self.upload_media_file(0)

    def test_upload_media_file_using_ajax(self):
        self.upload_media_file(1)

    def upload_media_file(self, ajax):
        url = self.from_uri('media-index', absolute=True)
        blobURL = self.from_uri('uploadBlob', absolute=True)
        self.assertIsNotNone(blobURL)

        # not logged in, should return authentication error
        self.logoutCurrentUser()
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int, 401)

        # logged in as non-admin, should return authentication error
        self.setCurrentUser(is_admin=False)
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int, 401)

        # logged in as admin should succeed
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)

        form = response.forms['upload-form']
        form['file'] = webtest.Upload('bbb_v1.mp4', b'data', 'video/mp4')
        self.assertEqual(form.method, 'POST')
        self.logoutCurrentUser()
        # a POST from a non-logged in user should fail
        response = form.submit('submit', status=401)

        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        upload_form = response.forms['upload-form']
        form = {
            "csrf_token": upload_form["csrf_token"].value,
            "ajax": ajax,
            "submit": "submit",
        }
        response = self.upload_blobstore_file(url, response.forms['upload-form'].action,
                                              form, 'file', 'bbb_v1.mp4', b'data',
                                              'video/mp4')
        if ajax:
            expected_result = {
                'csrf': 0,
                'name': 'bbb_v1.mp4',
            }
            for item in ['csrf', 'upload_url', 'file_html', 'key', 'blob',
                         'representation']:
                self.assertTrue(item in response.json)
                expected_result[item] = response.json[item]
            self.assertNotEqual(response.json['csrf'], form['csrf_token'])
            self.assertEqual(response.json, expected_result)
        else:
            response.mustcontain('<h2>Upload complete</h2>')

        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain('bbb_v1.mp4')


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestRestApi)

if __name__ == '__main__':
    unittest.main()
