#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import Callable

def create_id_factory(value: int = 1) -> Callable[[], int]:
    def next_value() -> int:
        nonlocal value
        val = value
        value += 1
        return val

    return next_value
