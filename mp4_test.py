import base64
import binascii
import os
import struct
import unittest
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import mp4

class DrmTest(unittest.TestCase):
    def setUp(self):
        with open("fixtures/seg1.mp4", "rb") as f:
            self.segment = f.read()
        with open("fixtures/moov.mp4", "rb") as f:
            self.moov = f.read()
        self.timescale = 240
        self.media_duration = 141941

    def _assert_true(self, result, a, b, msg, template):
        if not result:
            if msg is not None:
                raise AssertionError(msg)
            raise AssertionError(template.format(a,b))
                                                                
    def assertBuffersEqual(self, a, b):
        self.assertEqual(len(a), len(b))
        for idx in range(len(a)):
            self.assertEqual(ord(a[idx]), ord(b[idx]),
                'Expected 0x{:02x} got 0x{:02x} at position {}'.format(ord(a[idx]), ord(b[idx]), idx))
            
    def assertGreaterOrEqual(self, a, b, msg=None):
        self._assert_true(a>=b, a, b, msg, r'{} < {}')

    def test_parse_moov(self):
        inp = StringIO.StringIO(self.moov)
        atoms = mp4.Mp4Atom.create(inp)
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        self.assertEqual(atoms[1].atom_type, 'free')
        self.assertEqual(atoms[2].atom_type, 'moov')
        self.assertEqual(atoms[3].atom_type, 'styp')
        self.assertEqual(atoms[4].atom_type, 'sidx')
        moov = atoms[2]
        #moov.dump()
        self.assertEqual(len(moov.children), 3)

    def test_add_pssh_box_to_moov(self):
        inp = StringIO.StringIO(self.moov)
        atoms = mp4.Mp4Atom.create(inp)
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        self.assertEqual(len(moov.children), 3)
        pssh = mp4.ContentProtectionSpecificBox(atom_type='pssh', position=moov.payload_start,
                                                size=0, parent=moov,
                                                version=1, flags=0,
                                                system_id="e2719d58-a985-b3c9-781a-b030af78d30e",
                                                key_ids=["1AB45440532C439994DC5C5AD9584BAC"],
                                                data=None
        )
        enc_pssh = pssh.encode()
        moov_size = moov.size
        moov.insert_child(0, pssh)
        new_moov_data = moov.encode()
        self.assertEqual(len(new_moov_data), moov_size + len(enc_pssh))
        new_moov = mp4.Mp4Atom.create(StringIO.StringIO(new_moov_data))
        self.assertEqual(len(new_moov), 1)
        new_moov = new_moov[0]
        self.assertEqual(new_moov.atom_type, 'moov')
        self.assertEqual(len(new_moov.children), 4)
        #new_moov.dump()
        
    def test_remove_box_from_moov(self):
        inp = StringIO.StringIO(self.moov)
        atoms = mp4.Mp4Atom.create(inp)
        self.assertEqual(len(atoms), 5)
        self.assertEqual(atoms[2].atom_type, 'moov')
        moov = atoms[2]
        mvex = moov.mvex
        moov_size = moov.size
        del moov.mvex
        #moov.dump()
        new_moov_data = moov.encode()
        self.assertEqual(len(new_moov_data), moov_size - mvex.size)
        new_moov = mp4.Mp4Atom.create(StringIO.StringIO(new_moov_data))
        self.assertEqual(len(new_moov), 1)
        #new_moov[0].dump()

    def test_update_base_media_decode_time(self):
        frag = mp4.Mp4Atom.create(StringIO.StringIO(self.segment))
        self.assertEqual(len(frag), 4)
        self.assertEqual(frag[0].atom_type, 'moof')
        moof = frag[0]
        if moof.traf.tfdt.version==1:
            fmt='>Q'
            dec_time_sz=8
        else:
            fmt='>I'
            dec_time_sz=4
        offset = moof.traf.tfdt.position + 12 #dec_time_pos - frag_pos
        base_media_decode_time = struct.unpack(fmt, self.segment[offset:offset+dec_time_sz])[0]
        for loop in range(3):
            origin_time = loop * self.media_duration
            delta = long(origin_time*self.timescale)
            self.assertGreaterOrEqual(delta, 0L)
            base_media_decode_time += delta
            self.assertLess(base_media_decode_time, (1<<(8*dec_time_sz)))
            expected_data = ''.join([self.segment[:offset],
                                     struct.pack(fmt,base_media_decode_time),
                                     self.segment[offset+dec_time_sz:]])
            expected_data = expected_data[moof.position:moof.position+moof.size]
            moof.traf.tfdt.base_media_decode_time = base_media_decode_time
            data = moof.encode()
            new_moof = mp4.Mp4Atom.create(StringIO.StringIO(data))[0]
            #new_moof.dump()
            #print(moof.traf.tfdt)
            self.assertBuffersEqual(expected_data, data)

    def test_update_mfhd_sequence_number(self):
        frag = mp4.Mp4Atom.create(StringIO.StringIO(self.segment))
        self.assertEqual(len(frag), 4)
        self.assertEqual(frag[0].atom_type, 'moof')
        moof = frag[0]
        offset = moof.mfhd.position + 12
        segment_num = 0x1234
        expected_data = ''.join([self.segment[moof.position:offset],
                                 struct.pack('>I',segment_num),
                                 self.segment[offset+4:moof.position+moof.size]])
        moof.mfhd.sequence_number = segment_num
        data = moof.encode()
        new_moof = mp4.Mp4Atom.create(StringIO.StringIO(data))[0]
        new_moof.dump()
        print(moof.traf.tfdt)
        self.assertBuffersEqual(expected_data, data)
        
    def test_wrap_boxes(self):
        inp = StringIO.StringIO(self.moov)
        atoms = mp4.Mp4Atom.create(inp)
        self.assertEqual(len(atoms), 5)
        wrap = mp4.Mp4Atom(atom_type='wrap', position=0, size = len(self.moov), parent=None,
                           children=atoms)
        data = wrap.encode()
        self.assertEqual(len(data), len(self.moov)+8)
        self.assertBuffersEqual(data[8:], self.moov)
        
if __name__ == "__main__":
    unittest.main()

        
