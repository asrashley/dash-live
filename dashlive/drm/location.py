#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from enum import Enum

class DrmLocation(Enum):
    CENC = 'cenc'
    MOOV = 'moov'
    PRO = 'pro'

    @classmethod
    def all(cls) -> list["DrmLocation"]:
        return [cls[k] for k in cls.keys()]

    @classmethod
    def keys(cls) -> list[str]:
        """get list of items in this enum"""
        return sorted(cls.__members__.keys())  # type: ignore

    @classmethod
    def values(cls) -> list[str]:
        """get list of item values in this enum"""
        return sorted([c.lower() for c in cls.__members__.keys()])  # type: ignore

    @classmethod
    def from_string(cls, name: str) -> "DrmLocation":
        """
        Convert name string into this enum
        """
        return cls[name.upper()]  # type: ignore

    def to_json(self) -> str:
        return self.value
