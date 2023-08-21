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
import copy

def object_from(clz, value):
    if value is None:
        return None
    if isinstance(value, list):
        return clz(value)
    if isinstance(value, dict):
        if hasattr(clz, 'from_kwargs'):
            return clz.from_kwargs(**value)
        return clz(**value)
    if isinstance(clz, type) and isinstance(value, clz):
        return value
    if hasattr(clz, 'from_kwargs'):
        # print('object_from from_kwargs() before=', clz, type(value))
        value = clz.from_kwargs(value)
        # print('object_from from_kwargs() after=', clz, type(value))
    else:
        # print('object_from call() before=', clz, type(value))
        value = clz(value)
        # print('object_from call() after=', clz, type(value))
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

class ListOf:
    def __init__(self, clazz):
        self.clazz = clazz

    def __call__(self, value):
        return [object_from(self.clazz, s) for s in value]

    def __repr__(self):
        return fr'ListOf({self.clazz.__name__})'
