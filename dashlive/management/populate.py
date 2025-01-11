#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import json
import logging
from pathlib import Path

from dashlive.utils.json_object import JsonObject

from .db_access import DatabaseAccess
from .info import StreamInfo

class PopulateDatabase:
    """
    Helper class that uses a JSON file to describe a set of
    streams, keys and files that it will upload to the server.
    """

    def __init__(self, db: DatabaseAccess) -> None:
        self.db = db
        self.log = logging.getLogger('management')

    def populate_database(self, jsonfile: str) -> bool:
        self.log.debug('Loading JSON file %s', jsonfile)
        with open(jsonfile) as js:
            config = json.load(js)
        if 'files' in config:
            self.log.debug('Converting JSON script to v2 Schema')
            config = self.convert_v1_json_data(config)
        js_dir = Path(jsonfile).parent
        if not self.db.login():
            self.log.error('Login failed')
            return False
        if not self.db.fetch_media_info():
            self.log.error('Fetch media info failed')
            return False
        result = True
        db_keys = self.db.get_keys()
        for k in config['keys']:
            if k['kid'] not in db_keys:
                self.log.info('Add key KID={kid} computed={computed}'.format(**k))
                if not self.db.add_key(**k):
                    self.log.error('Failed to add key {kid}'.format(**k))
                    result = False
        directory = None
        for s in config['streams']:
            directory = s.get('directory')
            s_info = self.db.get_stream_info(directory)
            if s_info is None:
                self.log.info(f'Add stream directory="{directory}" title="{s["title"]}"')
                if not self.db.add_stream(**s):
                    self.log.error(f'Failed to add stream {directory}: {s["title"]}')
                    result = False
                    continue
                s_info = self.db.get_stream_info(directory)
            if s_info is None:
                continue
            for name in s['files']:
                if not self.upload_file_and_index(js_dir, s_info, Path(name)):
                    result = False
            if s.get('timing_ref'):
                self.db.set_timing_ref(s_info, s['timing_ref'])
        return result

    def convert_v1_json_data(self, v1json: JsonObject) -> JsonObject:
        """
        Converts v1 JSON Schema to current JSON Schema
        """
        files = set(v1json['files'])
        output = {
            'streams': [],
            'keys': v1json['keys']
        }
        if 'streams' not in v1json:
            v1json['streams'] = []
            file_prefixes = set()
            for filename in files:
                prefix = Path(filename).name.split('_')[0]
                if prefix not in file_prefixes:
                    v1json['streams'].append({
                        'title': prefix,
                        'prefix': prefix
                    })
                    file_prefixes.add(prefix)
            v1json['streams'].sort(key=lambda item: item['prefix'])
        for stream in v1json['streams']:
            new_st = {
                'directory': stream['prefix'],
                'timing_ref': None,
                'title': stream.get('title', stream['prefix']),
                'files': []
            }
            try:
                new_st["marlin_la_url"] = stream["marlin_la_url"]
            except KeyError:
                pass
            try:
                new_st["playready_la_url"] = stream["playready_la_url"]
            except KeyError:
                pass
            for filename in list(files):
                if Path(filename).name.startswith(stream['prefix']):
                    new_st['files'].append(filename)
                    files.remove(filename)
            new_st['files'].sort()
            output['streams'].append(new_st)
        return output

    def upload_file_and_index(self, js_dir: Path, stream: StreamInfo, name: Path) -> bool:
        if name.stem in stream.media_files:
            return True
        filename: Path = name
        if not filename.exists():
            self.log.debug(
                "%s not found, trying %s/%s", filename, js_dir, name)
            filename = js_dir / name
        if not filename.exists():
            self.log.debug(
                "%s not found, trying %s/%s", filename, js_dir, filename.name)
            filename = js_dir / filename.name
        if not filename.exists():
            self.log.warning("%s not found", name)
            return False
        self.log.info('Add file %s', filename.name)
        if not self.db.upload_file(stream, filename):
            self.log.error('Failed to add file %s', name)
            return False
        self.log.info('Index file %s', name)
        if not self.db.index_file(stream, name):
            self.log.error('Failed to index file %s', name)
            return False
        return True
