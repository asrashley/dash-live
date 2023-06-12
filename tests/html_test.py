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
import sys
import unittest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from server import manifests, models
from server.cgi_options import cgi_options
from server.requesthandler.htmlpage import CgiOptionsPage, MainPage
from server.requesthandler.media_management import MediaHandler
from server.requesthandler.streams import EditStreamHandler
from tests.gae_base import GAETestBase

class TestHtmlPageHandlers(GAETestBase):
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
        url = self.from_uri('home', absolute=True)
        self.logoutCurrentUser()
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(
            'Log In', no='href="{}"'.format(
                self.from_uri('media-index')))
        for filename, manifest in manifests.manifest.items():
            mpd_url = self.from_uri('dash-mpd-v3', manifest=filename, stream='placeholder',
                                    mode='live')
            mpd_url = mpd_url.replace('/placeholder/', '/{directory}/')
            mpd_url = mpd_url.replace('/live/', '/{mode}/')
            response.mustcontain(mpd_url)
        options_url = self.from_uri('cgi-options', absolute=False)
        response.mustcontain(r'href="{}"'.format(options_url))
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(
            'href="{}"'.format(
                self.from_uri('media-index')),
            no="Log In")
        response.mustcontain('Log Out')

    def test_cgi_options_page(self):
        self.assertIsNotNone(getattr(CgiOptionsPage(), 'get', None))
        url = self.from_uri('cgi-options', absolute=True)
        self.logoutCurrentUser()
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(
            'Log In', no='href="{}"'.format(
                self.from_uri('media-index')))
        for option in cgi_options:
            if option.name == 'drmloc':
                continue
            response.mustcontain(option.name)
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(
            'href="{}"'.format(
                self.from_uri('media-index')),
            no="Log In")
        response.mustcontain('Log Out')
        home_url = self.from_uri('home', absolute=False)
        response.mustcontain(r'href="{}"'.format(home_url))

    def test_media_page(self):
        self.setup_media()
        self.assertIsNotNone(getattr(MediaHandler(), 'get', None))
        self.assertIsNotNone(getattr(MediaHandler(), 'post', None))
        url = self.from_uri('media-index', absolute=True)

        try:
            self.current_url = url

            # user must be logged in to use media page
            self.logoutCurrentUser()
            response = self.app.get(url, status=401)
            self.assertEqual(response.status_int, 401)

            # user must be logged in as admin to use media page
            self.setCurrentUser(is_admin=False)
            response = self.app.get(url, status=401)
            self.assertEqual(response.status_int, 401)

            # user must be logged in as admin to use media page
            self.setCurrentUser(is_admin=True)
            response = self.app.get(url)
            self.assertEqual(response.status_int, 200)
        finally:
            self.current_url = None

    def test_stream_edit_page(self):
        self.setup_media()
        self.assertIsNotNone(getattr(EditStreamHandler(), 'get', None))
        self.assertIsNotNone(getattr(EditStreamHandler(), 'post', None))
        stream = models.Stream.query(models.Stream.prefix == 'bbb').get()
        url = self.from_uri(
            'stream-edit', key=stream.key.urlsafe(), absolute=True)

        try:
            self.current_url = url

            # user must be logged in to use media page
            self.logoutCurrentUser()
            response = self.app.get(url, status=401)
            self.assertEqual(response.status_int, 401)

            # user must be logged in as admin to use media page
            self.setCurrentUser(is_admin=False)
            response = self.app.get(url, status=401)
            self.assertEqual(response.status_int, 401)

            # user must be logged in as admin to use media page
            self.setCurrentUser(is_admin=True)
            response = self.app.get(url)
            self.assertEqual(response.status_int, 200)
            response.mustcontain('Title:')
            response.mustcontain('Prefix:')
            response.mustcontain('Marlin LA URL:')
            response.mustcontain('PlayReady LA URL:')
            html = response.html
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
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        num_tests = 0
        for filename, manifest in manifests.manifest.items():
            options = list(filter(opt_choose, manifest.get_cgi_options(simplified=True)))
            options = self.cgi_combinations(options)
            num_tests += len(options) * len(models.Stream.all())
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
                    html_url = self.from_uri(
                        "video", mode=mode, stream=stream.prefix,
                        manifest=filename[:-4], absolute=True)
                    html_url += r'?{0}'.format(opt)
                    self.progress(count, num_tests)
                    self.current_url = html_url
                    try:
                        response = self.app.get(html_url)
                        html = response.html
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
                            for field in ['title', 'prefix',
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
