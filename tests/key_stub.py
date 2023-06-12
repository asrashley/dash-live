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
from drm.keymaterial import KeyMaterial

class KeyStub(object):
    def __init__(self, kid, key, alg=None):
        self.KID = KeyMaterial(hex=kid)
        self.KEY = KeyMaterial(hex=key)
        self.ALG = 'AESCTR' if alg is None else alg
        self.computed = False
