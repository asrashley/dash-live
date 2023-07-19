"""
Database table for storing refresh tokens and expired access tokens
"""

from datetime import datetime
from enum import IntEnum
import hashlib
from typing import Optional

from sqlalchemy import (  # type: ignore
    Boolean, Column, DateTime, String, Integer,  # type: ignore
    ForeignKey, func, delete)  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from .db import db
from .mixin import ModelMixin

class TokenType(IntEnum):
    """
    Enum used in Token.token_type column
    """
    ACCESS = 1
    REFRESH = 2
    GUEST = 3
    CSRF = 4


class Token(db.Model, ModelMixin):
    """
    Database table for storing refresh tokens and expired access tokens
    """
    __tablename__ = 'Token'
    __plural__ = 'Tokens'
    CSRF_KEY_LENGTH = 32
    CSRF_SALT_LENGTH = 8
    MAX_TOKEN_LNGTH = max(36, 2 + CSRF_SALT_LENGTH + (3 * hashlib.sha1().digest_size // 2))

    pk = Column(Integer, primary_key=True)
    jti = Column(String(MAX_TOKEN_LNGTH), nullable=False)
    token_type = Column(Integer, nullable=False)
    user_pk = Column("user_pk", Integer, ForeignKey('User.pk'), nullable=True)
    created = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires = Column(DateTime, nullable=True)
    revoked = Column(Boolean, nullable=False)
    user = relationship("User", back_populates="tokens")

    @classmethod
    def get(cls, **kwargs) -> Optional["Token"]:
        return cls.get_one(**kwargs)

    @classmethod
    def prune_database(cls, all_csrf: bool) -> None:
        """
        Delete tokens that have expired from the database.
        """
        now = datetime.now()
        stmt = delete(cls).where(cls.expires < now)
        db.session.execute(stmt)
        if all_csrf:
            stmt = delete(cls).where(cls.token_type == TokenType.CSRF)
            db.session.execute(stmt)
        db.session.commit()
