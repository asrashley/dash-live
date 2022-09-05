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

import os

import jinja2

import utils

templates = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), '..', '..', 'templates')
    ),
    extensions=['jinja2.ext.autoescape'],
    trim_blocks=False,
)
templates.filters['base64'] = utils.toBase64
templates.filters['dateTimeFormat'] = utils.dateTimeFormat
templates.filters['isoDuration'] = utils.toIsoDuration
templates.filters['isoDateTime'] = utils.toIsoDateTime
templates.filters['sizeFormat'] = utils.sizeFormat
templates.filters['toHtmlString'] = utils.toHtmlString
templates.filters['toJson'] = utils.toJson
templates.filters['uuid'] = utils.toUuid
templates.filters['xmlSafe'] = utils.xmlSafe
templates.filters['default'] = utils.default
