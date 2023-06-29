"""
Database table for storing refresh tokens and expired access tokens
"""

from datetime import datetime
from enum import IntEnum
import hashlib
from typing import Dict, Optional

from sqlalchemy import (  # type: ignore
    Boolean, Column, DateTime, String, Integer,  # type: ignore
    ForeignKey, func)  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from sqlalchemy.orm.exc import NoResultFound  # type: ignore

from .db import db
from .mixin import ModelMixin
from .session import DatabaseSession
from .user import User

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
    def add(cls, decoded_token: Dict, identity_claim: str, revoked: bool,
            session: DatabaseSession) -> None:
        """
        Adds a new token to the database.
        """
        jti = decoded_token['jti']
        token_type = TokenType[decoded_token['type'].upper()]
        user_identity = decoded_token[identity_claim]
        expires = datetime.fromtimestamp(decoded_token['exp'])

        user = session.query(User).filter_by(username=user_identity).one_or_none()
        db_token = Token(
            jti=jti,
            token_type=token_type.value,
            user=user,
            expires=expires,
            revoked=revoked,
        )
        session.add(db_token)
        session.commit()

    @classmethod
    def is_revoked(cls, decoded_token, session: DatabaseSession) -> bool:
        """
        Has the specified token been revoked?
        """
        jti = decoded_token['jti']
        token_type = decoded_token['type']
        try:
            token = session.query(cls).filter_by(jti=jti).one()
            return token.revoked
        except NoResultFound:
            return token_type != 'access'

    @classmethod
    def prune_database(cls, session: DatabaseSession) -> None:
        """
        Delete tokens that have expired from the database.
        """
        now = datetime.now()
        expired = session.query(cls).filter(cls.expires < now).all()
        for token in expired:
            session.delete(token)
        session.commit()
