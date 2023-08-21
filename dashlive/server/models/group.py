"""
Enumeration for group types
"""
import enum

class Group(enum.IntFlag):
    """
    Enumeration for group types
    """
    USER = 0x00000002
    MEDIA = 0x00000004
    ADMIN = 0x40000000

    @classmethod
    def names(cls) -> list[str]:
        """
        get list of group names
        """
        return sorted(cls.__members__.keys())  # type: ignore
