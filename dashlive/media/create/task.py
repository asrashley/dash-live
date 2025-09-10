#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from abc import ABC, abstractmethod
import datetime
import io
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import BinaryIO, Sequence, cast

from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation
from dashlive.utils.timezone import UTC

from .creation_result import CreationResult
from .media_create_options import MediaCreateOptions

class MediaCreationTask(ABC):
    options: MediaCreateOptions

    def __init__(self, options: MediaCreateOptions) -> None:
        self.options = options

    @abstractmethod
    def run(self) -> Sequence[CreationResult]:
        ...

    def destination_filename(self, contentType: str, index: int, encrypted: bool) -> str:
        enc: str = '_enc' if encrypted else ''
        return f'{self.options.prefix}_{contentType[0]}{index:d}{enc}.mp4'

    def parse_representation(self, filename: str) -> Representation:
        parser = mp4.IsoParser()
        logging.debug('Parse %s', filename)
        atoms: list[mp4.Mp4Atom] = cast(list[mp4.Mp4Atom], parser.walk_atoms(filename))
        verbose: int = 2 if self.options.verbose else 0
        logging.debug('Create Representation from "%s"', filename)
        return Representation.load(filename=filename.replace('\\', '/'),
                                   atoms=atoms, verbose=verbose)

    def modify_mp4_file(self, mp4file: Path, track_id: int, language: str,
                        encrypted: bool = False) -> None:
        """
        Updates the track ID and language tag of the specified MP4 file
        """
        mp4_options = mp4.Options(mode='rw', lazy_load=True)
        if encrypted:
            mp4_options.iv_size = self.options.iv_size

        logging.info('Modifying MP4 file "%s"', mp4file.name)
        with tempfile.TemporaryFile() as tmp:
            with mp4file.open('rb') as src:
                reader: io.BufferedReader = io.BufferedReader(src)
                atoms: list[mp4.Mp4Atom] = cast(list[mp4.Mp4Atom], mp4.Mp4Atom.load(
                    reader, options=mp4_options, use_wrapper=False))
                self.copy_and_modify(atoms, tmp, track_id, language)
            mp4file.unlink()
            tmp.seek(0)
            with mp4file.open('wb') as dest:
                shutil.copyfileobj(tmp, dest)

    @staticmethod
    def copy_and_modify(atoms: list[mp4.Mp4Atom], dest: BinaryIO, track_id: int, language: str) -> None:
        def modify_atom(atom: mp4.Mp4Atom) -> None:
            if atom.atom_type not in {'moov', 'moof'}:
                return
            if atom.atom_type == 'moov':
                moov: mp4.MovieBox = cast(mp4.MovieBox, atom)
                modified: bool = False
                if moov.trak.tkhd.track_id != track_id:
                    moov.trak.tkhd.track_id = track_id
                    moov.mvex.trex.track_id = track_id
                    moov.mvhd.next_track_id = track_id + 1
                    modified = True
                if moov.trak.mdia.mdhd.language != language:
                    moov.trak.mdia.mdhd.language = language
                    modified = True
                if modified:
                    moov.trak.tkhd.modification_time = datetime.datetime.now(tz=UTC())
                return
            moof: mp4.MovieFragmentBox = cast(mp4.MovieFragmentBox, atom)
            if moof.traf.tfhd.track_id != track_id:
                moof.traf.tfhd.track_id = track_id

        for atom in atoms:
            modify_atom(atom)
            atom.encode(dest)

    def create_file_from_fragments(self, dest_filename: Path, moov: Path, prefix: str) -> None:
        """
        Move all of the fragments into one file that starts with the init fragment.
        """
        logging.info('Create file "%s" moov="%s" prefix="%s"',
                     dest_filename, moov, prefix)
        if not moov.exists():
            raise OSError(f'MOOV not found: {moov}')

        with dest_filename.open("wb") as dest:
            if self.options.verbose:
                sys.stdout.write('I')
                sys.stdout.flush()
            with open(moov, "rb") as src:
                shutil.copyfileobj(src, dest)
            segment = 1
            while True:
                moof: str = f'{prefix}{segment:03d}.mp4'
                if not os.path.exists(moof):
                    break
                if self.options.verbose:
                    sys.stdout.write('f')
                    sys.stdout.flush()
                with open(moof, "rb") as src:
                    shutil.copyfileobj(src, dest)
                os.remove(moof)
                segment += 1
            if self.options.verbose:
                sys.stdout.write('\n')
        logging.info(r'Generated file %s', dest_filename)
