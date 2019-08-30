import re

from google.appengine.ext import ndb
from google.appengine.api import search
from google.appengine.ext.blobstore import blobstore

from drm import KeyMaterial

class MediaFile(ndb.Model):
    """representation of one MP4 file"""
    name = ndb.StringProperty(required=True, indexed=True, verbose_name='Name')
    blob = ndb.BlobKeyProperty(indexed=False)

    @classmethod
    def all(clz):
        list_of_keys = MediaFile.query().fetch(keys_only=True)
        files = ndb.get_multi(list_of_keys)
        files = [f for f in files if f is not None]
        blobs = {}
        for b in blobstore.BlobInfo.get(map(lambda f: f.blob, files)):
            if b is not None:
                blobs[b.key()] = b
        result = []
        for f in files:
            try:
                b = blobs[f.blob]
            except KeyError:
                b = None
            result.append({
                "name": f.name,
                "key": f.key.urlsafe(),
                "blob": b
            })
        return result

    def delete(self):
        blobstore.delete(self.blob)
        self.key.delete()

    @classmethod
    def empty_database(clz):
        list_of_keys = MediaFile.query().fetch(keys_only=True)
        ndb.delete_multi(list_of_keys)

def kid_validator(prop, value):
    if not re.match(r'^[0-9a-f-]+$', value, re.IGNORECASE):
        raise TypeError('Expected a hex value, not {:s}'.format(value))
    return value.replace('-','').lower()

class Key(ndb.Model):
    hkid = ndb.StringProperty(required=True, indexed=True, verbose_name='Key identifier',
                              validator=kid_validator)
    hkey = ndb.StringProperty(required=True, verbose_name='Content encryption key')
    computed = ndb.BooleanProperty(verbose_name='computed')

    @property
    def KID(self):
        return KeyMaterial(self.hkid)

    @property
    def KEY(self):
        return KeyMaterial(self.hkey)

    @classmethod
    def get_kids(clz, kids):
        kids = map(lambda k: k.lower(), kids)
        if len(kids)==1:
            q = clz.query(clz.hkid==kids[0])
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

    def toJSON(self):
        return {
            'kid': self.hkid,
            'key': self.hkey,
            'computed': self.computed,
        }
