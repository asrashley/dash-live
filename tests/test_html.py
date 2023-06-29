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
from builtins import filter
import json
import os
import unittest

from bs4 import BeautifulSoup
import flask

from dashlive.server import manifests, models
from dashlive.server.cgi_options import cgi_options
from dashlive.server.requesthandler.htmlpage import CgiOptionsPage, MainPage
from dashlive.server.requesthandler.media_management import MediaList
from dashlive.server.requesthandler.streams import EditStreamHandler

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
        self.assertIsNotNone(getattr(MainPage(), 'get', None))
        url = flask.url_for('home')
        # self.logout_user()
        response = self.client.get(url)
        self.assertEqual(response.status, '200 OK')
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        self.assertIn('Log In', response.text)
        media_list_url = flask.url_for('media-list')
        self.assertNotIn(f'href="{media_list_url}"', response.text)
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

    def test_cgi_options_page(self):
        self.assertIsNotNone(getattr(CgiOptionsPage(), 'get', None))
        url = flask.url_for('cgi-options', absolute=True)
        self.logout_user()
        response = self.client.get(url)
        self.assertEqual(response.status, '200 OK')
        html = BeautifulSoup(response.text, 'lxml')
        self.assertIsNotNone(html)
        self.assertIn('Log In', response.text)
        media_list_url = flask.url_for('media-list')
        self.assertNotIn(f'href="{media_list_url}"', response.text)
        for option in cgi_options:
            if option.name == 'drmloc':
                continue
            self.assertIn(option.name, response.text)

    def test_media_page(self):
        self.setup_media()
        self.assertIsNotNone(getattr(MediaList, 'get', None))
        url = flask.url_for('media-list')

        try:
            self.current_url = url

            # user must be logged in to use media page
            self.logout_user()
            response = self.client.get(url)
            self.assertEqual(response.status, '200 OK')
            self.assertIn('This page requires you to log in', response.text)

            # user must be logged in as admin to use media page
            self.login_user(is_admin=False)
            response = self.client.get(url)
            self.assertEqual(response.status, '200 OK')
            self.assertIn('This page requires you to log in', response.text)
            self.logout_user()

            # user must be logged in as admin to use media page
            self.login_user(is_admin=True)
            response = self.client.get(url)
            self.assertEqual(response.status, '200 OK')
            self.assertNotIn('This page requires you to log in', response.text)
        finally:
            self.current_url = None

    def test_stream_edit_page(self):
        self.setup_media()
        self.assertIsNotNone(getattr(EditStreamHandler(), 'get', None))
        self.assertIsNotNone(getattr(EditStreamHandler(), 'post', None))
        stream = models.Stream.get(title='Big Buck Bunny')
        url = flask.url_for('stream-edit', spk=stream.pk)

        try:
            self.current_url = url

            # user must be logged in to use media page
            self.logout_user()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('This page requires you to log in', response.text)

            # user must be logged in as admin to use media page
            self.login_user(is_admin=False)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('This page requires you to log in', response.text)
            self.logout_user()

            # user must be logged in as admin to use media page
            self.login_user(is_admin=True)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('This page requires you to log in', response.text)
            for field in ['Title', 'Directory', 'Marlin LA URL', 'PlayReady LA URL']:
                self.assertIn(f'{field}:', response.text)
            html = BeautifulSoup(response.text, 'lxml')
            for input_field in html.find_all('input'):
                name = input_field.get('name')
                if name == 'csrf_token':
                    self.assertEqual(
                        input_field.get('type'),
                        'hidden')
                    continue
                self.assertEqual(
                    input_field.get('id'),
                    'stream-{0}'.format(name))
                self.assertEqual(
                    input_field.get('value'),
                    getattr(stream, name))
        finally:
            self.current_url = None

    def test_video_playback(self):
        """
        Test generating the video HTML page.
        Checks every manifest with every CGI parameter causes a valid
        HTML page that allows the video to be watched using a <video> element.
        """
        def opt_choose(item):
            return item[0] in {'mode', 'acodec', 'drm'}

        self.setup_media()
        self.logout_user()
        self.assertGreaterThan(models.MediaFile.count(), 0)
        num_tests = 0
        for filename, manifest in manifests.manifest.items():
            options = list(filter(opt_choose, manifest.get_cgi_options(simplified=True)))
            options = self.cgi_combinations(options)
            num_tests += len(options) * models.Stream.count()
        count = 0
        for filename, manifest in manifests.manifest.items():
            for stream in models.Stream.all():
                options = list(filter(opt_choose, manifest.get_cgi_options(simplified=True)))
                options = self.cgi_combinations(options)
                for opt in options:
                    mode = 'vod'
                    if 'mode=live' in opt:
                        mode = 'live'
                    elif 'mode=odvod' in opt:
                        mode = 'odvod'
                    html_url = flask.url_for(
                        "video",
                        mode=mode,
                        stream=self.FIXTURES_PATH.name,
                        manifest=filename[:-4])
                    html_url += r'?{0}'.format(opt)
                    self.progress(count, num_tests)
                    self.current_url = html_url
                    try:
                        response = self.client.get(html_url)
                        self.assertEqual(response.status, '200 OK')
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
                        count += 1
                    finally:
                        self.current_url = None
        self.progress(num_tests, num_tests)

    @staticmethod
    def cgi_combinations(cgi_options, exclude=None):
        """
        convert a list of CGI options into a set of all possible combinations
        """
        indexes = [0] * len(cgi_options)
        result = set()
        if exclude is None:
            exclude = set()
        done = False
        while not done:
            params = {}
            mode = None
            for idx, option in enumerate(cgi_options):
                name, values = option
                if name in exclude:
                    continue
                value = values[indexes[idx]]
                if name == 'mode':
                    mode = value[5:]
                if value:
                    params[name] = value
                if mode != "live":
                    if "mup" in params:
                        del params["mup"]
                    if "time" in params:
                        del params["time"]
                cgi = '&'.join(list(params.values()))
                result.add(cgi)
            idx = 0
            while idx < len(cgi_options):
                indexes[idx] += 1
                if indexes[idx] < len(cgi_options[idx][1]):
                    break
                indexes[idx] = 0
                idx += 1
            if idx == len(cgi_options):
                done = True
        return result


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestHtmlPageHandlers)

if __name__ == "__main__":
    unittest.main()
