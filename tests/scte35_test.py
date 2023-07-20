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
import copy
# import json
import logging
import os
import sys
import unittest
try:
    from unittest import mock
except ImportError:
    # use Python 2 back-port
    import mock

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
from utils.purecrc import Crc32Mpeg2 as PureCrc32Mpeg2
from testcase.mixin import TestCaseMixin
from mpeg import MPEG_TIMEBASE
from scte35.binarysignal import BinarySignal
from scte35.descriptors import SegmentationTypeId
from utils.buffered_reader import BufferedReader

class Scte35Tests(TestCaseMixin, unittest.TestCase):
    dash_timebase = 10000000
    test_cases = [{
        'name': 'section 14.2 splice_insert example from SCTE-35',
        'input': r'/DAvAAAAAAAA///wFAVIAACPf+/+c2nALv4AUsz1AAAAAAAKAAhDVUVJAAABNWLbowo=',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'section_length': 47,
            'protocol_version': 0,
            'encrypted_packet': False,
            'pts_adjustment': 0,
            'tier': 0xfff,
            'splice_command_length': 0x14,
            'splice_command_type': 5,
            'splice_insert': {
                'splice_event_id': 0x4800008f,
                'splice_event_cancel_indicator': False,
                'out_of_network_indicator': True,
                'program_splice_flag': True,
                'duration_flag': True,
                'splice_immediate_flag': False,
                'splice_time': {
                    'pts': 0x07369c02e,
                },
                'break_duration': {
                    'auto_return': True,
                    'duration': 0x00052ccf5,
                },
                'avail_num': 0,
                'avails_expected': 0,
                'unique_program_id': 0,
            },
            'descriptors': [{
                '_type': 'AvailDescriptor',
                'tag': 0,
                'length': 8,
                'provider_avail_id': 0x00000135
            }],
            'crc': 0x62dba30a,
            'crc_valid': True,
        }
    }, {
        'name': 'section 14.3 time_signal example from SCTE-35',
        'input': r'/DAvAAAAAAAA///wBQb+dGKQoAAZAhdDVUVJSAAAjn+fCAgAAAAALKChijUCAKnMZ1g=',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'section_length': 47,
            'protocol_version': 0,
            'encrypted_packet': False,
            'pts_adjustment': 0,
            'tier': 0xfff,
            'splice_command_length': 0x5,
            'splice_command_type': 6,
            'time_signal': {
                'pts': 0x0746290a0,
            },
            'descriptors': [{
                '_type': 'SegmentationDescriptor',
                'tag': 2,
                'length': 23,
                'segmentation_event_id': 0x4800008e,
                'segmentation_type': SegmentationTypeId.PROVIDER_PLACEMENT_OP_END,
                'device_restrictions': 3,
                'segmentation_event_cancel_indicator': False,
                'delivery_not_restricted_flag': False,
                'web_delivery_allowed_flag': True,
                'no_regional_blackout_flag': True,
                'archive_allowed_flag': True,
                'program_segmentation_flag': True,
                'segmentation_upid_type': 8,
                'segmentation_upid': base64.b64decode("AAAAACygoYo="),
                'segment_num': 2,
                'segments_expected': 0,
            }],
            'crc': 0xa9cc6758,
            'crc_valid': True,
        }
    }, {
        # DASH test stream
        # duration="2399838222" id="400063803" presentationTime="6937146800000"
        'name': 'DASH 400063803',
        'input': r'/DAlAAAAAA4QAP/wFAVCaTagf+/+iWAjMP4BSZFQxhQCAwAAQ6Xd5w==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x426936A0,
                'unique_program_id': 0xC614,
                'program_splice_flag': True,
                'splice_immediate_flag': False,
                'avail_num': 2,
                'avails_expected': 3,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(2399838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2304779056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="299838222" id="325059779" presentationTime="6937746800000"
        'name': 'DASH 325059779',
        'input': r'/DAlAAAAAA4QAP/wFAUDin0Jf+/+ibKI8P4AKS0wBhQDCAAAq6YflA==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x38A7D09,
                'unique_program_id': 0x614,
                'program_splice_flag': True,
                'splice_immediate_flag': False,
                'avail_num': 3,
                'avails_expected': 8,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(299838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2310179056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="299838222" id="3116305481" presentationTime="6938046800000"
        'name': 'DASH 3116305481',
        'input': r'/DAlAAAAAA4QAP/wFAUDin0Kf+/+idu70P4AKS0wBhQECAAAqX1jjQ==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x38A7D0A,
                'unique_program_id': 0x614,
                'program_splice_flag': True,
                'splice_immediate_flag': False,
                'avail_num': 4,
                'avails_expected': 8,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(299838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2312879056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="299838222" id="176443115" presentationTime="6938346800000"
        'name': 'DASH 176443115',
        'input': r'/DAlAAAAAA4QAP/wFAUDjfWzf+/+igTusP4AKS0wBhQFCAAAUfpPSg==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x38DF5B3,
                'unique_program_id': 0x614,
                'program_splice_flag': True,
                'splice_immediate_flag': False,
                'avail_num': 5,
                'avails_expected': 8,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(299838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2315579056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="299838222" id="1340092364" presentationTime="6938646800000"
        'name': 'DASH 1340092364',
        'input': r'/DAlAAAAAA4QAP/wFAUDjfogf+/+ii4hkP4AKS0wBhQGCAAAmZLEyA==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x38DFA20,
                'unique_program_id': 0x614,
                'program_splice_flag': True,
                'splice_immediate_flag': False,
                'avail_num': 6,
                'avails_expected': 8,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(299838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2318279056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="299838222" id="4093099307" presentationTime="6937446800000"
        'name': 'DASH 4093099307',
        'input': r'/DAlAAAAAA4QAP/wFAUDin0Gf+/+iYlWEP4AKS0wBhQCCAAATqxqgQ==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x38a7d06,
                'unique_program_id': 1556,
                'avail_num': 2,
                'avails_expected': 8,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(299838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2307479056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="2399838222" id="3231984362" presentationTime="6947106800000"
        'name': 'DASH 3231984362',
        'input': r'/DAlAAAAAA4QAP/wFAVCaTavf+/+jrfvcP4BSZFQxlQDAwAA/xNaEQ==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x426936af,
                'unique_program_id': 50772,
                'avail_num': 3,
                'avails_expected': 3,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(2399838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2394419056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="599838222" id="1505300925" presentationTime="6948306800000"
        'name': 'DASH 1505300925',
        'input': r'/DAlAAAAAA4QAP/wFAUDin0Yf+/+j1y68P4AUmAQBlQGBwAAh0Grdg==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x38a7d18,
                'unique_program_id': 1620,
                'avail_num': 6,
                'avails_expected': 7,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(599838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2405219056,
                },
            },
        }
    }, {
        # DASH test stream
        # duration="599838222" id="1182175218" presentationTime="6948906800000"
        'name': 'DASH 1182175218',
        'input': r'/DAlAAAAAA4QAP/wFAUDjwlrf+/+j68gsP4AUmAQBlQHBwAAA123CQ==',
        'expected': {
            'table_id': 0xFC,
            'private_indicator': False,
            'protocol_version': 0,
            'encrypted_packet': False,
            'cw_index': 0,
            'pts_adjustment': 3600,
            'splice_insert': {
                'splice_event_id': 0x38f096b,
                'unique_program_id': 1620,
                'avail_num': 7,
                'avails_expected': 7,
                'break_duration': {
                    'auto_return': True,
                    'duration': int(round(599838222.0 * MPEG_TIMEBASE / dash_timebase))
                },
                'splice_time': {
                    'pts': 2410619056,
                },
            },
        }
    }]

    def setUp(self):
        for tc in self.test_cases:
            if 'crc' not in tc['expected']:
                data = base64.b64decode(tc['input'])
                crc = PureCrc32Mpeg2()
                crc.process(map(lambda b: ord(b), data[:-4]))
                tc['expected']['crc'] = crc.final()
                tc['expected']['crc_valid'] = True

    def test_parsing_splice_info_section(self):
        for idx, tc in enumerate(self.test_cases):
            # print('test_case', idx + 1, tc['name'])
            data = base64.b64decode(tc['input'])
            src = BufferedReader(None, data=data)
            splice_kwargs = BinarySignal.parse(src, size=len(data))
            self.assertIn('crc', tc['expected'])
            msg = r'{0:d}: {1}'.format(idx, tc['name'])
            self.assertObjectEqual(tc['expected'], splice_kwargs, msg)
            splice = BinarySignal(**splice_kwargs)
            encoded = splice.encode()
            self.assertBuffersEqual(data, encoded, msg)

    @mock.patch('mpeg.section_table.Crc32Mpeg2', new=PureCrc32Mpeg2)
    def test_parsing_splice_info_section_with_pure_python_crc(self):
        for idx, tc in enumerate(self.test_cases):
            # print('test_case', idx + 1)
            data = base64.b64decode(tc['input'])
            src = BufferedReader(None, data=data)
            splice_kwargs = BinarySignal.parse(src, size=len(data))
            self.assertObjectEqual(tc['expected'], splice_kwargs)
            splice = BinarySignal(**splice_kwargs)
            encoded = splice.encode()
            self.assertBuffersEqual(data, encoded)

    def test_generating_splice_info_section(self):
        for idx, tc in enumerate(self.test_cases):
            # print('test_case', idx + 1)
            data = base64.b64decode(tc['input'])
            kwargs = copy.deepcopy(BinarySignal.DEFAULT_VALUES)
            kwargs.update(**tc['expected'])
            splice = BinarySignal(**kwargs)
            encoded = splice.encode()
            self.assertBuffersEqual(data, encoded)

    @mock.patch('mpeg.section_table.Crc32Mpeg2', new=PureCrc32Mpeg2)
    def test_generating_splice_info_section_with_pure_python_crc(self):
        for idx, tc in enumerate(self.test_cases):
            # print('test_case', idx + 1)
            data = base64.b64decode(tc['input'])
            kwargs = copy.deepcopy(BinarySignal.DEFAULT_VALUES)
            kwargs.update(**tc['expected'])
            splice = BinarySignal(**kwargs)
            encoded = splice.encode()
            self.assertBuffersEqual(data, encoded)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            Scte35Tests)

if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
