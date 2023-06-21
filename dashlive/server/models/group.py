"""
Enumeration for group types
"""
import enum


class Group(enum.IntFlag):
    """
    Enumeration for group types
    """
    GUEST = 0x00000001
    USER = 0x00000002
    EDITOR = 0x00000004
    ADMIN = 0x40000000
