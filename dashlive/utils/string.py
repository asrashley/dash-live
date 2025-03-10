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

def str_or_none(value: str | None) -> str:
    """
    Returns the input string, or an empty string if it's None
    """
    if value is None:
        return ''
    return value

def set_from_comma_string(text: str | None) -> set[str]:
    """
    Converts a comma separated string into a set of strings, discarding
    any empty strings.
    """
    if text is None:
        return set()
    rv: set[str] = set()
    for item in text.split(','):
        item = item.strip()
        if item:
            rv.add(item)
    return rv
