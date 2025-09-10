#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging
import os
from pathlib import Path
import subprocess
import tempfile
from typing import ClassVar, Sequence
from dashlive.drm.key_tuple import KeyTuple
from dashlive.drm.keymaterial import KeyMaterial
from dashlive.media.create.creation_result import CreationResult
from dashlive.media.create.encoded_representation import EncodedRepresentation
from dashlive.media.create.media_create_options import MediaCreateOptions
from dashlive.media.create.task import MediaCreationTask
from dashlive.mpeg.dash.representation import Representation

class InitialisationVector(KeyMaterial):
    length: ClassVar[int] = 8

class EncryptMediaTask(MediaCreationTask):
    # See https://wiki.gpac.io/xmlformats/Common-Encryption
    XML_TEMPLATE: ClassVar[str] = """<?xml version="1.0" encoding="UTF-8"?>
    <GPACDRM type="CENC AES-CTR">
      <CrypTrack trackID="{track_id:d}" IsEncrypted="1" IV_size="{iv_size:d}"
        first_IV="{iv}" saiSavedBox="senc">
        <key KID="0x{kid}" value="0x{key}" />
      </CrypTrack>
    </GPACDRM>
    """

    iv: InitialisationVector
    key_material: KeyTuple
    src: EncodedRepresentation
    dest_file: Path

    def __init__(self, options: MediaCreateOptions, src: EncodedRepresentation, key: KeyTuple) -> None:
        super().__init__(options)
        self.src = src
        self.dest_file = src.filename.parent / f"{src.filename.stem}_enc{src.filename.suffix}"
        self.key_material = key
        self.iv = InitialisationVector(raw=os.urandom(self.options.iv_size // 8))

    def run(self) -> Sequence[CreationResult]:
        result: EncodedRepresentation = EncodedRepresentation(
            source=self.src.filename, filename=self.dest_file,
            src_track_id=self.src.track_id, track_id=self.src.track_id,
            duration=self.src.duration, rep_id=self.src.rep_id, file_index=self.src.file_index,
            content_type=self.src.content_type, encrypted=True)
        if not self.dest_file.exists():
            with tempfile.TemporaryDirectory() as tmpdir:
                self.build_encrypted_file(Path(tmpdir))
        return [result]

    def build_encrypted_file(self, tmpdir: Path) -> None:
        assert self.src.filename.exists()
        representation: Representation = self.parse_representation(str(self.src.filename))
        basename: str = self.src.filename.stem
        moov_filename: Path = tmpdir / f'{basename}-moov-enc.mp4'
        xmlfile: Path = tmpdir / "drm.xml"
        with xmlfile.open('wt', encoding='utf-8') as xml:
            template: str = self.XML_TEMPLATE.format(
                kid=self.key_material.KID.hex,
                key=self.key_material.KEY.hex,
                iv=self.iv.hex, iv_size=self.iv.length,
                track_id=representation.track_id)
            logging.debug("%s", template)
            xml.write(template)
        # MP4Box does not appear to be able to encrypt and fragment in one
        # stage, so first encrypt the media and then fragment it afterwards
        args: list[str] = [
            "MP4Box",
            "-crypt", str(xmlfile),
            "-out", str(moov_filename),
        ]
        if representation.content_type == 'video' and self.options.framerate:
            args += ["-fps", str(self.options.framerate)]
        args.append(str(self.src.filename))
        logging.debug('MP4Box arguments: %s', args)
        subprocess.check_call(args, cwd=self.options.destdir)

        assert moov_filename.exists()

        prefix = str(tmpdir / "dash_enc_")
        args = [
            "MP4Box",
            "-dash", str(self.options.segment_duration * self.options.timescale),
            "-frag", str(self.options.segment_duration * self.options.timescale),
            "-segment-ext", "mp4",
            "-segment-name", 'dash_enc_$Number%03d$$Init=init$',
            "-profile", "live",
            "-frag-rap",
            "-fps", str(self.options.framerate),
            "-timescale", str(self.options.timescale),
            "-rap",
            "-out", "manifest",
            str(moov_filename),
        ]
        logging.debug('MP4Box arguments: %s', args)
        cwd: str = os.getcwd()
        try:
            os.chdir(tmpdir)
            subprocess.check_call(args)
        finally:
            os.chdir(cwd)
        moov = Path(prefix + "init.mp4")
        if self.options.verbose:
            subprocess.call(["ls", tmpdir])
        self.create_file_from_fragments(self.dest_file, moov, prefix)
