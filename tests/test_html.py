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

import json
import unittest

from bs4 import BeautifulSoup
import flask

from dashlive.server import manifests, models
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage

from .flask_base import FlaskTestBase

class TestHtmlPageHandlers(FlaskTestBase):
    def _assert_true(self, result, a, b, msg, template):
        if not result:
            current_url = getattr(self, "current_url")
            if current_url is not None:
                print(r'URL: {}'.format(current_url))
            if msg is not None:
                raise AssertionError(msg)
            raise AssertionError(template.format(a, b))

    def test_index_page(self):
        self.setup_media()
        url = flask.url_for('home')
        # self.logout_user()
        response = self.client.get(url)
        self.assertEqual(response.status, '200 OK')
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        self.assertIn('Log In', response.text)
        media_list_url = flask.url_for('list-streams')
        self.assertIn(f'href="{media_list_url}"', response.text)
        for filename, manifest in manifests.manifest.items():
            mpd_url = flask.url_for(
                'dash-mpd-v3', manifest=filename, stream='placeholder',
                mode='live')
            mpd_url = mpd_url.replace('/placeholder/', '/{directory}/')
            mpd_url = mpd_url.replace('/live/', '/{mode}/')
            self.assertIn(mpd_url, response.text)
        options_url = flask.url_for('cgi-options')
        self.assertIn(r'href="{}"'.format(options_url), response.text)
        self.login_user(is_admin=True)
        response = self.client.get(url)
        self.assertEqual(response.status, '200 OK')
        self.assertNotIn('Log In', response.text)
        self.assertIn(f'href="{media_list_url}"', response.text)
        self.assertIn('Log Out', response.text)
        user_admin_url = flask.url_for('list-users')
        self.assertIn(f'href="{user_admin_url}"', response.text)

    def test_cgi_options_page(self):
        url = flask.url_for('cgi-options')
        self.logout_user()
        response = self.client.get(url)
        self.assertEqual(response.status, '200 OK')
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        self.assertIn('Log In', response.text)
        media_list_url = flask.url_for('list-streams')
        self.assertIn(f'href="{media_list_url}"', response.text)
        for option in OptionsRepository.get_cgi_options():
            self.assertIn(option.name, response.text)
        response = self.client.get(f'{url}?json=1')
        self.assertEqual(response.status_code, 200)
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        for option in OptionsRepository.get_dash_options():
            row = html.find(id=f"opt_{option.short_name}")
            self.assertIsNotNone(row)
            name = row.find(class_='short-name')
            self.assertIsNotNone(name)
            self.assertEqual(name.string, option.short_name)
            name = row.find(class_='full-name')
            self.assertIsNotNone(name)
            self.assertEqual(name.string, option.full_name)
            param = row.find(class_='cgi-param')
            self.assertIsNotNone(param)
            self.assertEqual(param.string, str(option.cgi_name))

    def test_media_page(self):
        self.setup_media()
        url = flask.url_for('list-streams')

        try:
            self.current_url = url

            self.logout_user()
            response = self.client.get(url)
            self.assertEqual(response.status, '200 OK')
            # user must be logged in with a media account to edit media
            self.assertNotIn('Edit', response.text)
            self.assertNotIn('Add', response.text)

            self.login_user(is_admin=False)
            response = self.client.get(url)
            self.assertEqual(response.status, '200 OK')
            self.assertNotIn('Edit', response.text)
            self.assertNotIn('Add', response.text)
            self.logout_user()

            # user must be logged in with a media group account to edit
            self.login_user(is_admin=True)
            response = self.client.get(url)
            self.assertEqual(response.status, '200 OK')
            self.assertIn('Edit', response.text)
            self.assertIn('Add', response.text)
        finally:
            self.current_url = None

    def test_stream_edit_page(self):
        self.setup_media()
        stream = models.Stream.get(title='Big Buck Bunny')
        url = flask.url_for('view-stream', spk=stream.pk)

        try:
            self.current_url = url

            self.logout_user()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            # user must be logged in to edit media
            self.assertNotIn('Editing', response.text)

            self.login_user(is_admin=False)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            # user must be logged in to edit media
            self.assertNotIn('Editing', response.text)
            self.logout_user()

            # user must be logged in with media group to edit media
            self.login_user(username=self.MEDIA_USER, password=self.MEDIA_PASSWORD)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Editing', response.text)
            for field in ['Title', 'Directory', 'Marlin LA URL', 'PlayReady LA URL']:
                self.assertIn(f'{field}:', response.text)
            html = BeautifulSoup(response.text, 'lxml')
            for input_field in html.find(id="edit-model").find_all('input'):
                name = input_field.get('name')
                if name == 'csrf_token':
                    self.assertEqual(
                        input_field.get('type'),
                        'hidden')
                    continue
                self.assertEqual(f'model-{name}', input_field.get('id'))
                expected = getattr(stream, name)
                actual = input_field.get('value')
                self.assertEqual(
                    expected, actual,
                    msg=f'Expected field {name} to have "{expected}" but got "{actual}"')
            for input_field in html.find(id="upload-form").find_all('input'):
                name = input_field.get('name')
                if name in {'csrf_token', 'stream'}:
                    self.assertEqual(
                        input_field.get('type'),
                        'hidden')
                if name == 'stream':
                    self.assertEqual(f'{stream.pk}', input_field.get('value'))
        finally:
            self.current_url = None

    def test_video_playback(self) -> None:
        """
        Test generating the video HTML page.
        Checks every manifest with every CGI parameter causes a valid
        HTML page that allows the video to be watched using a <video> element.
        """
        only = {'audioCodec', 'textCodec', 'drmSelection', 'videoPlayer'}
        self.setup_media()
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        num_tests = 0
        use = OptionUsage.AUDIO + OptionUsage.VIDEO + OptionUsage.MANIFEST + OptionUsage.HTML
        for filename, manifest in manifests.manifest.items():
            for mode in manifest.supported_modes():
                options = manifest.get_cgi_query_combinations(
                    mode, simplified=True, only=only, use=use)
                num_tests += len(options) * models.Stream.count()
        count = 0
        for filename, manifest in manifests.manifest.items():
            for mode in manifest.supported_modes():
                options = manifest.get_cgi_query_combinations(
                    mode, simplified=True, only=only, use=use)
                for opt in options:
                    for stream in models.Stream.all():
                        self.progress(count, num_tests)
                        self.check_video_html_page(filename, manifest, mode, stream, opt)
                        count += 1
        self.progress(num_tests, num_tests)

    def check_video_html_page(self, filename: str, manifest, mode: str,
                              stream: models.Stream, query: str) -> None:
        html_url = flask.url_for(
            "video",
            mode=mode,
            stream=self.FIXTURES_PATH.name,
            manifest=filename[:-4])
        html_url += query
        try:
            self.current_url = html_url
            response = self.client.get(html_url)
            self.assertEqual(
                response.status_code, 200,
                msg=f'Failed to fetch video player HTML page {html_url}')
            html = BeautifulSoup(response.text, 'lxml')
            self.assertEqual(html.title.string, manifest.title)
            for script in html.find_all('script'):
                if script.get("src"):
                    continue
                text = script.get_text()
                if not text:
                    text = script.string
                self.assertIn('var dashParameters', text)
                start = text.index('{')
                end = text.rindex('}') + 1
                data = json.loads(text[start:end])
                for field in ['pk', 'title', 'directory',
                              'playready_la_url', 'marlin_la_url']:
                    self.assertEqual(
                        data['stream'][field], getattr(
                            stream, field))
        finally:
            self.current_url = None


if __name__ == "__main__":
    unittest.main()
