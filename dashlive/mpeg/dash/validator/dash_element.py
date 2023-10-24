#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import logging
import os
from typing import Optional
import urllib.parse

from lxml import etree as ET

from dashlive.utils.date_time import to_iso_datetime

from .concurrent_pool import ConcurrentWorkerPool
from .errors import ErrorSource, LineRange, ValidationChecks, ValidationError
from .options import ValidatorOptions
from .progress import NullProgress

class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs) -> tuple[str, dict]:
        # url = getattr(self.extra, "url", None)
        # if url is not None and 'http' not in msg:
        #    return (f'{msg}\n    "{url}"\n', kwargs,)
        return (msg, kwargs,)


class DashElement(ABC):
    class Parent:
        pass

    xmlNamespaces = {
        'cenc': 'urn:mpeg:cenc:2013',
        'dash': 'urn:mpeg:dash:schema:mpd:2011',
        'mspr': 'urn:microsoft:playready',
        'scte35': "http://www.scte.org/schemas/35/2016",
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'prh': 'http://schemas.microsoft.com/DRM/2007/03/PlayReadyHeader',
    }

    attributes = []

    def __init__(self,
                 elt: ET.ElementBase,
                 parent: Optional["DashElement"],
                 options: ValidatorOptions | None = None,
                 url: str | None = None) -> None:
        self.parent = parent
        self.url = url
        if parent:
            self.mode = parent.mode
            self.url = parent.url
            self.validator = getattr(parent, "validator")
            self.options = parent.options
            self.http = parent.http
            self.filenames = parent.filenames
            self.progress = parent.progress
            self.pool = parent.pool
        else:
            assert options is not None
            self.options = options
            self.filenames = set()
            if options.progress is None:
                self.progress = NullProgress()
            else:
                self.progress = options.progress
            if self.options.pool:
                self.pool = self.options.pool
            else:
                self.pool = ConcurrentWorkerPool(ThreadPoolExecutor())
        self.errors = []
        self.log = ContextAdapter(self.options.log, self)
        self.log.setLevel = self.options.log.setLevel
        self.baseurl = None
        self.ID = None
        sourceline: int | None = None
        line_range: tuple | None = None
        if elt is not None:
            sourceline = elt.sourceline
            end = elt.sourceline
            for child in elt:
                end = DashElement.max_source_line(end, child)
            line_range = LineRange(elt.sourceline, end)
            base = elt.findall('./dash:BaseURL', self.xmlNamespaces)
            if len(base):
                self.baseurl = base[0].text
                if self.parent and not self.baseurl.startswith('http'):
                    self.baseurl = urllib.parse.urljoin(
                        parent.baseurl, self.baseurl)
            elif parent:
                self.baseurl = parent.baseurl
            self.ID = elt.get('id')
        elif parent is not None:
            sourceline = parent.elt.location.start
            line_range = parent.elt.location
        self.attrs = ValidationChecks(
            ErrorSource.ATTRIBUTE, LineRange(sourceline, sourceline))
        self.elt = ValidationChecks(ErrorSource.ELEMENT, line_range)
        if self.ID is None:
            self.ID = str(id(self))
        self.parse_attributes(elt, self.attributes)

    @staticmethod
    def max_source_line(linenum: int, elt) -> int:
        if elt is None:
            return linenum
        if elt.sourceline is not None:
            linenum = max(linenum, elt.sourceline)
        for child in elt:
            linenum = DashElement.max_source_line(linenum, child)
        return linenum

    @classmethod
    def classname(clz) -> str:
        if clz.__module__.startswith('__'):
            return clz.__name__
        return clz.__module__ + '.' + clz.__name__

    def has_errors(self) -> bool:
        result = (self.attrs.has_errors() or
                  self.elt.has_errors())
        if result:
            return True
        for child in self.children():
            if child.has_errors():
                return True
        return False

    def get_errors(self) -> list[ValidationError]:
        result = self.attrs.errors + self.elt.errors
        for child in self.children():
            result += child.get_errors()
        return result

    @abstractmethod
    def children(self) -> list["DashElement"]:
        ...

    def parse_attributes(self, elt: ET.ElementBase, attributes: list[tuple]) -> None:
        for name, conv, dflt in attributes:
            if ':' in name:
                ns, nm = name.split(':')
                name = nm
                val = elt.get(f"{{{self.xmlNamespaces[ns]}}}{nm}")
            else:
                val = elt.get(name)
            if val is not None:
                try:
                    val = conv(val)
                except (ValueError) as err:
                    msg = f'Attribute "{self.classname()}@{name}" has invalid value "{val}": {err}'
                    self.attrs.add_error(msg)
                    self.log.error(msg)
                    val = dflt
            elif dflt == DashElement.Parent:
                val = getattr(self.parent, name, None)
            else:
                val = dflt
            setattr(self, name, val)

    def dump_attributes(self):
        for item in self.attributes:
            self.log.debug(
                '%s="%s"', item[0], str(
                    getattr(
                        self, item[0], None)))

    @property
    def mpd(self):
        if self.parent:
            return self.parent.mpd
        return self

    def find_parent(self, name: str) -> Optional["DashElement"]:
        if name == self.__class__.__name__:
            return self
        if self.parent:
            return self.parent.find_parent(name)
        return None

    @classmethod
    def init_xml_namespaces(clz) -> None:
        for prefix, url in clz.xmlNamespaces.items():
            ET.register_namespace(prefix, url)

    def num_tests(self) -> int:
        """
        Returns count of number of tests performed within this element.
        Used for progress reporting
        """
        return 0

    def finished(self) -> bool:
        return False

    def unique_id(self) -> str:
        rv = [self.classname(), self.ID]
        p = self.parent
        while p is not None:
            rv.append(p.ID)
            p = p.parent
        return '/'.join(rv)

    def output_filename(self, default: str | None,
                        bandwidth: int | None,
                        elt_id: str | None = None,
                        prefix: str | None = None,
                        filename: str | None = None,
                        makedirs: bool = False) -> str:
        if filename is None:
            filename = self.url
        if filename.startswith('http:'):
            parts = urllib.parse.urlsplit(filename)
            head, tail = os.path.split(parts.path)
            if tail and tail[0] != '.':
                filename = tail
            else:
                filename = default
        else:
            head, tail = os.path.split(filename)
            if tail:
                filename = tail
        if '?' in filename:
            filename = filename.split('?')[0]
        if '#' in filename:
            filename = filename.split('#')[0]
        root, ext = os.path.splitext(filename)
        if root == '':
            root, ext = os.path.splitext(default)
        now = self.options.start_time.replace(microsecond=0)
        dest = os.path.join(self.options.dest,
                            to_iso_datetime(now).replace(':', '-'))
        if prefix is not None and elt_id is not None:
            filename = f'{prefix}_{elt_id}.mp4'
        elif prefix is not None and bandwidth is not None:
            filename = f'{prefix}_{bandwidth}.mp4'
        else:
            filename = f'{root}{ext}'
        self.log.debug('dest=%s, filename=%s', dest, filename)
        if makedirs:
            if not os.path.exists(dest):
                os.makedirs(dest)
        return os.path.join(dest, filename)

    def open_file(self, filename: str, options):
        self.filenames.add(filename)
        if options.prefix:
            fd = open(filename, 'ab')
            fd.seek(0, os.SEEK_END)
            return fd
        return open(filename, 'wb')
