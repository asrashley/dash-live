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

# base64 and decimal are used when using eval() to create an mp4
# atom from the string returned by repr() on an existing mp4 atom
import base64
import binascii
import decimal
import io
import logging
import os
import struct
import sys
import unittest

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.append(_src)

# these imports *must* be after the modification of sys.path
import utils
from mixins.testcase import TestCaseMixin
import mp4

class Mp4Tests(TestCaseMixin, unittest.TestCase):
    __DECIMAL_TO_AVOID_UNUSED_IMPORT = decimal.Decimal(1)
    __BASE64_TO_AVOID_UNUSED_IMPORT = base64.EMPTYSTRING

    def setUp(self):
        self.fixtures = os.path.join(os.path.dirname(__file__), "fixtures")
        self.timescale = 240
        self.mediaDuration = 141941
        self._segment = None
        self._moov = None
        self._enc_moov = None
        self._segment = None
        logging.basicConfig(level=logging.WARNING)

    @property
    def segment(self):
        """An initialization segment"""
        return self._get_media('_segment', "seg1.mp4")

    @property
    def moov(self):
        """An unencrypted video fragment"""
        return self._get_media('_moov', "moov.mp4")

    @property
    def enc_moov(self):
        """An encrypted video fragment"""
        return self._get_media('_enc_moov', "enc-moov.mp4")

    def _get_media(self, name, filename):
        if getattr(self, name) is None:
            with open(os.path.join(self.fixtures, filename), "rb") as f:
                setattr(self, name, f.read())
        return getattr(self, name)

    def test_parse_moov(self):
        src = utils.BufferedReader(None, data=self.moov)
        atoms = mp4.Mp4Atom.create(src)
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        self.assertEqual(atoms[1].atom_type, 'free')
        self.assertEqual(atoms[2].atom_type, 'moov')
        self.assertEqual(atoms[3].atom_type, 'styp')
        self.assertEqual(atoms[4].atom_type, 'sidx')
        moov = atoms[2]
        self.assertEqual(len(moov.children), 3)

    def test_parse_encrypted_moov(self):
        src = utils.BufferedReader(None, data=self.enc_moov)
        atoms = mp4.Mp4Atom.create(src)
        self.assertEqual(len(atoms), 6)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        self.assertEqual(atoms[1].atom_type, 'mfra')
        self.assertEqual(atoms[2].atom_type, 'free')
        self.assertEqual(atoms[3].atom_type, 'moov')
        self.assertEqual(atoms[4].atom_type, 'styp')
        self.assertEqual(atoms[5].atom_type, 'sidx')
        moov = atoms[3]
        self.assertEqual(len(moov.children), 5)

    def test_add_pssh_box_to_moov(self):
        src = utils.BufferedReader(None, data=self.moov)
        atoms = mp4.Mp4Atom.create(src, options={'cache_encoded': True})
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        self.assertEqual(len(moov.children), 3)
        pssh = mp4.ContentProtectionSpecificBox(atom_type='pssh', position=moov.payload_start,
                                                size=0, parent=moov,
                                                version=1, flags=0,
                                                system_id="e2719d58-a985-b3c9-781a-b030af78d30e",
                                                key_ids=[
                                                    "1AB45440532C439994DC5C5AD9584BAC"],
                                                data=None
                                                )
        enc_pssh = pssh.encode()
        moov_size = moov.size
        moov.insert_child(0, pssh)
        new_moov_data = moov.encode()
        src = utils.BufferedReader(None, data=new_moov_data)
        new_moov = mp4.Mp4Atom.create(src)
        self.assertEqual(len(new_moov_data), moov_size + len(enc_pssh))
        self.assertEqual(len(new_moov), 1)
        new_moov = new_moov[0]
        self.assertEqual(new_moov.atom_type, 'moov')
        self.assertEqual(len(new_moov.children), 4)

    def test_remove_box_from_moov(self):
        src = utils.BufferedReader(None, data=self.moov)
        atoms = mp4.Mp4Atom.create(src, options={'cache_encoded': True})
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        mvex = moov.mvex
        moov_size = moov.size
        del moov.mvex
        new_moov_data = moov.encode()
        self.assertEqual(len(new_moov_data), moov_size - mvex.size)
        src = utils.BufferedReader(None, data=new_moov_data)
        new_moov = mp4.Mp4Atom.create(src)
        self.assertEqual(len(new_moov), 1)

    def test_update_base_media_decode_time(self):
        src = utils.BufferedReader(None, data=self.segment)
        frag = mp4.Mp4Atom.create(src, options={'cache_encoded': True})
        self.assertEqual(len(frag), 4)
        self.assertEqual(frag[0].atom_type, 'moof')
        moof = frag[0]
        if moof.traf.tfdt.version == 1:
            fmt = '>Q'
            dec_time_sz = 8
        else:
            fmt = '>I'
            dec_time_sz = 4
        offset = moof.traf.tfdt.position + 12  # dec_time_pos - frag_pos
        base_media_decode_time = struct.unpack(
            fmt, self.segment[offset:offset + dec_time_sz])[0]
        for loop in range(3):
            origin_time = loop * self.mediaDuration
            delta = long(origin_time * self.timescale)
            self.assertGreaterOrEqual(delta, 0)
            base_media_decode_time += delta
            self.assertLess(base_media_decode_time, (1 << (8 * dec_time_sz)))
            expected_data = ''.join([self.segment[:offset],
                                     struct.pack(fmt, base_media_decode_time),
                                     self.segment[offset + dec_time_sz:]])
            expected_data = expected_data[moof.position:moof.position + moof.size]
            moof.traf.tfdt.base_media_decode_time = base_media_decode_time
            data = moof.encode()
            src = utils.BufferedReader(None, data=data)
            new_moof = mp4.Mp4Atom.create(src)[0]
            self.assertBuffersEqual(expected_data, data)
            self.assertEqual(new_moof.traf.tfdt.base_media_decode_time,
                             base_media_decode_time)

    def test_update_mfhd_sequence_number(self):
        src = utils.BufferedReader(None, data=self.segment)
        frag = mp4.Mp4Atom.create(src, options={'cache_encoded': True})
        self.assertEqual(len(frag), 4)
        self.assertEqual(frag[0].atom_type, 'moof')
        moof = frag[0]
        offset = moof.mfhd.position + 12
        segment_num = 0x1234
        expected_data = ''.join([self.segment[moof.position:offset],
                                 struct.pack('>I', segment_num),
                                 self.segment[offset + 4:moof.position + moof.size]])
        moof.mfhd.sequence_number = segment_num
        data = moof.encode()
        src = utils.BufferedReader(None, data=data)
        new_moof = mp4.Mp4Atom.create(src)[0]
        self.assertBuffersEqual(expected_data, data)
        self.assertEqual(new_moof.mfhd.sequence_number, segment_num)

    def test_wrap_boxes(self):
        src = utils.BufferedReader(None, data=self.moov)
        atoms = mp4.Mp4Atom.create(src, options={'cache_encoded': True})
        self.assertEqual(len(atoms), 5)
        wrap = mp4.Wrapper(atom_type='wrap', position=0, size=len(self.moov), parent=None,
                           children=atoms)
        data = wrap.encode()
        self.assertEqual(len(data), len(self.moov) + 8)
        self.assertBuffersEqual(data[8:], self.moov)

    def test_create_all_boxes_in_moov(self):
        src = utils.BufferedReader(None, data=self.moov)
        wrap = mp4.Wrapper(atom_type='wrap', position=0, size=len(self.moov), parent=None,
                           children=mp4.Mp4Atom.create(src))
        moov = wrap.moov
        for child in moov.children:
            self.check_create_atom(child, self.moov)
        self.check_create_atom(moov, self.moov)

    def test_create_all_boxes_in_encrypted_moov(self):
        src = utils.BufferedReader(None, data=self.enc_moov)
        wrap = mp4.Wrapper(atom_type='wrap', position=0, size=len(self.enc_moov), parent=None,
                           children=mp4.Mp4Atom.create(src))
        moov = wrap.moov
        for child in moov.children:
            self.check_create_atom(child, self.enc_moov)
        self.check_create_atom(moov, self.enc_moov)

    def test_create_all_boxes_in_moof(self):
        src = utils.BufferedReader(None, data=self.segment)
        wrap = mp4.Wrapper(atom_type='wrap', position=0, size=len(self.segment), parent=None,
                           children=mp4.Mp4Atom.create(src))
        moof = wrap.moof
        for child in moof.children:
            self.check_create_atom(child, self.segment)

        moof_data = self.segment[moof.position:moof.position + moof.size]
        r = repr(moof)
        moof = eval(r)
        dest = io.BytesIO()
        moof.encode(dest)
        new_moof_data = dest.getvalue()
        self.assertBuffersEqual(moof_data, new_moof_data)

    def test_create_all_segments_in_video_file(self):
        self.check_create_all_segments_in_file("bbb_v7.mp4")

    def test_create_all_segments_in_aac_audio_file(self):
        self.check_create_all_segments_in_file("bbb_a1.mp4")

    def test_create_all_segments_in_eac3_audio_file(self):
        self.check_create_all_segments_in_file("bbb_a2.mp4")

    def check_create_all_segments_in_file(self, name):
        filename = os.path.join(self.fixtures, name)
        src = utils.BufferedReader(io.FileIO(filename, 'rb'))
        segments = mp4.Mp4Atom.create(src)
        for segment in segments:
            src.seek(segment.position)
            data = src.read(segment.size)
            self.check_create_atom(segment, data, offset=segment.position)

    def check_create_atom(self, child, orig_data, offset=0):
        if child.children:
            for ch in child.children:
                self.check_create_atom(ch, orig_data, offset)
        orig_data = orig_data[child.position -
                              offset: child.position + child.size - offset]
        try:
            r = repr(child)
        except BaseException:
            print child.toJSON(pure=False)
            raise
        try:
            ch2 = eval(r)
        except BaseException:
            print 'repr:'
            print r
            print 'json:'
            print child.toJSON(pure=False)
            raise
        name = 'Encoding %s (%s)' % (child.classname, child.atom_type)
        dest = io.BytesIO()
        try:
            ch2.encode(dest)
        except BaseException:
            print 'repr:'
            print r
            print 'json:'
            print child.toJSON(pure=False)
            raise
        new_child_data = dest.getvalue()
        self.assertBuffersEqual(orig_data, new_child_data, name)

    def test_avc3_encoding_from_original(self):
        src = utils.BufferedReader(None, data=self.moov)
        atoms = mp4.Mp4Atom.create(src, options={'cache_encoded': True})
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        avc3 = moov.trak.mdia.minf.stbl.stsd.avc3
        avc3_data = self.moov[avc3.position:avc3.position + avc3.size]
        dest = io.BytesIO()
        avc3.encode(dest)
        new_avc3_data = dest.getvalue()
        self.assertBuffersEqual(avc3_data, new_avc3_data)

    def test_avc3_encoding_all_boxes(self):
        src = utils.BufferedReader(None, data=self.moov)
        atoms = mp4.Mp4Atom.create(src)
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        avc3 = moov.trak.mdia.minf.stbl.stsd.avc3
        avc3_data = self.moov[avc3.position:avc3.position + avc3.size]
        dest = io.BytesIO()
        avc3.encode(dest)
        new_avc3_data = dest.getvalue()
        self.assertBuffersEqual(avc3_data, new_avc3_data)

        avcc = mp4.AVCConfigurationBox(AVCLevelIndication=31, AVCProfileIndication=77,
                                       profile_compatibility=64, lengthSizeMinusOne=3,
                                       configurationVersion=1, sps=[], pps=[])
        avc3 = mp4.AVC3SampleEntry(atom_type="avc3", temporal_quality=0, compressorname="", vendor=0,
                                   spatial_quality=0, frame_count=1, vertresolution=72.0,
                                   height=504, width=896, bit_depth=24, data_reference_index=1,
                                   colour_table=65535, version=0, horizresolution=72.0,
                                   revision=0, entry_data_size=0, children=[avcc])
        dest = io.BytesIO()
        avc3.encode(dest)
        new_avc3_data = dest.getvalue()
        self.assertBuffersEqual(avc3_data, new_avc3_data)

        avc3 = eval(repr(avc3))
        dest = io.BytesIO()
        avc3.encode(dest)
        new_avc3_data = dest.getvalue()
        self.assertBuffersEqual(avc3_data, new_avc3_data)

    def test_eac3_specific_box(self):
        with open(os.path.join(self.fixtures, "eac3-moov.mp4"), "rb") as f:
            src_data = f.read()
        src = utils.BufferedReader(None, data=src_data)
        atoms = mp4.Mp4Atom.create(src)
        self.assertEqual(len(atoms), 6)
        self.assertEqual(atoms[3].atom_type, 'moov')
        moov = atoms[3]
        ec3 = moov.trak.mdia.minf.stbl.stsd.ec_3
        orig_ec3_data = src_data[ec3.position:ec3.position + ec3.size]
        dest = io.BytesIO()
        ec3.encode(dest)
        new_ec3_data = dest.getvalue()
        self.assertBuffersEqual(orig_ec3_data, new_ec3_data)

        # create a new EC3SampleEntry object from the fields in the current
        # object
        ec3 = eval(repr(ec3))
        dest = io.BytesIO()
        ec3.encode(dest)
        new_ec3_data = dest.getvalue()
        self.assertBuffersEqual(orig_ec3_data, new_ec3_data)

    def test_parse_dash_events(self):
        """Test parsing a fragment with DASH event messages in it"""
        with open(os.path.join(self.fixtures, "emsg.mp4"), "rb") as f:
            src_data = f.read()
        src = utils.BufferedReader(None, data=src_data)
        atoms = mp4.Mp4Atom.create(src)
        self.assertEqual(len(atoms), 9)
        expected_data = [
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=S,YDUR=0.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=M,YDUR=2.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=M,YDUR=4.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=M,YDUR=6.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=E,YDUR=7.75",
        ]
        for idx, atom in enumerate(atoms):
            if atom.atom_type != "emsg":
                continue
            self.assertGreaterOrEqual(idx, 2)
            self.assertLessThan(idx, 7)
            self.assertEqual(atom.data, expected_data[idx - 2])
            self.assertEqual(atom.event_duration, 0)
            self.assertEqual(atom.event_id, 98 + idx)
            self.assertEqual(atom.scheme_id_uri, "urn:example:a:id3:2016")
            self.assertEqual(atom.timescale, 12800)
            self.assertEqual(atom.value, "")
            self.assertEqual(atom.version, 0)

    def test_create_all_segments_in_emsg_file(self):
        self.check_create_all_segments_in_file("emsg.mp4")

    def test_create_emsg_v1(self):
        emsg = mp4.EventMessageBox(
            version=1, flags=0,
            scheme_id_uri="urn:example:2022:6",
            value="42", timescale=1000, event_id=123,
            presentation_time=0x012345,
            event_duration=0x678,
            data="Hello World")
        data = emsg.encode()
        # self.hexdumpBuffer('emsg', data)
        # print(binascii.b2a_hex(data))
        expected_data = ''.join([
            '00000041',  # length
            '656d7367',  # "emsg"
            '01',  # version
            '000000',  # flags
            '000003e8',  # timescale
            '0000000000012345',  # presentation time
            '00000678',  # event duration
            '0000007b',  # event ID
            binascii.b2a_hex("urn:example:2022:6"), "00",
            binascii.b2a_hex("42"), "00",
            binascii.b2a_hex("Hello World"),
        ])
        # print(expected_data)
        expected_data = binascii.a2b_hex(expected_data)
        self.assertBuffersEqual(expected_data, data)
        src = utils.BufferedReader(None, data=expected_data)
        atoms = mp4.Mp4Atom.create(src)
        self.assertEqual(len(atoms), 1)
        new_emsg = atoms[0]
        self.assertEqual(emsg.version, new_emsg.version)
        self.assertEqual(emsg.flags, new_emsg.flags)
        self.assertEqual(emsg.scheme_id_uri, new_emsg.scheme_id_uri)
        self.assertEqual(emsg.value, new_emsg.value)
        self.assertEqual(emsg.timescale, new_emsg.timescale)
        self.assertEqual(emsg.event_id, new_emsg.event_id)
        self.assertEqual(emsg.presentation_time, new_emsg.presentation_time)
        self.assertEqual(emsg.event_duration, new_emsg.event_duration)
        self.assertEqual(emsg.data, new_emsg.data)

    def test_create_emsg_v0_from_scratch(self):
        emsg = mp4.EventMessageBox(version=0,
                                   flags=0,
                                   scheme_id_uri='urn:example:scheme:2022',
                                   timescale=0x1234,
                                   event_duration=0x3456,
                                   presentation_time_delta=0xabcd,
                                   event_id=0x6789,
                                   value="3366",
                                   data='hello world'
                                   )
        data = emsg.encode()
        # self.hexdumpBuffer('data', data)
        atom = ''.join([
            'emsg',  # atom type
            chr(0),  # version
            3 * chr(0),  # flags
            emsg.scheme_id_uri, chr(0),
            emsg.value, chr(0),
            struct.pack('>I', emsg.timescale),
            struct.pack('>I', emsg.presentation_time_delta),
            struct.pack('>I', emsg.event_duration),
            struct.pack('>I', emsg.event_id),
            emsg.data,
        ])
        length = struct.pack('>I', len(atom) + 4)
        expected = length + atom
        self.assertBuffersEqual(expected, data, name="emsg")
        src = utils.BufferedReader(None, data=data)
        new_emsg = mp4.Mp4Atom.create(src)
        self.assertEqual(len(new_emsg), 1)
        self.assertEqual(new_emsg[0].atom_type, 'emsg')
        self.assertEqual(emsg.timescale, new_emsg[0].timescale)
        self.assertEqual(emsg.presentation_time_delta,
                         new_emsg[0].presentation_time_delta)
        self.assertEqual(emsg.event_duration, new_emsg[0].event_duration)
        self.assertEqual(emsg.event_id, new_emsg[0].event_id)
        self.assertEqual(emsg.data, new_emsg[0].data)

    def test_create_emsg_v1_from_scratch(self):
        emsg = mp4.EventMessageBox(version=1,
                                   flags=0,
                                   scheme_id_uri='urn:example:scheme:2022',
                                   timescale=0x1234,
                                   event_duration=0x3456,
                                   presentation_time=0xabcdef0123456,
                                   event_id=0x6789,
                                   value="3366",
                                   data='hello world'
                                   )
        data = emsg.encode()
        # self.hexdumpBuffer('data', data)
        atom = ''.join([
            'emsg',  # atom type
            chr(1),  # version
            3 * chr(0),  # flags
            struct.pack('>I', emsg.timescale),
            struct.pack('>Q', emsg.presentation_time),
            struct.pack('>I', emsg.event_duration),
            struct.pack('>I', emsg.event_id),
            emsg.scheme_id_uri, chr(0),
            emsg.value, chr(0),
            emsg.data,
        ])
        length = struct.pack('>I', len(atom) + 4)
        expected = length + atom
        self.assertBuffersEqual(expected, data, name="emsg")
        src = utils.BufferedReader(None, data=data)
        new_emsg = mp4.Mp4Atom.create(src)
        self.assertEqual(len(new_emsg), 1)
        self.assertEqual(new_emsg[0].atom_type, 'emsg')
        self.assertEqual(emsg.timescale, new_emsg[0].timescale)
        self.assertEqual(emsg.presentation_time,
                         new_emsg[0].presentation_time)
        self.assertEqual(emsg.event_duration, new_emsg[0].event_duration)
        self.assertEqual(emsg.event_id, new_emsg[0].event_id)
        self.assertEqual(emsg.data, new_emsg[0].data)


if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            Mp4Tests)

if __name__ == "__main__":
    unittest.main()
