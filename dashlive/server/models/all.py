from .error_reason import ErrorReason
from .content_type import ContentType
from .blob import Blob
from .key import Key
from .token import Token
from .user import User
from .adaptation_set import AdaptationSet
from .mediafile import MediaFile
from .mediafile_error import MediaFileError
from .stream import Stream
from .period import Period
from .multi_period_stream import MultiPeriodStream
from .db import db

models = [
    AdaptationSet, Blob, ErrorReason, ContentType, Key, MediaFile,
    MediaFileError, MultiPeriodStream, Period, Stream, Token, User,
]

def create_all_tables() -> None:
    db.create_all()
