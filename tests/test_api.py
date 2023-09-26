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
import io
import logging
import os
import unittest

from bs4 import BeautifulSoup
import flask

from dashlive.server import models
from dashlive.utils.date_time import to_iso_datetime

from .mixins.flask_base import FlaskTestBase

class TestRestApi(FlaskTestBase):
    def test_add_stream(self):
        self.assertEqual(models.Stream.count(), 0)
        request = {
            'title': 'Big Buck Bunny',
            'directory': self.FIXTURES_PATH.name,
            'marlin_la_url': 'ms3://unit.test/bbb.sas',
            'playready_la_url': '',
            'ajax': '1',
        }
        url = flask.url_for('add-stream')

        # user must be logged in to use stream API
        self.logout_user()
        response = self.client.put(url, json=request)
        self.assertEqual(response.status_code, 401)

        # user must be logged in as admin to use stream API
        self.login_user(is_admin=False)
        response = self.client.put(url, json=request)
        self.assertEqual(response.status_code, 401)

        # user must be logged in as admin to use stream API
        self.login_user(is_admin=True)

        # request should fail due to lack of CSRF token
        response = self.client.put(url, json=request)
        self.assert401(response)
        self.assertTrue("error" in response.json)
        self.assertIn("csrf_token not present", response.json["error"])

        media_url = flask.url_for('list-streams', ajax=1)
        media = self.client.get(media_url)
        request['csrf_token'] = media.json['csrf_tokens']['streams']

        response = self.client.put(url, json=request)
        self.assert200(response)
        expected_result = copy.deepcopy(request)
        expected_result['playready_la_url'] = None
        del expected_result['csrf_token']
        del expected_result['ajax']
        expected_result['csrf_token'] = response.json["csrf_token"]
        expected_result['id'] = response.json["id"]
        self.assertObjectEqual(expected_result, response.json)

        streams = list(models.Stream.all())
        self.assertEqual(len(streams), 1)
        for k, v in request.items():
            if k in {'ajax', 'csrf_token'}:
                continue
            self.assertEqual(
                getattr(streams[0], k), expected_result[k],
                'Field {}: expected "{}" got "{}"'.format(
                    k, getattr(streams[0], k), expected_result[k]))

        url = flask.url_for('list-streams')
        response = self.client.get(url)
        self.assertIn(expected_result['title'], response.text)
        self.assertIn(expected_result['directory'], response.text)

    def test_get_media_info(self):
        """
        Test getting info on one media file
        """
        self.setup_media()
        media_file = models.MediaFile.search(max_items=1)[0]
        url = flask.url_for(
            'media-info', spk=media_file.stream_pk, mfid=media_file.pk, ajax=1)

        self.logout_user()
        response = self.client.get(url)
        self.assert200(response)

        self.login_user(is_admin=False)
        response = self.client.get(url)
        self.assert200(response)

        self.login_user(is_admin=True)

        response = self.client.get(url)
        self.assert200(response)
        actual = response.json
        info = {
            'size': media_file.blob.size,
            'created': to_iso_datetime(media_file.blob.created),
            'sha1_hash': media_file.blob.sha1_hash,
        }
        expected = {
            "representation": media_file.rep,
            "name": media_file.name,
            "key": media_file.pk,
            "blob": info,
        }
        self.assertObjectEqual(expected, actual)
        mfid = 9794759347593487
        url = flask.url_for(
            'media-info', spk=media_file.stream_pk, mfid=mfid, ajax=1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        url = flask.url_for('media-info', spk=media_file.stream_pk,
                            mfid=media_file.pk)
        response = self.client.get(url)
        self.assert200(response)

    def test_get_segment_info(self) -> None:
        """
        Test getting info the segments from an MP4 file
        """
        self.setup_media()
        media_file = models.MediaFile.search(max_items=1)[0]
        self.logout_user()
        for segnum in range(0, 2):
            url = flask.url_for(
                'view-media-segment', spk=media_file.stream_pk, mfid=media_file.pk,
                segnum=segnum, ajax=1)
            response = self.client.get(url)
            self.assert200(response)
            self.assertIn('segmentNumber', response.json)
            self.assertIn('atoms', response.json)
            self.assertIn('media', response.json)
            self.assertIn('stream', response.json)
            expected = {
                'segmentNumber': segnum,
                'atoms': response.json['atoms'],
                'media': media_file.to_dict(
                    with_collections=False, exclude={'stream', 'blob', 'representation', 'rep'}),
                'stream': media_file.stream.to_dict(
                    with_collections=False, exclude={'media_files'}),
            }
            self.assertDictEqual(expected, response.json)
            url = flask.url_for(
                'view-media-segment', spk=media_file.stream_pk, mfid=media_file.pk,
                segnum=segnum)
            response = self.client.get(url)
            self.assert200(response)

    def test_index_stream(self):
        """
        Test indexing of one representation file
        """
        self.setup_media()
        media_file = models.MediaFile.search(max_items=1)[0]

        url = flask.url_for('index-media-file', mfid=media_file.pk, index=1)

        # user must be logged in to use stream API
        self.logout_user()
        response = self.client.get(url)
        self.assert401(response)

        # user must be logged in as admin to use stream API
        self.login_user(is_admin=False)
        response = self.client.get(url)
        self.assert401(response)

        # user must be logged in as admin to use stream API
        self.login_user(is_admin=True)

        # request without CSRF token should fail
        response = self.client.get(url)
        self.assert401(response)

        media_url = flask.url_for('list-streams', ajax=1)
        media = self.client.get(media_url)
        self.assert200(media)
        self.assertIn("csrf_tokens", media.json)
        self.assertIn("files", media.json['csrf_tokens'])
        csrf_url = url + '&csrf_token=' + media.json['csrf_tokens']['files']

        response = self.client.get(csrf_url)
        self.assert200(response)
        actual = response.json
        expected = {
            "indexed": media_file.pk,
            "representation": media_file.rep,
            "csrf": actual["csrf"],
        }
        self.assertObjectEqual(expected, actual)

    def test_delete_stream(self):
        self.assertEqual(models.Stream.count(), 0)
        bbb = models.Stream(title='Big Buck Bunny', directory='bbb')
        bbb.add()
        tears = models.Stream(title='Tears of Steel', directory='tears')
        tears.add()
        models.db.session.commit()
        self.assertEqual(models.Stream.count(), 2)
        bbb = models.Stream.get(title='Big Buck Bunny')
        tears = models.Stream.get(title='Tears of Steel')

        url = flask.url_for('delete-stream', spk=tears.pk, ajax=1)

        # user must be logged in to use stream API
        self.logout_user()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.Stream.count(), 2)

        # user must be logged in as media user to use stream API
        # a conventional user should get a permission denied error
        self.login_user(is_admin=False)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.Stream.count(), 2)

        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)

        response = self.client.get(url)
        self.assert200(response)

        # request without CSRF token should fail
        response = self.client.delete(url)
        self.assert200(response)
        self.assertIn("error", response.json)
        self.assertIn("CSRF failure", response.json["error"])
        self.assertEqual(models.Stream.count(), 2)

        media_url = flask.url_for('list-streams', ajax=1)
        media = self.client.get(media_url)
        self.assert200(media)
        csrf_token = media.json['csrf_tokens']['streams']
        csrf_url = url + '&csrf_token=' + csrf_token

        response = self.client.delete(csrf_url)
        self.assert200(response)
        self.assertNotIn("error", response.json)
        self.assertEqual(models.Stream.count(), 1)
        next_csrf_token = response.json["csrf"]

        # try to re-use a CSRF token
        reuse_url = flask.url_for(
            'delete-stream',
            spk=bbb.pk,
            csrf_token=csrf_token)
        response = self.client.delete(reuse_url)
        self.assert200(response)
        self.assertTrue("error" in response.json)
        self.assertIn("CSRF", response.json["error"])

        # try to delete a stream that does not exist
        url = flask.url_for(
            'delete-stream',
            spk=79879823798720987,
            csrf_token=next_csrf_token)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)

    def test_add_full_key_pair(self):
        self.assertEqual(models.Key.count(), 0)

        request = {
            'kid': '1AB45440532C439994DC5C5AD9584BAC',
            'key': 'ccc0f2b3b279926496a7f5d25da692f6',
            'ajax': 1,
        }
        url = flask.url_for('add-key', **request)

        # user must be logged in to use keys API
        self.logout_user()
        response = self.client.put(url)
        self.assertNotAuthorized(response, 1)

        # user must be logged in as admin to use keys API
        self.login_user(is_admin=False)
        response = self.client.put(url)
        self.assertNotAuthorized(response, 1)

        # user must be logged in as admin to use keys API
        self.login_user(is_admin=True)

        # request should fail due to lack of CSRF token
        response = self.client.put(url)
        self.assertIn("error", response.json)
        self.assertIn("CSRF", response.json["error"])

        media_url = flask.url_for('list-streams', ajax=1)
        media = self.client.get(media_url)
        self.assert200(media)
        csrf_token = media.json['csrf_tokens']['kids']
        url += f'&csrf_token={csrf_token}'
        response = self.client.put(url)
        self.assert200(response)
        expected_result = {
            'kid': request['kid'].lower(),
            'key': request['key'].lower(),
            'computed': False,
            'csrf_token': response.json["csrf_token"],
        }
        self.assertEqual(expected_result, response.json)

        keys = list(models.Key.all())
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, expected_result['kid'])
        self.assertEqual(keys[0].hkey, expected_result['key'])
        self.assertEqual(keys[0].computed, False)

        url = flask.url_for('list-streams', ajax=1)
        response = self.client.get(url)
        self.assert200(response)
        del expected_result['csrf_token']
        self.assertListEqual([expected_result], response.json['keys'])

    def test_add_computed_keys(self):
        self.assertEqual(models.Key.count(), 0)
        kid = '01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower()
        flask.url_for('add-key', kid=kid)
        self.login_user(is_admin=True)
        url = flask.url_for('add-key', kid=kid)
        response = self.client.put(url)
        self.assert200(response)
        # request without CSRF token should fail
        self.assertIn("error", response.json)
        self.assertIn("CSRF", response.json["error"])

        media_url = flask.url_for('list-streams', ajax=1)
        media = self.client.get(media_url)
        self.assert200(media)
        csrf_token = media.json['csrf_tokens']['kids']
        url += f'&csrf_token={csrf_token}'
        response = self.client.put(url)
        self.assert200(response)
        expected_result = {
            'kid': kid,
            'key': self.to_hex(base64.b64decode('GUf166PQbx+sgBADjyBMvw==')),
            'computed': True,
            'csrf_token': response.json["csrf_token"],
        }
        self.assertEqual(expected_result, response.json)
        keys = list(models.Key.all())
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, expected_result['kid'])
        self.assertEqual(keys[0].hkey, expected_result['key'])
        self.assertEqual(keys[0].computed, True)

    def test_delete_key(self):
        self.assertEqual(models.Key.count(), 0)

        kid = '1AB45440532C439994DC5C5AD9584BAC'.lower()
        key1 = models.Key(
            hkid=kid,
            hkey='ccc0f2b3b279926496a7f5d25da692f6',
            computed=False)
        key1.add()
        key2 = models.Key(
            hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower(),
            hkey=self.to_hex(base64.b64decode('GUf166PQbx+sgBADjyBMvw==')),
            computed=True)
        key2.add(commit=True)
        self.assertEqual(models.Key.count(), 2)

        url = flask.url_for('delete-key', kpk=key1.pk)

        # user must be logged in to use keys API
        self.logout_user()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.Key.count(), 2)

        # user must be logged in as admin to use keys API
        self.login_user(is_admin=False)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.Key.count(), 2)

        # user must be logged in as admin to use keys API
        self.login_user(is_admin=True)

        # request without CSRF token should fail
        response = self.client.delete(url)
        self.assert400(response)

        media_url = flask.url_for('list-streams', ajax=1)
        media = self.client.get(media_url)
        self.assert200(media)
        csrf_token = media.json['csrf_tokens']['kids']

        csrf_url = flask.url_for('delete-key', kpk=key1.pk, csrf_token=csrf_token)
        response = self.client.delete(csrf_url)
        self.assert200(response)
        keys = list(models.Key.all())
        self.assertEqual(len(keys), 1)
        self.assertEqual(key2.hkid, keys[0].hkid)
        self.assertEqual(key2.hkey, keys[0].hkey)
        self.assertEqual(key2.computed, keys[0].computed)
        next_csrf_token = response.json["csrf"]

        # try to re-use a CSRF token
        csrf_url = flask.url_for('delete-key', kpk=key2.pk, csrf_token=csrf_token)
        response = self.client.delete(csrf_url)
        self.assert400(response)

        # try to delete a key that does not exist
        url = flask.url_for('delete-key', kpk=key1.pk, csrf_token=next_csrf_token)
        response = self.client.delete(url)
        self.assert404(response)

        media = self.client.get(media_url)
        self.assert200(media)
        next_csrf_token = media.json['csrf_tokens']['kids']

        url = flask.url_for('delete-key', kpk='12345', csrf_token=next_csrf_token)
        url = url.replace('12345', 'invalid')
        response = self.client.delete(url)
        self.assert404(response)

    def test_clearkey(self):
        self.assertEqual(models.Key.count(), 0)
        keypair1 = models.Key(
            hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
            hkey='ccc0f2b3b279926496a7f5d25da692f6',
            computed=False)
        keypair1.add()

        keypair2 = models.Key(
            hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower(),
            hkey=self.to_hex(base64.b64decode('GUf166PQbx+sgBADjyBMvw==')),
            computed=True)
        keypair2.add(commit=True)
        self.assertEqual(models.Key.count(), 2)

        url = flask.url_for('clearkey')
        request = {
            "kids": [
                self.base64url_encode(keypair1.KID.raw),
                self.base64url_encode(keypair2.KID.raw),
            ],
            "type": "temporary",
        }

        # user does not need to be logged in to use clearkey
        self.logout_user()
        response = self.client.post(url, json=request)
        expected_result = {
            "keys": [
                {
                    "kty": "oct",
                    "kid": self.base64url_encode(keypair1.KID.raw),
                    "k": self.base64url_encode(keypair1.KEY.raw),
                },
                {
                    "kty": "oct",
                    "kid": self.base64url_encode(keypair2.KID.raw),
                    "k": self.base64url_encode(keypair2.KEY.raw),
                },
            ],
            "type": "temporary",
        }
        # as the order of keys is not defined, sort both expected
        # and actual before the compare
        expected_result["keys"].sort(key=lambda k: k["kid"])
        actual_result = copy.deepcopy(response.json)
        actual_result["keys"].sort(key=lambda k: k["kid"])
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
        response = self.client.post(url, json=request)
        self.assertEqual(expected_result, response.json)

    def test_clearkey_bad_request(self):
        self.assertEqual(models.Key.count(), 0)
        keypair1 = models.Key(
            hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
            hkey='ccc0f2b3b279926496a7f5d25da692f6',
            computed=False)
        keypair1.add()

        keypair2 = models.Key(
            hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-', '').lower(),
            hkey=self.to_hex(base64.b64decode('GUf166PQbx+sgBADjyBMvw==')),
            computed=True)
        keypair2.add(commit=True)
        self.assertEqual(models.Key.count(), 2)

        url = flask.url_for('clearkey')

        # user does not need to be logged in to use clearkey
        self.logout_user()

        request = {
            "type": "temporary",
        }

        # check request without the kids parameter
        response = self.client.post(url, json=request)
        self.assert400(response)

        # check request with invalid base64url encoding
        request = {
            "kids": [
                '*invalid base64*',
            ],
            "type": "temporary",
        }

        response = self.client.post(url, json=request)
        try:
            base64.b64decode('*invalid base64*')
        except (TypeError, binascii.Error) as err:
            expected_result = {
                "error": f'Error: {err}'
            }
        self.assertEqual(expected_result, response.json)

    def base64url_encode(self, value):
        # See https://tools.ietf.org/html/rfc7515#page-54
        if len(value) != 16:
            value = binascii.a2b_hex(value)
        s = str(base64.b64encode(value), 'ascii')  # Regular base64 encoder
        s = s.split('=')[0]         # Remove any trailing '='s
        s = s.replace('+', '-')     # 62nd char of encoding
        s = s.replace('/', '_')     # 63rd char of encoding
        return s

    def test_upload_media_file(self):
        self.upload_media_file(ajax=0)

    def test_upload_media_file_using_ajax(self):
        self.upload_media_file(ajax=1)

    def upload_media_file(self, ajax: int) -> None:
        logging.disable(logging.CRITICAL)
        url = flask.url_for('list-streams', ajax=ajax)

        self.logout_user()
        response = self.client.get(url)
        self.assert200(response)
        if ajax:
            self.assertNotIn("upload", response.json)

        self.login_user(is_admin=False)
        response = self.client.get(url)
        self.assert200(response)
        if ajax:
            self.assertNotIn("upload", response.json)

        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        response = self.client.get(url)
        self.assert200(response)

        stream = models.Stream(
            title='upload media file test',
            directory='test_api',
            marlin_la_url='https://fake.domain/marlin',
            playready_la_url='https://fake.domain/playready'
        )
        stream.add(commit=True)
        stream = models.Stream.get(title='upload media file test')
        self.assertIsNotNone(stream)

        url = flask.url_for('view-stream', spk=stream.pk, ajax=ajax)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        if ajax:
            upload_url = response.json['upload_url']
            content_type = "multipart/form-data"
        else:
            html = BeautifulSoup(response.text, 'lxml')
            form = html.find("form", id='upload-form')
            self.assertIsNotNone(form, msg='Failed to find form[id="upload-form"]')
            self.assertEqual(form['method'], 'POST')
            upload_url = form['action']
            content_type = form['enctype']
        mock_file = io.BytesIO(b'data')
        data = {
            'file': (mock_file, 'bbb_v1.mp4', 'video/mp4',),
            "ajax": ajax,
            "submit": "submit",
        }
        self.logout_user()
        # a POST from a non-logged in user should fail
        response = self.client.post(
            upload_url, data=data, content_type=content_type)
        self.assert401(response)

        self.login_user(is_admin=True)
        self.create_upload_folder()
        # print('==== get upload form ====')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        if ajax:
            upload_url = response.json['upload_url']
            csrf_token = response.json['csrf_tokens']['upload']
            content_type = "multipart/form-data"
        else:
            html = BeautifulSoup(response.text, 'lxml')
            form = html.find("form", id='upload-form')
            self.assertEqual(form['method'], 'POST')
            upload_url = form['action']
            content_type = form['enctype']
            csrf_token = form.find('input', attrs={"name": "csrf_token"})['value']
        # check handling for lack of file
        data = {
            "ajax": ajax,
            "stream": stream.pk,
            "submit": "submit",
        }
        self.assert_upload_post_fails(upload_url, content_type, ajax, data)

        # check handling for lack of filename
        data = {
            "ajax": ajax,
            "stream": stream.pk,
            "submit": "submit",
            'file': (io.BytesIO(b'data'), '', 'video/mp4'),
        }
        self.assert_upload_post_fails(upload_url, content_type, ajax, data)

        # check handling for lack of CSRF token
        data = {
            "ajax": ajax,
            "stream": stream.pk,
            "submit": "submit",
            'file': (io.BytesIO(b'data'), 'bbb.mp4', 'video/mp4'),
        }
        self.assert_upload_post_fails(upload_url, content_type, ajax, data)

        data = {
            "csrf_token": csrf_token,
            "ajax": ajax,
            "stream": stream.pk,
            "submit": "submit",
            'file': (io.BytesIO(b'data'), 'bbb_v1.mp4', 'video/mp4'),
        }
        response = self.client.post(
            upload_url, data=data, content_type=content_type)
        self.assertEqual(response.status_code, 200)
        if ajax:
            self.assertNotIn('error', response.json)
            expected_result = {
                'name': 'bbb_v1',
            }
            for item in ['pk', 'bitrate', 'content_type', 'csrf_token', 'upload_url',
                         'file_html', 'stream', 'blob', 'representation',
                         'encrypted']:
                self.assertIn(item, response.json)
                expected_result[item] = response.json[item]
            self.assertNotEqual(response.json['csrf_token'], csrf_token)
            self.assertObjectEqual(expected_result, response.json)
        else:
            self.assertIn('Uploaded file bbb_v1', response.text)

        # print('==== get index ====')
        url = flask.url_for('view-stream', spk=stream.pk, ajax=1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['media_files'][0]['name'], 'bbb_v1')

    def assert_upload_post_fails(self, upload_url: str, content_type: str,
                                 ajax: int, data: dict) -> None:
        response = self.client.post(
            upload_url, data=data, content_type=content_type)
        if ajax:
            self.assert200(response)
            self.assertIn('error', response.json)
        else:
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers['Location'],
                             flask.url_for('list-streams'))

    def test_edit_stream(self) -> None:
        self.setup_media()
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        with self.app.app_context():
            stream = models.Stream(
                title='edit stream test',
                directory='test_api',
                marlin_la_url='https://fake.domain/marlin',
                playready_la_url='https://fake.domain/playready'
            )
            stream.add(commit=True)
            stream = models.Stream.get(title='edit stream test')
            self.assertIsNotNone(stream)
        url = flask.url_for('view-stream', spk=stream.pk, ajax=1)
        response = self.client.get(url)
        self.assert200(response)
        csrf_token = response.json['csrf_tokens']['streams']
        timing_ref = models.MediaFile.get(name="bbb_v7")
        self.assertIsNotNone(timing_ref)
        data = {
            'csrf_token': csrf_token,
            'directory': 'dir2',
            'title': 'new title',
            'playready_la_url': '',
            'marlin_la_url': 'ms3ha://unit.test/sas',
            'timing_ref': timing_ref.name,
        }
        response = self.client.post(url, json=data)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            st = models.Stream.get(pk=stream.pk)
            self.assertIsNotNone(st)
            self.assertEqual(st.title, 'new title')
            self.assertEqual(st.directory, 'dir2')
            self.assertIsNotNone(st.timing_reference)
            self.assertEqual(timing_ref.name, st.timing_reference.media_name)

    def test_edit_stream_bad_timing_reference(self) -> None:
        self.setup_media()
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        with self.app.app_context():
            stream = models.Stream(
                title='edit stream test',
                directory='test_api',
                marlin_la_url='https://fake.domain/marlin',
                playready_la_url='https://fake.domain/playready'
            )
            stream.add(commit=True)
            stream = models.Stream.get(title='edit stream test')
            self.assertIsNotNone(stream)
        url = flask.url_for('view-stream', spk=stream.pk, ajax=1)
        response = self.client.get(url)
        self.assert200(response)
        csrf_token = response.json['csrf_tokens']['streams']
        data = {
            'csrf_token': csrf_token,
            'directory': 'dir2',
            'title': 'new title',
            'playready_la_url': '',
            'marlin_la_url': 'ms3ha://unit.test/sas',
            'timing_ref': 'unknown_filename',
        }
        response = self.client.post(url, json=data)
        self.assertEqual(response.status_code, 400)

    def test_edit_stream_no_timing_reference(self) -> None:
        self.setup_media()
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        with self.app.app_context():
            stream = models.Stream(
                title='edit stream test',
                directory='test_api',
                marlin_la_url='https://fake.domain/marlin',
                playready_la_url='https://fake.domain/playready'
            )
            stream.add(commit=True)
            stream = models.Stream.get(title='edit stream test')
            self.assertIsNotNone(stream)
        url = flask.url_for('view-stream', spk=stream.pk, ajax=1)
        response = self.client.get(url)
        self.assert200(response)
        csrf_token = response.json['csrf_tokens']['streams']
        data = {
            'csrf_token': csrf_token,
            'directory': 'dir2',
            'title': 'new title',
            'playready_la_url': '',
            'marlin_la_url': 'ms3ha://unit.test/sas',
        }
        response = self.client.post(url, json=data)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            st = models.Stream.get(pk=stream.pk)
            self.assertIsNotNone(st)
            self.assertEqual(st.title, 'new title')
            self.assertEqual(st.directory, 'dir2')

    def test_delete_media_file(self):
        self.setup_media()
        num_files = models.MediaFile.count()
        self.assertGreaterThan(num_files, 0)
        media_file = models.MediaFile.search(max_items=1)[0]
        self.assertIsNotNone(media_file)
        mfid = media_file.pk
        url = flask.url_for(
            'media-info', spk=media_file.stream_pk, mfid=media_file.pk, ajax=1)
        # user must be logged in to use stream API
        self.logout_user()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)

        # user must be logged in as admin to use stream API
        self.login_user(is_admin=False)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 401)

        # user must be logged in media group user to use stream API
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)

        # request should fail due to lack of CSRF token
        response = self.client.delete(url)
        self.assertEqual(response.json['error'], "csrf_token not present")

        media_url = flask.url_for('list-streams', ajax=1)
        media = self.client.get(media_url)
        self.assert200(media)
        self.assertIn("csrf_tokens", media.json)
        self.assertIn("files", media.json['csrf_tokens'])

        csrf_url = url + '&csrf_token=' + media.json['csrf_tokens']['files']
        response = self.client.delete(csrf_url)
        self.assertEqual(response.json["deleted"], mfid)
        self.assertEqual(models.MediaFile.count(), num_files - 1)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        logging.basicConfig()
        # logging.getLogger().setLevel(logging.DEBUG)
        # logging.getLogger('mp4').setLevel(logging.INFO)
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestRestApi)

if __name__ == '__main__':
    unittest.main()
