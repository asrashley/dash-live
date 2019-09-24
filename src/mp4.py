from abc import ABCMeta, abstractmethod
import argparse
import base64
import datetime
import io
import logging
import os
import re
import struct
import sys

try:
    import bitstring
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
    import bitstring

from nal import Nal
import utils

# time values are in seconds since midnight, Jan. 1, 1904, in UTC time
ISO_EPOCH = datetime.datetime(year=1904, month=1, day=1, tzinfo=utils.UTC())

MP4_BOXES = {}
MP4_DESCRIPTORS = {}

def from_iso_epoch(delta):
    rv = ISO_EPOCH + datetime.timedelta(seconds=delta)
    return rv

def to_iso_epoch(dt):
    delta = dt - ISO_EPOCH
    return long(delta.total_seconds())

class NamedObject(object):
    __metaclass__ = ABCMeta
    debug=False

    @property
    def classname(self):
        clz = type(self)
        if clz.__module__.startswith('__'):
            return clz.__name__
        return clz.__module__ + '.' + clz.__name__

    def __repr__(self, exclude=None):
        if exclude is None:
            exclude=[]
        fields = self._field_repr(exclude)
        fields = ','.join(fields)
        return ''.join([self.classname, '(', fields, ')'])

    @abstractmethod
    def _field_repr(self, exclude):
        return []

class FieldReader(object):
    def __init__(self, clz, src, kwargs):
        self.clz = clz
        self.src = src
        self.kwargs = kwargs
        if getattr(self.clz, 'debug', False):
            self.log = logging.getLogger('mp4')
        else:
            self.log = None

    def read(self, size, field, mask=None):
        self.kwargs[field] = self.get(size, field, mask)

    def get(self, size, field, mask=None):
        if isinstance(size, (int, long)):
            value = self.src.read(size)
            if self.log and self.log.isEnabledFor(logging.DEBUG):
                self.log.debug('%s: read %s size=%d pos=%d value=0x%s', self.clz.__name__, field,
                               size, self.src.tell(), value.encode('hex'))
            return value
        if size=='B':
            value = ord(self.src.read(1))
        elif size=='H':
            d = self.src.read(2)
            value = (ord(d[0])<<8) + ord(d[1])
        elif size=='I':
            d = self.src.read(4)
            value = (ord(d[0])<<24) + (ord(d[1])<<16) + (ord(d[2])<<8) + ord(d[3])
        elif size=='0I':
            d = self.src.read(3)
            value = (ord(d[0])<<16) + (ord(d[1])<<8) + ord(d[2])
        else:
            raise ValueError("unsupported size: "+size)
        if mask is not None:
            value &= mask
        if self.log:
            self.log.debug('%s: read %s size=%s pos=%d value=0x%x', self.clz.__name__, field,
                           str(size), self.src.tell(), value)
        return value

class BitsFieldReader(object):
    def __init__(self, clz, src, kwargs, size=None):
        self.clz = clz
        if size is None:
            size = kwargs["size"] - kwargs["header_size"]
        self.data = src.read(size)
        self.src = bitstring.ConstBitStream(bytes=self.data)
        self.kwargs = kwargs
        if getattr(self.clz, 'debug', False):
            self.log = logging.getLogger('mp4')
        else:
            self.log = None

    def read(self, size, field):
        self.kwargs[field] = self.get(size, field)

    def get(self, size, field):
        if self.log:
            self.log.debug('%s: read %s size=%d pos=%s', self.clz.__name__, field, size,
                           self.src.pos)
        if size==1:
            return self.src.read('bool')
        return self.src.read('uint:%d'%size)

    def pos(self):
        return self.src.pos

class FieldWriter(object):
    def __init__(self, obj, dest):
        self.obj = obj
        self.dest = dest
        self.bits = None
        if getattr(self.obj, 'debug', False):
            self.log = logging.getLogger('mp4')
        else:
            self.log = None

    def write(self, size, field, value=None):
        if value is None:
            value = getattr(self.obj, field)
        if isinstance(size, basestring):
            if size=='0I':
                value = struct.pack('>I', value)[1:]
            else:
                value = struct.pack('>'+size, value)
        elif isinstance(size, (int, long)):
            padding = size - len(value)
            if padding > 0:
                value += '\0' * padding
            elif padding < 0:
                value = value[:size]
        if self.log and self.log.isEnabledFor(logging.DEBUG):
            if isinstance(value, (int, long)):
                v = '0x' + hex(value)
            elif isinstance(value, basestring):
                v = '0x' + value.encode('hex')
            else:
                v = str(value)
            self.log.debug('%s: Write %s size=%s (%d) pos=%d value=%s', self.obj.classname,
                           field, str(size), len(value), self.dest.tell(), v)
        self.dest.write(value)

    def writebits(self, size, field, value=None):
        if self.bits is None:
            self.bits = bitstring.BitArray()
        if value is None:
            value = getattr(self.obj, field)
        if isinstance(value, bool):
            value = 1 if value else 0
        if self.log:
            self.log.debug('%s: WriteBits %s size=%d value=0x%x',self.obj.classname, field, size,
                           value)
        self.bits.append(bitstring.Bits(uint=value, length=size))

    def done(self):
        if self.bits is not None:
            self.dest.write(self.bits.bytes)


class Options(object):
    def __init__(self, **kwargs):
        self.cache_encoded = kwargs.get("cache_encoded", False)
        self.iv_size = kwargs.get("iv_size")
        self.log = logging.getLogger('mp4')

class Mp4Atom(NamedObject):
    __metaclass__ = ABCMeta
    parse_children=False
    include_atom_type=False

    def __init__(self, **kwargs):
        try:
            atom_type = { "atom_type": kwargs["atom_type"] }
        except KeyError:
            atom_type = None
            for k,v in MP4_BOXES.iteritems():
                if v == type(self):
                    atom_type =  k
                    break
            if atom_type is None:
                raise KeyError("atom_type")
        self._fields = { "atom_type": atom_type }
        self.position = kwargs.get("position")
        self.size = kwargs.get("size", 0)
        self.parent = kwargs.get("parent")
        self.options = kwargs.get("options", Options())
        self.children = kwargs.get("children", [])
        self._encoded = None
        for key,value in kwargs.iteritems():
            assert "src" != key
            if not self.__dict__.has_key(key):
                self._fields[key] = value
        for ch in self.children:
            ch.parent = self

    def __getattr__(self, name):
        if name[0]=="_":
            # __getattribute__ should have responded before __getattr__ called
            raise AttributeError(name)
        if self._fields.has_key(name):
            return self._fields[name]
        for c in self.children:
            if c._fields["atom_type"] == name:
                return c
            elif '-' in c._fields["atom_type"]:
                if c._fields["atom_type"].replace('-','_')==name:
                    return c
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
        raise AttributeError(name)
        
    def _field_repr(self, exclude):
        fields = []
        if not self.include_atom_type:
            exclude = exclude + ['atom_type', 'options']
        for k,v in self._fields.iteritems():
            if k[0] != '_' and not k in exclude:
                if isinstance(v, (datetime.date, datetime.datetime,datetime.time)):
                    v = 'utils.from_isodatetime("%s")'%(utils.toIsoDateTime(v))
                elif isinstance(v, (datetime.timedelta)):
                    v = 'utils.from_isodatetime("%s")'%(utils.toIsoDuration(v))
                else:
                    v = repr(v)
                fields.append('%s=%s'%(k, v))
        if self.children:
            ch = map(repr, self.children)
            fields.append('children=[%s]'%(','.join(ch)))
        return fields

    def _int_field_repr(self, fields, names):
        for name in names:
            fields.append('%s=%d'%(name,self.__getattribute__(name)))
        return fields

    def find_atom(self,atom_type):
        #print('find_atom',atom_type, self._fields["atom_type"])
        if self._fields["atom_type"]==atom_type:
            #print('found')
            return self
        for ch in self.children:
            #print('find_atom', atom_type, 'child=',ch._fields["atom_type"])
            if ch._fields["atom_type"]==atom_type:
                #print('found')
                return ch
        if self.parent:
            return self.parent.find_atom(atom_type)
        raise AttributeError(atom_type)

    def find_child(self, atom_type):
        for child in self.children:
            if child._fields["atom_type"] == atom_type:
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

    def append_child(self, child):
        self.children.append(child)
        if child.size:
            self.size += child.size
        self._invalidate()

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
    def create(cls, src, parent=None, options=None):
        assert src is not None
        if options is None:
            options=Options()
        elif isinstance(options, dict):
            options=Options(**options)
        if parent is not None:
            cursor = parent.payload_start
            end = parent.position + parent.size
        else:
            parent = Wrapper(position=src.tell(), atom_type='wrap')
            end=None
            cursor = 0
        rv = parent.children
        while end is None or cursor<end:
            assert cursor is not None
            if src.tell() != cursor:
                src.seek(cursor)
            hdr = Mp4Atom.peek(src, parent)
            if hdr is None:
                break
            #src.seek(hdr["position"])
            try:
                Box = MP4_BOXES[hdr['atom_type']]
            except KeyError,k:
                Box = UnknownBox
            options.log.debug('create %s %s pos=%d size=%d',
                              hdr['atom_type'], Box.__name__,
                              hdr['position'], hdr['size'])
            encoded = None
            if options.cache_encoded and not Box.parse_children:
                encoded = src.peek(hdr["size"])[:hdr["size"]]
            kwargs = Box.parse(src, parent, options)
            atom = Box(**kwargs)
            atom.payload_start = src.tell()
            atom.options = options
            rv.append(atom)
            if atom.parse_children:
                Mp4Atom.create(src, atom, options)
            if encoded:
                atom._encoded = encoded
            if (src.tell() - atom.position) != atom.size:
                options.log.warning('expected {atom_type:s} to contain {expected:d} bytes but parsed {actual:d} bytes'.format(
                    atom_type=atom.atom_type, expected=atom.size, actual=src.tell()-atom.position))
            cursor += atom.size
        return rv
        
    @classmethod
    def parse(cls, src, parent, options):
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
            "header_size": src.tell() - position,
            "parent": parent,
        }

    @classmethod
    def peek(cls, src, parent):
        position = src.tell()
        header_size = 8
        data = src.peek(header_size)
        if not data or len(data) < header_size:
            return None
        size = struct.unpack('>I', data[:4])[0]
        atom_type = data[4:8]
        if not atom_type:
            return None
        if size == 0:
            pos = src.tell()
            src.seek(0,2) # seek to end
            size = src.tell() - pos
            src.seek(pos)
        elif size == 1:
            if len(data) < (header_size+8):
                data = src.peek(header_size+8)
            size = struct.unpack('>Q', data[header_size:header_size+8])[0]
            if not size:
                return None
            header_size += 8
        if atom_type=='uuid':
            if len(data) < (header_size+16):
                data = src.peek(header_size+16)
            atom_type = data[header_size:header_size+16]
            header_size += 16
        return {
            "atom_type": atom_type,
            "position": position,
            "size": size,
            "parent": parent,
            "header_size": header_size,
        }

    def encode(self, dest=None):
        out = dest
        if out is None:
            out = io.BytesIO()
        self.position = out.tell()
        self.options.log.debug('encode %s %d %d',self.atom_type, self.position, self.size)
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
        #print(self.atom_type,'produced',self.size)
        if dest is None:
            return out.getvalue()
        return dest

    @abstractmethod
    def encode_fields(self, dest):
        pass
    
    def dump(self, indent=''):
        print('{}{}: {:d} -> {:d} [{:d} bytes]'.format(indent,
                                                       self.atom_type,
                                                       self.position,
                                                       self.position + self.size,
                                                       self.size))
        if 'descriptors' in self._fields:
            for d in self._fields['descriptors']:
                d.dump(indent+'  ')
        for c in self.children:
            c.dump(indent+'  ')

class Wrapper(Mp4Atom):
    def encode_fields(self, dest):
        pass

class UnknownBox(Mp4Atom):
    include_atom_type = True

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Mp4Atom.parse(src, parent, options)
        hdr_sz = src.tell() - kwargs["position"]
        size = kwargs["size"] - hdr_sz
        if size > 0:
            kwargs["data"] = src.read(size)
        else:
            kwargs["data"] = None
        return kwargs

    def _field_repr(self, exclude):
        exclude.append('data')
        fields = super(UnknownBox, self)._field_repr(exclude)
        if self.data is not None:
            fields.append('data=base64.b64decode("%s")'%base64.b64encode(self.data))
        else:
            fields.append('data=None')
        return fields

    def encode_fields(self, dest):
        if self.data is not None:
            dest.write(self.data)

class Descriptor(NamedObject):
    __metaclass__ = ABCMeta
    def __init__(self, tag, **kwargs):
        self.tag = tag
        self.children = []
        self._encoded = None
        self.options = kwargs.get("options", Options())
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    @classmethod
    def peek(cls, src, parent):
        position = src.tell()
        header_size=1
        data = src.peek(header_size)
        if not data:
            return None
        tag = struct.unpack('B', data[0])[0]
        more_bytes = True
        size = 0
        while more_bytes:
            header_size += 1
            data = src.peek(header_size)
            if len(data) < header_size:
                data = src.peek(header_size)
                if len(data) < header_size:
                    return None
            b = struct.unpack('B', data[header_size-1])[0]
            more_bytes = b & 0x80
            size = (size<<7) + (b&0x7f)
        return {
            "position": position,
            "tag": tag,
            "header_size": header_size,
            "size": size,
        }

    @classmethod
    def create(clz, src, parent, options):
        d = Descriptor.peek(src, parent)
        try:
            Desc = MP4_DESCRIPTORS[d["tag"]]
        except KeyError:
            Desc = UnknownDescriptor
        total_size = d["size"] + d["header_size"]
        #print('create descriptor', d["tag"], Desc.__name__, d["position"], total_size)
        encoded = src.peek(total_size)[:total_size]
        kw = Desc.parse(src, parent, options)
        del kw["tag"]
        rv = Desc(tag=d["tag"], parent=parent, **kw)
        rv._encoded = encoded
        end = rv.position + rv.size + rv.header_size
        while src.tell() < end:
            dc = Descriptor.create(src, rv, options)
            rv.children.append(dc)
            if (src.tell() - dc.position) != (dc.size + dc.header_size):
                options.log.warning('expected tag %d to contain %d bytes but parsed %d bytes',
                                    dc.tag, dc.size, src.tell()-dc.position)
                src.seek(dc.position + dc.size + dc.header_size)
        return rv

    @classmethod
    def parse(clz, src, parent, options):
        position = src.tell()
        tag = struct.unpack('B', src.read(1))[0]
        header_size=1
        more_bytes = True
        size = 0
        while more_bytes and header_size<5:
            header_size += 1
            b = struct.unpack('B', src.read(1))[0]
            more_bytes = b & 0x80
            size = (size<<7) + (b&0x7f)
        return {
            "position": position,
            "tag": tag,
            "header_size": header_size,
            "size": size,
            "options": options,
        }

    def encode(self, dest):
        d = FieldWriter(self, dest)
        self.options.log.debug('Encode Descriptor %s', self.tag)
        if self._encoded is not None:
            d.write(None, '_encoded', self._encoded)
            return
        payload = io.BytesIO()
        self.encode_fields(payload)
        for ch in self.children:
            ch.encode(payload)
        payload = payload.getvalue()
        if self.size != len(payload):
            self.options.log.warning("Descriptor %s should be %d bytes but encoded %d",
                                     self.classname, self.size, len(payload))
            self.size = len(payload)
        d.write('B', 'tag')
        sizes=[]
        size = self.size
        while size > 0x7f:
            sizes.append(size & 0x7f)
            size = size >> 7
        sizes.append(size & 0x7f)
        while sizes:
            a = sizes.pop(0)
            flag = 0x80 if sizes else 0x00
            d.write('B', 'size', a + flag)
        if payload:
            d.write(None, 'payload', payload)

    @abstractmethod
    def encode_fields(self, dest):
        pass

    def __getattr__(self, name):
        if type(self).__name__ == name:
            return self
        for d in self.children:
            if type(d).__name__ == name:
                return d
            v = getattr(d, name)
            if v is not None:
                return v
        raise AttributeError(name)

    def _field_repr(self, exclude):
        rv = []
        exclude += ['parent', 'children', 'options', 'data']
        for k,v in self.__dict__.iteritems():
            if k[0]!='_' and k not in exclude:
                rv.append('%s=%s'%(k,str(v)))
        if self.children:
            ch = map(repr, self.children)
            rv.append('children=[%s]'%(', '.join(ch)))
        if 'data' in self.__dict__:
            if self.data is None:
                rv.append('data=None')
            else:
                rv.append('data=base64.b64decode("%s")'%base64.b64encode(self.data))
        return rv

    def dump(self, indent=''):
        f = '{}{}: {:d} -> {:d} [header {:d} bytes] [{:d} bytes]'
        print(f.format(indent,
                       self.classname,
                       self.position,
                       self.position + self.size + self.header_size,
                       self.header_size,
                       self.size))
        for c in self.children:
            c.dump(indent+'  ')

class UnknownDescriptor(Descriptor):
    include_atom_type = True

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Descriptor.parse(src, parent, options)
        if kwargs["size"] > 0:
            kwargs["data"] = src.read(kwargs["size"])
        else:
            kwargs["data"] = None
        return kwargs

    def encode_fields(self, dest):
        if self.data is not None:
            dest.write(self.data)

class ESDescriptor(Descriptor):
    @classmethod
    def parse(clz, src, parent, options):
        rv = Descriptor.parse(src, parent, options)
        r = FieldReader(clz, src, rv)
        r.read('H', 'es_id')
        b = r.get('B', 'flags')
        rv["stream_dependence_flag"] = (b&0x80)==0x80
        url_flag = (b&0x40)==0x40
        ocr_stream_flag = (b&0x20)==0x20
        rv["stream_priority"] = b&0x1f
        if rv["stream_dependence_flag"]:
            r.read('H',"depends_on_es_id")
        if url_flag:
            leng = r.get('B', 'url_length')
            r.read(leng, 'url')
        else:
            rv["url"] = None
        if ocr_stream_flag:
            r.read('H', 'ocr_es_id')
        else:
            rv['ocr_es_id'] = None
        return rv

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('H', 'es_id')
        b = self.stream_priority & 0x1f
        if self.stream_dependence_flag:
            b += 0x80
        if self.url is not None:
            b += 0x40
        if self.ocr_es_id is not None:
            b += 0x20
        w.write('B', 'flags', b)
        if self.stream_dependence_flag:
            w.write('H',"depends_on_es_id")
        if self.url is not None:
            w.write('B', 'url_length', len(self.url))
            w.write(None, 'url')
        if self.ocr_es_id is not None:
            w.write('H', 'ocr_es_id')

MP4_DESCRIPTORS[0x03]=ESDescriptor

class DecoderConfigDescriptor(Descriptor):
    @classmethod
    def parse(clz, src, parent, options):
        rv = Descriptor.parse(src, parent, options)
        r = FieldReader(clz, src, rv)
        r.read('B', "object_type")
        b = r.get('B', "stream_type")
        rv["stream_type"] = (b>>2)
        rv["unknown_flag"] = (b&0x01)==0x01
        rv["upstream"] = (b&0x02)==0x02
        r.read('0I', "buffer_size")
        r.read('I', "max_bitrate")
        r.read('I', "avg_bitrate")
        return rv

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write('B', "object_type")
        b = self.stream_type << 2
        if self.unknown_flag:
            b |= 0x01
        if self.upstream:
            b |= 0x02
        w.write('B', 'stream_type', b)
        w.write('0I', 'buffer_size')
        w.write('I', "max_bitrate")
        w.write('I', "avg_bitrate")

MP4_DESCRIPTORS[0x04] = DecoderConfigDescriptor

class DecoderSpecificInfo(Descriptor):
    SAMPLE_RATES=[ 96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350 ]
    @classmethod
    def parse(clz, src, parent, options):
        rv = Descriptor.parse(src, parent, options)
        rv["object_type"] = parent.object_type
        r = BitsFieldReader(clz, src, rv, rv["size"])
        if rv["object_type"]==0x40: # Audio ISO/IEC 14496-3 subpart 1
            r.read(5, "audio_object_type")
            r.read(4, "sampling_frequency_index")
            if rv["sampling_frequency_index"]==0xf:
                r.read(24, "sampling_frequency")
            else:
                rv["sampling_frequency"] = clz.SAMPLE_RATES[rv["sampling_frequency_index"]]
            r.read(4, "channel_configuration")
            r.read(1, "frame_length_flag")
            r.read(1, "depends_on_core_coder")
            if rv["depends_on_core_coder"]:
                r.read(14, "core_coder_delay")
            r.read(1, "extension_flag")
            #if not rv["channel_configuration"]:
            #    rv["channel_configuration"] = clz.parse_config_element(src, parent)
            if rv["audio_object_type"] == 6 or rv["audio_object_type"] == 20:
                r.read(3, "layer_nr")
            if rv["extension_flag"]:
                if rv["audio_object_type"]==22:
                    r.read(5, "num_sub_frame")
                    r.read(11, "layer_length")
                if rv["audio_object_type"] in [17, 19, 20, 23]:
                    r.read(1, "aac_section_data_resilience_flag")
                    r.read(1, "aac_scalefactor_data_resilience_flag")
                    r.read(1, "aac_spectral_data_resilience_flag")
                r.read(1, "extension_flag_3")
        rv["data"] = None
        if r.pos() != 8*rv["size"]:
            rv["data"] = r.data[r.pos()/8:]
        return rv

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        if self.object_type==0x40: # Audio ISO/IEC 14496-3 subpart 1
            w.writebits(5, "audio_object_type")
            w.writebits(4, "sampling_frequency_index")
            if self.sampling_frequency_index==0xf:
                w.writebits(24, "sampling_frequency")
            w.writebits(4, "channel_configuration")
            w.writebits(1, 'frame_length_flag')
            w.writebits(1, "depends_on_core_coder")
            if self.depends_on_core_coder:
                w.writebits(14, "core_coder_delay")
            w.writebits(1, "extension_flag")
            if self.audio_object_type == 6 or self.audio_object_type == 20:
                w.writebits(3, "layer_nr")
            if self.extension_flag:
                if self.audio_object_type==22:
                    w.writebits(5, "num_sub_frame")
                    w.writebits(11, "layer_length")
                if self.audio_object_type in [17, 19, 20, 23]:
                    w.writebits(1, "aac_section_data_resilience_flag")
                    w.writebits(1, "aac_scalefactor_data_resilience_flag")
                    w.writebits(1, "aac_spectral_data_resilience_flag")
                w.writebits(1, "extension_flag_3")
        w.done()
        if self.data is not None:
            w.write(None, "data")

MP4_DESCRIPTORS[0x05] = DecoderSpecificInfo


class FullBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Mp4Atom.parse(src, parent, options)
        #print 'parse FullBox'
        kwargs["version"] = struct.unpack('B', src.read(1))[0]
        f = '\000'+src.read(3)
        kwargs["flags"] = struct.unpack('>I', f)[0]
        return kwargs

    def _field_repr(self, exclude):
        exclude.append('flags')
        fields = super(FullBox,self)._field_repr(exclude)
        fields.append('flags=0x%x'%self._fields['flags'])
        return fields

    def encode_fields(self, dest, payload=None):
        dest.write(struct.pack('B', self.version))
        dest.write(struct.pack('>I', self.flags)[1:])
        if payload is not None:
            dest.write(payload)

class BoxWithChildren(Mp4Atom):
    parse_children = True
    include_atom_type = True

    def encode_fields(self, dest):
        pass

class MovieBox(BoxWithChildren):
    include_atom_type = False
    pass
MP4_BOXES['moov'] = MovieBox

class TrackBox(BoxWithChildren):
    include_atom_type = False
    pass
MP4_BOXES['trak'] = TrackBox

for box in ['mdia', 'minf', 'mvex', 'moof', 'schi', 'sinf', 'stbl', 'traf']:
    MP4_BOXES[box] = BoxWithChildren

class SampleEntry(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Mp4Atom.parse(src, parent, options)
        #unsigned int(32) format
        src.read(6) # reserved
        kwargs["data_reference_index"] = struct.unpack('>H', src.read(2))[0]
        return kwargs

    def encode_fields(self, dest):
        dest.write('\0' * 6) # reserved
        dest.write(struct.pack('>H', self.data_reference_index))

class VisualSampleEntry(SampleEntry):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = SampleEntry.parse(src, parent, options)
        r = FieldReader(clz, src, kwargs)
        r.read('H',"version")
        r.read('H',"revision")
        r.read('I',"vendor")
        r.read('I',"temporal_quality")
        r.read('I',"spatial_quality")
        r.read('H',"width")
        r.read('H',"height")
        r.read('I',"horizresolution")
        kwargs["horizresolution"] /= 65536.0
        r.read('I',"vertresolution")
        kwargs["vertresolution"] /= 65536.0
        r.read('I',"entry_data_size")
        r.read('H',"frame_count")
        r.read(32,"compressorname")
        r.read('H',"bit_depth")
        r.read('H',"colour_table")
        return kwargs

    def encode_fields(self, dest):
        super(VisualSampleEntry, self).encode_fields(dest)
        dest.write(struct.pack('>H', self.version))
        dest.write(struct.pack('>H', self.revision))
        dest.write(struct.pack('>I', self.vendor))
        dest.write(struct.pack('>I', self.temporal_quality))
        dest.write(struct.pack('>I', self.spatial_quality))
        dest.write(struct.pack('>H', self.width))
        dest.write(struct.pack('>H', self.height))
        dest.write(struct.pack('>I', long(self.horizresolution * 65536.0)))
        dest.write(struct.pack('>I', long(self.vertresolution * 65536.0)))
        dest.write(struct.pack('>I', self.entry_data_size))
        dest.write(struct.pack('>H', self.frame_count))
        c = self.compressorname + '\0'*32
        dest.write(c[:32])
        dest.write(struct.pack('>H', self.bit_depth))
        dest.write(struct.pack('>H', self.colour_table))

class AVC1SampleEntry(VisualSampleEntry):
    pass
MP4_BOXES['avc1'] = AVC1SampleEntry

class AVC3SampleEntry(VisualSampleEntry):
    pass
MP4_BOXES['avc3'] = AVC3SampleEntry

class EncryptedSampleEntry(VisualSampleEntry):
    pass
MP4_BOXES['encv'] = EncryptedSampleEntry

class AVCConfigurationBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Mp4Atom.parse(src, parent, options)
        r = FieldReader(clz, src, kwargs)
        r.read('B',"configurationVersion")
        r.read('B',"AVCProfileIndication")
        r.read('B',"profile_compatibility")
        r.read('B',"AVCLevelIndication")
        r.read('B',"lengthSizeMinusOne", mask=0x03)
        numOfSequenceParameterSets = r.get('B',"numOfSequenceParameterSets", mask=0x1F)
        kwargs["sps"] = []
        for i in range(numOfSequenceParameterSets):
            sequenceParameterSetLength = struct.unpack('>H', src.read(2))[0]
            sequenceParameterSetNALUnit = src.read(sequenceParameterSetLength)
            kwargs["sps"].append(sequenceParameterSetNALUnit)
        numOfPictureParameterSets = r.get('B', 'numOfPictureParameterSets')
        kwargs["pps"] = []
        for i in range(numOfPictureParameterSets):
            pictureParameterSetLength = struct.unpack('>H', src.read(2))[0]
            pictureParameterSetNALUnit = src.read(pictureParameterSetLength)
            kwargs["pps"].append(pictureParameterSetNALUnit)
        if clz.is_ext_profile(kwargs["AVCProfileIndication"]):
            r.read('B', 'chroma_format', mask=0x03)
            r.read('B', 'luma_bit_depth', mask=0x03)
            kwargs["luma_bit_depth"] += 8
            r.read('B', 'chroma_bit_depth', mask=0x03)
            kwargs["chroma_bit_depth"] += 8
            numOfSequenceParameterSetExtensions = r.get('B', 'numOfSequenceParameterSetExtensions')
            kwargs["sps_ext"] = []
            for i in range(numOfSequenceParameterSetExtensions):
                length = struct.unpack('>H', src.read(2))[0]
                NALUnit = src.read(length)
                kwargs["sps_ext"].append(NALUnit)
        return kwargs

    def _field_repr(self, exclude):
        param_sets = ['sps', 'sps_ext', 'pps']
        exclude += param_sets
        fields = super(AVCConfigurationBox,self)._field_repr(exclude)
        for param in param_sets:
            try:
                sets = map(lambda a: 'base64.b64decode("{}")'.format(base64.b64encode(a)), self._fields[param])
                fields.append('{0}=[{1}]'.format(param, ','.join(sets)))
            except KeyError:
                pass
        return fields

    def encode_fields(self, dest):
        d = FieldWriter(self, dest)
        d.write('B', 'configurationVersion')
        d.write('B', 'AVCProfileIndication')
        d.write('B', 'profile_compatibility')
        d.write('B', 'AVCLevelIndication')
        d.write('B', 'lengthSizeMinusOne', 0xFC + (self.lengthSizeMinusOne &0x03))
        d.write('B', 'sps_count', 0xE0 + (len(self.sps) & 0x1F))
        for sps in self.sps:
            d.write('H', 'sps_size', len(sps))
            d.write(None, 'sps', sps)
        d.write('B', 'pps_count', len(self.pps) & 0x1F)
        for pps in self.pps:
            d.write('H', 'pps_size', len(pps))
            d.write(None, 'pps', pps)
        if AVCConfigurationBox.is_ext_profile(self.AVCProfileIndication):
            d.write('B', 'chroma_format', self.chroma_format + 0xFC)
            d.write('B', 'luma_bit_depth', self.luma_bit_depth - 8 + 0xF8)
            d.write('B', 'chroma_bit_depth', self.chroma_bit_depth - 8 + 0xF8)
            d.write('B', 'sps_ext_count', len(self.sps_ext))
            for s in self.sps_ext:
                d.write('H', 'sps_ext_size', len(s))
                d.write(None, 'sps_ext', s)

    @classmethod
    def is_ext_profile(clz, profile_idc):
        return profile_idc in [ 100, 110, 122, 244, 44, 83, 86, 118, 128, 134, 135, 138, 139]


MP4_BOXES['avcC'] = AVCConfigurationBox

class AudioSampleEntry(SampleEntry):
    parse_children = True
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = SampleEntry.parse(src, parent, options)
        src.read(8) # reserved
        kwargs["channel_count"] = struct.unpack('>H', src.read(2))[0]
        kwargs["sample_size"] = struct.unpack('>H', src.read(2))[0]
        src.read(4) # reserved
        kwargs["sampling_frequency"] = struct.unpack('>H', src.read(2))[0]
        src.read(2) # reserved
        return kwargs

    def encode_fields(self, dest):
        super(AudioSampleEntry, self).encode_fields(dest)
        dest.write('\0' * 8) # reserved
        dest.write(struct.pack('>H', self.channel_count))
        dest.write(struct.pack('>H', self.sample_size))
        dest.write('\0' * 4) # reserved
        dest.write(struct.pack('>H', self.sampling_frequency))
        dest.write('\0' * 2) # reserved

class EC3SampleEntry(AudioSampleEntry):
    pass

MP4_BOXES['ec-3'] = EC3SampleEntry

class EC3SpecificBox(Mp4Atom):
    ACMOD_NUM_CHANS = [2,1,2,3,3,4,4,5]

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Mp4Atom.parse(src, parent, options)
        r = BitsFieldReader(clz, src, kwargs)
        r.read(13, "data_rate")
        r.read(3, "num_ind_sub")
        kwargs["num_ind_sub"] += 1
        r.read(2, 'fscod')
        r.read(5, 'bsid')
        r.read(5, 'bsmod')
        r.read(3, 'acmod')
        kwargs['channel_count'] = EC3SpecificBox.ACMOD_NUM_CHANS[kwargs['acmod']]
        r.read(1, 'lfeon')
        r.get(3, 'reserved')
        r.read(4, 'num_dep_sub')
        if kwargs["num_dep_sub"]>0:
            r.read(9, 'chan_loc')
        else:
            r.get(1, 'reserved')
        return kwargs

    def encode_fields(self, dest):
        ba = bitstring.BitArray()
        ba.append(bitstring.pack('uint:13, uint:3', self.data_rate, self.num_ind_sub-1))
        ba.append(bitstring.pack('uint:2, uint:5, uint:5, uint:3, bool',
                                 self.fscod, self.bsid, self.bsmod, self.acmod,
                                 self.lfeon))
        ba.append(bitstring.Bits(uint=0, length=3)) # reserved
        ba.append(bitstring.Bits(uint=self.num_dep_sub, length=4))
        if self.num_dep_sub>0:
            ba.append(bitstring.Bits(uint=self.chan_loc, length=9))
        else:
            ba.append(bitstring.Bits(uint=0, length=1)) # reserved
        dest.write(ba.bytes)

MP4_BOXES['dec3'] = EC3SpecificBox

class OriginalFormatBox(Mp4Atom):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Mp4Atom.parse(src, parent, options)
        kwargs["data_format"] = src.read(4)
        return kwargs

    def encode_fields(self, dest):
        dest.write(self.data_format)
MP4_BOXES['frma'] = OriginalFormatBox

#see table 6.3 of 3GPP TS 26.244 V12.3.0
class MP4AudioSampleEntry(Mp4Atom):
    parse_children = True
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = Mp4Atom.parse(src, parent, options)
        r = FieldReader(clz, src, kwargs)
        r.get(6, 'reserved') # (8)[6] reserved
        r.read('H', "data_reference_index")
        r.get(8+4+4, 'reserved') # (8)[6] reserved
        r.read('H', "timescale")
        r.get(2, 'reserved') # (16) reserved
        return kwargs

    def encode_fields(self, dest):
        w = FieldWriter(self, dest)
        w.write(6, 'reserved', '')
        w.write('H','data_reference_index')
        w.write(8, 'reserved_8', '')
        w.write('H', 'reserved_2', 2)
        w.write('H', 'reserved_2', 16)
        w.write(4, 'reserved_4', '')
        w.write('H', 'timescale')
        w.write(2, 'reserved', '')

MP4_BOXES['mp4a'] = MP4AudioSampleEntry


class EncryptedMP4A(MP4AudioSampleEntry):
    pass

MP4_BOXES['enca'] = EncryptedMP4A


class ESDescriptorBox(FullBox):
    def __init__(self, **kwargs):
        super(ESDescriptorBox, self).__init__(**kwargs)
        for d in self._fields["descriptors"]:
            d.parent = self

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        descriptors=[]
        end = kwargs["position"]+kwargs["size"]
        while src.tell()<end:
            d = Descriptor.create(src, parent, options)
            descriptors.append(d)
            if src.tell() != (d.position + d.size + d.header_size):
                options.log.warning("Expected descriptor %s to be %d bytes, but read %d bytes",
                                    d.classname, d.size + d.header_size, src.tell() - d.position)
                src.seek(d.position + d.size + d.header_size)
        kwargs["descriptors"] = descriptors
        return kwargs

    def descriptor(self, name):
        for d in self._fields["descriptors"]:
            if type(d).__name__ == name:
                return d
            v = getattr(d, name)
            if v is not None:
                return v

    def remove_descriptor(self, name):
        for idx, d in enumerate(self._fields['descriptors']):
            if type(d).__name__==name:
                del self._fields['descriptors'][idx]
                if d.size:
                    self.size -= d.size
                self._invalidate()
                return
        raise AttributeError(name)

    def encode_fields(self, dest):
        super(ESDescriptorBox, self).encode_fields(dest)
        for d in self.descriptors:
            d.encode(dest)

MP4_BOXES['esds'] = ESDescriptorBox

class SampleDescriptionBox(FullBox):
    parse_children = True

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        kwargs["entry_count"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        super(SampleDescriptionBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.entry_count))

MP4_BOXES['stsd'] = SampleDescriptionBox

class TrackFragmentHeaderBox(FullBox):
    base_data_offset_present = 0x000001
    sample_description_index_present = 0x000002
    default_sample_duration_present = 0x000008
    default_sample_size_present = 0x000010
    default_sample_flags_present = 0x000020
    duration_is_empty = 0x010000
    default_base_is_moof = 0x020000

    def __init__(self, *args, **kwargs):
        super(TrackFragmentHeaderBox, self).__init__(*args, **kwargs)
        #default base offset = first byte of moof
        if self.base_data_offset is None:
            self.base_data_offset= self.find_atom('moof').position
        
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        kwargs["base_data_offset"] = None
        kwargs["sample_description_index"] = 0
        kwargs["default_sample_duration"] = 0
        kwargs["default_sample_size"] = 0
        kwargs["default_sample_flags"] = 0
        kwargs["track_id"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.base_data_offset_present:
            kwargs["base_data_offset"] = struct.unpack('>Q', src.read(8))[0]
        elif kwargs["flags"] & clz.default_base_is_moof:
            kwargs["base_data_offset"] = parent.find_atom('moof').position
        if kwargs["flags"] & clz.sample_description_index_present:
            kwargs["sample_description_index"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.default_sample_duration_present:
            kwargs["default_sample_duration"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.default_sample_size_present:
            kwargs["default_sample_size"] = struct.unpack('>I', src.read(4))[0]
        if kwargs["flags"] & clz.default_sample_flags_present:
            kwargs["default_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        super(TrackFragmentHeaderBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.track_id))
        if self.flags & self.base_data_offset_present:
            dest.write(struct.pack('>Q', self.base_data_offset))
        if self.flags & self.sample_description_index_present:
            dest.write(struct.pack('>I', self.sample_description_index))
        if self.flags & self.default_sample_duration_present:
            dest.write(struct.pack('>I', self.default_sample_duration))
        if self.flags & self.default_sample_size_present:
            dest.write(struct.pack('>I', self.default_sample_size))
        if self.flags & self.default_sample_flags_present:
            dest.write(struct.pack('>I', self.default_sample_flags))

    def _field_repr(self, exclude):
        exclude.append('default_sample_flags')
        fields = super(TrackFragmentHeaderBox,self)._field_repr(exclude)
        fields.append('default_sample_flags=0x%08x'%self.default_sample_flags)
        return fields

MP4_BOXES['tfhd'] = TrackFragmentHeaderBox


class TrackHeaderBox(FullBox):
    Track_enabled    = 0x000001
    Track_in_movie   = 0x000002
    Track_in_preview = 0x000004

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
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
        kwargs["creation_time"] = from_iso_epoch(kwargs["creation_time"])
        kwargs["modification_time"] = from_iso_epoch(kwargs["modification_time"])
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
        return kwargs

    def encode_fields(self, dest):
        self.flags = 0
        if self.is_enabled:
            self.flags |= self.Track_enabled
        if self.in_movie:
            self.flags |= self.Track_in_movie
        if self.in_preview:
            self.flags |= self.Track_in_preview
        super(TrackHeaderBox, self).encode_fields(dest)
        if self.version == 1:
            sz = '>Q'
        else:
            sz = '>I'
        dest.write(struct.pack(sz, to_iso_epoch(self.creation_time)))
        dest.write(struct.pack(sz, to_iso_epoch(self.modification_time)))
        dest.write(struct.pack('>I', self.track_id))
        dest.write('\0' * 4) # reserved
        dest.write(struct.pack(sz, self.duration))
        dest.write('\0' * 8) # reserved
        dest.write(struct.pack('>H', self.layer))
        dest.write(struct.pack('>H', self.alternate_group))
        dest.write(struct.pack('>H', int(self.volume * 256.0)))
        dest.write('\0' * 2) # reserved
        for m in self.matrix:
            dest.write(struct.pack('>I', m))
        dest.write(struct.pack('>I', long(self.width * 65536.0)))
        dest.write(struct.pack('>I', long(self.height * 65536.0)))
MP4_BOXES['tkhd'] = TrackHeaderBox

class TrackFragmentDecodeTimeBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        if kwargs["version"]==1:
            kwargs["base_media_decode_time"] = struct.unpack('>Q', src.read(8))[0]
        else:
            kwargs["base_media_decode_time"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        payload = io.BytesIO()
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
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        kwargs["track_id"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_description_index"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_duration"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_size"]  = struct.unpack('>I', src.read(4))[0]
        kwargs["default_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        super(TrackExtendsBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.track_id))
        dest.write(struct.pack('>I', self.default_sample_description_index))
        dest.write(struct.pack('>I', self.default_sample_duration))
        dest.write(struct.pack('>I', self.default_sample_size))
        dest.write(struct.pack('>I', self.default_sample_flags))

MP4_BOXES['trex'] = TrackExtendsBox


class MediaHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
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
        kwargs["creation_time"] = from_iso_epoch(kwargs["creation_time"])
        kwargs["modification_time"] = from_iso_epoch(kwargs["modification_time"])
        tmp = struct.unpack('>H', src.read(2))[0]
        kwargs["language"] = chr(0x60+((tmp>>10)&0x1F)) + chr(0x60+((tmp>>5)&0x1F)) + chr(0x60+(tmp&0x1F))
        src.read(2) # unsigned int(16) pre_defined = 0
        return kwargs

    def encode_fields(self, dest):
        super(MediaHeaderBox, self).encode_fields(dest)
        if self.version == 1:
            sz = '>Q'
        else:
            sz = '>I'
        dest.write(struct.pack(sz, to_iso_epoch(self.creation_time)))
        dest.write(struct.pack(sz, to_iso_epoch(self.modification_time)))
        dest.write(struct.pack('>I', self.timescale))
        dest.write(struct.pack(sz, self.duration))
        chars = map(lambda c: ord(c) - 0x60, list(self.language))
        lang = (chars[0] << 10) + (chars[1] << 5) + chars[2]
        dest.write(struct.pack('>H', lang))
        dest.write(struct.pack('>H', 0)) # pre_defined

MP4_BOXES['mdhd'] = MediaHeaderBox

class MovieFragmentHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        kwargs["sequence_number"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        super(MovieFragmentHeaderBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.sequence_number))
    
MP4_BOXES['mfhd'] = MovieFragmentHeaderBox

class HandlerBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        src.read(4) # unsigned int(32) pre_defined = 0
        kwargs["handler_type"] = src.read(4)
        src.read(12) # const unsigned int(32)[3] reserved = 0;
        name_len = kwargs["position"] + kwargs["size"] - src.tell()
        kwargs["name"] = src.read(name_len)
        return kwargs

    def encode_fields(self, dest):
        super(HandlerBox, self).encode_fields(dest)
        dest.write('\0' * 4) # pre_defined = 0
        dest.write(self.handler_type)
        dest.write('\0' * 12) # reserved = 0
        dest.write(self.name)

MP4_BOXES['hdlr'] = HandlerBox

class MovieExtendsHeaderBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        if kwargs["version"]==1:
            kwargs["fragment_duration"] = struct.unpack('>Q', src.read(8))[0]
        else:
            kwargs["fragment_duration"] = struct.unpack('>I', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        super(MovieExtendsHeaderBox, self).encode_fields(dest)
        if self.version == 1:
            dest.write(struct.pack('>Q', self.fragment_duration))
        else:
            dest.write(struct.pack('>I', self.fragment_duration))
MP4_BOXES['mehd'] = MovieExtendsHeaderBox


class SampleAuxiliaryInformationSizesBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
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
        payload = io.BytesIO()
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

    def _field_repr(self, exclude):
        exclude.append('aux_info_type')
        fields = super(FullBox,self)._field_repr(exclude)
        if self._fields.has_key("aux_info_type"):
            if isinstance(self.aux_info_type, basestring):
                fields.append('aux_info_type="%s"'%self.aux_info_type)
            else:
                fields.append('aux_info_type=0x%x'%self.aux_info_type)
        return fields

MP4_BOXES['saiz'] = SampleAuxiliaryInformationSizesBox


class CencSampleAuxiliaryData(NamedObject):
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

    def _field_repr(self, exclude):
        rv = []
        rv.append('initialization_vector=0x%s'%self.initialization_vector.encode('hex'))
        if haskey(self._fields, "subsamples"):
            subsamples = []
            for s in self._fields["subsamples"]:
                subsamples.append('{"clear":%d, "encrypted":%d}'%(s["clear"], s["encrypted"]))
            rv.append('subsamples=[%s]'%(','.join(subsamples)))
        return rv


class CencSampleEncryptionBox(FullBox):
    def __init__(self, **kwargs):
        super(CencSampleEncryptionBox, self).__init__(**kwargs)
        if self._fields.has_key("samples"):
            self._fields["samples"] = map(lambda s: CencSampleAuxiliaryData(**s), self._fields["samples"])

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        if kwargs["flags"] & 0x01:
            f = '\000'+src.read(3)
            kwargs["algorithm_id"] = struct.unpack('>I',f)[0]
            kwargs["iv_size"] = struct.unpack('B', src.read(1))[0]
            if kwargs["iv_size"] == 0:
                kwargs["iv_size"] = 8
            kwargs["kid"] = src.read(16)
        else:
            try:
                moov = parent.find_atom("moov")
                tenc = moov.find_child("tenc")
                kwargs["iv_size"] = tenc.iv_size
            except AttributeError:
                kwargs["iv_size"] = options.iv_size
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
        payload = io.BytesIO()
        if self.flags & 0x01:
            payload.write(struct.pack('>I', self.algorithm_id))
            payload.write(struct.pack('B', self.iv_size))
            payload.write(self.kid)
        payload.write(struct.pack('>I', len(self.samples)))
        for s in self.samples:
            s.encode_fields(payload)
        return super(CencSampleEncryptionBox, self).encode_fields(dest=dest, payload=payload.getvalue())

    def _field_repr(self, exclude):
        exclude += ['kid', 'samples']
        fields = super(CencSampleEncryptionBox,self)._field_repr(exclude)
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
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
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
        payload = io.BytesIO()
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

    def _field_repr(self, exclude):
        exclude.append('aux_info_type')
        fields = super(FullBox,self)._field_repr(exclude)
        if self._fields.has_key("aux_info_type"):
            if isinstance(self.aux_info_type, basestring):
                fields.append('aux_info_type="%s"'%self.aux_info_type)
            else:
                fields.append('aux_info_type=0x%x'%self.aux_info_type)
        return fields
SampleAuxiliaryInformationOffsetsBox.check_info_type = SampleAuxiliaryInformationSizesBox.check_info_type

MP4_BOXES['saio'] = SampleAuxiliaryInformationOffsetsBox


class TrackSample(NamedObject):
    def __init__(self, index, offset, **kwargs):
        self.index = index
        self.offset = offset
        self._fields = {}
        for key,value in kwargs.iteritems():
            self._fields[key] = value

    def __getattr__(self, name):
        if name[0]=="_":
            # __getattribute__ should have responded before __getattr__ called
            raise AttributeError(name)
        if self._fields.has_key(name):
            return self._fields[name]
        raise AttributeError(name)

    @classmethod
    def parse(clz, src, index, offset, trun, tfhd):
        kwargs = {
            'index': index,
            'offset': offset,
            'duration': None
        }
        flags = trun["flags"]
        if flags & TrackFragmentRunBox.sample_duration_present:
            kwargs['duration'] = struct.unpack('>I', src.read(4))[0]
        elif tfhd.default_sample_duration:
            kwargs['duration'] = tfhd.default_sample_duration
        if flags & TrackFragmentRunBox.sample_size_present:
            kwargs['size'] = struct.unpack('>I', src.read(4))[0]
        else:
            kwargs['size'] = tfhd.default_sample_size
        if flags & TrackFragmentRunBox.sample_flags_present:
            kwargs['flags'] = struct.unpack('>I', src.read(4))[0]
        else:
            kwargs['flags'] = tfhd.default_sample_flags
        if index==0 and (flags & TrackFragmentRunBox.first_sample_flags_present):
            kwargs['flags'] = trun["first_sample_flags"]
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            kwargs["composition_time_offset"] = struct.unpack('>i', src.read(4))[0]
        return kwargs

    def encode_fields(self, dest):
        flags = self.parent.flags
        d = FieldWriter(self, dest)
        if flags & TrackFragmentRunBox.sample_duration_present:
            d.write('I', 'duration')
        if flags & TrackFragmentRunBox.sample_size_present:
            d.write('I', 'size')
        if flags & TrackFragmentRunBox.sample_flags_present:
            d.write('I', 'flags')
        if flags & TrackFragmentRunBox.sample_composition_time_offsets_present:
            d.write('I', 'composition_time_offset')

    def _field_repr(self, exclude):
        rv = ['index='+str(self.index), 'offset='+str(self.offset)]
        for k,v in self._fields.iteritems():
            if v is None or k in exclude:
                continue
            if k=='flags':
                v = hex(v)
            rv.append('{0}={1}'.format(k, v))
        return rv


class TrackFragmentRunBox(FullBox):
    data_offset_present = 0x000001
    first_sample_flags_present = 0x000004
    sample_duration_present = 0x000100 #each sample has its own duration?
    sample_size_present = 0x000200 #each sample has its own size, otherwise the default is used.
    sample_flags_present = 0x000400 # each sample has its own flags, otherwise the default is used.
    sample_composition_time_offsets_present = 0x000800

    def __init__(self, **kwargs):
        super(TrackFragmentRunBox, self).__init__(**kwargs)
        for s in self.samples:
            s.parent = self

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        tfhd = parent.tfhd
        sample_count = struct.unpack('>I', src.read(4))[0]
        kwargs["sample_count"] = sample_count
        if kwargs["flags"] & clz.data_offset_present:
            kwargs["data_offset"] = struct.unpack('>i', src.read(4))[0]
        else:
            kwargs["data_offset"] = 0
        if kwargs["flags"] & clz.first_sample_flags_present:
            kwargs["first_sample_flags"] = struct.unpack('>I', src.read(4))[0]
        else:
            kwargs["first_sample_flags"] = 0
        #print('Trun: count=%d offset=%d flags=%x'%(kwargs["sample_count,kwargs["data_offset,kwargs["first_sample_flags))
        kwargs["samples"] = []
        offset = kwargs["data_offset"]
        for i in range(sample_count):
            ts = TrackSample.parse(src, i, offset, kwargs, tfhd)
            ts = TrackSample(**ts)
            kwargs["samples"].append(ts)
            offset += ts.size
        return kwargs

    def parse_samples(self, src, nal_length_field_length):
        tfhd = self.parent.tfhd
        for sample in self.samples:
            pos = sample.offset + tfhd.base_data_offset
            end = pos + sample.size
            sample.nals = []
            while pos < end:
                src.seek(pos)
                nal = Nal(src,nal_length_field_length)
                pos += nal.size + nal_length_field_length
                sample.nals.append(nal)

    def encode_fields(self, dest):
        super(TrackFragmentRunBox, self).encode_fields(dest)
        dest.write(struct.pack('>I', self.sample_count))
        if self.flags & self.data_offset_present:
            dest.write(struct.pack('>i', self.data_offset))
        if self.flags & self.first_sample_flags_present:
            dest.write(struct.pack('>I', self.first_sample_flags))
        for sample in self.samples:
            sample.encode_fields(dest)

MP4_BOXES['trun']=TrackFragmentRunBox

class TrackEncryptionBox(FullBox):
    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        r = FieldReader(clz, src, kwargs)
        r.read('0I',"is_encrypted")
        r.read('B',"iv_size")
        r.read(16,"default_kid")
        return kwargs

    def encode_fields(self, dest):
        super(TrackEncryptionBox, self).encode_fields(dest)
        w = FieldWriter(self, dest)
        w.write('0I',"is_encrypted")
        w.write('B',"iv_size")
        w.write(16,"default_kid")

    def _field_repr(self, exclude):
        exclude.append('default_kid')
        fields = super(TrackEncryptionBox,self)._field_repr(exclude)
        fields.append('default_kid="{}".decode("hex")'.format(self.default_kid.encode('hex')))
        return fields
MP4_BOXES['tenc']=TrackEncryptionBox

class ContentProtectionSpecificBox(FullBox):
    def __init__(self, **kwargs):
        super(ContentProtectionSpecificBox, self).__init__(**kwargs)
        if len(self.system_id) != 16:
            if re.match(r'^(0x)?[0-9a-f-]+$', self.system_id, re.IGNORECASE):
                if self.system_id.startswith('0x'):
                    self.system_id = self.system_id[2:]
                self.system_id = self.system_id.replace('-','').decode('hex')
        if len(self.system_id) != 16:
            raise ValueError("Invalid system ID")

    @classmethod
    def parse(clz, src, parent, options):
        kwargs = FullBox.parse(src, parent, options)
        r = FieldReader(clz, src, kwargs)
        r.read(16, "system_id")
        if kwargs["version"] > 0:
            kid_count = r.get('I', 'kid_count')
            kwargs["key_ids"] = []
            for i in range(kid_count):
                kwargs["key_ids"].append(r.read(16, 'kid'))
        data_size = r.get('I', 'data_size')
        if data_size > 0:
            r.read(data_size,"data")
        else:
            kwargs["data"] = None
        return kwargs

    def encode_fields(self, dest):
        super(ContentProtectionSpecificBox, self).encode_fields(dest)
        w = FieldWriter(self, dest)
        w.write(16, 'system_id')
        if self.version > 0:
            w.write('I', 'num_keys', len(self.key_ids))
            for kid in self.key_ids:
                w.write(16, 'kid', kid)
        if self.data is None:
            w.write('I', 'data_len', 0)
        else:
            w.write('I', 'data_len', len(self.data))
            w.write(None, 'data')

    def _field_repr(self, exclude):
        exclude += ['data','system_id', 'key_ids']
        fields = super(FullBox,self)._field_repr(exclude)
        if self._fields["data"] is not None:
            data = 'base64.b64decode("{}")'.format(base64.b64encode(self._fields["data"]))
        else:
            data = "None"
        fields.append('data={}'.format(data))
        fields.append('system_id="{0}".decode("hex")'.format(self.system_id.encode('hex')))
        if self.version > 0:
            kids = map(lambda k: '"{0}".decode("hex")'.format(k.encode('hex')), self.key_ids)
            fields.append('key_ids=[{}]'.format(','.join(kids)))
        return fields
MP4_BOXES['pssh'] = ContentProtectionSpecificBox

class IsoParser(object):
    def walk_atoms(self, filename, atom=None):
        atoms = None
        src = None
        try:
            if isinstance(filename, basestring):
                src = io.open(filename, mode="rb", buffering=16384)
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

    logging.basicConfig()
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
                show_atom(args.show, atom)
