
import argparse
import base64
import datetime
import io
import struct
import sys

from bitstring import ConstBitStream
from nal import Nal
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import utils

class ParseException(Exception):
    pass

# time values are in seconds since midnight, Jan. 1, 1904, in UTC time
ISO_EPOCH = datetime.datetime(year=1904, month=1, day=1, tzinfo=utils.UTC())

MP4_BOXES = {}
MP4_DESCRIPTORS = {}

class Mp4Atom(object):
    #MEMBERS = [ "position", "size", "parent", "children", "descriptors" ]
    parse_children=False

    def __init__(self, **kwargs):
        self._fields = { "atom_type": kwargs["atom_type"] }
        self.position = kwargs.get("position")
        self.size = kwargs.get("size")
        self.parent = kwargs.get("parent")
        self.children = kwargs.get("children", [])
        self.descriptors = kwargs.get("descriptors", [])
        self._encoded = None
        for key,value in kwargs.iteritems():
            assert "src" != key
            if not self.__dict__.has_key(key):
                self._fields[key] = value

    def __getattr__(self, name):
        if name[0]=="_":
            # __getattribute__ should have responded before __getattr__ called
            raise AttributeError(name)
        if self._fields.has_key(name):
            return self._fields[name]
        for c in self.children:
            if '-' in c.atom_type:
                if c.atom_type.replace('-','_')==name:
                    return c
            elif c.atom_type==name:
                return c
        for d in self.descriptors:
            if d.__class__.__name__==name:
                return d
        raise AttributeError(name)

    def _invalidate(self):
        if self._encoded is not None:
            self._encoded = None
            if self.parent:
                self.parent._invalidate()

    def __setattr__(self, name, value):
        if name[0]!='_' and self._fields.has_key(name):
            self._fields[name] = value
            self._invalidate()
            return
        object.__setattr__(self, name, value)
            
    def __delattr__(self, name):
        if self._fields.has_key(name):
            raise AttributeError('Unable to delete field {} '.format(name))
        for idx, c in enumerate(self.children):
            if c.atom_type==name or ('-' in c.atom_type and c.atom_type.replace('-','_')==name):
                self.remove_child(idx)
                return
        for idx, d in enumerate(self.descriptors):
            if d.__class__.__name__==name:
                del self.descriptors[idx]
                if d.size:
                    self.size -= d.size
                self._invalidate()
                return
        raise AttributeError(name)
        
    def _field_repr(self, exclude=[]):
        fields = []
        exclude = exclude + ['atom_type']
        for k,v in self._fields.iteritems():
            if k[0] != '_' and not k in exclude:
                if isinstance(v, (list,dict)):
                    if not v:
                        continue
                fields.append('%s=%s'%(k,str(v)))
        return fields

    def _int_field_repr(self, fields, names):
        for name in names:
            fields.append('%s=%d'%(name,self.__getattribute__(name)))
        return fields

    def __repr__(self):
        fields = self._field_repr()
        fields = ','.join(fields)
        return ''.join([self.atom_type,'(',fields,')'])

    def find_parent(self,atom_type):
        if self.parent:
            if self.parent.atom_type==atom_type:
                return self.parent
            return self.parent.find_parent(atom_type)
        raise AttributeError(atom_type)

    def find_child(self, atom_type):
        for child in self.children:
            if child.atom_type == atom_type:
                return child
            child = child.find_child(atom_type)
            if child:
                return child
        return None

    def index(self, atom_type):
        for idx, c in enumerate(self.children):
            if c.atom_type==atom_type:
                return idx
        raise ValueError(atom_type)

    def insert_child(self, index, child):
        self.children.insert(index, child)
        if child.size:
            self.size += child.size
        self._invalidate()

    def remove_child(self, idx):
        child = self.children[idx]
        del self.children[idx]
        if child.size:
            self.size += child.size
        self._invalidate()
        
    @classmethod
    def create(cls, src, parent=None):
        if parent is not None:
            cursor = parent.payload_start
            end = parent.position + parent.size
        else:
            parent = Mp4Atom(position=src.tell(), atom_type='wrap')
            end=None
            cursor = 0
        rv = parent.children
        while end is None or cursor<end:
            src.seek(cursor)
            hdr = Mp4Atom.parse(src, parent)
            if hdr is None:
                break
            src.seek(hdr["position"])
            try:
                Box = MP4_BOXES[hdr['atom_type']]
            except KeyError,k:
                Box = Mp4Atom
            #print('create',hdr['atom_type'], Box.__class__.__name__)
            kwargs = Box.parse(src, parent)
            atom = Box(**kwargs)
            atom.payload_start = src.tell()
            rv.append(atom)
            if atom.parse_children:
                Mp4Atom.create(src, atom)
            src.seek(hdr["position"])
            atom._encoded = src.read(atom.size)
            cursor += atom.size
        return rv
        
    @classmethod
    def parse(cls, src, parent):
        position = src.tell()
        size = src.read(4)
        if not size or len(size)!=4:
            return None
        size = struct.unpack('>I', size)[0]
        atom_type = src.read(4)
        if not atom_type:
            return None
        if size == 0:
            pos = src.tell()
            src.seek(0,2) # seek to end
            size = src.tell() - pos
            src.seek(pos)
        elif size == 1:
            size = struct.unpack('>Q', src.read(8))[0]
            if not size:
                return None
        if atom_type=='uuid':
            atom_type = src.read(16)
        return {
            "atom_type": atom_type,
            "position": position,
            "size": size,
            "parent": parent,
        }

    @classmethod
    def create_descriptors(clz, src, parent, **kwargs):
        descriptors=[]
        end = kwargs["position"]+kwargs["size"]
        while src.tell()<end:
            d = Descriptor.create(src, parent)
            assert isinstance(d, Descriptor)
            descriptors.append(d)
            dc = d
            while src.tell() < (d.position+d.size):
                dc = Descriptor.create(src, dc)
                descriptors.append(dc)
            src.seek(d.position + d.size + d.header_size)
        return descriptors

    def encode(self, dest=None):
        out = dest
        if out is None:
            out = StringIO.StringIO()
        #print('encode',self.atom_type, self.size, out.tell())
        if self._encoded is not None:
            #print('  _encoded=',len(self._encoded))
            out.write(self._encoded)
            if dest is None:
                return out.getvalue()
            return dest
        if len(self.atom_type)>4:
            assert len(self.atom_type)==16
            t = 'uuid' + self.atom_type
        else:
            assert len(self.atom_type)==4
            t = self.atom_type
        self.position = out.tell()
        out.write(struct.pack('>I', 4+len(t)))
        out.write(t)
        self.encode_fields(dest=out)
        for child in self.children:
            child.encode(dest=out)
        self.size = out.tell() - self.position
        out.seek(self.position)
        # replace the length field
        out.write(struct.pack('>I', self.size))
        out.seek(0,2) # seek to end
        #print('  produced',self.size)
        if dest is None:
            return out.getvalue()
        return dest

    def encode_fields(self, dest):
        pass
    
    def dump(self, indent=''):
        print('{}{}: {:d} -> {:d} [{:d} bytes]'.format(indent, self.atom_type, self.position,
                                                       self.position+self.size, self.size))
        for c in self.children:
            c.dump(indent+'  ')

class Descriptor(object):
    def __init__(self, tag, parent, **kwargs):
        self.tag = tag
        self.parent = parent
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    @classmethod
    def create(clz, src, parent, **kwargs):
        pos = src.tell()
        tag = struct.unpack('B', src.read(1))[0]
        try:
            Desc = MP4_DESCRIPTORS[tag]
        except KeyError:
            Desc = Descriptor
        src.seek(pos)
        kw = Desc.parse(src, parent)
        del kw["tag"]
        return Desc(tag, parent, **kw)

    @classmethod
    def parse(clz, src, parent):
        position = src.tell()
        tag = struct.unpack('B', src.read(1))[0]
        header_size=1
        more_bytes = True
        size = 0
        while more_bytes:
            header_size += 1
            b = struct.unpack('B', src.read(1))[0]
            more_bytes = b & 0x80
            size = (size<<7) + (b&0x7f)
        return {
            "position": position,
            "tag": tag,
            "header_size": header_size,
            "size": size,
        }

    def _field_repr(self):
        rv = []
        for k,v in self.__dict__.iteritems():
            if k!='parent':
                rv.append('%s=%s'%(k,str(v)))
        return rv
        #return ['tag=0x%x'%self.tag, 'size=%d'%self.size,'position=%d'%self.position]
    def __repr__(self):
        fields = self._field_repr()
        fields = ','.join(fields)
        return ''.join([ self.__class__.__name__, '(',fields,')'])

class ESDescriptor(Descriptor):
    @classmethod
    def parse(clz, src, parent):
        rv = Descriptor.parse(src, parent)
        rv["es_id"] = struct.unpack('>H', src.read(2))[0]
        b = struct.unpack('B', src.read(1))[0]
        rv["stream_dependence_flag"] = (b&0x80)==0x80
        rv["url_flag"] = (b&0x40)==0x40
        rv["ocr_stream_flag"] = (b&0x20)==0x20
        rv["stream_priority"] = b&0x1f
        if rv["stream_dependence_flag"]:
            rv["depends_on_es_id"] = struct.unpack('>H', src.read(2))[0]
        if rv["url_flag"]:
            leng = struct.unpack('B', src.read(1))[0]
            rv["url"] = src.read(leng)
        if rv["ocr_stream_flag"]:
            rv["ocr_es_id"] = struct.unpack('>H', src.read(2))[0]
        #if src.tell() < (rv["position"]+rv["size"]):
        #    d = self.parent.parse_descriptor(src)
        #    self.parent.descriptors.append(d)
        return rv
MP4_DESCRIPTORS[0x03]=ESDescriptor

class DecoderConfigDescriptor(Descriptor):
    @classmethod
    def parse(clz, src, parent):
        rv = Descriptor.parse(src, parent)
        rv["object_type"] = struct.unpack('B', src.read(1))[0]
        b = struct.unpack('B', src.read(1))[0]
        rv["stream_type"] = (b>>2)
        rv["upstream"] = (b&0x02)==0x02
        f = '\000'+src.read(3)
        rv["buffer_size"] = struct.unpack('>I',f)[0]
        rv["max_bitrate"] = struct.unpack('>I', src.read(4))[0]
        rv["avg_bitrate"] = struct.unpack('>I', src.read(4))[0]
        #if src.tell() < (rv["position"]+rv["size"]):
        #    d = self.parent.parse_descriptor(src, object_type=self.object_type)
        #    self.parent.descriptors.append(d)
        return rv
MP4_DESCRIPTORS[0x04] = DecoderConfigDescriptor

class DecoderSpecificInfo(Descriptor):
    SAMPLE_RATES=[ 96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350 ]
    @classmethod
    def parse(clz, src, parent):
        rv = Descriptor.parse(src, parent)
        rv["object_type"] = parent.object_type
        data = src.read(rv["size"])
        bs = ConstBitStream(bytes=data)
        if rv["object_type"]==0x40: # Audio ISO/IEC 14496-3 subpart 1
            rv["audio_object_type"] = bs.read('uint:5')
            rv["sampling_frequency_index"] = bs.read('uint:4')
            if rv["sampling_frequency_index"]==0xf:
                rv["sampling_frequency"] = bs.read('uint:24')
            else:
                rv["sampling_frequency"] = clz.SAMPLE_RATES[rv["sampling_frequency_index"]]
            rv["channel_configuration"] = bs.read('uint:4')
            rv["frame_length_flag"] =  bs.read('bool')
            rv["depends_on_core_coder"] =  bs.read('uint:1')
            if rv["depends_on_core_coder"]:
                rv["core_coder_delay"] = bs.read('uint:14')
            rv["extension_flag"] =  bs.read('bool')
            #if not rv["channel_configuration"]:
            #    rv["channel_configuration"] = clz.parse_config_element(src, parent)
            if rv["audio_object_type"] == 6 or rv["audio_object_type"] == 20:
                rv["layer_nr"] = bs.read('uint:3')
            if rv["extension_flag"]:
                if rv["audio_object_type"]==22:
                    rv["num_sub_frame"] = bs.read('uint:5')
                    rv["layer_length"] = bs.read('uint:11')
                if rv["audio_object_type"]==17 or rv["audio_object_type"]==19 or rv["audio_object_type"]==20 or rv["audio_object_type"]==23:
                    rv["aac_section_data_resilience_flag"] =  bs.read('bool')
                    rv["aac_scalefactor_data_resilience_flag"] =  bs.read('bool')
                    rv["aac_spectral_data_resilience_flag"] =  bs.read('bool')
                rv["extension_flag_3"] =  bs.read('bool')
            return rv
MP4_DESCRIPTORS[0x05] = DecoderSpecificInfo


class FullBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent):
        kwargs = Mp4Atom.parse(src, parent)
        #print 'parse FullBox'
        kwargs["version"] = struct.unpack('B', src.read(1))[0]
        f = '\000'+src.read(3)
        kwargs["flags"] = struct.unpack('>I', f)[0]
        return kwargs

    def _field_repr(self, **args):
        if not args.has_key('exclude'):
            args['exclude'] = []
        args['exclude'].append('flags')
        fields = super(FullBox,self)._field_repr(**args)
        fields.append('flags=0x%x'%self.flags)
        return fields

    def encode_fields(self, dest, payload=None):
        dest.write(struct.pack('B', self.version))
        dest.write(struct.pack('>I', self.flags)[1:])
        if payload is not None:
            dest.write(payload)

class BoxWithChildren(Mp4Atom):
    parse_children = True

for box in ['mdia', 'minf', 'mvex', 'moof', 'moov', 'schi', 'sinf', 'stbl', 'traf', 'trak']:
    MP4_BOXES[box] = BoxWithChildren

class SampleEntry(Mp4Atom):
    @classmethod
    def parse(clz, src, parent):
        kwargs = Mp4Atom.parse(src, parent)
        #unsigned int(32) format
        src.read(6) # reserved
        kwargs["data_reference_index"] = struct.unpack('>H', src.read(2))[0]
        return kwargs

class VisualSampleEntry(SampleEntry):
    parse_children = True
    @classmethod
    def parse(self, src, parent):
        kwargs = SampleEntry.parse(src, parent)
        kwargs["pre_defined"] = struct.unpack('>H', src.read(2))[0]
        src.read(2) # reserved
        src.read(12) # unsigned int(32)[3] pre_defined = 0;
        kwargs["width"] = struct.unpack('>H', src.read(2))[0]
        kwargs["height"] = struct.unpack('>H', src.read(2))[0]
        kwargs["horizresolution"] = struct.unpack('>I', src.read(4))[0] / 65536.0
        kwargs["vertresolution"] = struct.unpack('>I', src.read(4))[0] / 65536.0
        src.read(4) # reserved
        kwargs["frame_count"] = struct.unpack('>H', src.read(2))[0]
        kwargs["compressorname"] = src.read(32)
        kwargs["depth"] = struct.unpack('>H', src.read(2))[0]
        src.read(2) # int(16) pre_defined = -1;
        return kwargs

class AVCConfigurationBox(Mp4Atom):
    #class AVCDecoderConfigurationRecord(object):
    @classmethod
    def parse(self, src, parent):
        kwargs = Mp4Atom.parse(src, parent)
        kwargs["configurationVersion"] = struct.unpack('B', src.read(1))[0]
        kwargs["AVCProfileIndication"] = struct.unpack('B', src.read(1))[0]
        kwargs["profile_compatibility"] = struct.unpack('B', src.read(1))[0]
        kwargs["AVCLevelIndication"] = struct.unpack('B', src.read(1))[0]
        b0 = struct.unpack('B', src.read(1))[0]
        kwargs["lengthSizeMinusOne"] = b0 & 0x03
        b0 = struct.unpack('B', src.read(1))[0]
        numOfSequenceParameterSets = b0 & 0x1F
        kwargs["sps"] = []
        for i in range(numOfSequenceParameterSets):
            sequenceParameterSetLength = struct.unpack('>H', src.read(2))[0]
            sequenceParameterSetNALUnit = src.read(sequenceParameterSetLength)
            kwargs["sps"].append(sequenceParameterSetNALUnit)
        numOfPictureParameterSets = struct.unpack('B', src.read(1))[0]
        kwargs["pps"] = []
        for i in range(numOfPictureParameterSets):
            pictureParameterSetLength = struct.unpack('>H', src.read(2))[0]
            pictureParameterSetNALUnit = src.read(pictureParameterSetLength)
            kwargs["pps"].append(pictureParameterSetNALUnit)
        return kwargs
MP4_BOXES['avcC'] = AVCConfigurationBox

class AVCSampleEntry(VisualSampleEntry):
    pass
MP4_BOXES['avc1'] = AVCSampleEntry
MP4_BOXES['avc3'] = AVCSampleEntry
MP4_BOXES['encv'] = AVCSampleEntry

class EC3SampleEntry(SampleEntry):
    parse_children = True
    @classmethod
    def parse(clz, src, parent):
        kwargs = SampleEntry.parse(src, parent)
        src.read(8) # reserved
        kwargs["channel_count"] = struct.unpack('>H', src.read(2))[0]
        kwargs["sample_size"] = struct.unpack('>H', src.read(2))[0]
        src.read(4) # reserved
        kwargs["sampling_frequency"] = struct.unpack('>H', src.read(2))[0]
        src.read(2) # reserved
        return kwargs
MP4_BOXES['ec-3'] = EC3SampleEntry

class EC3SpecificBox(Mp4Atom):
    ACMOD_NUM_CHANS = [2,1,2,3,3,4,4,5]

    class SubStream(object):
        def __init__(self, bs):
            self.fscod = bs.read('uint:2')
            self.bsid = bs.read('uint:5')
            self.bsmod = bs.read('uint:5')
            self.acmod = bs.read('uint:3')
            self.channel_count = EC3SpecificBox.ACMOD_NUM_CHANS[self.acmod]
            self.lfeon = bs.read('bool')
            bs.read('uint:3') #reserved
            self.num_dep_sub  = bs.read('uint:4')
            if self.num_dep_sub>0:
                self.chan_loc = bs.read('uint:9')
            else:
                bs.read('uint:1') #reserved
        def __repr__(self):
            fields = []
            for k,v in self.__dict__.iteritems():
                if k!='parent':
                    fields.append('%s=%s'%(k,str(v)))
            fields = ','.join(fields)
            return ''.join([ self.__class__.__name__, '(',fields,')'])

    @classmethod
    def parse(clz, src, parent):
        kwargs = Mp4Atom.parse(src, parent)
        data = src.read(kwargs["size"])
        bs = ConstBitStream(bytes=data)
        kwargs["data_rate"] = bs.read('uint:13')
        num_ind_sub = 1+bs.read('uint:3')
        kwargs["substreams"] = []
        for i in range(num_ind_sub):
            kwargs["substreams"].append(EC3SpecificBox.SubStream(bs))
        return kwargs
MP4_BOXES['dec3'] = EC3SpecificBox

class OriginalFormatBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent):
        kwargs = Mp4Atom.parse(src, parent)
        kwargs["data_format"] = src.read(4)
        return kwargs
MP4_BOXES['frma'] = OriginalFormatBox

class MP4A(Mp4Atom):
    parse_children = True
    @classmethod
    def parse(clz, src, parent):
        kwargs = Mp4Atom.parse(src, parent)
        src.read(6) # (8)[6] reserved
        kwargs["data_reference_index"] = struct.unpack('>H', src.read(2))[0]
        src.read(8+4+4) # (32)[2], (16)[2], (32) reserved
        kwargs["timescale"] = struct.unpack('>H', src.read(2))[0]
        src.read(2) # (16) reserved
        return kwargs
MP4_BOXES['mp4a'] = MP4A
MP4_BOXES['enca'] = MP4A


class ESDescriptorBox(FullBox):
    #def __init__(self, *args, **kwargs):
    #    super(ESDescriptorBox, self).__init__(*args, **kwargs)
    #    self.descriptors = map(lambda d: Descriptor.from_kwargs(**d), self.descriptors)
    
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["descriptors"] = FullBox.create_descriptors(src, **kwargs)
        return kwargs
MP4_BOXES['esds'] = ESDescriptorBox

class SampleDescriptionBox(FullBox):
    parse_children = True
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["entry_count"] = struct.unpack('>I', src.read(4))[0]
        return kwargs
MP4_BOXES['stsd'] = SampleDescriptionBox

class TrackFragmentHeaderBox(FullBox):
    base_data_offset_present = 0x000001
    sample_description_index_present = 0x000002
    default_sample_duration_present = 0x000008
    default_sample_size_present = 0x000010
    default_sample_flags_present = 0x000020
    duration_is_empty = 0x010000

    def __init__(self, *args, **kwargs):
        super(TrackFragmentHeaderBox, self).__init__(*args, **kwargs)
        #default base offset = first byte of moof
        if self.base_data_offset is None:
            self.base_data_offset= self.find_parent('moof').position
        
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["base_data_offset"] = 0
        kwargs["sample_description_index"] = 0
        kwargs["default_sample_duration"] = 0
        kwargs["default_sample_size"] = 0
        kwargs["default_sample_flags"] = 0
        kwargs["track_id"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.base_data_offset_present:
            kwargs["base_data_offset"] = struct.unpack('>Q', src.read(8))[0]
        else:
            kwargs["base_data_offset"] = None
        if kwargs["flags"] & clz.sample_description_index_present:
            kwargs["sample_description_index"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.default_sample_duration_present:
            kwargs["default_sample_duration"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.default_sample_size_present:
            kwargs["default_sample_size"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.default_sample_flags_present:
            kwargs["default_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def _field_repr(self):
        fields = super(TrackFragmentHeaderBox,self)._field_repr(exclude=['default_sample_flags'])
        fields.append('default_sample_flags=0x%08x'%self.default_sample_flags)
        return fields
MP4_BOXES['tfhd'] = TrackFragmentHeaderBox

class TrackHeaderBox(FullBox):
    Track_enabled    = 0x000001
    Track_in_movie   = 0x000002
    Track_in_preview = 0x000004

    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["is_enabled"] = (kwargs["flags"] & clz.Track_enabled)==clz.Track_enabled
        kwargs["in_movie"] = (kwargs["flags"] & clz.Track_in_movie)==clz.Track_in_movie
        kwargs["in_preview"] = (kwargs["flags"] & clz.Track_in_preview)==clz.Track_in_preview
        if kwargs["version"]==1:
            kwargs["creation_time"] = struct.unpack('>Q', src.read(8))[0]
            kwargs["modification_time"] = struct.unpack('>Q', src.read(8))[0]
            kwargs["track_id"] = struct.unpack('>I', src.read(4))[0]
            src.read(4) # reserved
            kwargs["duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            kwargs["creation_time"] = struct.unpack('>I', src.read(4))[0]
            kwargs["modification_time"] = struct.unpack('>I', src.read(4))[0]
            kwargs["track_id"] = struct.unpack('>I', src.read(4))[0]
            src.read(4) # reserved
            kwargs["duration"] = struct.unpack('>I', src.read(4))[0]
        src.read(8) # 2 x 32 bits reserved
        kwargs["layer"] = struct.unpack('>H', src.read(2))[0]
        kwargs["alternate_group"] = struct.unpack('>H', src.read(2))[0]
        kwargs["volume"] = struct.unpack('>H', src.read(2))[0] / 256.0  # value is fixed point 8.8
        src.read(2) # reserved
        kwargs["matrix"] = []
        for i in range(9):
            kwargs["matrix"].append( struct.unpack('>I', src.read(4))[0] )
        kwargs["width"] = struct.unpack('>I', src.read(4))[0] / 65536.0 # value is fixed point 16.16
        kwargs["height"] = struct.unpack('>I', src.read(4))[0] / 65536.0 # value is fixed point 16.16
        kwargs["creation_time"] = ISO_EPOCH + datetime.timedelta(seconds=kwargs["creation_time"])
        kwargs["modification_time"] = ISO_EPOCH + datetime.timedelta(seconds=kwargs["modification_time"])
        return kwargs
MP4_BOXES['tkhd'] = TrackHeaderBox

class TrackFragmentDecodeTimeBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        if kwargs["version"]==1:
            kwargs["base_media_decode_time"] = struct.unpack('>Q', src.read(8))[0]
        else:
            kwargs["base_media_decode_time"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        payload = StringIO.StringIO()
        if self.base_media_decode_time > long(1<<32):
            self.version = 1
        else:
            self.version = 0
        if self.version==1:
            payload.write(struct.pack('>Q', self.base_media_decode_time))
        else:
            payload.write(struct.pack('>I', self.base_media_decode_time))
        return super(TrackFragmentDecodeTimeBox, self).encode_fields(dest=dest, payload=payload.getvalue())

MP4_BOXES['tfdt'] = TrackFragmentDecodeTimeBox

class TrackExtendsBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["track_id"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_description_index"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_duration"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_size"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        return kwargs
MP4_BOXES['trex'] = TrackExtendsBox

class MediaHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        if kwargs["version"]==1:
            kwargs["creation_time"] = struct.unpack('>Q', src.read(8))[0]
            kwargs["modification_time"] = struct.unpack('>Q', src.read(8))[0]
            kwargs["timescale"] = struct.unpack('>I', src.read(4))[0]
            kwargs["duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            kwargs["creation_time"] = struct.unpack('>I', src.read(4))[0]
            kwargs["modification_time"] = struct.unpack('>I', src.read(4))[0]
            kwargs["timescale"] = struct.unpack('>I', src.read(4))[0]
            kwargs["duration"] = struct.unpack('>I', src.read(4))[0]
        kwargs["creation_time"] = ISO_EPOCH + datetime.timedelta(seconds=kwargs["creation_time"])
        kwargs["modification_time"] = ISO_EPOCH + datetime.timedelta(seconds=kwargs["modification_time"])
        tmp = struct.unpack('>H', src.read(2))[0]
        kwargs["language"] = chr(0x60+((tmp>>10)&0x1F)) + chr(0x60+((tmp>>5)&0x1F)) + chr(0x60+(tmp&0x1F))
        return kwargs

    def _field_repr(self):
        fields = super(MediaHeaderBox,self)._field_repr(exclude=['creation_time','modification_time'])
        fields.append('creation_time=%s'%utils.toIsoDateTime(self.creation_time))
        fields.append('modification_time=%s'%utils.toIsoDateTime(self.modification_time))
        return fields
MP4_BOXES['mdhd'] = MediaHeaderBox

class MovieFragmentHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["sequence_number"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        payload = struct.pack('>I', self.sequence_number)
        super(MovieFragmentHeaderBox, self).encode_fields(dest=dest, payload=payload)
    
MP4_BOXES['mfhd'] = MovieFragmentHeaderBox

class HandlerBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        src.read(4) # unsigned int(32) pre_defined = 0
        kwargs["handler_type"] = src.read(4)
        src.read(12) # const unsigned int(32)[3] reserved = 0;
        name_len = kwargs["position"] + kwargs["size"] - src.tell()
        kwargs["name"] = src.read(name_len)
        return kwargs
MP4_BOXES['hdlr'] = HandlerBox

class MovieExtendsHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        if kwargs["version"]==1:
            kwargs["fragment_duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            kwargs["fragment_duration"] = struct.unpack('>I', src.read(4))[0]
        return kwargs
MP4_BOXES['mehd'] = MovieExtendsHeaderBox


class SampleAuxiliaryInformationSizesBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        if kwargs["flags"] & 1:
            kwargs["aux_info_type"] = clz.check_info_type(struct.unpack('>I',
                                                                        src.read(4))[0])
            kwargs["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_info_size"] = struct.unpack('B', src.read(1))[0]
        kwargs["sample_info_sizes"] = []
        sample_count = struct.unpack('>I', src.read(4))[0]
        if kwargs["default_sample_info_size"] == 0:
            for i in range(sample_count):
                kwargs["sample_info_sizes"].append(struct.unpack('B', src.read(1))[0])
        return kwargs

    @classmethod
    def check_info_type(clz, info_type):
        a = (info_type >> 24) & 0xFF
        b = (info_type >> 16) & 0xFF
        c = (info_type >> 8) & 0xFF
        d = (info_type) & 0xFF
        s = chr(a)+chr(b)+chr(c)+chr(d)
        if s.isalpha():
            return s
        return info_type

    def encode_fields(self, dest):
        payload = StringIO.StringIO()
        if self.flags & 1:
            if isinstance(self.aux_info_type, basestring):
                payload.write(self.aux_info_type)
            else:
                payload.write(struct.pack('>I', self.aux_info_type))
            payload.write(struct.pack('>I', self.aux_info_type_parameter))
        payload.write(struct.pack('B', self.default_sample_info_size))
        payload.write(struct.pack('>I', len(self.sample_info_sizes)))
        if self.default_sample_info_size == 0:
            for sz in self.sample_info_sizes:
                payload.write(struct.pack('B', sz))
        super(SampleAuxiliaryInformationSizesBox, self).encode_fields(dest=dest,
                                                                      payload=payload)

    def _field_repr(self, **args):
        if not args.has_key('exclude'):
            args['exclude'] = []
        args['exclude'].append('aux_info_type')
        fields = super(FullBox,self)._field_repr(**args)
        if self._fields.has_key("aux_info_type"):
            if isinstance(self.aux_info_type, basestring):
                fields.append('aux_info_type="%s"'%self.aux_info_type)
            else:
                fields.append('aux_info_type=0x%x'%self.aux_info_type)
        return fields

MP4_BOXES['saiz'] = SampleAuxiliaryInformationSizesBox


class CencSampleAuxiliaryData(object):
    def __init__(self, **kwargs):
        for key,value in kwargs.iteritems():
            assert "src" != key
            setattr(self, key, value)

    @classmethod
    def parse(clz, src, size, iv_size, flags, parent):
        rv = {}
        rv["initialization_vector"] = src.read(iv_size)
        if (flags & 0x02) == 0x02 and size >= iv_size+2:
            rv["subsamples"] = []
            subsample_count = struct.unpack('>H', src.read(2))[0]
            if size < subsample_count*6:
                print 'Invalid subsample_count %d'%subsample_count
                return rv
            for i in range(subsample_count):
                s = {
                    'clear': struct.unpack('>H', src.read(2))[0],
                    'encrypted': struct.unpack('>I', src.read(4))[0],
                }
                rv["subsamples"].append(s)
        return rv

    def encode_fields(self, dest):
        dest.write(self.initialization_vector)
        if hasattr(self, "subsamples"):
            for s in self.subsamples:
                dest.write(struct.pack('>H', s['clear']))
                dest.write(struct.pack('>I', s['encrypted']))

    def _field_repr(self):
        rv = []
        rv.append('initialization_vector=0x%s'%self.initialization_vector.encode('hex'))
        if hasattr(self, "subsamples"):
            subsamples = []
            for s in self.subsamples:
                subsamples.append('{"clear":%d, "encrypted":%d}'%(s["clear"], s["encrypted"]))
            rv.append('subsamples=[%s]'%(','.join(subsamples)))
        return rv

    def __repr__(self):
        fields = self._field_repr()
        fields = ','.join(fields)
        return ''.join([ self.__class__.__name__, '(',fields,')'])


class CencSampleEncryptionBox(FullBox):
    def __init__(self, **kwargs):
        super(CencSampleEncryptionBox, self).__init__(**kwargs)
        if self._fields.has_key("samples"):
            self._fields["samples"] = map(lambda s: CencSampleAuxiliaryData(**s), self._fields["samples"])

    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        if kwargs["flags"] & 0x01:
            f = '\000'+src.read(3)
            kwargs["algorithm_id"] = struct.unpack('>I',f)[0]
            kwargs["iv_size"] = struct.unpack('B', src.read(1))[0]
            if kwargs["iv_size"] == 0:
                kwargs["iv_size"] = 8
            kwargs["kid"] = src.read(16)
        else:
            try:
                moov = parent.find_parent("moov")
            except AttributeError:
                p = parent
                while p.parent:
                    p = p.parent
                try:
                    moov = p.moov
                except AttributeError:
                    return kwargs
            tenc = moov.find_child("tenc")
            if tenc is None:
                return kwargs
            kwargs["iv_size"] = tenc.iv_size
        num_entries = struct.unpack('>I', src.read(4))[0]
        kwargs["subsample_count"] = num_entries
        kwargs["samples"] = []
        saiz = parent.saiz
        for i in range(num_entries):
            size = saiz.sample_info_sizes[i] if saiz.sample_info_sizes else saiz.default_sample_info_size
            if size:
                s = CencSampleAuxiliaryData.parse(src, size, kwargs["iv_size"], kwargs["flags"], parent)
                kwargs["samples"].append(s)
        return kwargs

    def encode_fields(self, dest):
        payload = StringIO.StringIO()
        if self.flags & 0x01:
            payload.write(struct.pack('>I', self.algorithm_id))
            payload.write(struct.pack('B', self.iv_size))
            payload.write(self.kid)
        payload.write(struct.pack('>I', len(self.samples)))
        for s in self.samples:
            s.encode_fields(payload)
        return super(CencSampleEncryptionBox, self).encode_fields(dest=dest, payload=payload.getvalue())

    def _field_repr(self, **args):
        if not args.has_key('exclude'):
            args['exclude'] = []
        args['exclude'] += ['kid', 'samples']
        fields = super(CencSampleEncryptionBox,self)._field_repr(**args)
        try:
            fields.append("kid=0x%s"%self.kid.encode('hex'))
        except AttributeError:
            pass
        if self._fields.has_key("samples"):
            samples = map(lambda s: repr(s), self.samples)
            fields.append("samples=[%s]"%(','.join(samples)))
        return fields

MP4_BOXES["senc"] = CencSampleEncryptionBox

class SampleAuxiliaryInformationOffsetsBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        if kwargs["flags"] & 0x01:
            kwargs["aux_info_type"] = clz.check_info_type(struct.unpack('>I',
                                                                        src.read(4))[0])
            kwargs["aux_info_type_parameter"] = struct.unpack('>I', src.read(4))[0]
        entry_count = struct.unpack('>I', src.read(4))[0]
        kwargs["offsets"] = []
        for i in range(entry_count):
            if kwargs["version"] == 0:
                o = struct.unpack('>I', src.read(4))[0]
            else:
                o = struct.unpack('>Q', src.read(8))[0]
            kwargs["offsets"].append(o)
        return kwargs

    def encode_fields(self, dest):
        payload = StringIO.StringIO()
        if self.flags & 0x01:
            if isinstance(self.aux_info_type, basestring):
                payload.write(self.aux_info_type)
            else:
                payload.write(struct.pack('>I', self.aux_info_type))
            payload.write(struct.pack('>I', self.aux_info_type_parameter))
        payload.write(struct.pack('>I', len(self.offsets)))
        for off in self.offsets:
            if self.version == 0:
                payload.write(struct.pack('>I', off))
            else:
                payload.write(struct.pack('>Q', off))
        super(SampleAuxiliaryInformationOffsetsBox, self).encode_fields(dest=dest,
                                                                        payload=payload)

    def _field_repr(self, **args):
        if not args.has_key('exclude'):
            args['exclude'] = []
        args['exclude'].append('aux_info_type')
        fields = super(FullBox,self)._field_repr(**args)
        if self._fields.has_key("aux_info_type"):
            if isinstance(self.aux_info_type, basestring):
                fields.append('aux_info_type="%s"'%self.aux_info_type)
            else:
                fields.append('aux_info_type=0x%x'%self.aux_info_type)
        return fields
SampleAuxiliaryInformationOffsetsBox.check_info_type = SampleAuxiliaryInformationSizesBox.check_info_type

MP4_BOXES['saio'] = SampleAuxiliaryInformationOffsetsBox


class TrackSample(object):
    def __init__(self,index, offset):
        self.index = index
        self.offset = offset
        self.duration = None
        self.size = None
        self.flags = None
        self.composition_time_offset = None

    def __repr__(self, *args, **kwargs):
        rv = [str(self.index),str(self.offset)]
        if self.duration is not None:
            rv.append('duration=%d'%self.duration)
        if self.size is not None:
            rv.append('size=%d'%self.size)
        if self.flags is not None:
            rv.append('flags=0x%x'%self.flags)
        if self.composition_time_offset is not None:
            rv.append('composition_time_offset=%d'%self.composition_time_offset)
        return ''.join(['TrackSample(', ','.join(rv), ')'])

class TrackFragmentRunBox(FullBox):
    data_offset_present = 0x000001
    first_sample_flags_present = 0x000004
    sample_duration_present = 0x000100 #each sample has its own duration?
    sample_size_present = 0x000200 #each sample has its own size, otherwise the default is used.
    sample_flags_present = 0x000400 # each sample has its own flags, otherwise the default is used.
    sample_composition_time_offsets_present = 0x000800

    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        tfhd = parent.tfhd
        sample_count = struct.unpack('>I', src.read(4))[0]
        kwargs["sample_count"] = sample_count
        if kwargs["flags"] & clz.data_offset_present:
            kwargs["data_offset"] = struct.unpack('>i', src.read(4))[0]
        else:
            kwargs["data_offset"] = 0
        kwargs["data_offset"] += tfhd.base_data_offset
        if kwargs["flags"] & clz.first_sample_flags_present:
            kwargs["first_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        else:
            kwargs["first_sample_flags"] = 0
        #print('Trun: count=%d offset=%d flags=%x'%(kwargs["sample_count,kwargs["data_offset,kwargs["first_sample_flags))
        kwargs["samples"] = []
        offset = kwargs["data_offset"]
        for i in range(sample_count):
            ts = TrackSample(i,offset)
            if kwargs["flags"] & clz.sample_duration_present:
                ts.duration = struct.unpack('>I', src.read(4))[0]
            elif tfhd.default_sample_duration:
                ts.duration = tfhd.default_sample_duration
            if kwargs["flags"] & clz.sample_size_present:
                ts.size = struct.unpack('>I', src.read(4))[0]
            else:
                ts.size = tfhd.default_sample_size
            if kwargs["flags"] & clz.sample_flags_present:
                ts.flags = struct.unpack('>I', src.read(4))[0]
            else:
                ts.flags = tfhd.default_sample_flags
            if i==0 and (kwargs["flags"] & clz.first_sample_flags_present):
                ts.flags = kwargs["first_sample_flags"]
            if kwargs["flags"] & clz.sample_composition_time_offsets_present:
                ts.composition_time_offset = struct.unpack('>i', src.read(4))[0]
            #print ts
            kwargs["samples"].append(ts)
            offset += ts.size
        return kwargs

    def parse_samples(self, src, nal_length_field_length):
        for sample in self.samples:
            pos = 0
            sample.nals = []
            while pos<sample.size:
                src.seek(sample.offset+pos)
                nal = Nal(src,nal_length_field_length)
                pos += nal.size + nal_length_field_length
                sample.nals.append(nal)
MP4_BOXES['trun']=TrackFragmentRunBox

class TrackEncryptionBox(FullBox):
    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["is_encrypted"] = struct.unpack('>I', '\0'+src.read(3))[0]
        kwargs["iv_size"] = struct.unpack('B', src.read(1))[0]
        kwargs["default_kid"] = src.read(16)
        return kwargs
    def _field_repr(self, **args):
        if not args.has_key('exclude'):
            args['exclude'] = []
        args['exclude'].append('default_kid')
        fields = super(TrackEncryptionBox,self)._field_repr(**args)
        fields.append('default_kid=0x{}'.format(self.default_kid.encode('hex')))
        return fields
MP4_BOXES['tenc']=TrackEncryptionBox

class ContentProtectionSpecificBox(FullBox):
    def __init__(self, **kwargs):
        super(ContentProtectionSpecificBox, self).__init__(**kwargs)
        if '-' in self.system_id:
            self.system_id = self.system_id.replace('-','')

    @classmethod
    def parse(clz, src, parent):
        kwargs = FullBox.parse(src, parent)
        kwargs["system_id"] = src.read(16).encode('hex')
        if kwargs["version"] > 0:
            kid_count = struct.unpack('>I', src.read(4))[0]
            kwargs["key_ids"] = []
            for i in range(kid_count):
                kid = src.read(16)
                kwargs["key_ids"].append(kid.encode('hex'))
        data_size = struct.unpack('>I', src.read(4))[0]
        if data_size > 0:
            kwargs["data"] = src.read(data_size)
        else:
            kwargs["data"] = None
        return kwargs

    def encode_fields(self, dest):
        payload = StringIO.StringIO()
        payload.write(self.system_id.decode('hex'))
        if self.version > 0:
            payload.write(struct.pack('>I', len(self.key_ids)))
            for kid in self.key_ids:
                payload.write(kid.decode('hex'))
        if self.data is None:
            payload.write(struct.pack('>I',0))
        else:
            payload.write(struct.pack('>I',len(self.data)))
            payload.write(self.data)
        return super(ContentProtectionSpecificBox, self).encode_fields(dest=dest, payload=payload.getvalue())

    def _field_repr(self, **args):
        if not args.has_key('exclude'):
            args['exclude'] = []
        args['exclude'].append('data')
        fields = super(FullBox,self)._field_repr(**args)
        if self._fields["data"] is not None:
            data = '"{}"'.format(base64.b64encode(self._fields["data"]))
        else:
            data = "None"
        fields.append('data={}'.format(data))
        return fields
MP4_BOXES['pssh'] = ContentProtectionSpecificBox

class IsoParser(object):
    def walk_atoms(self, filename, atom=None):
        atoms = None
        src = None
        try:
            if isinstance(filename,(str,unicode)):
                src = io.FileIO(filename, "rb")
            else:
                src = filename
            atoms = Mp4Atom.create(src)
        finally:
            if src and isinstance(filename,(str,unicode)):
                src.close()
        return atoms

if __name__ == "__main__":
    def show_atom(atom_types, atom):
        if atom.atom_type in atom_types:
            print(atom)
        else:
            for child in atom.children:
                show_atom(atom_types, child)

    ap = argparse.ArgumentParser(description='MP4 parser')
    ap.add_argument('-d', '--debug', action="store_true")
    ap.add_argument('-s', '--show', help='Show contents of specified atom')
    ap.add_argument('-t', '--tree', action="store_true", help='Show atom tree')
    ap.add_argument('mp4file', help='Filename of MP4 file', nargs='+', default=None)
    args = ap.parse_args()
    for filename in args.mp4file:
        parser = IsoParser()
        atoms = parser.walk_atoms(filename)
        for atom in atoms:
            if args.tree:
                atom.dump()
            if args.show:
                #print('show_atom', args.show[0], atom)
                show_atom(args.show, atom)
