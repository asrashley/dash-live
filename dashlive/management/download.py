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

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from dashlive.utils.json_object import JsonObject
from .base import ManagementBase
from .info import StreamInfo

class DownloadDatabase(ManagementBase):
    OUTPUT_NAME = 'downloaded.json'

    def download_database(self, destination: Path) -> bool:
        if not self.login():
            return False
        if not self.get_media_info(with_details=True):
            return False
        if not destination.exists():
            destination.mkdir()
        result = {
            "keys": list(self.keys.values()),
            "streams": [],
        }
        retval = True
        for stream in self.streams.values():
            js = self.download_stream(stream, destination)
            if js is None:
                retval = False
            else:
                js['files'] = [f'{stream.directory}/{name}' for name in js['files']]
            result['streams'].append(js)
        filename = destination / self.OUTPUT_NAME
        with filename.open('wt', encoding='utf-8') as dest:
            json.dump(result, dest, indent=2, sort_keys=True)
        return retval

    def download_stream(self, stream: StreamInfo, destination: Path) -> Optional[JsonObject]:
        js = stream.to_dict(only={'directory', 'title', 'marlin_la_url', 'playready_la_url'})
        # js['files'] = [mf.blob.filename for mf in stream.media_files.values()]
        js['files'] = []
        destdir = destination / stream.directory
        if not destdir.exists():
            destdir.mkdir()
        if not destdir.exists():
            return None
        for name, info in stream.media_files.items():
            filename = destdir / f'{name}.mp4'
            if filename.exists():
                self.log.info('Already have file: %s', filename)
                js['files'].append(f'{name}.mp4')
                continue
            if self.download_file(stream, name, filename, info):
                js['files'].append(f'{name}.mp4')
        js['files'].sort()
        filename = destination / stream.directory / f'{stream.directory}.json'
        # TODO: only select keys used by this stream
        result = {
            'keys': list(self.keys.values()),
            'streams': [js]
        }
        with filename.open('wt', encoding='utf-8') as dest:
            json.dump(result, dest, indent=2, sort_keys=True)
        return js

    def download_file(self, stream: StreamInfo, name: str, filename: Path, info) -> bool:
        url = self.url_for(
            'dash-od-media', stream=stream.directory, filename=filename.stem,
            ext=filename.suffix[1:])
        self.log.info('Downloading %s', name)
        self.log.debug('GET %s', url)
        headers = {"Range": "bytes=0-"}
        result = self.session.get(url, headers=headers)
        if result.status_code not in {200, 206}:
            self.log.warning('Get %s: HTTP status %d', url, result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        self.log.info('Writing file to %s', filename)
        with filename.open('wb') as dest:
            dest.write(result.content)
        return True

    @classmethod
    def main(cls) -> None:
        ap = argparse.ArgumentParser(description='dashlive database download')
        ap.add_argument('--debug', action="store_true")
        ap.add_argument('--host', help='HTTP address of host',
                        default="http://localhost:9080/")
        ap.add_argument('dest', help='Destination directory')
        args = ap.parse_args()
        mm_log = logging.getLogger('DownloadDatabase')
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
        mm_log.addHandler(ch)
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            mm_log.setLevel(logging.DEBUG)
        else:
            mm_log.setLevel(logging.INFO)
        dd = DownloadDatabase(args.host)
        dd.download_database(args.dest)
