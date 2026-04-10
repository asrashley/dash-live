import argparse
import json
import logging
from typing import Any, BinaryIO, TypedDict, cast
from weakref import ref


from .atom_factory import AtomFactory
from .atom import MODULE_PREFIX_RE, Mp4Atom
from .boxes.avc1 import AVC1SampleEntryFactory
from .boxes.avc3 import AVC3SampleEntryFactory
from .boxes.avcC import AVCConfigurationBoxFactory
from .boxes.btrt import BitRateBoxFactory
from .boxes.dac3 import AC3SpecificBoxFactory
from .boxes.dec3 import EAC3SpecificBoxFactory
from .boxes.emsg import EventMessageBoxFactory
from .boxes.enca import EncryptedMP4AFactory
from .boxes.encv import EncryptedSampleEntryFactory
from .boxes.esds import ESDescriptorBoxFactory
from .boxes.frma import OriginalFormatBoxFactory
from .boxes.ftab import FontTableBoxFactory
from .boxes.ftyp import FileTypeBoxFactory
from .boxes.hdlr import HandlerBoxFactory
from .boxes.hev1 import HEV1SampleEntryFactory
from .boxes.hvc1 import HVC1SampleEntryFactory
from .boxes.hvcC import HEVCConfigurationBoxFactory
from .boxes.lazy_loaded import LazyLoadedBox
from .boxes.mdhd import MediaHeaderBoxFactory
from .boxes.mdia import MediaDataBoxFactory
from .boxes.mehd import MovieExtendsHeaderBoxFactory
from .boxes.mfhd import MovieFragmentHeaderBoxFactory
from .boxes.mime import MimeBoxFactory
from .boxes.minf import MediaInformationBoxFactory
from .boxes.moof import MovieFragmentBoxFactory
from .boxes.moov import MovieBoxFactory
from .boxes.mp4a import MP4AudioSampleEntryFactory
from .boxes.mvex import MovieExtendsBoxFactory
from .boxes.mvhd import MovieHeaderBoxFactory
from .boxes.pasp import PixelAspectRatioBoxFactory
from .boxes.pssh import ContentProtectionSpecificBoxFactory
from .boxes.saio import SampleAuxiliaryInformationOffsetsBoxFactory
from .boxes.saiz import SampleAuxiliaryInformationSizesBoxFactory
from .boxes.schi import SchemaInformationBoxFactory
from .boxes.schm import ProtectionSchemeTypeBoxFactory
from .boxes.senc import CencSampleEncryptionBoxFactory
from .boxes.sidx import SegmentIndexBoxFactory
from .boxes.sinf import ProtectionSchemeInformationBoxFactory
from .boxes.stbl import SampleTableBoxFactory
from .boxes.stpp import XMLSubtitleSampleEntryFactory
from .boxes.stsd import SampleDescriptionBoxFactory
from .boxes.styp import SegmentTypeBoxFactory
from .boxes.tenc import TrackEncryptionBoxFactory
from .boxes.tfdt import TrackFragmentDecodeTimeBoxFactory
from .boxes.tfhd import TrackFragmentHeaderBoxFactory
from .boxes.tkhd import TrackHeaderBoxFactory
from .boxes.traf import TrackFragmentBoxFactory
from .boxes.trak import TrackBoxFactory
from .boxes.trex import TrackExtendsBoxFactory
from .boxes.trun import TrackFragmentRunBoxFactory
from .boxes.tx3g import TextSampleEntryFactory
from .boxes.udta import UserDataBoxFactory
from .boxes.unknown import UnknownBoxFactory
from .boxes.vttC import WebVTTConfigurationBoxFactory
from .boxes.wvtt import WVTTSampleEntryFactory
from .boxes.ac_3 import AC3SampleEntryFactory
from .boxes.ec_3 import EC3SampleEntryFactory
from .boxes.piff import PiffSampleEncryptionBoxFactory
from .wrapper import Wrapper
from .options import Options
from .event_bus import EventBus

FOURCC_TO_ATOM: dict[str, AtomFactory] = {}  # map from fourcc code to Mp4Atom class factory

NAMES_TO_ATOM: dict[str, AtomFactory] = {
    # 'BoxWithChildren': BoxWithChildrenFactory(),
    'UnknownBox': UnknownBoxFactory(),
}  # map from class name to Mp4Atom class factory

ALL_ATOMS: list[type[AtomFactory]] = [
    FileTypeBoxFactory,
    SegmentTypeBoxFactory,
    MovieBoxFactory,
    TrackBoxFactory,
    TrackFragmentBoxFactory,
    MovieFragmentBoxFactory,
    MediaInformationBoxFactory,
    MovieExtendsBoxFactory,
    MediaDataBoxFactory,
    SchemaInformationBoxFactory,
    ProtectionSchemeInformationBoxFactory,
    SampleTableBoxFactory,
    UserDataBoxFactory,
    MovieHeaderBoxFactory,
    AVC1SampleEntryFactory,
    AVC3SampleEntryFactory,
    HEV1SampleEntryFactory,
    HVC1SampleEntryFactory,
    EncryptedSampleEntryFactory,
    FontTableBoxFactory,
    TextSampleEntryFactory,
    WebVTTConfigurationBoxFactory,
    BitRateBoxFactory,
    WVTTSampleEntryFactory,
    XMLSubtitleSampleEntryFactory,
    MimeBoxFactory,
    AVCConfigurationBoxFactory,
    HEVCConfigurationBoxFactory,
    PixelAspectRatioBoxFactory,
    EC3SampleEntryFactory,
    AC3SampleEntryFactory,
    EAC3SpecificBoxFactory,
    AC3SpecificBoxFactory,
    OriginalFormatBoxFactory,
    MP4AudioSampleEntryFactory,
    EncryptedMP4AFactory,
    ESDescriptorBoxFactory,
    SampleDescriptionBoxFactory,
    TrackFragmentHeaderBoxFactory,
    TrackHeaderBoxFactory,
    TrackFragmentDecodeTimeBoxFactory,
    TrackExtendsBoxFactory,
    MediaHeaderBoxFactory,
    MovieFragmentHeaderBoxFactory,
    HandlerBoxFactory,
    MovieExtendsHeaderBoxFactory,
    SampleAuxiliaryInformationSizesBoxFactory,
    CencSampleEncryptionBoxFactory,
    PiffSampleEncryptionBoxFactory,
    ProtectionSchemeTypeBoxFactory,
    SampleAuxiliaryInformationOffsetsBoxFactory,
    TrackFragmentRunBoxFactory,
    TrackEncryptionBoxFactory,
    ContentProtectionSpecificBoxFactory,
    SegmentIndexBoxFactory,
    EventMessageBoxFactory,
]  # list of all atom factories


class DeferredBox(TypedDict):
    factory: AtomFactory
    initial_data: dict[str, Any]
    index: int


class IsoParser:
    @staticmethod
    def walk_atoms(filename: str | BinaryIO, atom: Mp4Atom | None = None, options: Options | None = None) -> list[Mp4Atom]:
        atoms: list[Mp4Atom] = []
        src = None
        try:
            if options is not None:
                options.log.debug('Parse %s', filename)
            if isinstance(filename, str):
                src = open(filename, mode="rb", buffering=32768)
            else:
                src = filename
            atoms = cast(list[Mp4Atom], IsoParser.load(src, options=options))
        finally:
            if src and isinstance(filename, (str, str)):
                src.close()
        return atoms

    @staticmethod
    def show_atom(atom, atom_types: set[str], as_json: bool, with_children: set[str],
                  count: int = 0) -> int:
        check_children = True
        if atom.atom_name() in atom_types:
            if atom.atom_name() in with_children:
                exclude = atom.DEFAULT_EXCLUDE
                check_children = False
            else:
                exclude = atom.DEFAULT_EXCLUDE.union({'children'})
            if atom.atom_type == b'mdat' and 'mdat' not in with_children:
                exclude.add('data')
            if as_json:
                if count > 0:
                    print(',')
                item = atom.toJSON(exclude=exclude, pure=True)
                item['atom_type'] = atom.atom_name()
                if atom.children is not None and 'children' in exclude:
                    item['children'] = [a.atom_name() for a in atom.children]
                print(json.dumps(item, sort_keys=True, indent=2))
            else:
                try:
                    exclude.remove('atom_type')
                except KeyError:
                    pass
                print(atom.as_python(exclude))
            count += 1
        if check_children and atom.children is not None:
            ch_count = 0
            for child in atom.children:
                ch_count += IsoParser.show_atom(
                    child, atom_types=atom_types, as_json=as_json,
                    with_children=with_children, count=ch_count)
        return count

    @classmethod
    def load(cls,
             src: BinaryIO,
             parent: Mp4Atom | None = None,
             options: Options | dict[str, Any] | None = None) -> list[Mp4Atom]:
        """
        Parse the given source to create MP4 atoms.
        :src: a readable (file) source
        :parent: the parent MP4Atom
        :options: the mp4.Options to use, or a dictionary of option values
        """
        assert src is not None
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        assert options is not None
        cls._setup()
        end: int | None = None
        prefix: str = ''
        cursor: int
        ev_bus: EventBus["Mp4Atom"]
        rv: list[Mp4Atom] = []
        top_level: bool = parent is None
        if parent is not None:
            try:
                cursor = parent.payload_start
            except AttributeError:
                cursor = src.tell()
            end = parent.position + parent.size
            prefix = f'{parent._fullname}: '
            assert parent._ev_bus is not None
            ev_bus = parent._ev_bus
            # the _children list might be used when parsing an atom, as it
            # might need to get data from one of its peers
            if parent._children is None:
                parent._children = rv
            else:
                rv = parent._children
        else:
            cursor = src.tell()
            parent = Wrapper(position=src.tell(), options=options)
            ev_bus = EventBus["Mp4Atom"]()
            parent._ev_bus = ev_bus
        if options.iv_size and options.iv_size > 16:
            # assume user has provided IV size in bits rather than bytes
            options.iv_size = options.iv_size // 8
            assert options.iv_size in {8, 16}
        if end is None:
            options.log.debug('%sLoad start=%d end=None', prefix, cursor)
        else:
            options.log.debug('%sLoad start=%d end=%d (%d)', prefix,
                              cursor, end, end - cursor)
        deferred_boxes: list[DeferredBox] = []
        unknown = UnknownBoxFactory()
        while end is None or cursor < end:
            assert cursor is not None
            if src.tell() != cursor:
                options.log.debug('Move cursor from %d to %d', src.tell(), cursor)
                src.seek(cursor)
            hdr = AtomFactory.parse_header(src, options=options)
            if hdr is None:
                break
            factory: AtomFactory
            factory = FOURCC_TO_ATOM.get(hdr['atom_type'], unknown)  # pyright: ignore[reportFunctionMemberAccess]
            options.log.debug('%sfound atom "%s" type=%s pos=%d size=%d',
                              prefix,
                              hdr['atom_type'], type(factory).__name__,
                              hdr['position'], hdr['size'])
            if factory.REQUIRED_PEERS is not None:
                required = set(factory.REQUIRED_PEERS)
                for name in factory.REQUIRED_PEERS:
                    if parent.find_child(name) is not None:
                        required.remove(name)
                if required:
                    options.log.debug(
                        'Defer parsing of "%s" as %s needs to be parsed',
                        hdr['atom_type'], list(required))
                    del hdr['_buffer']
                    db: DeferredBox = {'factory': factory, 'initial_data': hdr, 'index': len(rv)}
                    deferred_boxes.append(db)
                    cursor += hdr['size']
                    continue
            encoded: bytes | None = None
            lazy_load_this_atom: bool = not top_level and options.lazy_load and factory != unknown
            if lazy_load_this_atom:
                options.log.debug(
                    'lazy loading parent=%s this=%s pos=%d', parent.atom_type,
                    hdr["atom_type"], hdr["position"])
                kwargs = LazyLoadedBox.parse(src, parent, options=options, initial_data=hdr)
                # hexdump_buffer(
                #    f'lazy {kwargs["atom_type"]}@{kwargs["position"]}', kwargs['buffer'], 32)
            else:
                del hdr['_buffer']
                kwargs = factory.parse(src, parent, options=options, initial_data=hdr)
            if kwargs is None:
                break
            kwargs['_parent'] = ref(parent)
            kwargs['options'] = options
            atom: Mp4Atom
            if lazy_load_this_atom:
                atom = LazyLoadedBox(**kwargs)
                atom._box_factory = factory
                deps = factory.depends_upon()
                for name in deps:
                    ev_bus.on(f'change.{name}', atom.atom_changed)
            else:
                if options.mode == 'rw' and not factory.parse_children:
                    sz: int = hdr["size"] - hdr["header_size"]
                    if sz == 0:
                        encoded = b''
                    else:
                        here: int = src.tell()
                        encoded = src.read(sz)
                        src.seek(here)
                atom = factory.create(**kwargs)
                atom.payload_start = src.tell()
            atom._encoded = encoded
            atom._ev_bus = ev_bus
            rv.append(atom)
            # print(f'name={atom.atom_name()} pos={atom.position} size={atom.size} children={factory.parse_children}')
            if factory.parse_children:
                # options.log.debug('Parse %s children', hdr['atom_type'])
                atom._children = []
                cls.load(src, parent=atom, options=options)
            if (src.tell() - atom.position) != atom.size:
                msg = r'{}: expected "{}" to contain {:d} bytes but parsed {:d} bytes'.format(
                    prefix, atom.atom_type, atom.size, src.tell() - atom.position)
                options.log.warning(msg)
                if options.strict:
                    raise ValueError(msg)
            cursor += atom.size
        if not deferred_boxes:
            return rv
        cur_pos = src.tell()
        for item in deferred_boxes:
            options.log.debug('Parsing deferred box: "%s"',
                              item['initial_data']['atom_type'])
            hdr = item['initial_data']
            df_factory: AtomFactory = item['factory']
            src.seek(hdr['position'] + hdr['header_size'])
            df_kwargs = df_factory.parse(
                src, parent, options=options, initial_data=hdr)
            assert df_kwargs is not None
            df_kwargs['_parent'] = ref(parent) if parent else None
            df_kwargs['options'] = options
            new_atom = df_factory.create(**df_kwargs)
            new_atom.payload_start = src.tell()
            if df_factory.parse_children:
                options.log.debug('Parse %s children', new_atom.atom_type)
                cls.load(src, new_atom, options)
            options.log.debug('finished parsing of deferred "%s"',
                              new_atom.atom_type)
            rv.insert(item['index'], new_atom)
        src.seek(cur_pos)
        return rv

    @classmethod
    def load_wrapped(cls,
                     src: BinaryIO,
                     options: Options | dict[str, Any] | None = None,
                     ) -> Wrapper:
        position: int = src.tell()
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        children: list[Mp4Atom] = IsoParser.load(src, options=options)
        size: int = src.tell() - position
        return Wrapper(children=children, options=options, position=position, size=size)

    @classmethod
    def fromJSON(cls,
                 src: dict[str, Any] | list[dict[str, Any]],
                 parent: Mp4Atom | None = None,
                 options: Options | dict | None = None) -> Mp4Atom | list[Mp4Atom]:
        cls._setup()
        assert src is not None
        if options is None:
            options = Options()
        elif isinstance(options, dict):
            options = Options(**options)
        if isinstance(src, list):
            return [cast(Mp4Atom, cls.fromJSON(atom)) for atom in src]

        factory: AtomFactory
        if '_type' in src:
            name = src['_type']
            name = MODULE_PREFIX_RE.sub(r'\g<box_name>', name)
            factory = NAMES_TO_ATOM[name]
        elif 'atom_type' in src:
            factory = FOURCC_TO_ATOM[src['atom_type']]
        else:
            factory = UnknownBoxFactory()
        src['_parent'] = ref(parent) if parent else None
        src['options'] = options
        if 'children' not in src and '_children' not in src:
            return factory.create(**src)
        try:
            children = src['_children']
        except KeyError:
            children = src['children']
        rv = factory.create(**src)
        assert rv is not None
        rv._children = []
        if children is None:
            return rv
        for child in children:
            if isinstance(child, dict):
                child['_parent'] = ref(rv)
                child['options'] = options
                atom = cls.fromJSON(child)
                assert isinstance(atom, Mp4Atom)
                rv._children.append(atom)
            else:
                rv._children.append(child)
        return rv

    @classmethod
    def _setup(cls) -> None:
        Mp4Atom.FROM_JSON = cls.fromJSON
        LazyLoadedBox.CHILDREN_LOADER = cls.load
        if not FOURCC_TO_ATOM:
            factory_type: type[AtomFactory]
            for factory_type in ALL_ATOMS:
                ft = factory_type()
                FOURCC_TO_ATOM[ft.fourcc()] = ft
                NAMES_TO_ATOM[ft.classname()] = ft

    @classmethod
    def main(cls):
        logging.basicConfig()
        ap = argparse.ArgumentParser(description='MP4 parser')
        ap.add_argument('-d', '--debug', action="store_true")
        ap.add_argument('--json', action="store_true")
        ap.add_argument(
            '-s', '--show', help='Show contents of specified atom')
        ap.add_argument(
            '-t', '--tree', action="store_true", help='Show atom tree')
        ap.add_argument(
            '--ivsize', type=int, help='IV size (in bits or bytes)')
        ap.add_argument(
            'mp4file', help='Filename of MP4 file', nargs='+', default=None)
        args = ap.parse_args()
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        options = Options(lazy_load=False)
        if args.ivsize:
            if args.ivsize > 16:
                # user has provided IV size in bits
                options.iv_size = args.ivsize // 8
            else:
                options.iv_size = args.ivsize
        if args.json:
            print('[')
        if args.show:
            atom_types = set()
            with_children = set()
            for name in args.show.split(','):
                if name.endswith('+'):
                    name = name[:-1]
                    with_children.add(name)
                atom_types.add(name)
        for filename in args.mp4file:
            atoms = IsoParser.walk_atoms(filename, options=options)
            count = 0
            for atom in atoms:
                if args.tree:
                    atom.dump()
                if args.show:
                    count += IsoParser.show_atom(
                        atom, atom_types=atom_types, with_children=with_children,
                        as_json=args.json, count=count)
        if args.json:
            print(']')
