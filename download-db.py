from __future__ import print_function
import argparse
from HTMLParser import HTMLParser
import json
import logging
import os
import ssl
import sys
import time
import urllib

import requests

class FormParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.form = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        if tag=='form':
            a = {}
            for name, value in attrs:
                a[name] = value
            self.form = {
                'method': a['method'].upper(),
                'action': a['action'],
            }
        elif tag=='input':
            name = None
            a = {}
            for k, v in attrs:
                if k == 'name':
                    name = v
                else:
                    a[k] = v
            assert name is not None
            self.fields[name] = a

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        pass

class Routes(object):
    def __init__(self, base_url):
        self.base_url = base_url
        self.media = "{0}media".format(self.base_url)
        self.login = "{0}_ah/login?continue={1}".format(self.base_url,
                                                        urllib.quote(self.base_url))
        self.key = "{}key".format(self.base_url)
        self.stream = "{}stream".format(self.base_url)

    def media_info(self, mfid):
        return "{base_url}media/{mfid}".format(base_url=self.base_url, mfid=mfid)

    def media_file(self, name):
        return "{base_url}dash/vod/{name}".format(base_url=self.base_url, name=name)

class DownloadDatabase(object):
    def __init__(self, url):
        self.routes = Routes(url)
        self.session = requests.Session()
        self._has_logged_in = False
        self.files = {}
        self.csrf_tokens = {}
        self.upload_url = None
        self.keys = {}
        self.streams = {}
        self.log = logging.getLogger('DownloadDatabase')

    def download_database(self, destination):
        self.login()
        self.get_media_info()
        if not os.path.exists(destination):
            os.mkdir(destination)
        result = {
            "keys": self.keys.values(),
            "streams": self.streams.values(),
            "files": []
        }
        for name, info in self.files.items():
            filename = os.path.join(destination, name)
            if os.path.exists(filename):
                self.log.info('Already have file: %s', filename)
                result['files'].append(name)
                continue
            if self.download_file(name, filename, info):
                result['files'].append(name)
        filename = os.path.join(destination, 'downloaded.json')
        with open(filename, 'wt') as dest:
            json.dump(result, dest, indent=2, sort_keys=True)

    def login(self):
        if self._has_logged_in:
            return True
        self.log.debug('GET %s', self.routes.login)
        result = self.session.get(self.routes.login)
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        fp = FormParser()
        fp.feed(result.text)
        fields = {
            "email": fp.fields['email']['value'],
            "admin": True,
            "action": "Login",
            "continue": self.routes.base_url,
        }
        assert fp.form['method'] == 'GET'
        self.log.debug('GET %s', fp.form['action'])
        result = self.session.get(fp.form['action'],
                                  params=fields)
        self._has_logged_in = result.status_code == 200 and \
                              'dev_appserver_login' in self.session.cookies
        return self._has_logged_in

    def get_media_info(self):
        self.login()
        self.log.debug('GET %s', self.routes.media)
        result = self.session.get(self.routes.media, params={'ajax':1})
        if result.status_code != 200:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        js = result.json()
        self.csrf_tokens.update(js['csrf_tokens'])
        for f in js['files']:
            self.files[f['name']] = f
            self.log.debug('File %s', f['name'])
        for k in js['keys']:
            kid = k['kid']
            self.log.debug('KID %s: computed=%s', kid, k['computed'])
            self.keys[kid] = k
        for s in js['streams']:
            self.streams[s['prefix']] = s
            self.log.debug('Stream %s: %s', s['prefix'], s['title'])
        self.upload_url = js['upload_url']
        return True

    def download_file(self, name, filename, info):
        if name not in self.files:
            return False
        url = self.routes.media_file(name)
        self.log.info('Downloading %s', name)
        self.log.debug('GET %s', url)
        headers = {"Range": "bytes=0-"}
        result = self.session.get(url, headers=headers)
        if result.status_code not in {200, 206}:
            self.log.warning('HTTP status %d', result.status_code)
            self.log.debug('HTTP headers %s', str(result.headers))
            return False
        self.log.info('Writing file to %s', filename)
        with open(filename, 'wb') as dest:
            dest.write(result.content)
        return True

    @classmethod
    def main(cls):
        ap = argparse.ArgumentParser(description='dashlive database download')
        ap.add_argument('--debug', action="store_true")
        ap.add_argument('--host', help='HTTP address of host',
                        default="http://localhost:9080/" )
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


if __name__ == "__main__":
    DownloadDatabase.main()
