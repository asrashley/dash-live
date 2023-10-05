import datetime
import unittest

from dashlive.server.options.drm_options import DrmSelection
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.repository import OptionsRepository
from dashlive.server.options.types import OptionUsage

from .mixins.mixin import TestCaseMixin

class TestServerOptions(TestCaseMixin, unittest.TestCase):
    def test_option_usage_from_string(self) -> None:
        test_cases = [
            ('manifest', OptionUsage.MANIFEST),
            ('video', OptionUsage.VIDEO),
            ('audio', OptionUsage.AUDIO),
            ('text', OptionUsage.TEXT),
            ('time', OptionUsage.TIME),
            ('html', OptionUsage.HTML),
        ]
        for txt, usage in test_cases:
            actual = OptionUsage.from_string(txt)
            self.assertEqual(usage, actual)

    def test_option_usage_to_string_set(self) -> None:
        test_cases = [
            (OptionUsage.MANIFEST, {'manifest'}),
            (OptionUsage.VIDEO, {'video'}),
            (OptionUsage.AUDIO, {'audio'}),
            (OptionUsage.TEXT, {'text'}),
            (OptionUsage.TIME, {'time'}),
            (OptionUsage.HTML, {'html'}),
            (
                OptionUsage.MANIFEST + OptionUsage.VIDEO,
                {'manifest', 'video'}
            ),
            (
                OptionUsage.AUDIO + OptionUsage.VIDEO,
                {'audio', 'video'}
            ),
        ]
        for usage, expected in test_cases:
            actual = OptionUsage.to_string_set(usage)
            self.assertEqual(expected, actual)

    def test_option_short_names_are_unique(self) -> None:
        names: set[str] = set()
        for opt in OptionsRepository.get_dash_options():
            self.assertNotIn(opt.short_name, names)
            names.add(opt.short_name)

    def test_option_full_names_are_unique(self) -> None:
        names: set[str] = set()
        for opt in OptionsRepository.get_dash_options():
            name = f'{opt.prefix}{opt.full_name}'
            self.assertNotIn(name, names)
            names.add(name)

    def test_cgi_option_names_are_unique(self) -> None:
        names: set[str] = set()
        for opt in OptionsRepository.get_dash_options():
            self.assertIsInstance(opt.cgi_name, str)
            self.assertNotIn(opt.cgi_name, names)
            names.add(opt.cgi_name)

    def test_get_cgi_options(self) -> None:
        names: set[str] = set()
        for opt in OptionsRepository.get_cgi_options():
            self.assertNotIn(opt.name, names)
            names.add(opt.name)

    @TestCaseMixin.mock_datetime_now(datetime.datetime(2023, 4, 5, 6, 30))
    def test_convert_cgi_options(self) -> None:
        params = {
            'abr': '1',
            'acodec': 'ec-3',
            'base': 'on',
            'bugs': 'saio',
            'depth': '60',
            'drift': '20',
            'drm': 'playready',
            'player': 'shaka',
            'mup': 'none',
            'periods': '2',
            'playready_piff': '1',
            'playready_version': '2.0',
            'start': 'epoch',
            'frames': '3',
            'vcorrupt': '2:03:05Z',
        }
        expected = {
            'abr': True,
            'audioCodec': 'ec-3',
            'availabilityStartTime': 'epoch',
            'bugCompatibility': ['saio'],
            'clockDrift': 20,
            'drmSelection': [('playready', {'pro', 'moov', 'cenc'})],
            'minimumUpdatePeriod': None,
            'numPeriods': 2,
            'playready': {
                'piff': True,
                'version': 2.0,
            },
            'timeShiftBufferDepth': 60,
            'useBaseUrls': True,
            'videoPlayer': 'shaka',
            'videoCorruption': ['2:03:05Z'],
            'videoCorruptionFrameCount': 3,
        }
        result = OptionsRepository.convert_cgi_options(params)
        for key, value in expected.items():
            actual = getattr(result, key)
            self.assertEqual(
                value, actual,
                msg=f'Expected {key} to be "{value}" but found "{actual}"')
        self.assertTrue(result.encrypted)
        params['vcorrupt'] = '1,2'
        expected['videoCorruption'] = ['1', '2']
        result = OptionsRepository.convert_cgi_options(params)
        for key, value in expected.items():
            actual = getattr(result, key)
            self.assertEqual(
                value, actual,
                msg=f'Expected {key} to be "{value}" but found "{actual}"')

    def test_convert_event_cgi_options(self) -> None:
        params = {
            'acodec': 'ec-3',
            'events': 'ping',
            'ping_inband': '1',
            'ping_duration': '120',
            'ping_timescale': '1000',
            'ping_value': 'hello',
        }
        expected = {
            '_type': 'dashlive.server.options.container.OptionsContainer',
            'audioCodec': 'ec-3',
            'eventTypes': ['ping'],
            'ping': {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                'inband': True,
                'duration': 120,
                'timescale': 1000,
                'value': 'hello',
            }
        }
        result = OptionsRepository.convert_cgi_options(params).toJSON()
        self.assertDictEqual(expected, result)

    def test_convert_event_params_to_cgi_parameters(self) -> None:
        defaults = OptionsRepository.get_default_options()
        options = OptionsContainer(
            parameter_map=OptionsRepository.get_parameter_map(),
            defaults=defaults,
            audioCodec='ec-3',
            eventTypes=['ping'],
            ping=OptionsContainer(
                parameter_map=OptionsRepository.get_parameter_map(),
                defaults=defaults['ping'],
                inband=False,
                duration=120,
                timescale=1000,
                value='hello',
            ))
        expected = {
            'acodec': 'ec-3',
            'events': 'ping',
            'ping_inband': '0',
            'ping_duration': '120',
            'ping_timescale': '1000',
            'ping_value': 'hello',
        }
        result = options.generate_cgi_parameters()
        for key, value in expected.items():
            self.assertIn(key, result, f'Expected {key} to be in result')
            actual = result[key]
            self.assertEqual(
                value, actual,
                msg=f'Expected {key} to be "{value}" but found "{actual}"')

    def test_drm_locations(self) -> None:
        self.assertEqual(
            DrmSelection.from_string('marlin'),
            [('marlin', {'pro', 'moov', 'cenc'})])
        self.assertEqual(
            DrmSelection.from_string('MARLIN'),
            [('marlin', {'pro', 'moov', 'cenc'})])
        self.assertEqual(
            DrmSelection.from_string('ClearKey'),
            [('clearkey', {'pro', 'moov', 'cenc'})])
        self.assertEqual(
            DrmSelection.from_string('playready,marlin'),
            [('playready', {'pro', 'moov', 'cenc'}), ('marlin', {'pro', 'moov', 'cenc'})])
        self.assertEqual(
            DrmSelection.from_string('all'),
            [
                ('clearkey', {'pro', 'moov', 'cenc'}),
                ('marlin', {'pro', 'moov', 'cenc'}),
                ('playready', {'pro', 'moov', 'cenc'})
            ])
        self.assertEqual(
            DrmSelection.from_string('all-cenc-moov'),
            [
                ('clearkey', {'cenc', 'moov'}),
                ('marlin', {'cenc', 'moov'}),
                ('playready', {'cenc', 'moov'})
            ])

    @TestCaseMixin.mock_datetime_now(datetime.datetime(2023, 4, 5, 6, 30))
    def test_default_values(self) -> None:
        expected = {
            '_type': 'dashlive.server.options.container.OptionsContainer',
            'abr': True,
            'availabilityStartTime': 'today',
            'audioCodec': 'mp4a',
            'audioDescription': None,
            'audioErrors': [],
            'bugCompatibility': [],
            'clearkey': {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                'licenseUrl': None
            },
            'clockDrift': None,
            'dashjsVersion': None,
            'drmSelection': [],
            'eventTypes': [],
            'failureCount': None,
            'mainAudio': None,
            'mode': 'vod',
            'manifestErrors': [],
            'mainText': None,
            'marlin': {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                'licenseUrl': None,
            },
            'minimumUpdatePeriod': None,
            'numPeriods': None,
            'ping': {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                'count': 0,
                'duration': 200,
                'inband': True,
                'interval': 1000,
                'start': 0,
                'timescale': 100,
                'value': '0',
                'version': 0
            },
            'playready': {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                'licenseUrl': None,
                'piff': True,
                'version': None,
            },
            'scte35': {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                'count': 0,
                'duration': 200,
                'inband': True,
                'interval': 1000,
                'program_id': 1620,
                'start': 0,
                'timescale': 100,
                'value': '',
                'version': 0
            },
            'segmentTimeline': False,
            'shakaVersion': None,
            'textCodec': None,
            'textErrors': [],
            'textLanguage': None,
            'timeShiftBufferDepth': 1800,
            'videoCorruption': [],
            'videoCorruptionFrameCount': None,
            'videoErrors': [],
            'updateCount': None,
            'utcMethod': None,
            'useBaseUrls': True,
            'videoPlayer': 'native',
            'utcValue': None,
        }
        # print(OptionsRepository.get_default_options())
        actual = OptionsRepository.get_default_options().toJSON()
        self.maxDiff = None
        self.assertDictEqual(expected, actual)

    def test_convert_shaka_cgi_options(self) -> None:
        params = {
            'player': 'shaka',
            'shaka': '1.2.3',
        }
        expected = {
            '_type': 'dashlive.server.options.container.OptionsContainer',
            'shakaVersion': '1.2.3',
            'videoPlayer': 'shaka',
        }
        result = OptionsRepository.convert_cgi_options(params).toJSON()
        self.assertDictEqual(expected, result)

    def test_convert_dashjs_cgi_options(self) -> None:
        params = {
            'player': 'dashjs',
            'dashjs': '1.2.3',
        }
        expected = {
            '_type': 'dashlive.server.options.container.OptionsContainer',
            'dashjsVersion': '1.2.3',
            'videoPlayer': 'dashjs',
        }
        result = OptionsRepository.convert_cgi_options(params).toJSON()
        self.assertDictEqual(expected, result)

    def test_convert_stream_default_options(self) -> None:
        form = {
            'abr': '1',
            'acodec': 'mp4a',
            'start': 'epoch',
            'events': 'ping',
            'ping_count': '5',
            'ping_duration': '200',
            'ping_inband': '1',
            'ping_interval': '1000',
            'ping_start': '',
            'ping_timescale': '100',
            'ping_value': '0',
            'ping_version': '',
            'playready_piff': '1',
            'scte35_count': '',
            'scte35_duration': '200',
            'scte35_inband': '1',
            'scte35_interval': '1000',
            'scte35_program_id': '1620',
            'scte35_start': '',
            'scte35_timescale': '100',
            'scte35_value': '',
            'timeline': '0',
            'base': '1',
            'depth': '1800',
        }
        expected = {
            "_type": "dashlive.server.options.container.OptionsContainer",
            "abr": True,
            "audioCodec": "mp4a",
            "audioDescription": None,
            "audioErrors": [],
            "availabilityStartTime": "epoch",
            "bugCompatibility": [],
            'clearkey': {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                'licenseUrl': None
            },
            "clockDrift": None,
            "dashjsVersion": None,
            "drmSelection": [],
            "eventTypes": [
                "ping"
            ],
            "failureCount": None,
            "mainAudio": None,
            "mainText": None,
            "manifestErrors": [],
            "marlin": {
                "_type": "dashlive.server.options.container.OptionsContainer",
                "licenseUrl": None,
            },
            "minimumUpdatePeriod": None,
            "mode": "vod",
            "numPeriods": None,
            "ping": {
                "_type": "dashlive.server.options.container.OptionsContainer",
                "count": 5,
                "duration": 200,
                "inband": True,
                "interval": 1000,
                "start": 0,
                "timescale": 100,
                "value": "0",
                "version": 0
            },
            "playready": {
                '_type': 'dashlive.server.options.container.OptionsContainer',
                "licenseUrl": None,
                "piff": True,
                "version": None,
            },
            "scte35": {
                "_type": "dashlive.server.options.container.OptionsContainer",
                "count": 0,
                "duration": 200,
                "inband": True,
                "interval": 1000,
                "program_id": 1620,
                "start": 0,
                "timescale": 100,
                "value": "",
                "version": 0
            },
            "segmentTimeline": False,
            "shakaVersion": None,
            "textCodec": None,
            "textErrors": [],
            "textLanguage": None,
            "timeShiftBufferDepth": 1800,
            "updateCount": None,
            "useBaseUrls": True,
            "utcMethod": None,
            "utcValue": None,
            "videoCorruption": [],
            "videoCorruptionFrameCount": None,
            "videoErrors": [],
            "videoPlayer": "native"
        }
        defaults = OptionsRepository.get_default_options()
        opts = OptionsRepository.convert_cgi_options(form, defaults)
        self.maxDiff = None
        self.assertDictEqual(expected, opts.toJSON())
        result = opts.remove_default_values()
        without_defaults = {
            'availabilityStartTime': 'epoch',
            'eventTypes': ['ping'],
            'ping': {
                'count': 5,
            },
        }
        self.assertDictEqual(without_defaults, result)
        new_opts = defaults.clone(**result)
        self.assertDictEqual(expected, new_opts.toJSON())

    def test_generate_drm_input_fields_playready(self) -> None:
        self.check_generate_drm_input_fields({
            'playready': ({'pro', 'cenc', 'moov'}, ''),
        })
        self.check_generate_drm_input_fields({
            'playready': ({'cenc', 'moov'}, 'cenc-moov'),
        })
        self.check_generate_drm_input_fields({
            'playready': ({'cenc'}, 'cenc'),
        })
        self.check_generate_drm_input_fields({
            'playready': ({'moov'}, 'moov'),
        })
        self.check_generate_drm_input_fields({
            'playready': ({'moov', 'pro'}, 'moov-pro'),
        })

    def test_generate_drm_input_fields_clearkey(self) -> None:
        self.check_generate_drm_input_fields({
            'clearkey': ({'pro', 'cenc', 'moov'}, ''),
        })
        self.check_generate_drm_input_fields({
            'clearkey': ({'cenc', 'moov'}, 'cenc-moov'),
        })
        self.check_generate_drm_input_fields({
            'clearkey': ({'cenc'}, 'cenc'),
        })
        self.check_generate_drm_input_fields({
            'clearkey': ({'moov'}, 'moov'),
        })
        self.check_generate_drm_input_fields({
            'clearkey': ({'moov', 'pro'}, 'moov-pro'),
        })

    def test_generate_drm_input_fields_marlin(self) -> None:
        self.check_generate_drm_input_fields({
            'marlin': ({'pro', 'cenc', 'moov'}, ''),
        })
        self.check_generate_drm_input_fields({
            'marlin': ({'cenc', 'moov'}, 'cenc-moov'),
        })
        self.check_generate_drm_input_fields({
            'marlin': ({'cenc'}, 'cenc'),
        })
        self.check_generate_drm_input_fields({
            'marlin': ({'moov'}, 'moov'),
        })
        self.check_generate_drm_input_fields({
            'marlin': ({'moov', 'pro'}, 'moov-pro'),
        })

    def test_generate_drm_input_fields_playready_clearkey(self) -> None:
        self.check_generate_drm_input_fields({
            'playready': ({'pro', 'cenc', 'moov'}, ''),
            'clearkey': ({'pro', 'cenc', 'moov'}, ''),
        })
        self.check_generate_drm_input_fields({
            'playready': ({'cenc', 'moov'}, 'cenc-moov'),
            'clearkey': ({'cenc', 'moov', 'pro'}, ''),
        })
        self.check_generate_drm_input_fields({
            'playready': ({'cenc'}, 'cenc'),
            'clearkey': ({'moov'}, 'moov'),
        })

    def check_generate_drm_input_fields(self, drm_map: dict) -> None:
        expected = []
        for name in ['clearkey', 'marlin', 'playready']:
            try:
                loc = drm_map[name][1]
            except KeyError:
                loc = ''
            expected.append({
                'name': f'drm_{name}',
                'title': f'{name.title()} DRM',
                'value': name in drm_map,
                'type': 'checkbox'
            })
            options = [{
                'value': '',
                'title':
                'All locations',
                'selected': loc == ''
            }, {
                'value': 'pro',
                'title': 'mspr:pro element in MPD',
                'selected': loc == 'pro'
            }, {
                'value': 'cenc',
                'title': 'dash:cenc element in MPD',
                'selected': loc == 'cenc'
            }, {
                'value': 'moov',
                'title': 'PSSH in init segment',
                'selected': loc == 'moov'
            }, {
                'value': 'cenc-pro',
                'title': 'mspr:pro + dash:cenc in MPD',
                'selected': loc == 'cenc-pro'
            }, {
                'value': 'moov-pro',
                'title': 'mspr:pro MPD + PSSH init',
                'selected': loc == 'moov-pro'
            }, {
                'value': 'cenc-moov',
                'title': 'dash:cenc MPD + PSSH init',
                'selected': loc == 'cenc-moov'
            }]
            expected.append({
                'name': f'{name}_drmloc',
                'title': f'{name.title()} location',
                'value': loc,
                'text': 'Location to place DRM data',
                'type': 'select',
                'prefix': '',
                'options': options,
                'rowClass': f'row mb-3 drm-location prefix-{name}'
            })
        defaults = OptionsRepository.get_default_options()
        drm_selection = []
        for key in sorted(list(drm_map.keys())):
            drm_selection.append((key, drm_map[key][0]))
        fields = defaults.generate_drm_fields(drm_selection)
        self.assertListEqual(expected, fields)


if __name__ == "__main__":
    unittest.main()
