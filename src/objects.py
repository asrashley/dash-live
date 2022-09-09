#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import ABCMeta, abstractmethod
import base64
import copy

from utils import as_python, flatten

class Binary(object):
    BASE64 = 1
    HEX = 2

    def __init__(self, data, encoding=BASE64):
        self.data = data
        self.encoding = encoding

    def toJSON(self, pure=False):
        if self.data is None:
            return None
        if pure:
            if self.encoding == self.BASE64:
                return base64.b64encode(self.data)
            return '0x' + self.data.encode('hex')
        if self.encoding == self.BASE64:
            return 'base64.b64decode("%s")' % base64.b64encode(self.data)
        return '"%s".decode("hex")' % (self.data.encode('hex'))

    def __len__(self):
        if self.data is None:
            return 0
        return len(self.data)

    def __repr__(self):
        if self.data is None:
            return 'None'
        return self.toJSON(pure=False)


class NamedObject(object):
    __metaclass__ = ABCMeta
    debug = False

    @property
    def classname(self):
        clz = type(self)
        if clz.__module__.startswith('__'):
            return clz.__name__
        return clz.__module__ + '.' + clz.__name__

    def __repr__(self, exclude=None):
        if exclude is None:
            exclude = []
        fields = self._field_repr(exclude)
        fields = ','.join(fields)
        return '{name}({fields})'.format(name=self.classname, fields=fields)

    def _field_repr(self, exclude):
        rv = []
        fields = self._to_json(exclude)
        for k, v in fields.iteritems():
            if k != '_type':
                rv.append('{0}={1}'.format(k, as_python(v)))
        return rv

    @abstractmethod
    def _to_json(self, exclude):
        return {}

    def toJSON(self, exclude=None, pure=False):
        if exclude is None:
            exclude = ['parent']
        rv = {
            '_type': self.classname
        }
        rv.update(self._to_json(exclude))
        if pure:
            rv = flatten(rv)
        return rv

def object_from(clz, value):
    if value is None:
        return None
    if isinstance(value, list):
        return clz(value)
    if isinstance(value, dict):
        return clz(**value)
    if isinstance(clz, type) and not isinstance(value, clz):
        return clz(value)
    return value

def clone_object(clz, value):
    if value is None:
        return None
    if isinstance(value, list):
        return clz(value)
    if isinstance(value, dict):
        return clz(**value)
    if isinstance(clz, type) and not isinstance(value, clz):
        return clz(value)
    return copy.deepcopy(value)

class ListOf(object):
    def __init__(self, clazz):
        self.clazz = clazz

    def __call__(self, value):
        return map(lambda s: object_from(self.clazz, s), value)


class ObjectWithFields(NamedObject):
    OBJECT_FIELDS = {}
    DEFAULT_VALUES = {}
    REQUIRED_FIELDS = {}

    def __init__(self, **kwargs):
        self._fields = {}
        self._copy_args(self.DEFAULT_VALUES)
        self._copy_args(kwargs)
        for key, clz in self.REQUIRED_FIELDS.iteritems():
            assert key in self._fields
            assert isinstance(self._fields[key], clz)

    def clone(self):
        kwargs = {}
        for key, value in self._fields.iteritems():
            if isinstance(value, ObjectWithFields):
                value = value.clone()
            elif key in self.OBJECT_FIELDS:
                clz = self.OBJECT_FIELDS[key]
                value = clone_object(clz, value)
            kwargs[key] = value
        return self.__class__(**kwargs)

    def apply_defaults(self, defaults):
        for key, value in defaults.iteritems():
            if key not in self._fields:
                self._fields[key] = value

    def __getattr__(self, name):
        if name[0] == "_":
            # __getattribute__ should have responded before __getattr__ called
            raise AttributeError(name)
        if name in self._fields:
            return self._fields[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name[0] != '_' and name in self._fields:
            self._fields[name] = value
            return
        object.__setattr__(self, name, value)

    def _to_json(self, exclude):
        rv = {
            '_type': self.classname
        }
        for k, v in self._fields.iteritems():
            if k[0] != '_' and k not in exclude:
                if v is not None:
                    if k in self.OBJECT_FIELDS:
                        clz = self.OBJECT_FIELDS[k]
                        if isinstance(clz, ListOf) or not isinstance(v, clz):
                            v = clz(v)
                rv[k] = v
        return rv

    def _copy_args(self, args):
        for key, value in args.iteritems():
            if key not in self.__dict__:
                if key in self.OBJECT_FIELDS:
                    clz = self.OBJECT_FIELDS[key]
                    self._fields[key] = object_from(clz, value)
                else:
                    self._fields[key] = value
