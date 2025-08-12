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

import binascii
import io
import json
import logging
from pathlib import Path
import struct
from typing import ClassVar
import unittest

from dashlive.mpeg import mp4
from dashlive.utils.binary import Binary, HexBinary
from dashlive.utils.json_object import JsonObject

from .mixins.mixin import TestCaseMixin

class Mp4Tests(TestCaseMixin, unittest.TestCase):
    FIXTURES_PATH: ClassVar[Path] = Path(__file__).parent / "fixtures"

    def setUp(self):
        self.timescale = 240
        self.mediaDuration = 141941
        self._segment = None
        self._moov = None
        self._enc_moov = None
        self._segment = None

    @property
    def segment(self):
        """An initialization segment"""
        return self._get_media('_segment', "seg1.mp4")

    @property
    def moov(self):
        """An unencrypted video fragment init segment"""
        return self._get_media('_moov', "moov.mp4")

    @property
    def enc_moov(self):
        """An encrypted video fragment init segment"""
        return self._get_media('_enc_moov', "enc-moov.mp4")

    def _get_media(self, name: str, filename: str) -> bytes:
        if getattr(self, name) is None:
            fixture_file: Path = Mp4Tests.FIXTURES_PATH / filename
            with fixture_file.open("rb") as f:
                setattr(self, name, f.read())
        return getattr(self, name)

    def test_parse_moov(self):
        src = io.BufferedReader(io.BytesIO(self.moov))
        atoms = mp4.Mp4Atom.load(src)
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        self.assertEqual(atoms[1].atom_type, 'free')
        self.assertEqual(atoms[2].atom_type, 'moov')
        self.assertEqual(atoms[3].atom_type, 'styp')
        self.assertEqual(atoms[4].atom_type, 'sidx')
        moov = atoms[2]
        self.assertEqual(len(moov.children), 3)

    def test_parse_encrypted_moov(self):
        src = io.BufferedReader(io.BytesIO(self.enc_moov))
        atoms = mp4.Mp4Atom.load(src)
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
        self.check_add_pssh_box_to_moov(False)

    def test_add_pssh_box_to_moov_lazy_loaded(self):
        self.check_add_pssh_box_to_moov(True)

    def check_add_pssh_box_to_moov(self, lazy_load: bool):
        src = io.BufferedReader(io.BytesIO(self.moov))
        atoms = mp4.Mp4Atom.load(
            src, options={'lazy_load': lazy_load, 'mode': 'rw'})
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        self.assertEqual(len(moov.children), 3)
        pssh = mp4.ContentProtectionSpecificBox(
            atom_type='pssh',
            position=moov.payload_start,
            size=0,
            parent=moov,
            version=1,
            flags=0,
            system_id=HexBinary("e2719d58a985b3c9781ab030af78d30e", _type='hex'),
            key_ids=[HexBinary("1AB45440532C439994DC5C5AD9584BAC", _type='hex')],
            data=None
        )
        enc_pssh = pssh.encode()
        moov_size = moov.size
        moov.insert_child(0, pssh)
        new_moov_data = moov.encode()
        src = io.BufferedReader(io.BytesIO(new_moov_data))
        new_moov = mp4.Mp4Atom.load(src)
        self.assertEqual(len(new_moov_data), moov_size + len(enc_pssh))
        self.assertEqual(len(new_moov), 1)
        new_moov = new_moov[0]
        self.assertEqual(new_moov.atom_type, 'moov')
        self.assertEqual(len(new_moov.children), 4)

    def test_remove_box_from_moov(self) -> None:
        self.check_remove_box_from_moov(False)

    def test_remove_box_from_moov_lazy_loaded(self) -> None:
        self.check_remove_box_from_moov(True)

    def check_remove_box_from_moov(self, lazy_load: bool) -> None:
        src = io.BufferedReader(io.BytesIO(self.moov))
        atoms = mp4.Mp4Atom.load(src, options={'lazy_load': lazy_load, 'mode': 'rw'})
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        mvex = moov.mvex
        moov_size = moov.size
        del moov.mvex
        new_moov_data = moov.encode()
        self.assertEqual(len(new_moov_data), moov_size - mvex.size)
        src = io.BufferedReader(io.BytesIO(new_moov_data))
        new_moov = mp4.Mp4Atom.load(src)
        self.assertEqual(len(new_moov), 1)

    def test_update_base_media_decode_time(self):
        self.check_update_base_media_decode_time(False)

    def test_update_base_media_decode_time_lazy_loaded(self):
        self.check_update_base_media_decode_time(True)

    def check_update_base_media_decode_time(self, lazy_load: bool):
        src = io.BufferedReader(io.BytesIO(self.segment))
        wrap = mp4.Mp4Atom.load(src, options={'lazy_load': True, 'mode': 'rw'}, use_wrapper=True)
        self.assertEqual(len(wrap._children), 4)
        self.assertEqual(wrap._children[0].atom_type, 'moof')
        moof = wrap.moof
        first_sample_pos = moof.traf.tfhd.base_data_offset + moof.traf.trun.data_offset
        self.assertGreaterOrEqual(first_sample_pos,
                                  wrap.mdat.position + wrap.mdat.header_size)
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
            delta = int(origin_time * self.timescale)
            self.assertGreaterOrEqual(delta, 0)
            base_media_decode_time += delta
            self.assertLess(base_media_decode_time, (1 << (8 * dec_time_sz)))
            expected_data = b''.join([self.segment[:offset],
                                     struct.pack(fmt, base_media_decode_time),
                                     self.segment[offset + dec_time_sz:]])
            self.assertEqual(len(self.segment), len(expected_data))
            moof.traf.tfdt.base_media_decode_time = base_media_decode_time
            first_sample_pos = moof.traf.tfhd.base_data_offset + moof.traf.trun.data_offset
            self.assertGreaterOrEqual(
                first_sample_pos, wrap.mdat.position + wrap.mdat.header_size)
            dest = io.BytesIO()
            wrap.encode(dest)
            data = dest.getvalue()
            first_sample_pos = moof.traf.tfhd.base_data_offset + moof.traf.trun.data_offset
            self.assertGreaterOrEqual(
                first_sample_pos, wrap.mdat.position + wrap.mdat.header_size)
            src = io.BufferedReader(io.BytesIO(data))
            new_wrap = mp4.Mp4Atom.load(
                src, options={'lazy_load': True, 'mode': 'rw'}, use_wrapper=True)
            self.assertBuffersEqual(
                expected_data, data, dump=True, max_length=48, name='media segment')
            self.assertEqual(new_wrap.moof.traf.tfdt.base_media_decode_time,
                             base_media_decode_time)
            first_sample_pos = new_wrap.moof.traf.tfhd.base_data_offset + new_wrap.moof.traf.trun.data_offset
            self.assertGreaterOrEqual(
                first_sample_pos, new_wrap.mdat.position + new_wrap.mdat.header_size)
            last_sample_end = first_sample_pos
            for samp in moof.traf.trun.samples:
                last_sample_end += samp.size
            self.assertLessThanOrEqual(
                last_sample_end, new_wrap.mdat.position + new_wrap.mdat.size)
            sidx_len = wrap.sidx.size
            del new_wrap.sidx
            new_wrap.moof.traf.tfhd.base_data_offset = None
            dest = io.BytesIO()
            for child in new_wrap.children:
                child.encode(dest)
            data = dest.getvalue()
            self.assertEqual(len(expected_data) - sidx_len, len(data))
            src = io.BufferedReader(io.BytesIO(data))
            new_wrap = mp4.Mp4Atom.load(
                src, options={'lazy_load': True, 'mode': 'ro'}, use_wrapper=True)
            first_sample_pos = new_wrap.moof.traf.tfhd.base_data_offset + new_wrap.moof.traf.trun.data_offset
            self.assertGreaterOrEqual(
                first_sample_pos, new_wrap.mdat.position + new_wrap.mdat.header_size)

    def test_update_base_media_decode_time_over_32_bits(self):
        src = io.BufferedReader(io.BytesIO(self.segment))
        wrap = mp4.Mp4Atom.load(src, options={'lazy_load': True, 'mode': 'rw'}, use_wrapper=True)
        self.assertEqual(len(wrap._children), 4)
        moof = wrap.moof
        offset = moof.traf.tfdt.position + 12  # dec_time_pos - frag_pos
        base_media_decode_time = struct.unpack(
            '>I', self.segment[offset:offset + 4])[0]
        delta = 1 << 34
        base_media_decode_time += delta
        before = moof.traf.tfdt.size
        moof.traf.tfdt.base_media_decode_time = base_media_decode_time
        # force base_data_offset to be re-calculated when the tfhd box is encoded
        moof.traf.tfhd.base_data_offset = None
        self.assertEqual(before + 4, moof.traf.tfdt.size)
        dest = io.BytesIO()
        wrap.encode(dest)
        data = dest.getvalue()
        new_wrap = mp4.Mp4Atom.load(
            io.BufferedReader(io.BytesIO(data)), options={'lazy_load': True}, use_wrapper=True)
        first_sample_pos = new_wrap.moof.traf.tfhd.base_data_offset + new_wrap.moof.traf.trun.data_offset
        self.assertEqual(
            new_wrap.mdat.position + new_wrap.mdat.header_size, first_sample_pos)

    def test_update_mfhd_sequence_number(self):
        src = io.BufferedReader(io.BytesIO(self.segment))
        frag = mp4.Mp4Atom.load(src, options={'lazy_load': True})
        self.assertEqual(len(frag), 4)
        self.assertEqual(frag[0].atom_type, 'moof')
        moof = frag[0]
        offset = moof.mfhd.position + 12
        segment_num = 0x1234
        expected_data = b''.join([
            self.segment[moof.position:offset],
            struct.pack('>I', segment_num),
            self.segment[offset + 4:moof.position + moof.size]])
        moof.mfhd.sequence_number = segment_num
        data = moof.encode()
        src = io.BufferedReader(io.BytesIO(data))
        new_moof = mp4.Mp4Atom.load(src)[0]
        self.assertBuffersEqual(expected_data, data)
        self.assertEqual(new_moof.mfhd.sequence_number, segment_num)

    def test_wrap_boxes(self):
        src = io.BufferedReader(io.BytesIO(self.moov))
        wrap = mp4.Mp4Atom.load(src, options={'lazy_load': True}, use_wrapper=True)
        self.assertEqual(len(wrap._children), 5)
        data = wrap.encode()
        self.assertEqual(len(data), len(self.moov))
        self.assertBuffersEqual(data, self.moov)

    def test_create_all_boxes_in_moov(self):
        src = io.BufferedReader(io.BytesIO(self.moov))
        options = mp4.Options(lazy_load=False)
        wrap = mp4.Wrapper(
            size=len(self.moov),
            _children=mp4.Mp4Atom.load(src, options=options))
        moov = wrap.moov
        for child in moov.children:
            self.check_create_atom(child, self.moov)
        self.check_create_atom(moov, self.moov)

    def test_create_all_boxes_in_encrypted_moov(self):
        src = io.BufferedReader(io.BytesIO(self.enc_moov))
        wrap = mp4.Wrapper(size=len(self.enc_moov), children=mp4.Mp4Atom.load(src))
        moov = wrap.moov
        for child in moov.children:
            self.check_create_atom(child, self.enc_moov)
        self.check_create_atom(moov, self.enc_moov)

    def test_create_all_boxes_in_moof(self):
        self.check_create_all_boxes_in_moof(False)

    def test_create_all_boxes_in_moof_lazy_loaded(self):
        self.check_create_all_boxes_in_moof(True)

    def check_create_all_boxes_in_moof(self, lazy_load: bool):
        src = io.BufferedReader(io.BytesIO(self.segment))
        options = mp4.Options(lazy_load=lazy_load)
        wrap = mp4.Mp4Atom.load(src, use_wrapper=True, options=options)
        moof = wrap.moof
        for child in moof.children:
            self.check_create_atom(child, self.segment)
        moof_data = self.segment[moof.position:moof.position + moof.size]
        r = moof.toJSON()
        moof = mp4.Mp4Atom.fromJSON(r)
        dest = io.BytesIO()
        moof.encode(dest)
        new_moof_data = dest.getvalue()
        self.assertBuffersEqual(moof_data, new_moof_data)

    def test_check_sample_count_in_saiz_box(self):
        filename: Path = Mp4Tests.FIXTURES_PATH / "bbb" / "bbb_a1_enc.mp4"
        with filename.open('rb') as f:
            with io.BufferedReader(f) as src:
                segments = mp4.Mp4Atom.load(src)
        for seg in segments:
            if seg.atom_type != 'moof':
                continue
            saiz = seg.traf.saiz
            trun = seg.traf.trun
            self.assertEqual(saiz.sample_count, trun.sample_count)

    def test_create_all_segments_in_video_file(self):
        self.check_create_all_segments_in_file("bbb_v7.mp4", False)

    def test_create_all_segments_in_video_file_lazy_loaded(self):
        self.check_create_all_segments_in_file("bbb_v7.mp4", True)

    def test_create_all_segments_in_aac_audio_file(self):
        self.check_create_all_segments_in_file("bbb_a1.mp4", False)

    def test_create_all_segments_in_aac_audio_file_lazy_loaded(self):
        self.check_create_all_segments_in_file("bbb_a1.mp4", True)

    def test_create_all_segments_in_eac3_audio_file(self):
        self.check_create_all_segments_in_file("bbb_a2.mp4", False)

    def test_create_all_segments_in_eac3_audio_file_lazy_loaded(self):
        self.check_create_all_segments_in_file("bbb_a2.mp4", True)

    def check_create_all_segments_in_file(self, name: str, lazy_load: bool) -> None:
        if name.startswith('bbb_'):
            filename: Path = Mp4Tests.FIXTURES_PATH / "bbb" / name
        else:
            filename = Mp4Tests.FIXTURES_PATH / name
        options = mp4.Options(lazy_load=lazy_load)
        with filename.open('rb') as f:
            with io.BufferedReader(f) as src:
                segments = mp4.Mp4Atom.load(src, options=options)
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
        js = child.toJSON()
        ch2 = mp4.Mp4Atom.fromJSON(js)
        name = 'Encoding {} ({})'.format(child.classname(), child.atom_type)
        dest = io.BytesIO()
        ch2.encode(dest)
        new_child_data = dest.getvalue()
        self.assertBuffersEqual(orig_data, new_child_data, name=name)

    def test_avc3_encoding_from_original(self):
        src = io.BufferedReader(io.BytesIO(self.moov))
        atoms = mp4.Mp4Atom.load(src, options={'lazy_load': True})
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
        src = io.BufferedReader(io.BytesIO(self.moov))
        atoms = mp4.Mp4Atom.load(src)
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        avc3 = moov.trak.mdia.minf.stbl.stsd.avc3
        avc3_data = self.moov[avc3.position:avc3.position + avc3.size]
        dest = io.BytesIO()
        avc3.encode(dest)
        new_avc3_data = dest.getvalue()
        self.assertBuffersEqual(avc3_data, new_avc3_data)

        avcc = mp4.AVCConfigurationBox(
            AVCLevelIndication=31, AVCProfileIndication=77,
            profile_compatibility=64, lengthSizeMinusOne=3,
            configurationVersion=1, sps=[], pps=[])
        avc3 = mp4.AVC3SampleEntry(
            atom_type='avc3', temporal_quality=0, compressorname="", vendor=0,
            spatial_quality=0, frame_count=1, vertresolution=72.0,
            height=504, width=896, bit_depth=24, data_reference_index=1,
            colour_table=65535, version=0, horizresolution=72.0,
            revision=0, entry_data_size=0, children=[avcc])
        dest = io.BytesIO()
        avc3.encode(dest)
        new_avc3_data = dest.getvalue()
        self.assertBuffersEqual(avc3_data, new_avc3_data)

        avc3 = mp4.Mp4Atom.fromJSON(avc3.toJSON())
        dest = io.BytesIO()
        avc3.encode(dest)
        new_avc3_data = dest.getvalue()
        self.assertBuffersEqual(avc3_data, new_avc3_data)

    def test_eac3_specific_box(self):
        filename: Path = Mp4Tests.FIXTURES_PATH / "eac3-moov.mp4"
        with filename.open("rb") as f:
            src_data = f.read()
        src = io.BufferedReader(io.BytesIO(src_data))
        atoms = mp4.Mp4Atom.load(src)
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
        ec3 = mp4.Mp4Atom.fromJSON(ec3.toJSON())
        dest = io.BytesIO()
        ec3.encode(dest)
        new_ec3_data = dest.getvalue()
        self.assertBuffersEqual(orig_ec3_data, new_ec3_data)

    def test_parse_dash_events(self) -> None:
        """Test parsing a fragment with DASH event messages in it"""
        filename: Path = Mp4Tests.FIXTURES_PATH / "emsg.mp4"
        with filename.open("rb") as f:
            src_data = f.read()
        src = io.BufferedReader(io.BytesIO(src_data))
        atoms = mp4.Mp4Atom.load(src)
        self.assertEqual(len(atoms), 9)
        expected_data = [
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=S,YDUR=0.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=M,YDUR=2.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=M,YDUR=4.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=M,YDUR=6.00",
            "YMID=337880795,YCSP=337880795,YSEQ=1:4,YTYP=E,YDUR=7.75",
        ]
        for idx, atom in enumerate(atoms):
            if atom.atom_type != 'emsg':
                continue
            self.assertGreaterOrEqual(idx, 2)
            self.assertLessThan(idx, 7)
            self.assertEqual(
                str(atom.data.data, 'ascii'), expected_data[idx - 2])
            self.assertEqual(atom.event_duration, 0)
            self.assertEqual(atom.event_id, 98 + idx)
            self.assertEqual(atom.scheme_id_uri, "urn:example:a:id3:2016")
            self.assertEqual(atom.timescale, 12800)
            self.assertEqual(atom.value, "")
            self.assertEqual(atom.version, 0)

    def test_create_all_segments_in_emsg_file(self):
        self.check_create_all_segments_in_file("emsg.mp4", False)

    def test_create_all_segments_in_emsg_file_lazy_loaded(self):
        self.check_create_all_segments_in_file("emsg.mp4", True)

    def test_create_emsg_v1(self):
        emsg = mp4.EventMessageBox(
            atom_type='emsg',
            version=1,
            flags=0,
            scheme_id_uri="urn:example:2022:6",
            value="42",
            timescale=1000,
            event_id=123,
            presentation_time=0x012345,
            event_duration=0x678,
            data=Binary(b'Hello World'))
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
            str(binascii.b2a_hex(b'urn:example:2022:6'), 'ascii'), "00",
            str(binascii.b2a_hex(b'42'), 'ascii'), "00",
            str(binascii.b2a_hex(b'Hello World'), 'ascii'),
        ])
        # print(expected_data)
        expected_data = binascii.a2b_hex(expected_data)
        self.assertBuffersEqual(expected_data, data)
        src = io.BufferedReader(io.BytesIO(expected_data))
        atoms = mp4.Mp4Atom.load(src)
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
        emsg = mp4.EventMessageBox(
            version=0,
            flags=0,
            scheme_id_uri='urn:example:scheme:2022',
            timescale=0x1234,
            event_duration=0x3456,
            presentation_time_delta=0xabcd,
            event_id=0x6789,
            value="3366",
            data=Binary(b'hello world')
        )
        data = emsg.encode()
        # self.hexdumpBuffer('data', data)
        atom_data = io.BytesIO()
        for item in [
                b'emsg',
                b'\0',  # version
                3 * b'\0',  # flags
                bytes(emsg.scheme_id_uri, 'ascii'),
                b'\0',
                bytes(emsg.value, 'ascii'),
                b'\0',
                struct.pack('>I', emsg.timescale),
                struct.pack('>I', emsg.presentation_time_delta),
                struct.pack('>I', emsg.event_duration),
                struct.pack('>I', emsg.event_id),
                emsg.data.data,
        ]:
            atom_data.write(item)
        atom = atom_data.getvalue()
        length = struct.pack('>I', len(atom) + 4)
        expected = length + atom
        self.assertBuffersEqual(expected, data, name="emsg")
        src = io.BufferedReader(io.BytesIO(data))
        new_emsg = mp4.Mp4Atom.load(src)
        self.assertEqual(len(new_emsg), 1)
        self.assertEqual(new_emsg[0].atom_type, 'emsg')
        self.assertEqual(emsg.timescale, new_emsg[0].timescale)
        self.assertEqual(emsg.presentation_time_delta,
                         new_emsg[0].presentation_time_delta)
        self.assertEqual(emsg.event_duration, new_emsg[0].event_duration)
        self.assertEqual(emsg.event_id, new_emsg[0].event_id)
        self.assertEqual(emsg.data, new_emsg[0].data)

    def test_create_emsg_v1_from_scratch(self):
        emsg = mp4.EventMessageBox(
            atom_type='emsg',
            version=1,
            flags=0,
            scheme_id_uri='urn:example:scheme:2022',
            timescale=0x1234,
            event_duration=0x3456,
            presentation_time=0xabcdef0123456,
            event_id=0x6789,
            value='3366',
            data=Binary(b'hello world')
        )
        data = emsg.encode()
        # self.hexdumpBuffer('data', data)
        atom_data = io.BytesIO()
        for item in [
                b'emsg',  # atom type
                b'\01',  # version
                3 * b'\0',  # flags
                struct.pack('>I', emsg.timescale),
                struct.pack('>Q', emsg.presentation_time),
                struct.pack('>I', emsg.event_duration),
                struct.pack('>I', emsg.event_id),
                bytes(emsg.scheme_id_uri, 'utf-8'),
                b'\0',
                bytes(emsg.value, 'utf-8'),
                b'\0',
                emsg.data.data,
        ]:
            atom_data.write(item)
        atom = atom_data.getvalue()
        length = struct.pack('>I', len(atom) + 4)
        expected = length + atom
        self.assertBuffersEqual(expected, data, name="emsg")
        src = io.BufferedReader(io.BytesIO(data))
        new_emsg = mp4.Mp4Atom.load(src)
        self.assertEqual(len(new_emsg), 1)
        self.assertEqual(new_emsg[0].atom_type, 'emsg')
        self.assertEqual(emsg.timescale, new_emsg[0].timescale)
        self.assertEqual(emsg.presentation_time,
                         new_emsg[0].presentation_time)
        self.assertEqual(emsg.event_duration, new_emsg[0].event_duration)
        self.assertEqual(emsg.event_id, new_emsg[0].event_id)
        self.assertEqual(emsg.data, new_emsg[0].data)

    def test_parse_senc_box_before_saiz_box(self):
        options = mp4.Options(iv_size=8, strict=True, lazy_load=True, mode='rw')
        filename: Path = Mp4Tests.FIXTURES_PATH / "bbb" / "bbb_v6_enc.mp4"
        with filename.open('rb') as f:
            with io.BufferedReader(f) as src:
                wrap = mp4.Mp4Atom.load(src, options=options, use_wrapper=True)
        seg = wrap.moof
        traf = seg.traf
        before = len(traf.children)
        pos = traf.index('senc')
        senc = traf.children[pos]
        traf.remove_child(pos)
        pos = traf.index('saiz')
        traf.insert_child(pos, senc)
        # force base_data_offset to be re-calculated
        traf.tfhd.base_data_offset = None
        self.assertGreaterThan(traf.index('saiz'), traf.index('senc'))
        self.assertEqual(before, len(traf.children))
        new_moof_data = seg.encode()
        src = io.BufferedReader(io.BytesIO(new_moof_data))
        new_moof = mp4.Mp4Atom.load(src, options=options)[0]
        expected = seg.toJSON()
        actual = new_moof.toJSON()
        # expected box ordering is [mfhd, traf]
        self.assertEqual(expected['children'][0]['atom_type'], 'mfhd')
        self.assertEqual(expected['children'][1]['atom_type'], 'traf')
        expected_traf = expected['children'][1]
        # expected box ordering in traf is [tfhd, tfdt, senc, saiz, saio, trun]
        for index, atom_type in enumerate([
                'tfhd', 'tfdt', 'senc', 'saiz', 'saio', 'trun']):
            self.assertEqual(
                expected_traf['children'][index]['atom_type'], atom_type)
        # the newly encoded traf will start at position zero
        # patch the tfhd box to match this offset
        expected_traf['children'][0]["base_data_offset"] = 0
        self.assertObjectEqual(expected, actual, list_key=self.list_key_fn)

    def test_insert_piff_box_before_saiz_box(self) -> None:
        self.check_insert_piff_box_before_saiz_box(False)

    def test_insert_piff_box_before_saiz_box_lazy_loaded(self) -> None:
        self.check_insert_piff_box_before_saiz_box(True)

    def check_insert_piff_box_before_saiz_box(self, lazy_load: bool) -> None:
        options = mp4.Options(
            iv_size=8, strict=True, lazy_load=lazy_load, debug=lazy_load, mode='rw')
        options.log = logging.getLogger('mp4')
        filename: Path = Mp4Tests.FIXTURES_PATH / "bbb" / "bbb_v6_enc.mp4"
        with filename.open('rb') as f:
            with io.BufferedReader(f) as src:
                wrap = mp4.Mp4Atom.load(src, options=options, use_wrapper=True)
        traf = wrap.moof.traf
        pos = traf.index('saiz')
        piff = mp4.PiffSampleEncryptionBox.clone_from_senc(traf.senc)
        traf.insert_child(pos, piff)
        # force base_data_offset to be re-calculated
        traf.tfhd.base_data_offset = None
        # force re-calculation of offset to first senc sample
        traf.saio.offsets = None
        new_moof_data = wrap.moof.encode()
        src = io.BufferedReader(io.BytesIO(new_moof_data))
        new_moof = mp4.Mp4Atom.load(src, options=options)[0]
        # expected box ordering is [mfhd, traf]
        self.assertEqual(new_moof.children[0].atom_type, 'mfhd')
        self.assertEqual(new_moof.children[1].atom_type, 'traf')
        traf = new_moof.traf
        # expected box ordering in traf is [tfhd, tfdt, senc, saiz, saio, trun]
        for index, atom_type in enumerate([
                'tfhd', 'tfdt', 'UUID(a2394f525a9b4f14a2446c427c648df4)',
                'saiz', 'saio', 'senc', 'trun']):
            self.assertEqual(
                traf.children[index].atom_name(), atom_type)
        expected = wrap.moof.toJSON()
        actual = new_moof.toJSON()
        expected_traf = expected['children'][1]
        # the newly encoded traf will start at position zero
        # patch the tfhd box to match this offset
        expected_traf['children'][0]["base_data_offset"] = 0
        # patch the sample position values in:
        #   CencSampleEncryptionBox
        #   PiffSampleEncryptionBox
        #   TrackFragmentRunBox
        boxes_to_patch = {'senc', 'trun', 'UUID(a2394f525a9b4f14a2446c427c648df4)'}
        for idx, child in enumerate(new_moof.traf.children):
            if child.atom_name() not in boxes_to_patch:
                continue
            for j, sample in enumerate(expected_traf['children'][idx]['samples']):
                sample['offset'] = new_moof.traf.children[idx].samples[j].offset
        self.assertObjectEqual(expected, actual, list_key=self.list_key_fn)
        self.assertEqual(len(new_moof.traf.saio.offsets), 1)
        self.assertEqual(
            new_moof.traf.tfhd.base_data_offset + new_moof.traf.saio.offsets[0],
            new_moof.traf.senc.position + new_moof.traf.senc.samples[0].offset)

    def test_parse_ebu_tt_d_subs(self):
        """Test parsing an init segment for a stream containing EBU-TT-D subtitles"""
        namespaces: list[str] = [
            "http://www.w3.org/ns/ttml",
            "http://www.w3.org/ns/ttml#parameter",
            "http://www.w3.org/ns/ttml#styling",
            "http://www.w3.org/ns/ttml#metadata",
            "urn:ebu:tt:metadata",
            "urn:ebu:tt:style",
            "http://www.w3.org/ns/ttml/profile/imsc1#styling",
            "http://www.w3.org/ns/ttml/profile/imsc1#parameter"
        ]
        self.check_ebu_tt_d_subs("ebuttd.mp4", 0, namespaces)

    def test_parse_bbb_t1_fixture(self) -> None:
        namespaces: list[str] = [
            'http://www.w3.org/ns/ttml',
            'http://www.w3.org/ns/ttml#parameter',
            'http://www.w3.org/ns/ttml#styling',
            'http://www.w3.org/ns/ttml#metadata',
            'urn:ebu:tt:metadata',
            'urn:ebu:tt:style',
        ]
        self.check_ebu_tt_d_subs("bbb/bbb_t1.mp4", 8, namespaces)

    def check_ebu_tt_d_subs(self,
                            filename: str,
                            num_fragments: int,
                            namespaces: list[str]) -> None:
        # See http://rdmedia.bbc.co.uk/testcard/vod/ for source
        filename: Path = Mp4Tests.FIXTURES_PATH / filename
        with filename.open("rb") as f:
            src_data = f.read()
        src = io.BufferedReader(io.BytesIO(src_data))
        atoms = mp4.Mp4Atom.load(src)
        # ftyp, moov and then moof fragments
        self.assertEqual(len(atoms), num_fragments + 2)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        self.assertEqual(atoms[1].atom_type, 'moov')
        stpp = atoms[1].trak.mdia.minf.stbl.stsd.stpp
        self.assertEqual(stpp.namespace.split(' '), namespaces)
        if stpp.find_child('mime'):
            self.assertEqual(
                stpp.mime.content_type,
                "application/ttml+xml;codecs=im1t|etd1")
        for child in atoms[1].children:
            self.check_create_atom(child, src_data)
        self.check_create_atom(atoms[1], src_data)

    def test_parse_webvtt_subs(self) -> None:
        """Test parsing a stream containing WebVTT subtitles"""
        filename: Path = Mp4Tests.FIXTURES_PATH / "webvtt.mp4"
        with filename.open("rb") as f:
            src_data = f.read()
        src = io.BufferedReader(io.BytesIO(src_data))
        atoms = mp4.Mp4Atom.load(src)
        self.assertEqual(len(atoms), 9)
        self.assertEqual(atoms[2].atom_type, 'moov')
        wvtt = atoms[2].trak.mdia.minf.stbl.stsd.wvtt
        self.assertEqual(wvtt.vttC.config, 'WEBVTT - This file has cues.')
        for child in atoms[2].children:
            self.check_create_atom(child, src_data)
        self.check_create_atom(atoms[2], src_data)

    def test_parse_hevc_moov(self) -> None:
        filename: Path = Mp4Tests.FIXTURES_PATH / "hevc-moov.mp4"
        with filename.open("rb") as f:
            src_data = f.read()
        src = io.BufferedReader(io.BytesIO(src_data))
        atoms = mp4.Mp4Atom.load(src)
        self.assertEqual(len(atoms), 3)
        self.assertEqual(atoms[2].atom_type, 'moov')
        hev1 = atoms[2].trak.mdia.minf.stbl.stsd.hev1
        self.assertEqual(hev1.width, 2048)
        self.assertEqual(hev1.height, 872)
        self.assertEqual(hev1.hvcC.general_level_idc, 120)
        self.assertEqual(hev1.hvcC.general_profile_idc, 2)
        self.assertEqual(hev1.hvcC.luma_bit_depth, 10)
        self.assertEqual(hev1.hvcC.chroma_bit_depth, 10)
        for child in atoms[2].children:
            self.check_create_atom(child, src_data)
        self.check_create_atom(atoms[2], src_data)

    def test_trun_with_negative_sample_composition_time_offset(self):
        samples = [
            mp4.TrackSample(
                composition_time_offset=0,
                duration=25,
                flags=33554432,
                index=0,
                offset=496,
                size=3648
            ),
            mp4.TrackSample(
                composition_time_offset=100,
                duration=25,
                flags=16842752,
                index=1,
                offset=4144,
                size=214
            ),
            mp4.TrackSample(
                composition_time_offset=25,
                duration=25,
                flags=16842752,
                index=2,
                offset=4358,
                size=217,
            ),
            mp4.TrackSample(
                composition_time_offset=-50,
                duration=25,
                flags=16842752,
                index=3,
                offset=4575,
                size=215,
            )
        ]

        trun = mp4.TrackFragmentRunBox(
            atom_type='trun',
            data_offset=496,
            first_sample_flags=33554432,
            flags=2565,
            header_size=8,
            position=3001,
            sample_count=len(samples),
            version=1,
            samples=samples,
        )
        flags = (
            mp4.TrackFragmentHeaderBox.base_data_offset_present +
            mp4.TrackFragmentHeaderBox.sample_description_index_present +
            mp4.TrackFragmentHeaderBox.default_sample_duration_present +
            mp4.TrackFragmentHeaderBox.default_sample_flags_present)
        tfhd = mp4.TrackFragmentHeaderBox(
            atom_type='tfhd',
            base_data_offset=2921,
            children=None,
            default_sample_duration=25,
            default_sample_flags=16842752,
            default_sample_size=0,
            flags=flags,
            header_size=8,
            position=2953,
            sample_description_index=1,
            track_id=1,
            version=0,
        )
        traf = mp4.TrackFragmentBox(
            atom_type='traf',
            children=[tfhd, trun],
        )
        dest = io.BytesIO()
        traf.encode(dest)
        src = io.BufferedReader(io.BytesIO(dest.getvalue()))
        atoms = mp4.Mp4Atom.load(src)
        self.assertEqual(len(atoms), 1)
        self.assertObjectEqual(traf.toJSON(), atoms[0].toJSON())

    def test_parsing_pasp_box(self):
        data = binascii.a2b_hex('000000107061737000000663000006b2')
        src = io.BufferedReader(io.BytesIO(data))
        atoms = mp4.Mp4Atom.load(src)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'pasp')
        self.assertEqual(atoms[0].h_spacing, 0x663)
        self.assertEqual(atoms[0].v_spacing, 0x6B2)
        dest = io.BytesIO()
        atoms[0].encode(dest)
        self.assertBuffersEqual(dest.getvalue(), data, name="pasp")

    def test_parsing_against_fixture(self):
        self.check_parsing_against_fixture('bbb/bbb_v7_enc', False)

    def test_parsing_against_fixture_lazy_loaded(self):
        self.check_parsing_against_fixture('bbb/bbb_v7_enc', True)

    @staticmethod
    def update_type_field(typename: str) -> str:
        typename = typename.replace('dashlive.mpeg.mp4.', '')
        return typename

    def update_atom(self, atom: JsonObject) -> None:
        for key, value in atom.items():
            if key == '_type':
                atom[key] = self.update_type_field(value)
            elif key == 'children' and value:
                for ch in value:
                    self.update_atom(ch)
            elif isinstance(value, dict) and '_type' in value:
                value['_type'] = self.update_type_field(value['_type'])
            elif (isinstance(value, list) and value and
                  isinstance(value[0], dict)):
                for ch in value:
                    self.update_atom(ch)

    def check_parsing_against_fixture(self, name: str, lazy_load: bool) -> None:
        # To re-create a JSON fixture:
        # python -m dashlive.mpeg.mp4 --json --show "ftyp,moov+,moof+" .\tests\fixtures\bbb_v7_enc.mp4
        filename = self.FIXTURES_PATH / f'{name}.mp4'
        options = mp4.Options(lazy_load=lazy_load)
        with open(filename, 'rb') as f:
            with io.BufferedReader(f) as src:
                segments = mp4.Mp4Atom.load(src, options=options)
        filename = self.FIXTURES_PATH / f'{name}.json'
        with open(filename, 'rt') as src:
            expected = json.load(src)
        actual = []
        for atom in segments:
            if atom.atom_type in {'ftyp', 'moov', 'moof'}:
                js = atom.toJSON(pure=True)
                self.update_atom(js)
                actual.append(js)
        self.assertListEqual(expected, actual)

    def test_insert_tfdt_after_tfhd(self) -> None:
        self.check_insert_tfdt_box_after_tfhd_box(False)

    def test_insert_tfdt_after_tfhd_using_lazy_load(self) -> None:
        self.check_insert_tfdt_box_after_tfhd_box(True)

    def check_insert_tfdt_box_after_tfhd_box(self, lazy_load: bool) -> None:
        options = mp4.Options(
            iv_size=8, strict=True, lazy_load=lazy_load, debug=lazy_load, mode='rw')
        options.log = logging.getLogger('mp4')
        filename: Path = Mp4Tests.FIXTURES_PATH / "webvtt.mp4"
        with filename.open('rb') as f:
            f.seek(674)
            src = io.BufferedReader(io.BytesIO(f.read(831 - 674)))
        wrap = mp4.Mp4Atom.load(src, options=options, use_wrapper=True)
        for index, atom_type in enumerate(['moof', 'mdat']):
            self.assertEqual(
                wrap.children[index].atom_name(), atom_type)
        traf = wrap.moof.traf
        for index, atom_type in enumerate(['tfhd', 'trun']):
            self.assertEqual(
                traf.children[index].atom_name(), atom_type)
        pos = traf.index('tfhd')
        tfdt = mp4.TrackFragmentDecodeTimeBox(
            version=0, flags=0, base_media_decode_time=0x1234)
        traf.insert_child(pos + 1, tfdt)

        # force base_data_offset to be re-calculated
        traf.tfhd.base_data_offset = None

        # force trun box to have a data_offset field, as its
        # position will have changed
        traf.trun.flags |= mp4.TrackFragmentRunBox.data_offset_present

        new_data = wrap.encode()
        src = io.BufferedReader(io.BytesIO(new_data))
        new_wrap = mp4.Mp4Atom.load(src, options=options, use_wrapper=True)
        for index, atom_type in enumerate(['moof', 'mdat']):
            self.assertEqual(
                new_wrap.children[index].atom_name(), atom_type)

        new_moof = new_wrap.moof
        self.assertEqual(new_moof.children[0].atom_type, 'mfhd')
        self.assertEqual(new_moof.children[1].atom_type, 'traf')
        traf = new_moof.traf

        # expected box ordering in traf is [tfhd, tfdt, trun]
        for index, atom_type in enumerate([
                'tfhd', 'tfdt', 'trun']):
            self.assertEqual(
                traf.children[index].atom_name(), atom_type)

        expected = wrap.toJSON()
        moof_js = expected['children'][0]
        self.assertEqual(moof_js['atom_type'], 'moof')
        traf_js = moof_js['children'][1]
        self.assertEqual(traf_js['atom_type'], 'traf')
        trun_js = traf_js['children'][2]
        self.assertEqual(trun_js['atom_type'], 'trun')
        for idx, sample in enumerate(trun_js['samples']):
            sample['offset'] = new_moof.traf.trun.samples[idx].offset
        actual = new_wrap.toJSON()
        self.assertObjectEqual(expected, actual, list_key=self.list_key_fn)

        first_sample_pos: int = (
            new_moof.traf.tfhd.base_data_offset +
            new_moof.traf.trun.data_offset)
        last_sample_end: int = first_sample_pos
        for samp in new_moof.traf.trun.samples:
            last_sample_end += samp.size
        mdat = new_wrap.mdat
        msg = (
            'trun.data_offset must point inside the MDAT box. ' +
            f'trun points to {first_sample_pos} but first sample of ' +
            f'MDAT is at {mdat.position + mdat.header_size}. ' +
            f'trun last sample is {last_sample_end}. End of ' +
            f'MDAT is {mdat.position + mdat.size}. ' +
            f'tfhd.base_data_offset={new_moof.traf.tfhd.base_data_offset} and ' +
            f'trun.data_offset={new_moof.traf.trun.data_offset}'
        )
        self.assertEqual(
            first_sample_pos, mdat.position + mdat.header_size, msg=msg)
        self.assertLessThanOrEqual(
            last_sample_end, mdat.position + mdat.size, msg=msg)


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    unittest.main()
