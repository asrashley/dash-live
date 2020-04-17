import struct

class ParseException(Exception):
    pass

class Nal(object):
    SLICE_NON_IDR=1
    SLICE_A=2
    SLICE_B=3
    SLICE_C=4
    IDR=5
    SEI=6
    SPS=7
    PPS=8
    AU_DELIM=9
    END_OF_SEQ=10
    END_OF_STREAM=11
    FILLER=12

    def __init__(self, src, nal_length_field_length):
        self.position = src.tell()
        l = src.read(nal_length_field_length)
        if len(l) != nal_length_field_length:
            raise ParseException("Failed to read NAL length field: expected {:d} read {:d}".format(nal_length_field_length, len(l)))
        if nal_length_field_length<4:
            l = '\000'*(4-nal_length_field_length) + l
        self.size = struct.unpack('>I', l)[0]
        b0 = struct.unpack('B', src.read(1))[0]
        if (b0 & 0x80)!=0:
            raise ParseException('NAL header zero_bit not zero')
        self.ref_idc = (b0>>5) & 0x03
        self.unit_type = b0 & 0x1F
        self.is_idr_frame = self.unit_type==self.IDR
        self.is_ref_frame = self.is_idr_frame
        if self.ref_idc!=0 and not self.unit_type in [self.SPS, self.PPS, self.IDR]:
            self.is_ref_frame = True

    def __repr__(self):
        fields = ['%d'%self.unit_type,'length=%d'%self.size,'idc=0x%x'%self.ref_idc]
        if self.is_idr_frame:
            fields.append('idr=True')
        elif self.is_ref_frame:
            fields.append('ref=True')
        return ''.join(['Nal(', ','.join(fields), ')'])

