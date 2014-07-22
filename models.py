import logging, datetime, math, functools

from google.appengine.ext import ndb
from google.appengine.api import search

class MediaFile(ndb.Model):
    """representation of one MP4 file"""
    name = ndb.StringProperty(required=True, indexed=True, verbose_name='Name')
    blob = ndb.BlobKeyProperty(indexed=False)
    
    @classmethod
    def empty_database(clz):
        list_of_keys = MediaFile.query().fetch(keys_only=True)
        ndb.delete_multi(list_of_keys)
        