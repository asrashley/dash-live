import re

from google.appengine.ext import ndb
from google.appengine.ext.blobstore import blobstore

from drm.keymaterial import KeyMaterial
from mpeg.dash.representation import Representation
from utils.date_time import toIsoDateTime

class Stream(ndb.Model):
    title = ndb.StringProperty(required=True, indexed=True)
    prefix = ndb.StringProperty(required=True, verbose_name='File name prefix', indexed=True,
                                repeated=False)
    marlin_la_url = ndb.StringProperty(required=False, indexed=False, default=None)
    playready_la_url = ndb.StringProperty(required=False, indexed=False, default=None)

    @classmethod
    def all(clz):
        return clz.query().order(clz.prefix).fetch()

    def toJSON(self, pure=False):
        return {
            'title': self.title,
            'prefix': self.prefix,
            'marlin_la_url': self.marlin_la_url,
            'playready_la_url': self.playready_la_url,
        }

class MediaFile(ndb.Model):
    """representation of one MP4 file"""
    name = ndb.StringProperty(required=True, indexed=True, verbose_name='Name')
    blob = ndb.BlobKeyProperty(indexed=False)
    rep = ndb.JsonProperty(indexed=False, required=False, default={})
    bitrate = ndb.IntegerProperty(indexed=True, required=True, default=0)
    contentType = ndb.StringProperty(required=False, indexed=True,
                                     verbose_name='Content Type', default=None)
    encrypted = ndb.BooleanProperty(default=False, indexed=True)

    def __init__(self, *args, **kwargs):
        super(MediaFile, self).__init__(*args, **kwargs)
        self._info = None
        self._representation = None

    def _pre_put_hook(self):
        if self._representation is not None:
            if self.contentType is None:
                self.contentType = self._representation.contentType
                self.encrypted = self._representation.encrypted
                self.bitrate = self._representation.bitrate

    @property
    def info(self):
        if self._info is None:
            self._info = blobstore.BlobInfo.get(self.blob)
        return self._info

    def get_representation(self):
        if self._representation is None and self.rep:
            self._representation = Representation(**self.rep)
            try:
                if self._representation.version < Representation.VERSION:
                    self._representation = None
            except AttributeError:
                self._representation = None
        return self._representation

    def set_representation(self, rep):
        self.rep = rep.toJSON()
        self._representation = rep

    representation = property(get_representation, set_representation)

    @classmethod
    def all(clz, contentType=None, encrypted=None, prefix=None):
        return clz.search()

    @classmethod
    def search(clz, contentType=None, encrypted=None, prefix=None, maxItems=None):
        # print('MediaFile.all()', contentType, encrypted, prefix, maxItems)
        query = clz.query()
        if contentType is not None:
            query = query.filter(clz.contentType == contentType)
        if encrypted is not None:
            query = query.filter(clz.encrypted == encrypted)
        list_of_keys = query.order(clz.bitrate).fetch(keys_only=True)
        # print('list_of_keys', list_of_keys)
        fallback = False
        if len(list_of_keys) == 0:
            if contentType is not None or encrypted is not None:
                # fall-back if the contentType fields have not been populated
                list_of_keys = MediaFile.query().fetch(keys_only=True)
                fallback = True
        if maxItems is not None and not fallback:
            list_of_keys = list_of_keys[:maxItems]
        files = []
        for mf in ndb.get_multi(list_of_keys):
            if mf is None:
                print('mf is none')
                continue
            if prefix is None or mf.name.startswith(prefix):
                if mf.contentType is None:
                    fallback = True
                files.append(mf)
        # print('list_of_keys', list_of_keys, files)
        blobs = {}
        for b in blobstore.BlobInfo.get(map(lambda f: f.blob, files)):
            if b is not None:
                blobs[b.key()] = b
        for f in files:
            try:
                f._info = blobs[f.blob]
            except KeyError:
                pass
        if not fallback:
            # print('no fallback', len(files))
            return files
        rv = []
        for f in files:
            match = True
            rep = f.get_representation()
            if rep is not None:
                f.contentType = rep.contentType
                f.encrypted = rep.encrypted
                f.bitrate = rep.bitrate
                f.put()
                if contentType is not None and f.contentType != contentType:
                    match = False
                if encrypted is not None and f.encrypted != encrypted:
                    match = False
            if prefix is not None and not f.name.startswith(prefix):
                match = False
            # print(f.name, match, f.contentType, f.encrypted, contentType, encrypted, prefix)
            if match:
                rv.append(f)
        files.sort(key=lambda f: f.bitrate)
        if maxItems is not None:
            rv = rv[:maxItems]
        # print('fallback', len(rv))
        return rv

    @classmethod
    def get(clz, name):
        """
        Get one entry by name from the database
        """
        mf = clz.query(clz.name == name).get()
        if mf is not None and mf.contentType is None:
            rep = mf.get_representation()
            if rep is not None:
                mf.contentType = rep.contentType
                mf.encrypted = rep.encrypted
                mf.bitrate = rep.bitrate
                mf.put()
        return mf

    def delete(self):
        blobstore.delete(self.blob)
        self.key.delete()

    @classmethod
    def empty_database(clz):
        list_of_keys = MediaFile.query().fetch(keys_only=True)
        ndb.delete_multi(list_of_keys)

    def toJSON(self, convert_date=True, pure=False):
        i = self.info
        blob = {}
        if i is not None:
            for k in ["creation", "size", "md5_hash", "content_type", "filename"]:
                blob[k] = getattr(i, k)
            if convert_date or pure:
                blob["creation"] = toIsoDateTime(blob["creation"])
        r = self.representation
        if r is not None:
            r = r.toJSON(pure=pure)
        return {
            "name": self.name,
            "key": self.key.urlsafe(),
            "blob": blob,
            "representation": r,
        }


def kid_validator(prop, value):
    if not re.match(r'^[0-9a-f-]+$', value, re.IGNORECASE):
        raise TypeError('Expected a hex value, not {:s}'.format(value))
    return value.replace('-', '').lower()

class Key(ndb.Model):
    hkid = ndb.StringProperty(required=True, indexed=True,
                              verbose_name='Key identifier',
                              validator=kid_validator)
    hkey = ndb.StringProperty(required=True,
                              verbose_name='Content encryption key')
    computed = ndb.BooleanProperty(verbose_name='computed')
    halg = ndb.StringProperty(required=False, indexed=False, default=None,
                              verbose_name='Encryption algorithm')

    @property
    def KID(self):
        return KeyMaterial(self.hkid)

    @property
    def KEY(self):
        return KeyMaterial(self.hkey)

    @property
    def ALG(self):
        if self.halg is None:
            return "AESCTR"
        return self.halg

    @classmethod
    def get_kids(clz, kids):
        def to_hex(kid):
            if isinstance(kid, KeyMaterial):
                return kid.hex
            return kid.lower()
        kids = map(to_hex, kids)
        if len(kids) == 1:
            q = clz.query(clz.hkid == kids[0])
        else:
            q = clz.query(clz.hkid.IN(kids))
        rv = {}
        for k in q:
            rv[k.hkid.lower()] = k
        return rv

    @classmethod
    def all(clz):
        list_of_keys = clz.query().fetch(keys_only=True)
        return ndb.get_multi(list_of_keys)

    @classmethod
    def all_as_dict(clz):
        list_of_keys = clz.query().fetch(keys_only=True)
        rv = {}
        for k in ndb.get_multi(list_of_keys):
            rv[k.hkid.lower()] = k
        return rv

    def toJSON(self, pure=False):
        return {
            'kid': self.hkid,
            'key': self.hkey,
            'alg': self.ALG,
            'computed': self.computed,
        }
