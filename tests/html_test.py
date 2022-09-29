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
import json
import os
import sys
import unittest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from gae_base import GAETestBase
from server import manifests, models
from server.cgi_options import cgi_options
from server.requesthandler.htmlpage import CgiOptionsPage, MainPage
from server.requesthandler.media_management import MediaHandler

class TestHtmlPageHandlers(GAETestBase):
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
        for filename, manifest in manifests.manifest.iteritems():
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
        url = self.from_uri("video", absolute=True)
        num_tests = 0
        for filename, manifest in manifests.manifest.iteritems():
            options = filter(opt_choose, manifest.get_cgi_options(simplified=True))
            options = self.cgi_combinations(options)
            num_tests += len(options) * len(models.Stream.all())
        count = 0
        for filename, manifest in manifests.manifest.iteritems():
            for stream in models.Stream.all():
                options = filter(opt_choose, manifest.get_cgi_options(simplified=True))
                options = self.cgi_combinations(options)
                for opt in options:
                    html_url = url + '?mpd={prefix}/{mpd}&{opt}'.format(
                        prefix=stream.prefix, mpd=filename, opt=opt)
                    self.progress(count, num_tests)
                    response = self.app.get(html_url)
                    html = response.html
                    self.assertEqual(html.title.string, manifest.title)
                    for script in html.find_all('script'):
                        if script.get("src"):
                            continue
                        script = script.get_text()
                        self.assertIn('var dashParameters', script)
                        start = script.index('{')
                        end = script.rindex('}') + 1
                        script = json.loads(script[start:end])
                        for field in ['title', 'prefix',
                                      'playready_la_url', 'marlin_la_url']:
                            self.assertEqual(
                                script['stream'][field], getattr(
                                    stream, field))
                    count += 1
        self.progress(num_tests, num_tests)

    @staticmethod
    def cgi_combinations(cgi_options):
        """
        convert a list of CGI options into a set of all possible combinations
        """
        indexes = [0] * len(cgi_options)
        result = set()
        done = False
        while not done:
            params = {}
            mode = None
            for idx, option in enumerate(cgi_options):
                name, values = option
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
                cgi = '&'.join(params.values())
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
