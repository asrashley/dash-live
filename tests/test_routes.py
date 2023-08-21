import unittest

from dashlive.server.routes import Route

class RoutesTests(unittest.TestCase):
    def test_re_template(self):
        complex_path = (
            r'/dash/<regex("(live|vod)"):mode>/<stream>/<filename>/' +
            r'<regex("(\d+|init)"):segment_num>.<regex("(mp4|m4v|m4a|m4s)"):ext>')
        complex_expected = (
            r'/dash/(?P<mode>(live|vod))/(?P<stream>\w+)/(?P<filename>\w+)/' +
            r'(?P<segment_num>(\d+|init)).(?P<ext>(mp4|m4v|m4a|m4s))')
        test_cases = [
            (r'/key/<kid>', r'/key/(?P<kid>\w+)'),
            (r'/key', r'/key'),
            (r'/dash/<regex("[\w\-_]+\.mpd"):manifest>',
             r'/dash/(?P<manifest>[\w\-_]+\.mpd)'),
            (r'/media/index/<int:mfid>', r'/media/index/(?P<mfid>\d+)'),
            (complex_path, complex_expected),
        ]
        for template, expected in test_cases:
            route = Route(template, 'handler', 'title')
            self.assertEqual(route.reTemplate.pattern, expected)

    def test_format_template(self):
        complex_path = (
            r'/dash/<regex("(live|vod)"):mode>/<stream>/<filename>/' +
            r'<regex("(\d+|init)"):segment_num>.<regex("(mp4|m4v|m4a|m4s)"):ext>')
        complex_expected = r'/dash/{mode}/{stream}/{filename}/{segment_num}.{ext}'
        test_cases = [
            (r'/key/<kid>', r'/key/{kid}'),
            (r'/key', r'/key'),
            (r'/dash/<regex("[\w\-_]+\.mpd"):manifest>',
             r'/dash/{manifest}'),
            (r'/media/index/<int:mfid>', r'/media/index/{mfid}'),
            (complex_path, complex_expected),
        ]
        for template, expected in test_cases:
            route = Route(template, 'handler', 'title')
            self.assertEqual(route.formatTemplate, expected)


if __name__ == "__main__":
    unittest.main()
