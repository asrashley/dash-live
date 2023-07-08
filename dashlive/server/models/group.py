"""
Enumeration for group types
"""
import enum
from typing import List

class Group(enum.IntFlag):
    """
    Enumeration for group types
    """
    GUEST = 0x00000001
    USER = 0x00000002
    EDITOR = 0x00000004
    ADMIN = 0x40000000

    @classmethod
    def names(cls) -> List[str]:
        """
        get list of group names
        """
        return sorted(cls.__members__.keys())  # type: ignore
