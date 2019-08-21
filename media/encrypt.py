#!/usr/bin/python

import argparse
import os
import shutil
import subprocess
import tempfile
import sys

from gen_index import create_index_file, create_representation

KID='c001de8e567b5fcfbc22c565ed5bda24'
KEY='533a583a843436a536fbe2a5821c4b6c'
IV='c2b4b2f6ce549280'

XML_TEMPLATE="""<?xml version="1.0" encoding="UTF-8"?>
<GPACDRM type="CENC AES-CTR">
  <CrypTrack trackID="{track_id:d}" IsEncrypted="1" IV_size="{iv_size:d}"
             first_IV="{iv}" saiSavedBox="senc">
    <key KID="0x{kid}" value="0x{key}" />
  </CrypTrack>
</GPACDRM>
"""

class IndexArgs(object):
    debug=False
    codec=None
    index=True
    manifest=False
    split=False

    def __init__(self, filename):
        self.mp4file = [ filename ]
        
def encrypt_file(source, kid, key, iv):
    #mp4encrypt --show-progress --method MPEG-CENC --key 1:${KEY}:${IV} --property 1:KID:${KID} ${1}.mp4 ${1}ENC.mp4
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
        moov_filename = os.path.join(tmpdir, basename+'-moov-enc.mp4')
        xmlfile = os.path.join(tmpdir,"drm.xml")
        iv_size = len(iv.decode('hex'))
        with open(xmlfile, 'w') as xml:
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
            print 'Failed to generate encrypted MOOV file: {:d}'.format(rv)
            return rv
        prefix = os.path.join(tmpdir, basename+"-moov-enc_dash_")
        args = ["MP4Box",
                "-dash", "4000", "-frag", "4000", "-segment-name", "%s_dash_",
                "-profile", "live", "-rap", "-out", prefix]
        if fps:
            args += ["-fps", str(fps), "-timescale", str(fps*10)]
        args.append(moov_filename)
        print(args)
        rv = subprocess.call(args)
        if rv:
            print 'Failed to split encrypted MOOV file into fragments: {:d}'.format(rv)
            return rv
        #subprocess.call(["ls", tmpdir])
        dest_filename = basename+"ENC"+ext
        with open(dest_filename, "wb") as dest:
            sys.stdout.write('I')
            sys.stdout.flush()
            with open(prefix+"init.mp4", "rb") as src:
                shutil.copyfileobj(src, dest)
            segment=1
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
        create_index_file(dest_filename, IndexArgs(dest_filename))
    finally:
        try:
            shutil.rmtree(tmpdir)
        except (Exception) as ex:
            print(ex)
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MP4 encryption')
    parser.add_argument('--kid', help='Key ID', nargs=1, default=KID)
    parser.add_argument('--key', help='Encryption Key', nargs=1, default=KEY)
    parser.add_argument('--iv', help='Initial Initialisation Vector', nargs=1, default=IV)
    parser.add_argument('mp4file', help='Filename of MP4 file', nargs='+', default=None)
    args = parser.parse_args()
    for fname in args.mp4file:
        encrypt_file(fname, args.kid, args.key, args.iv)
