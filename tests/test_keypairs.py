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

from __future__ import absolute_import, print_function
import os
import unittest

from bs4 import BeautifulSoup
import flask

from dashlive.utils.date_time import from_isodatetime
from dashlive.server import models

from .flask_base import FlaskTestBase

class TestKeypairHandlers(FlaskTestBase):
    NOW = from_isodatetime("2023-07-18T20:10:02Z")

    def test_add_keypair(self):
        url = flask.url_for('add-key')
        response = self.client.get(url)
        self.assert401(response)
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        response = self.client.get(url)
        self.assert200(response)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="edit-model")
        self.assertIsNotNone(form)
        csrf_token = None
        for input_field in form.find_all('input'):
            name = input_field.get('name')
            if name == 'csrf_token':
                self.assertEqual(
                    input_field.get('type'),
                    'hidden')
                csrf_token = input_field.get('value')
        self.assertIsNotNone(csrf_token)
        data = {
            'hkid': 'c001de8e567b5fcfbc22c565ed5bda24',
            'hkey': '533a583a843436a536fbe2a5821c4b6c',
            'new_key': '1',
        }
        # should fail CSRF check
        response = self.client.post(url, data=data)
        self.assert400(response)
        data['csrf_token'] = csrf_token
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            keypair = models.Key.get(hkid=data['hkid'])
            self.assertIsNotNone(keypair)

    def test_edit_keypair(self):
        hkid = 'c001de8e567b5fcfbc22c565ed5bda24'
        hkey = '533a583a843436a536fbe2a5821c4b6c'
        with self.app.app_context():
            keypair = models.Key(hkid=hkid, hkey=hkey, computed=False)
            keypair.add(commit=True)
            keypair = models.Key.get(hkid=hkid)
            self.assertIsNotNone(keypair)
        url = flask.url_for('edit-key', kpk=keypair.pk)
        response = self.client.get(url)
        self.assert401(response)
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        response = self.client.get(url)
        self.assert200(response)
        expected = {
            'hkid': hkid,
            'hkey': hkey,
            'computed': False,
            'new_key': '0',
        }
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="edit-model")
        self.assertIsNotNone(form)
        csrf_token = self.check_form(form, expected)
        hkey2 = 'abcdef0123456789abcdef0123456789'
        data = {
            'hkid': hkid,
            'hkey': hkey2,
            'computed': False,
            'new_key': '0',
            'csrf_token': csrf_token,
        }
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            keypair = models.Key.get(hkid=hkid)
            self.assertIsNotNone(keypair)
            self.assertEqual(keypair.hkey, hkey2)
            self.assertEqual(keypair.computed, False)

    def test_add_keypair_using_put(self):
        url = flask.url_for('add-key')
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        response = self.client.get(url)
        self.assert200(response)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="edit-model")
        self.assertIsNotNone(form)
        csrf_token = None
        for input_field in form.find_all('input'):
            name = input_field.get('name')
            if name == 'csrf_token':
                self.assertEqual(
                    input_field.get('type'),
                    'hidden')
                csrf_token = input_field.get('value')
        self.assertIsNotNone(csrf_token)
        data = {
            'kid': 'c001de8e567b5fcfbc22c565ed5bda24',
            'key': '533a583a843436a536fbe2a5821c4b6c',
        }
        url = flask.url_for('add-key', **data)
        # should fail CSRF check
        response = self.client.put(url)
        self.assert200(response)
        self.assertIn('error', response.json)
        self.assertTrue(response.json['error'].startswith('CSRF failure'))
        data['csrf_token'] = csrf_token
        url = flask.url_for('add-key', **data)
        response = self.client.put(url)
        self.assert200(response)
        with self.app.app_context():
            keypair = models.Key.get(hkid=data['kid'])
            self.assertIsNotNone(keypair)
        expected = {
            'kid': data['kid'],
            'key': data['key'],
            'computed': False,
            'csrf_token': response.json['csrf_token'],
        }
        self.assertDictEqual(expected, response.json)
        data['csrf_token'] = response.json['csrf_token']
        url = flask.url_for('add-key', **data)
        response = self.client.put(url)
        self.assert200(response)
        self.assertIn('error', response.json)
        self.assertEqual(response.json['error'], f"Duplicate KID {data['kid']}")

    def test_delete_keypair(self):
        hkid = 'c001de8e567b5fcfbc22c565ed5bda24'
        hkey = '533a583a843436a536fbe2a5821c4b6c'
        with self.app.app_context():
            keypair = models.Key(hkid=hkid, hkey=hkey, computed=False)
            keypair.add(commit=True)
            keypair = models.Key.get(hkid=hkid)
            self.assertIsNotNone(keypair)
        url = flask.url_for('delete-key', kpk=keypair.pk)
        response = self.client.get(url)
        self.assert401(response)
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        response = self.client.get(url)
        self.assert200(response)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="delete-model")
        self.assertIsNotNone(form)
        expected = {'pk': f'{keypair.pk}'}
        csrf_token = self.check_form(form, expected)
        response = self.client.post(url, data=expected)
        self.assert400(response)
        data = {
            'pk': f'{keypair.pk}',
            'csrf_token': csrf_token,
        }
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            keypair = models.Key.get(hkid=hkid)
            self.assertIsNone(keypair)

    def test_delete_keypair_using_ajax(self):
        hkid = 'c001de8e567b5fcfbc22c565ed5bda24'
        hkey = '533a583a843436a536fbe2a5821c4b6c'
        with self.app.app_context():
            keypair = models.Key(hkid=hkid, hkey=hkey, computed=False)
            keypair.add(commit=True)
            keypair = models.Key.get(hkid=hkid)
            self.assertIsNotNone(keypair)
        url = flask.url_for('delete-key', kpk=keypair.pk, ajax=1)
        response = self.client.get(url)
        self.assert401(response)
        self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
        response = self.client.get(url)
        self.assert200(response)
        csrf_token = response.json['csrf_token']
        response = self.client.delete(url)
        self.assert400(response)
        url = flask.url_for(
            'delete-key', kpk=keypair.pk, ajax=1, csrf_token=csrf_token)
        response = self.client.delete(url)
        self.assert200(response)
        self.assertEqual(hkid, response.json['deleted'])
        with self.app.app_context():
            keypair = models.Key.get(hkid=hkid)
            self.assertIsNone(keypair)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestKeypairHandlers)

if __name__ == "__main__":
    unittest.main()
