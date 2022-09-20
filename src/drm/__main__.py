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
import sys
from utils.buffered_reader import BufferedReader

from drm.playready import PlayReady
from mp4 import IsoParser

if __name__ == "__main__":
    def show_pssh(atom):
        if atom.atom_type == 'pssh':
            print(atom)
            if atom.system_id == PlayReady.RAW_SYSTEM_ID:
                pro = PlayReady.parse_pro(
                    BufferedReader(
                        None, data=atom.data))
                print(pro)
        else:
            for child in atom.children:
                show_pssh(child)

    for filename in sys.argv[1:]:
        parser = IsoParser()
        atoms = parser.walk_atoms(filename)
        for atom in atoms:
            show_pssh(atom)
