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
from collections.abc import MutableMapping
from typing import AbstractSet, Any, Optional

from dashlive.utils.json_object import JsonObject
from dashlive.utils.list_of import ListOf, clone_object, object_from
from dashlive.utils.objects import as_python, flatten

class ObjectFieldIterator:
    def __init__(self, obj: "ObjectWithFields") -> None:
        self.obj = obj
        self.names = list(obj._fields)

    def __iter__(self) -> "ObjectFieldIterator":
        return self

    def __next__(self) -> tuple[str, Any]:
        if not self.names:
            raise StopIteration()
        name = self.names.pop()
        return (name, getattr(self.obj, name),)


class ObjectWithFields(MutableMapping):
    OBJECT_FIELDS = None
    DEFAULT_VALUES = None
    REQUIRED_FIELDS = None
    DEFAULT_EXCLUDE = None
    debug = False

    def __init__(self, **kwargs):
        self._fields = set()
        if self.OBJECT_FIELDS is None:
            self.OBJECT_FIELDS = dict()
        if self.DEFAULT_EXCLUDE is None:
            self.DEFAULT_EXCLUDE = set()
        if self.DEFAULT_VALUES is not None:
            self._copy_args(self.DEFAULT_VALUES)
        self._copy_args(kwargs)
        if self.REQUIRED_FIELDS is not None:
            for key, clz in self.REQUIRED_FIELDS.items():
                assert key in self._fields
                value = self.__dict__[key]
                assert isinstance(value, clz), r"{0}: Expected type {1}, got {2}".format(
                    key, clz.__name__, type(value).__name__)

    def clone(self, **kwargs) -> "ObjectWithFields":
        args = {}
        for key in self._fields:
            if key[0] == '_':
                continue
            value = getattr(kwargs, key, getattr(self, key))
            if value is not None:
                if isinstance(value, ObjectWithFields):
                    value = value.clone()
                elif key in self.OBJECT_FIELDS:
                    clz = self.OBJECT_FIELDS[key]
                    value = clone_object(clz, value)
            args[key] = value
        for key, value in kwargs.items():
            if key in self._fields:
                continue
            args[key] = value
        return self.__class__(**args)

    def apply_defaults(self, defaults: dict) -> None:
        for key, value in defaults.items():
            if key not in self._fields:
                setattr(self, key, value)
                self._fields.add(key)

    def add_field(self, name: str, value: Any) -> None:
        self._fields.add(name)
        setattr(self, name, value)

    def remove_field(self, name: str) -> bool:
        if name in self._fields:
            self._fields.remove(name)
            delattr(self, name)
            return True
        return False

    @classmethod
    def classname(clz):
        if clz.__module__.startswith('__'):
            return clz.__name__
        return clz.__module__ + '.' + clz.__name__

    def __repr__(self):
        return self.as_python()

    def as_python(self, exclude=None):
        if exclude is None:
            exclude = self.DEFAULT_EXCLUDE
        fields = self._field_repr(exclude)
        fields = ','.join(fields)
        return '{name}({fields})'.format(name=self.classname(), fields=fields)

    def toJSON(self, exclude: Optional[AbstractSet] = None, pure: bool = False) -> JsonObject:
        if exclude is None:
            exclude = self.DEFAULT_EXCLUDE
            if exclude is None:
                exclude = set()
        rv = self._to_json(exclude)
        if pure:
            rv = flatten(rv)
        return rv

    def _field_repr(self, exclude: AbstractSet) -> list:
        rv = []
        fields = self._to_json(exclude)
        for k, v in fields.items():
            if k != '_type':
                rv.append('{0}={1}'.format(k, as_python(v)))
        return rv

    def _to_json(self, exclude: AbstractSet) -> JsonObject:
        rv = {
            '_type': self.classname(),
        }
        if '_type' in exclude:
            del rv['_type']
        for k in self._fields:
            if k[0] == '_' or k in exclude:
                continue
            v = getattr(self, k)
            rv[k] = self._convert_value_to_json(k, v)
        return rv

    def _convert_value_to_json(self, key: str, value: Any) -> Any:
        if value is None:
            return value
        if key and self.OBJECT_FIELDS and key in self.OBJECT_FIELDS:
            clz = self.OBJECT_FIELDS[key]
            # print('_convert_value_to_json check clz', self.classname(), key, clz)
            if isinstance(clz, ListOf):
                # print('_convert_value_to_json listOf', self.classname(), key, clz.clazz)
                return list(map(flatten, value))
        return flatten(value)

    def _copy_args(self, args: dict) -> None:
        for key, value in args.items():
            if key[0] == '_':
                object.__setattr__(self, key, value)
                continue
            self._fields.add(key)
            if key in self.OBJECT_FIELDS:
                clz = self.OBJECT_FIELDS[key]
                # print('object_from', self.classname(), key, clz)
                value = object_from(clz, value)
                # print('value', self.classname(), key, type(value))
                object.__setattr__(self, key, value)
            else:
                object.__setattr__(self, key, value)

    def items(self) -> ObjectFieldIterator:
        return ObjectFieldIterator(self)

    def __iter__(self) -> ObjectFieldIterator:
        return ObjectFieldIterator(self)

    def __contains__(self, field: str) -> bool:
        return field in self._fields

    def __len__(self) -> int:
        return len(self._fields)

    def __setitem__(self, field: str, value: Any) -> None:
        self.add_field(field, value)

    def __delitem__(self, name: str) -> None:
        rv = self.remove_field(name)
        if not rv:
            raise KeyError(name)

    def __getitem__(self, field: str) -> Any:
        if field not in self._fields:
            raise KeyError(field)
        return getattr(self, field)
