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

import os
import unittest

from bs4 import BeautifulSoup
import flask
from werkzeug.test import TestResponse

from dashlive.server.models import Group, User, db

from .mixins.flask_base import FlaskTestBase
from .mixins.mock_time import MockTime

class TestUserManagementHandlers(FlaskTestBase):

    def test_html_login_page(self):
        url = flask.url_for('login')
        response = self.client.get(url)
        self.assert200(response)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="login-form")
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
            'csrf_token': csrf_token,
            'username': self.STD_USER,
            'password': self.STD_PASSWORD,
        }
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)

    def test_html_login_unknown_user(self):
        self.check_html_login_failure('not.known', 'password')

    def test_html_login_wrong_password(self):
        self.check_html_login_failure(self.STD_USER, 'password')
        self.check_html_login_failure(self.STD_USER, self.ADMIN_PASSWORD)

    def check_html_login_failure(self, username: str, password: str) -> None:
        url = flask.url_for('login')
        response = self.client.get(url)
        self.assert200(response)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="login-form")
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
            'csrf_token': csrf_token,
            'username': username,
            'password': password,
        }
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Wrong username or password", response.text)

    @MockTime("2023-07-18T20:10:02Z")
    def test_ajax_login_page(self):
        url = flask.url_for('login', ajax=1)
        response = self.client.get(url)
        self.assert200(response)
        self.assertIn('csrf_token', response.json)
        payload = {
            'csrf_token': response.json['csrf_token'],
            'username': self.STD_USER,
            'password': self.STD_PASSWORD,
            'rememberme': False,
        }
        response = self.client.post(url, json=payload)
        self.assert200(response)
        self.assertNotIn('error', response.json)
        expected = {
            'csrf_token': response.json['csrf_token'],
            'success': True,
            'user': {
                'email': self.STD_EMAIL,
                'groups': ['USER'],
                'last_login': '2023-07-18T20:10:02Z',
                'pk': 2,
                'username': self.STD_USER,
            }
        }
        self.assertDictEqual(expected, response.json)

    def check_requires_admin(self, url: str, html: bool = False) -> TestResponse:
        response = self.client.get(url)
        if html:
            self.assert200(response)
            self.assertIn('This page requires you to log in', response.text)
        else:
            self.assert401(response)
        self.login_user(is_admin=False)
        response = self.client.get(url)
        if html:
            self.assert200(response)
            self.assertIn('This page requires you to log in', response.text)
        else:
            self.assert401(response)
        self.logout_user()
        self.login_user(is_admin=True)
        response = self.client.get(url)
        self.assert200(response)
        return response

    def test_list_users(self) -> None:
        url = flask.url_for('list-users')
        response = self.check_requires_admin(url)
        for usr in User.all():
            self.assertIn(usr.username, response.text)
            self.assertIn(usr.email, response.text)

    def test_add_user(self) -> None:
        self.check_add_modify_user(new_item='1')

    def test_modify_user(self) -> None:
        self.check_add_modify_user(new_item='0')

    def check_add_modify_user(self, new_item: str) -> None:
        if new_item == '0':
            with self.app.app_context():
                user = User.get(username=self.STD_USER)
                self.assertIsNotNone(user)
                user.must_change = True
                db.session.commit()
                user = User.get(username=self.STD_USER)
                self.assertIsNotNone(user)
            url = flask.url_for('edit-user', upk=user.pk)
        else:
            url = flask.url_for('add-user')
            user = User(
                username='a.new.user',
                email='new.user@unit.test',
                groups_mask=Group.USER.value)
        response = self.check_requires_admin(url)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        if new_item == '1':
            form = html.find(id="add-user")
        else:
            form = html.find(id="edit-user")
        self.assertIsNotNone(form, msg='Failed to find HTML form')
        expected = {
            'email': user.email,
            'username': user.username,
            'password': None,
            'confirm_password': None,
            'must_change': True,
            'new_item': new_item,
            'admin_group': False,
            'media_group': False,
            'user_group': True,
        }
        if new_item == '1':
            expected['email'] = None
            expected['username'] = None
            expected['must_change'] = False
        csrf_token = self.check_form(form, expected)
        self.assertIsNotNone(csrf_token)
        data = {
            'csrf_token': csrf_token,
            'email': user.email,
            'username': user.username,
            'password': 'new.password',
            'confirm_password': 'new.password',
            'new_item': new_item,
            'user_group': 'checked',
        }
        response = self.client.post(url, data=data)
        self.assertEqual(302, response.status_code)
        with self.app.app_context():
            if new_item == '0':
                user = User.get(username=self.STD_USER)
                self.assertIsNotNone(user)
                self.assertTrue(user.check_password('new.password'))
            else:
                new_user = User.get(username=user.username)
                self.assertIsNotNone(new_user)
                self.assertTrue(new_user.check_password('new.password'))
        self.assertEqual(
            flask.url_for('list-users'), response.headers['Location'])
        data['password'] = 'another.password'
        data['confirm_password'] = 'another.password'
        # check CSRF token re-use
        response = self.client.post(url, data=data)
        self.assert400(response)
        if new_item == '0':
            with self.app.app_context():
                user = User.get(username=self.STD_USER)
                self.assertIsNotNone(user)
                self.assertTrue(user.check_password('new.password'))

    def test_change_my_password(self) -> None:
        url = flask.url_for('change-password')
        response = self.client.get(url)
        self.assert401(response)
        self.login_user(is_admin=False)
        response = self.client.get(url)
        self.assert200(response)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="edit-user")
        self.assertIsNotNone(form, msg='Failed to find HTML form')
        csrf_token = None
        expected = {
            'email': self.STD_EMAIL,
            'username': self.STD_USER,
            'password': None,
            'confirm_password': None,
            'new_item': '0',
        }
        csrf_token = self.check_form(form, expected)
        self.assertIsNotNone(csrf_token)
        data = {
            'csrf_token': csrf_token,
            'email': self.STD_EMAIL,
            'username': self.STD_USER,
            'password': 'new.password',
            'confirm_password': 'new.password',
            'new_item': '0',
        }
        response = self.client.post(url, data=data)
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            flask.url_for('home'), response.headers['Location'])
        with self.app.app_context():
            user = User.get(username=self.STD_USER)
            self.assertTrue(user.check_password('new.password'))

    def test_delete_user(self) -> None:
        with self.app.app_context():
            user = User.get(username=self.STD_USER)
            self.assertIsNotNone(user)
        url = flask.url_for('delete-user', upk=user.pk)
        response = self.check_requires_admin(url, html=True)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        form = html.find(id="delete-model")
        self.assertIsNotNone(form, msg='Failed to find HTML form')
        expected = {
            'pk': f'{user.pk}',
        }
        csrf_token = self.check_form(form, expected)
        self.assertIsNotNone(csrf_token)
        data = {
            'csrf_token': csrf_token,
            'pk': f'{user.pk}',
        }
        response = self.client.post(url, data=data)
        self.assertEqual(302, response.status_code)
        with self.app.app_context():
            user = User.get(username=self.STD_USER)
            self.assertIsNone(user)
        # check CSRF token re-use
        admin = User.get(username=self.ADMIN_USER)
        self.assertIsNotNone(admin)
        data['pk'] = admin.pk
        url = flask.url_for('delete-user', upk=admin.pk)
        response = self.client.post(url, data=data)
        self.assert400(response)
        with self.app.app_context():
            user = User.get(username=self.ADMIN_USER)
            self.assertIsNotNone(user)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestUserManagementHandlers)

if __name__ == "__main__":
    unittest.main()
