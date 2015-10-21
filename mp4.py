import datetime, io, struct

from bitstring import ConstBitStream
from nal import Nal
import utils

class ParseException(Exception):
    pass

# time values are in seconds since midnight, Jan. 1, 1904, in UTC time
ISO_EPOCH = datetime.datetime(year=1904, month=1, day=1, tzinfo=utils.UTC())

MP4_BOXES = {}
MP4_DESCRIPTORS = {}

class Mp4Atom(object):
    parse_children=False

    @classmethod
    def parse_atom_header(cls, src):
        position = src.tell()
        size = src.read(4)
        if not size:
            return None
        size = struct.unpack('>I', size)[0]
        type = src.read(4)
        if not type:
            return None
        if size == 0:
            pos = src.tell()
            src.seek(0,2) # seek to end
            size = src.tell() - cursor
            src.seek(pos)
        elif size == 1:
            size = struct.unpack('>Q', src.read(8))[0]
            if not size:
                return None
        if type=='uuid':
            type = src.read(16)
        return locals()

    def __init__(self, src, type, position, size, parent):
        self.position = position
        self.size = size
        self.type = type
        self.parent = parent
        self.children = []
        self.descriptors = []

    def __getattr__(self, name):
        for c in self.children:
            if '-' in c.type:
                if c.type.replace('-','_')==name:
                    return c
            elif c.type==name:
                return c
        for d in self.descriptors:
            if d.__class__.__name__==name:
                return d
        raise AttributeError(name)

    def _field_repr(self, exclude=[]):
        fields = []
        exclude = exclude + ['parent', 'type']
        for k,v in self.__dict__.iteritems():
            if not k in exclude:
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
        return ''.join([self.type,'(',fields,')'])

    def find_parent(self,type):
        if self.parent:
            if self.parent.type==type:
                return self.parent
            return self.parent.find_parent(type)
        raise AttributeError(type)

    def parse_descriptors(self,src):
        self.descriptors=[]
        end = self.position+self.size
        while src.tell()<end:
            d = self.parse_descriptor(src)
            self.descriptors.append(d)
            src.seek(d.position+d.size+d.header_size)

    def parse_descriptor(self,src, **kwargs):
        pos = src.tell()
        tag = struct.unpack('B', src.read(1))[0]
        try:
            Desc = MP4_DESCRIPTORS[tag]
        except KeyError:
            Desc = Descriptor
        return Desc(src, tag=tag, position=pos, parent=self, **kwargs)

class Descriptor(object):
    def __init__(self, src, tag, position, parent, *args, **kwargs):
        self.tag = tag
        self.size = 0
        self.header_size=1
        self.position = position
        self.parent = parent
        more_bytes = True
        while more_bytes:
            self.header_size += 1
            b = struct.unpack('B', src.read(1))[0]
            more_bytes = b & 0x80
            self.size = (self.size<<7) + (b&0x7f)
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
    def __init__(self, src, *args, **kwargs):
        super(ESDescriptor,self).__init__(src, *args,**kwargs)
        self.es_id = struct.unpack('>H', src.read(2))[0]
        b = struct.unpack('B', src.read(1))[0]
        self.stream_dependence_flag = (b&0x80)==0x80
        self.url_flag = (b&0x40)==0x40
        self.ocr_stream_flag = (b&0x20)==0x20
        self.stream_priority = b&0x1f
        if self.stream_dependence_flag:
            self.depends_on_es_id = struct.unpack('>H', src.read(2))[0]
        if self.url_flag:
            leng = struct.unpack('B', src.read(1))[0]
            self.url = src.read(leng)
        if self.ocr_stream_flag:
            self.ocr_es_id = struct.unpack('>H', src.read(2))[0]
        if src.tell() < (self.position+self.size):
            d = self.parent.parse_descriptor(src)
            self.parent.descriptors.append(d)
MP4_DESCRIPTORS[0x03]=ESDescriptor

class DecoderConfigDescriptor(Descriptor):
    def __init__(self, src, *args, **kwargs):
        super(DecoderConfigDescriptor,self).__init__(src, *args,**kwargs)
        self.object_type = struct.unpack('B', src.read(1))[0]
        b = struct.unpack('B', src.read(1))[0]
        self.stream_type = (b>>2)
        self.upstream = (b&0x02)==0x02
        f = '\000'+src.read(3)
        self.buffer_size = struct.unpack('>I',f)[0]
        self.max_bitrate = struct.unpack('>I', src.read(4))[0]
        self.avg_bitrate = struct.unpack('>I', src.read(4))[0]
        if src.tell() < (self.position+self.size):
            d = self.parent.parse_descriptor(src, object_type=self.object_type)
            self.parent.descriptors.append(d)
MP4_DESCRIPTORS[0x04] = DecoderConfigDescriptor

class DecoderSpecificInfo(Descriptor):
    SAMPLE_RATES=[ 96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350 ]
    def __init__(self, src, object_type, *args, **kwargs):
        super(DecoderSpecificInfo,self).__init__(src, *args,**kwargs)
        self.object_type = object_type
        data = src.read(self.size)
        bs = ConstBitStream(bytes=data)
        if object_type==0x40: # Audio ISO/IEC 14496-3 subpart 1
            self.audio_object_type = bs.read('uint:5')
            self.sampling_frequency_index = bs.read('uint:4')
            if self.sampling_frequency_index==0xf:
                self.sampling_frequency = bs.read('uint:24')
            else:
                self.sampling_frequency = self.SAMPLE_RATES[self.sampling_frequency_index]
            self.channel_configuration = bs.read('uint:4')
            self.frame_length_flag =  bs.read('bool')
            self.depends_on_core_coder =  bs.read('uint:1')
            if self.depends_on_core_coder:
                self.core_coder_delay = bs.read('uint:14')
            self.extension_flag =  bs.read('bool')
            if not self.channel_configuration:
                self.parse_config_element()
            if self.audio_object_type == 6 or self.audio_object_type == 20:
                self.layer_nr = bs.read('uint:3')
            if self.extension_flag:
                if self.audio_object_type==22:
                    self.num_sub_frame = bs.read('uint:5')
                    self.layer_length = bs.read('uint:11')
                if self.audio_object_type==17 or self.audio_object_type==19 or self.audio_object_type==20 or audio_object_type==23:
                    self.aac_section_data_resilience_flag =  bs.read('bool')
                    self.aac_scalefactor_data_resilience_flag =  bs.read('bool')
                    self.aac_spectral_data_resilience_flag =  bs.read('bool')
                self.extension_flag_3 =  bs.read('bool')
MP4_DESCRIPTORS[0x05] = DecoderSpecificInfo


class FullBox(Mp4Atom):
    def __init__(self, src, *args, **kwargs):
        super(FullBox,self).__init__(src, *args,**kwargs)
        #print 'parse FullBox'
        self.version = struct.unpack('B', src.read(1))[0]
        f = '\000'+src.read(3)
        self.flags = struct.unpack('>I', f)[0]
        #print 'FullBox version=%d flags=%x'%(self.version,self.flags)

    def _field_repr(self, **args):
        if not args.has_key('exclude'):
            args['exclude'] = []
        args['exclude'].append('flags')
        fields = super(FullBox,self)._field_repr(**args)
        fields.append('flags=0x%x'%self.flags)
        return fields

class BoxWithChildren(Mp4Atom):
    parse_children = True

for box in ['mdia', 'minf', 'mvex', 'moof', 'moov', 'sinf', 'stbl', 'traf', 'trak']:
    MP4_BOXES[box] = BoxWithChildren

class SampleEntry (Mp4Atom):
    def __init__(self, src, *args, **kwargs):
        super(SampleEntry,self).__init__(src, *args,**kwargs)
        #unsigned int(32) format
        src.read(6) # reserved
        self.data_reference_index = struct.unpack('>H', src.read(2))[0]

class VisualSampleEntry(SampleEntry):
    parse_children = True
    def __init__(self, src, *args, **kwargs):
        super(VisualSampleEntry,self).__init__(src, *args,**kwargs)
        self.pre_defined = struct.unpack('>H', src.read(2))[0]
        src.read(2) # reserved
        src.read(12) # unsigned int(32)[3] pre_defined = 0;
        self.width = struct.unpack('>H', src.read(2))[0]
        self.height = struct.unpack('>H', src.read(2))[0]
        self.horizresolution = struct.unpack('>I', src.read(4))[0] / 65536.0
        self.vertresolution = struct.unpack('>I', src.read(4))[0] / 65536.0
        src.read(4) # reserved
        self.frame_count = struct.unpack('>H', src.read(2))[0]
        self.compressorname = src.read(32)
        self.depth = struct.unpack('>H', src.read(2))[0]
        src.read(2) # int(16) pre_defined = -1;

class AVCConfigurationBox(Mp4Atom):
    #class AVCDecoderConfigurationRecord(object):
    def __init__(self, src, *args, **kwargs):
        super(AVCConfigurationBox,self).__init__(src, *args,**kwargs)
        self.configurationVersion = struct.unpack('B', src.read(1))[0]
        self.AVCProfileIndication = struct.unpack('B', src.read(1))[0]
        self.profile_compatibility = struct.unpack('B', src.read(1))[0]
        self.AVCLevelIndication = struct.unpack('B', src.read(1))[0]
        b0 = struct.unpack('B', src.read(1))[0]
        self.lengthSizeMinusOne = b0 & 0x03
        b0 = struct.unpack('B', src.read(1))[0]
        numOfSequenceParameterSets = b0 & 0x1F
        self.sps = []
        for i in range(numOfSequenceParameterSets):
            sequenceParameterSetLength = struct.unpack('>H', src.read(2))[0]
            sequenceParameterSetNALUnit = src.read(sequenceParameterSetLength)
            self.sps.append(sequenceParameterSetNALUnit)
        numOfPictureParameterSets = struct.unpack('B', src.read(1))[0]
        self.pps = []
        for i in range(numOfPictureParameterSets):
            pictureParameterSetLength = struct.unpack('>H', src.read(2))[0]
            pictureParameterSetNALUnit = src.read(pictureParameterSetLength)
            self.pps.append(pictureParameterSetNALUnit)
MP4_BOXES['avcC'] = AVCConfigurationBox

class AVCSampleEntry(VisualSampleEntry):
    pass
MP4_BOXES['avc1'] = AVCSampleEntry
MP4_BOXES['avc3'] = AVCSampleEntry
MP4_BOXES['encv'] = AVCSampleEntry
MP4_BOXES['enca'] = AVCSampleEntry

class EC3SampleEntry(SampleEntry):
    parse_children = True
    def __init__(self, src, *args, **kwargs):
        super(EC3SampleEntry,self).__init__(src, *args,**kwargs)
        src.read(8) # reserved
        self.channel_count = struct.unpack('>H', src.read(2))[0]
        self.sample_size = struct.unpack('>H', src.read(2))[0]
        src.read(4) # reserved
        self.sampling_frequency = struct.unpack('>H', src.read(2))[0]
        src.read(2) # reserved
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

    def __init__(self, src, *args, **kwargs):
        super(EC3SpecificBox,self).__init__(src, *args,**kwargs)
        data = src.read(self.size)
        bs = ConstBitStream(bytes=data)
        self.data_rate = bs.read('uint:13')
        self.num_ind_sub = 1+bs.read('uint:3')
        self.substreams = []
        for i in range(self.num_ind_sub):
            self.substreams.append(EC3SpecificBox.SubStream(bs))
MP4_BOXES['dec3'] = EC3SpecificBox

class OriginalFormatBox(Mp4Atom):
    def __init__(self, src, *args, **kwargs):
        super(OriginalFormatBox,self).__init__(src, *args,**kwargs)
        self.data_format = src.read(4)
MP4_BOXES['frma'] = OriginalFormatBox

class MP4A(Mp4Atom):
    parse_children = True
    def __init__(self,src, *args,**kwargs):
        super(MP4A,self).__init__(src, *args,**kwargs)
        src.read(6) # (8)[6] reserved
        self.data_reference_index = struct.unpack('>H', src.read(2))[0]
        src.read(8+4+4) # (32)[2], (16)[2], (32) reserved
        self.timescale = struct.unpack('>H', src.read(2))[0]
        src.read(2) # (16) reserved
MP4_BOXES['mp4a'] = MP4A

class ESDescriptorBox(FullBox):
    def __init__(self,src, *args,**kwargs):
        super(ESDescriptorBox,self).__init__(src, *args,**kwargs)
        self.parse_descriptors(src)
MP4_BOXES['esds'] = ESDescriptorBox

class SampleDescriptionBox(FullBox):
    parse_children = True
    def __init__(self,src, *args,**kwargs):
        super(SampleDescriptionBox,self).__init__(src, *args,**kwargs)
        self.entry_count = struct.unpack('>I', src.read(4))[0]
MP4_BOXES['stsd'] = SampleDescriptionBox

class TrackFragmentHeaderBox(FullBox):
    base_data_offset_present = 0x000001
    sample_description_index_present = 0x000002
    default_sample_duration_present = 0x000008
    default_sample_size_present = 0x000010
    default_sample_flags_present = 0x000020
    duration_is_empty = 0x010000

    def __init__(self,src, *args,**kwargs):
        super(TrackFragmentHeaderBox,self).__init__(src, *args,**kwargs)
        self.base_data_offset = 0
        self.sample_description_index = 0
        self.default_sample_duration = 0
        self.default_sample_size = 0
        self.default_sample_flags = 0
        self.track_id = struct.unpack('>I', src.read(4))[0]
        if self.flags & self.base_data_offset_present:
            self.base_data_offset = struct.unpack('>Q', src.read(8))[0]
        else:
            #default base offset = first byte of moof
            self.base_data_offset = self.find_parent('moof').position
        if self.flags & self.sample_description_index_present:
            self.sample_description_index = struct.unpack('>I', src.read(4))[0]
        if self.flags & self.default_sample_duration_present:
            self.default_sample_duration = struct.unpack('>I', src.read(4))[0]
        if self.flags & self.default_sample_size_present:
            self.default_sample_size = struct.unpack('>I', src.read(4))[0]
        if self.flags & self.default_sample_flags_present:
            self.default_sample_flags = struct.unpack('>I', src.read(4))[0]

    def _field_repr(self):
        fields = super(TrackFragmentHeaderBox,self)._field_repr(exclude=['default_sample_flags'])
        fields.append('default_sample_flags=0x%08x'%self.default_sample_flags)
        return fields
MP4_BOXES['tfhd'] = TrackFragmentHeaderBox

class TrackHeaderBox(FullBox):
    Track_enabled    = 0x000001
    Track_in_movie   = 0x000002
    Track_in_preview = 0x000004
    def __init__(self,src, *args,**kwargs):
        super(TrackHeaderBox,self).__init__(src, *args,**kwargs)
        self.is_enabled = (self.flags & self.Track_enabled)==self.Track_enabled
        self.in_movie = (self.flags & self.Track_in_movie)==self.Track_in_movie
        self.in_preview = (self.flags & self.Track_in_preview)==self.Track_in_preview
        if self.version==1:
            self.creation_time = struct.unpack('>Q', src.read(8))[0]
            self.modification_time = struct.unpack('>Q', src.read(8))[0]
            self.track_ID = struct.unpack('>I', src.read(4))[0]
            src.read(4) # reserved
            self.duration = struct.unpack('>Q', src.read(8))[0]
        else:
            self.creation_time = struct.unpack('>I', src.read(4))[0]
            self.modification_time = struct.unpack('>I', src.read(4))[0]
            self.track_ID = struct.unpack('>I', src.read(4))[0]
            src.read(4) # reserved
            self.duration = struct.unpack('>I', src.read(4))[0]
        src.read(8) # 2 x 32 bits reserved
        self.layer = struct.unpack('>H', src.read(2))[0]
        self.alternate_group = struct.unpack('>H', src.read(2))[0]
        self.volume = struct.unpack('>H', src.read(2))[0] / 256.0  # value is fixed point 8.8
        src.read(2) # reserved
        self.matrix = []
        for i in range(9):
            self.matrix.append( struct.unpack('>I', src.read(4))[0] )
        self.width = struct.unpack('>I', src.read(4))[0] / 65536.0 # value is fixed point 16.16
        self.height = struct.unpack('>I', src.read(4))[0] / 65536.0 # value is fixed point 16.16
        self.creation_time = ISO_EPOCH + datetime.timedelta(seconds=self.creation_time)
        self.modification_time = ISO_EPOCH + datetime.timedelta(seconds=self.modification_time)
MP4_BOXES['tkhd'] = TrackHeaderBox

class TrackFragmentDecodeTimeBox(FullBox):
    def __init__(self,src, *args,**kwargs):
        super(TrackFragmentDecodeTimeBox,self).__init__(src, *args,**kwargs)
        if self.version==1:
            self.base_media_decode_time = struct.unpack('>Q', src.read(8))[0]
        else:
            self.base_media_decode_time = struct.unpack('>I', src.read(4))[0]
MP4_BOXES['tfdt'] = TrackFragmentDecodeTimeBox

class TrackExtendsBox(FullBox):
    def __init__(self,src, *args,**kwargs):
        super(TrackExtendsBox,self).__init__(src, *args,**kwargs)
        self.track_ID  = struct.unpack('>I', src.read(4))[0]
        self.default_sample_description_index  = struct.unpack('>I', src.read(4))[0]
        self.default_sample_duration  = struct.unpack('>I', src.read(4))[0]
        self.default_sample_size  = struct.unpack('>I', src.read(4))[0]
        self.default_sample_flags = struct.unpack('>I', src.read(4))[0]
MP4_BOXES['trex'] = TrackExtendsBox

class MediaHeaderBox(FullBox):
    def __init__(self,src, *args,**kwargs):
        super(MediaHeaderBox,self).__init__(src, *args,**kwargs)
        if self.version==1:
            self.creation_time = struct.unpack('>Q', src.read(8))[0]
            self.modification_time = struct.unpack('>Q', src.read(8))[0]
            self.timescale = struct.unpack('>I', src.read(4))[0]
            self.duration = struct.unpack('>Q', src.read(8))[0]
        else:
            self.creation_time = struct.unpack('>I', src.read(4))[0]
            self.modification_time = struct.unpack('>I', src.read(4))[0]
            self.timescale = struct.unpack('>I', src.read(4))[0]
            self.duration = struct.unpack('>I', src.read(4))[0]
        self.creation_time = ISO_EPOCH + datetime.timedelta(seconds=self.creation_time)
        self.modification_time = ISO_EPOCH + datetime.timedelta(seconds=self.modification_time)
        tmp = struct.unpack('>H', src.read(2))[0]
        self.language = chr(0x60+((tmp>>10)&0x1F)) + chr(0x60+((tmp>>5)&0x1F)) + chr(0x60+(tmp&0x1F))

    def _field_repr(self):
        fields = super(MediaHeaderBox,self)._field_repr(exclude=['creation_time','modification_time'])
        fields.append('creation_time=%s'%utils.toIsoDateTime(self.creation_time))
        fields.append('modification_time=%s'%utils.toIsoDateTime(self.modification_time))
        return fields
MP4_BOXES['mdhd'] = MediaHeaderBox

class MovieFragmentHeaderBox(FullBox):
    def __init__(self,src, *args,**kwargs):
        super(MovieFragmentHeaderBox,self).__init__(src, *args,**kwargs)
        self.sequence_number = struct.unpack('>I', src.read(4))[0]
MP4_BOXES['mfhd'] = MovieFragmentHeaderBox

class HandlerBox(FullBox):
    def __init__(self,src, *args,**kwargs):
        super(HandlerBox,self).__init__(src, *args,**kwargs)
        src.read(4) # unsigned int(32) pre_defined = 0
        self.handler_type = src.read(4)
        src.read(12) # const unsigned int(32)[3] reserved = 0;
        name_len = self.position + self.size - src.tell()
        self.name = src.read(name_len)
MP4_BOXES['hdlr'] = HandlerBox

class MovieExtendsHeaderBox(FullBox):
    def __init__(self,src, *args,**kwargs):
        super(MovieExtendsHeaderBox,self).__init__(src, *args,**kwargs)
        if self.version==1:
            self.fragment_duration = struct.unpack('>Q', src.read(8))[0]
        else:
            self.fragment_duration = struct.unpack('>I', src.read(4))[0]
MP4_BOXES['mehd'] = MovieExtendsHeaderBox

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

    def __init__(self,src, *args,**kwargs):
        super(TrackFragmentRunBox,self).__init__(src, *args,**kwargs)
        tfhd = self.parent.tfhd
        self.sample_count = struct.unpack('>I', src.read(4))[0]
        if self.flags & self.data_offset_present:
            self.data_offset = struct.unpack('>i', src.read(4))[0]
        else:
            self.data_offset = 0
        self.data_offset += tfhd.base_data_offset
        if self.flags & self.first_sample_flags_present:
            self.first_sample_flags = struct.unpack('>I', src.read(4))[0]
        else:
            self.first_sample_flags = 0
        #print('Trun: count=%d offset=%d flags=%x'%(self.sample_count,self.data_offset,self.first_sample_flags))
        self.samples = []
        offset = self.data_offset
        for i in range(self.sample_count):
            ts = TrackSample(i,offset)
            if self.flags & self.sample_duration_present:
                ts.duration = struct.unpack('>I', src.read(4))[0]
            elif tfhd.default_sample_duration:
                ts.duration = tfhd.default_sample_duration
            if self.flags & self.sample_size_present:
                ts.size = struct.unpack('>I', src.read(4))[0]
            else:
                ts.size = tfhd.default_sample_size
            if self.flags & self.sample_flags_present:
                ts.flags = struct.unpack('>I', src.read(4))[0]
            else:
                ts.flags = tfhd.default_sample_flags
            if i==0 and (self.flags & self.first_sample_flags_present):
                ts.flags = self.first_sample_flags
            if self.flags & self.sample_composition_time_offsets_present:
                ts.composition_time_offset = struct.unpack('>i', src.read(4))[0]
            #print ts
            self.samples.append(ts)
            offset += ts.size

    def parse_samples(self,src, nal_length_field_length):
        for sample in self.samples:
            pos = 0
            sample.nals = []
            while pos<sample.size:
                src.seek(sample.offset+pos)
                nal = Nal(src,nal_length_field_length)
                pos += nal.size + nal_length_field_length
                sample.nals.append(nal)
MP4_BOXES['trun']=TrackFragmentRunBox

#
# The following class is based on code from http://www.bok.net/trac/bento4/browser/trunk/Source/Python/utils/mp4-dash.py
#
class IsoParser(object):
    def walk_atoms(self, filename, atom=None):
        if isinstance(filename,(str,unicode)):
            src = io.FileIO(filename, "rb")
        else:
            src = filename
        if atom is None:
            atoms = []
            end=None
            parent=None
            cursor = 0
        else:
            atoms = atom.children
            parent = atom
            cursor = atom.payload
            end = atom.position + atom.size
            src.seek(cursor)
        try:
            while end is None or cursor<end:
                hdr = Mp4Atom.parse_atom_header(src)
                if hdr is None:
                    break
                try:
                    Box = MP4_BOXES[hdr['type']]
                except KeyError,k:
                    Box = Mp4Atom
                a = Box(src, type=hdr['type'], position=hdr['position'], size=hdr['size'], parent=parent)
                a.payload = src.tell()
                if a.parse_children:
                    self.walk_atoms(src, atom=a)
                atoms.append(a)
                cursor += a.size
                #print('cursor',cursor)
                src.seek(cursor)
        #except Exception,e:
        #    print e
        #    raise e
        finally:
            if isinstance(filename,(str,unicode)):
                src.close()
        if atom is not None:
            return atom
        return atoms

