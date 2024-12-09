#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

def content_type_to_mime_type(content_type: str, codecs: str | None) -> str:
    if content_type in {'audio', 'video'}:
        return f"{content_type}/mp4"
    if content_type == 'text':
        if codecs is not None and 'wvtt' in codecs:
            return 'text/vtt'
    return 'application/mp4'

def content_type_file_suffix(content_type: str) -> str:
    if content_type == 'audio':
        return 'm4a'
    if content_type == 'video':
        return 'm4v'
    return 'mp4'
