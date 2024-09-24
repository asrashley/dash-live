#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from langcodes import standardize_tag

UNDEFINED_LANGS: set[str | None] = {'und', 'zxx', None}

def lang_is_equal(a: str | None,
                  b: str | None,
                  match_undefined: bool = False) -> bool:
    """
    Checks if two BCP-47 languages match.
    If match_undefined is True, it also matches any of the
    undefined or not-applicable codes with the other language tag.
    """
    if a == b:
        return True
    if match_undefined:
        if a in UNDEFINED_LANGS:
            return True
        if b in UNDEFINED_LANGS:
            return True
    if a is None or b is None:
        return False
    try:
        a = standardize_tag(a)
        b = standardize_tag(b)
    except ValueError:
        return False
    return a == b
