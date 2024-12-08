#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from enum import IntEnum

class ContentRole(IntEnum):
    """
    Enumerates all possible content roles
    """

    MAIN = 1
    ALTERNATE = 2
    SUPPLEMENTAL = 3
