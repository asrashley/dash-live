#!/usr/bin/python2

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

from __future__ import print_function
import argparse
import os
import shutil
import subprocess
import tempfile
import sys

from .gen_index import create_representation

# KID='c001de8e567b5fcfbc22c565ed5bda24'
KID = '1ab45440532c439994dc5c5ad9584bac'

# KEY='533a583a843436a536fbe2a5821c4b6c'
KEY = 'd6d39cedee9024c88b64eb1bdd617a47'

# IV='c2b4b2f6ce549280'
IV = '1927bd83df40bc4d'

XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<GPACDRM type="CENC AES-CTR">
  <CrypTrack trackID="{track_id:d}" IsEncrypted="1" IV_size="{iv_size:d}"
             first_IV="{iv}" saiSavedBox="senc">
    <key KID="0x{kid}" value="0x{key}" />
  </CrypTrack>
</GPACDRM>
"""

class IndexArgs(object):
    debug = False
    codec = None
    index = True
    manifest = False
    split = False

    def __init__(self, filename):
        self.mp4file = [filename]

def encrypt_file(source, kid, key, iv):
    kid = kid.lower()
    if kid.startswith('0x'):
        kid = kid[2:]
    key = key.lower()
    if key.startswith('0x'):
        key = key[2:]
    iv = iv.lower()
    if iv.startswith('0x'):
        iv = key[2:]
    representation = create_representation(source, IndexArgs(source))
    try:
        fps = representation.frameRate
    except AttributeError:
        fps = None
    try:
        tmpdir = tempfile.mkdtemp()
        basename, ext = os.path.splitext(os.path.split(source)[1])
        moov_filename = os.path.join(tmpdir, basename + '-moov-enc.mp4')
        xmlfile = os.path.join(tmpdir, "drm.xml")
        iv_size = len(iv.decode('hex'))
        with open(xmlfile, 'wt') as xml:
            xml.write(XML_TEMPLATE.format(kid=kid, key=key, iv=iv, iv_size=iv_size,
                                          track_id=representation.track_id))

        # MP4Box does not appear to be able to encrypt and fragment in one
        # stage, so first encrypt the media and then fragment it afterwards
        args = ["MP4Box", "-crypt", xmlfile, "-out", moov_filename]
        if fps:
            args += ["-fps", str(fps)]
        args.append(source)
        print(args)
        rv = subprocess.call(args)
        if rv:
            print('Failed to generate encrypted MOOV file: {:d}'.format(rv))
            return rv
        prefix = os.path.join(tmpdir, basename + "-moov-enc_dash_")
        args = ["MP4Box",
                "-dash", "4000", "-frag", "4000", "-segment-name", "%s_dash_",
                "-profile", "live", "-rap", "-out", prefix]
        if fps:
            args += ["-fps", str(fps), "-timescale", str(fps * 10)]
        args.append(moov_filename)
        print(args)
        rv = subprocess.call(args)
        if rv:
            print('Failed to split encrypted MOOV file into fragments: {:d}'.format(rv))
            return rv
        # subprocess.call(["ls", tmpdir])
        dest_filename = basename + "_enc" + ext
        with open(dest_filename, "wb") as dest:
            sys.stdout.write('I')
            sys.stdout.flush()
            with open(prefix + "init.mp4", "rb") as src:
                shutil.copyfileobj(src, dest)
            segment = 1
            moof = "{}{:d}.m4s".format(prefix, segment)
            while os.path.exists(moof):
                sys.stdout.write('f')
                sys.stdout.flush()
                with open(moof, "rb") as src:
                    shutil.copyfileobj(src, dest)
                segment += 1
                moof = "{}{:d}.m4s".format(prefix, segment)
        sys.stdout.write('\n')
        sys.stdout.flush()
    finally:
        try:
            shutil.rmtree(tmpdir)
        except (Exception) as ex:
            print(ex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MP4 encryption')
    parser.add_argument('--kid', help='Key ID', nargs=1, default=[KID])
    parser.add_argument('--key', help='Encryption Key', nargs=1, default=[KEY])
    parser.add_argument('--iv', help='Initial Initialisation Vector', nargs=1, default=[IV])
    parser.add_argument('mp4file', help='Filename of MP4 file', nargs='+', default=None)
    args = parser.parse_args()
    for fname in args.mp4file:
        encrypt_file(fname, args.kid[0], args.key[0], args.iv[0])
