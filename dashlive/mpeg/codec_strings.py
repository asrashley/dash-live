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
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from typing import ClassVar

import bitstring

from .mp4 import VisualSampleEntry

class CodecData(ABC):
    codec: str

    @abstractmethod
    def to_string(self) -> str:
        ...

    @abstractmethod
    def profile_string(self) -> str:
        ...

    def __str__(self) -> str:
        return self.to_string()


@dataclass(slots=True)
class H264Codec(CodecData):
    PROFILE_NAMES: ClassVar[dict[int, str]] = {
        44: 'intra',
        66: 'baseline',
        77: 'main',
        83: 'scalable baseline',
        86: 'scalable high',
        88: 'extended',
        100: 'high',
        110: 'high10',
        122: 'high422',
        244: 'high444',
    }
    avc_type: str
    profile: int
    compatibility: int
    level: float

    def __post_init__(self) -> None:
        self.codec = 'h.264'

    @classmethod
    def from_avc_box(cls, avc_type: str, avc: VisualSampleEntry) -> CodecData:
        profile = avc.avcC.AVCProfileIndication
        compatibility = avc.avcC.profile_compatibility
        level: float = avc.avcC.AVCLevelIndication / 10.0
        return H264Codec(avc_type, profile, compatibility, level)

    @classmethod
    def from_string(cls, codec_string: str) -> CodecData:
        codec_name, details = codec_string.split('.')
        profile = int(details[:2], 16)
        compatibility = int(details[2:4], 16)
        level = int(details[4:], 16) / 10.0
        return H264Codec(codec_name, profile, compatibility, level)

    def to_string(self) -> str:
        level = int(math.floor(self.level * 10))
        pcl = f'{self.profile:02x}{self.compatibility:02x}{level:02x}'
        return f'{self.avc_type}.{pcl.upper()}'

    def profile_string(self) -> str:
        try:
            return H264Codec.PROFILE_NAMES[self.profile]
        except KeyError:
            return f'{self.profile}'


@dataclass(slots=True)
class H265Codec(CodecData):
    avc_type: str
    profile_idc: int
    profile_space: int
    level_idc: int
    tier_flag: int
    profile_compatibility_flags: int
    constraint_indicator_flags: int

    def __post_init__(self) -> None:
        self.codec = 'h.265'

    @classmethod
    def from_avc_box(cls, avc_type: str, avc: VisualSampleEntry) -> CodecData:
        gpcf = bitstring.BitArray(
            uint=avc.hvcC.general_profile_compatibility_flags, length=32)
        gpcf.reverse()
        return H265Codec(
            avc_type=avc_type,
            profile_idc=avc.hvcC.general_profile_idc,
            profile_space=avc.hvcC.general_profile_space,
            level_idc=avc.hvcC.general_level_idc,
            tier_flag=avc.hvcC.general_tier_flag,
            profile_compatibility_flags=gpcf.uint,
            constraint_indicator_flags=avc.hvcC.general_constraint_indicator_flags)

    def to_string(self) -> str:
        # According to ISO 14496-15, the codec string for hev1 and hvc1
        # should be:
        # * the general_profile_space, encoded as no character
        #   (general_profile_space == 0), or 'A', 'B', 'C' for
        #   general_profile_space 1, 2, 3, followed by the general_profile_idc
        #   encoded as a decimal number;
        # * the general_profile_compatibility_flags, encoded in hexadecimal
        #   (leading zeroes may be omitted);
        # * the general_tier_flag, encoded as 'L' (general_tier_flag==0) or
        #   'H' (general_tier_flag==1), followed by the general_level_idc,
        #   encoded as a decimal number;
        # * each of the 6 bytes of the constraint flags, starting from the byte
        #   containing the general_progressive_source_flag, each encoded as a
        #   hexadecimal number, and the encoding of each byte separated by a
        #   period; trailing bytes that are zero may be omitted.
        gps: str = ['', 'A', 'B', 'C'][self.profile_space]
        lh: str = 'LH'[self.tier_flag]
        tier: str = f'{lh}{self.level_idc}'
        parts: list[str] = [
            str(self.avc_type),
            f'{gps}{self.profile_idc:d}',
            f'{self.profile_compatibility_flags:x}',
            tier,
        ]
        gcif: int = self.constraint_indicator_flags
        pos = 40
        while gcif > 0:
            mask: int = 0xFF << pos
            parts.append(f'{(gcif & mask) >> pos:x}'.upper())
            gcif = gcif & ~mask
            pos -= 8
        return '.'.join(parts)

    def profile_string(self) -> str:
        if self.tier_flag:
            return f'high.{self.profile_idc}'
        return f'main.{self.profile_idc}'

    @classmethod
    def from_string(cls, codec_string: str) -> CodecData:
        parts: list[str] = codec_string.split('.')
        if parts[1][0] >= 'A':
            profile_space: int = 1 + ord(parts[1][0]) - ord('A')
            profile_idc = int(parts[1][1:], 10)
        else:
            profile_space = 0
            profile_idc = int(parts[1], 10)
        profile_compatibility_flags = int(parts[2], 16)
        level_idc = int(parts[3][1:], 10)
        tier_flag: int = 1 if parts[3] == 'H' else 0
        constraint_indicator_flags: int = 0
        if len(parts) > 4:
            constraint_indicator_flags = int(''.join(parts[4:]), 16)
            shift: int = 8 * (10 - len(parts))
            constraint_indicator_flags = constraint_indicator_flags << shift
        return H265Codec(
            avc_type=parts[0], profile_space=profile_space,
            profile_idc=profile_idc, level_idc=level_idc, tier_flag=tier_flag,
            profile_compatibility_flags=profile_compatibility_flags,
            constraint_indicator_flags=constraint_indicator_flags)


@dataclass(slots=True)
class Mp4AudioCodec(CodecData):
    MP2_OBJECT_TYPE: ClassVar[int] = 0x67
    MP2_PROFILE_NAMES: ClassVar[dict[int, str]] = {
        0x67: 'LC',
    }
    MP4_OBJECT_TYPE: ClassVar[int] = 0x40
    MP4_PROFILE_NAMES: ClassVar[dict[int, str]] = {
        1: 'main',
        2: 'LC',
        3: 'SSR',
        4: 'LTP',
        5: 'SBR',
        6: 'scalable',
        7: 'twin VQ',
        8: 'CELP',
        9: 'HVXC',
        29: 'LC + SBR + PS'
    }
    codec: str = field(default='mp4a', init=False)
    avc_type: str
    object_type: int
    audio_object_type: int

    @classmethod
    def from_avc_box(cls, avc_type: str, avc: VisualSampleEntry) -> CodecData:
        dsi = avc.esds.descriptor("DecoderSpecificInfo")
        return Mp4AudioCodec(
            avc_type=avc_type,
            object_type=dsi.object_type,
            audio_object_type=dsi.audio_object_type)

    @classmethod
    def from_string(cls, codec_string: str) -> CodecData:
        try:
            codec_name, object_type, audio_object_type = codec_string.split('.')
        except ValueError:
            codec_name, object_type = codec_string.split('.')
            audio_object_type = '0'
        return Mp4AudioCodec(
            avc_type=codec_name, object_type=int(object_type, 16),
            audio_object_type=int(audio_object_type, 10))

    def to_string(self) -> str:
        return f"{self.avc_type}.{self.object_type:02x}.{self.audio_object_type:d}"

    def profile_string(self) -> str:
        if self.object_type == Mp4AudioCodec.MP4_OBJECT_TYPE:
            try:
                return f'MPEG-4 AAC {Mp4AudioCodec.MP4_PROFILE_NAMES[self.audio_object_type]}'
            except KeyError:
                return f'MPEG-4 AAC 0x{self.audio_object_type:x}'
        if self.object_type == Mp4AudioCodec.MP2_OBJECT_TYPE:
            try:
                return f'MPEG-2 AAC {Mp4AudioCodec.MP2_PROFILE_NAMES[self.object_type]}'
            except KeyError:
                return f'MPEG-2 AAC 0x{self.object_type:x}'
        return self.to_string()


@dataclass(slots=True)
class DolbyAudioCodec(CodecData):
    codec: str
    avc_type: str

    @classmethod
    def from_avc_box(cls, avc_type: str, avc: VisualSampleEntry) -> CodecData:
        return cls.from_string(avc_type)

    @classmethod
    def from_string(cls, avc_type: str) -> CodecData:
        codec = 'eac3' if avc_type[0] == 'e' else 'ac3'
        return DolbyAudioCodec(codec, avc_type)

    def to_string(self) -> str:
        return self.avc_type

    def profile_string(self) -> str:
        return ''


CODEC_DATA_TYPES = {
    'ac-3': DolbyAudioCodec,
    'avc1': H264Codec,
    'avc3': H264Codec,
    'ec-3': DolbyAudioCodec,
    'hev1': H265Codec,
    'hvc1': H265Codec,
    'mp4a': Mp4AudioCodec,
}

def codec_string_from_avc_box(avc_type: str, avc_box: VisualSampleEntry) -> str:
    try:
        cls = CODEC_DATA_TYPES[avc_type]
        data = cls.from_avc_box(avc_type, avc_box)
        return data.to_string()
    except KeyError:
        return avc_type

def codec_data_from_string(codec: str) -> CodecData:
    avc_type = codec.split('.')[0]
    cls = CODEC_DATA_TYPES[avc_type]
    return cls.from_string(codec)
