#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import abstractmethod
import logging
import os
from typing import Any, Never
import urllib.parse

from lxml import etree as ET

from dashlive.testcase.mixin import TestCaseMixin
from dashlive.utils.date_time import to_iso_datetime

class ContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        url = getattr(self.extra, "url", None)
        if url is not None and 'http' not in msg:
            return f'{msg}\n    "{url}"\n', kwargs
        return msg, kwargs


class DashElement(TestCaseMixin):
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

    def __init__(self, elt, parent, options=None, url=None):
        self.parent = parent
        self.url = url
        if parent:
            self.mode = parent.mode
            self.url = parent.url
            self.validator = getattr(parent, "validator")
            self.options = parent.options
            self.http = parent.http
            self.errors = parent.errors
            self.filenames = parent.filenames
        else:
            assert options is not None
            self.options = options
            self.errors = []
            self.filenames = set()
        # self.log = logging.getLogger(self.classname())
        #    log.addFilter(mixins.HideMixinsFilter())
        self.log = ContextAdapter(self.options.log, self)
        self.log.setLevel = self.options.log.setLevel
        self.baseurl = None
        self.ID = None
        if elt is not None:
            base = elt.findall('./dash:BaseURL', self.xmlNamespaces)
            if len(base):
                self.baseurl = base[0].text
                if self.parent and not self.baseurl.startswith('http'):
                    self.baseurl = urllib.parse.urljoin(
                        parent.baseurl, self.baseurl)
            elif parent:
                self.baseurl = parent.baseurl
            self.ID = elt.get('id')
        if self.ID is None:
            self.ID = str(id(self))
        self.parse_attributes(elt, self.attributes)

    def parse_attributes(self, elt, attributes):
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
                    self.log.error('Attribute "%s@%s" has invalid value "%s": %s',
                                   self.classname(), name, val, err)
                    xml = ET.tostring(elt)
                    print(f'Error parsing attribute "{name}": {xml}')
                    raise err
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

    @classmethod
    def init_xml_namespaces(clz):
        for prefix, url in clz.xmlNamespaces.items():
            ET.register_namespace(prefix, url)

    @abstractmethod
    def validate(self, depth=-1) -> Never:
        raise Exception("Not implemented")

    def unique_id(self) -> str:
        rv = [self.classname(), self.ID]
        p = self.parent
        while p is not None:
            rv.append(p.ID)
            p = p.parent
        return '/'.join(rv)

    def _check_true(self, result: bool, a: Any, b: Any,
                    msg: str | None, template: str) -> bool:
        if not result:
            if msg is None:
                msg = template.format(a, b)
            if self.options.strict:
                raise AssertionError(msg)
            self.log.warning('%s', msg)
            self.errors.append(msg)
        return result

    def output_filename(self, default, bandwidth, prefix=None, filename=None, makedirs=False):
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
        if prefix is not None and bandwidth is not None:
            filename = f'{prefix}_{bandwidth}.mp4'
        else:
            filename = ''.join([root, ext])
        self.log.debug('dest=%s, filename=%s', dest, filename)
        if makedirs:
            if not os.path.exists(dest):
                os.makedirs(dest)
        return os.path.join(dest, filename)

    def open_file(self, filename, options):
        self.filenames.add(filename)
        if options.prefix:
            fd = open(filename, 'ab')
            fd.seek(0, os.SEEK_END)
            return fd
        return open(filename, 'wb')
