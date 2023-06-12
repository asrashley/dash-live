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

from builtins import object
import os

import jinja2

from . import tags
from utils.date_time import toIsoDuration, toIsoDateTime

class TemplateFactory(object):
    _singleton = None

    @classmethod
    def get_template(clz, name):
        return clz.get_singleton().get_template_by_name(name)

    @classmethod
    def get_singleton(clz):
        if clz._singleton is None:
            clz._singleton = TemplateFactory()
        return clz._singleton

    def __init__(self):
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__),
                        '..',
                        '..',
                        'templates'))),
            extensions=['jinja2.ext.autoescape'],
            trim_blocks=True)
        self.templates.filters['base64'] = tags.toBase64
        self.templates.filters['dateTimeFormat'] = tags.dateTimeFormat
        self.templates.filters['isoDuration'] = toIsoDuration
        self.templates.filters['isoDateTime'] = toIsoDateTime
        self.templates.filters['sizeFormat'] = tags.sizeFormat
        self.templates.filters['toHtmlString'] = tags.toHtmlString
        self.templates.filters['toJson'] = tags.toJson
        self.templates.filters['trueFalse'] = tags.trueFalse
        self.templates.filters['uuid'] = tags.toUuid
        self.templates.filters['xmlSafe'] = tags.xmlSafe
        self.templates.filters['default'] = tags.default
        self.templates.filters['sortedAttributes'] = tags.sortedAttributes

    def get_template_by_name(self, name):
        return self.templates.get_template(name)
