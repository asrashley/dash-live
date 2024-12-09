"""
Database table for storing refresh tokens and expired access tokens
"""

from datetime import datetime, timedelta
from enum import IntEnum
import hashlib
from typing import ClassVar, Optional, TypedDict, TYPE_CHECKING

from sqlalchemy import (  # type: ignore
    Boolean, Column, DateTime, String, Integer,  # type: ignore
    ForeignKey, func, delete)  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from sqlalchemy.orm.exc import NoResultFound
from flask_jwt_extended import create_access_token

from .db import db
from .mixin import ModelMixin

if TYPE_CHECKING:
    from .user import User

class TokenType(IntEnum):
    """
    Enum used in Token.token_type column
    """
    ACCESS = 1
    REFRESH = 2
    GUEST = 3
    CSRF = 4

class DecodedJwtToken(TypedDict):
    jti: str
    type: str  # 'access' or 'refresh'


class Token(db.Model, ModelMixin):
    """
    Database table for storing refresh tokens and expired access tokens
    """
    __tablename__ = 'Token'
    __plural__ = 'Tokens'
    API_KEY_LENGTH: ClassVar[int] = 32
    ACCESS_KEY_EXPIRY: ClassVar[timedelta] = timedelta(seconds=3600)
    REFRESH_KEY_EXPIRY: ClassVar[timedelta] = timedelta(days=7)
    CSRF_KEY_LENGTH: ClassVar[int] = 32
    CSRF_SALT_LENGTH: ClassVar[int] = 8
    MAX_TOKEN_LENGTH: ClassVar[int] = max(
        36, 2 + CSRF_SALT_LENGTH + (3 * hashlib.sha1().digest_size // 2))

    pk = Column(Integer, primary_key=True)
    jti = Column(String(MAX_TOKEN_LENGTH), nullable=False)
    token_type = Column(Integer, nullable=False)
    user_pk = Column("user_pk", Integer, ForeignKey('User.pk'), nullable=True)
    created = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires = Column(DateTime, nullable=True)
    revoked = Column(Boolean, nullable=False)
    user = relationship("User", back_populates="tokens")

    def has_expired(self) -> bool:
        if self.expires is None:
            return False
        return self.expires <= datetime.now()

    @classmethod
    def get(cls, **kwargs) -> Optional["Token"]:
        return cls.get_one(**kwargs)

    @classmethod
    def generate_api_token(cls, user: "User", token_type: TokenType) -> "Token":
        token: Token | None = Token.get(user_pk=user.pk, token_type=token_type)
        if token is not None and token.has_expired():
            db.session.delete(token)
            token = None
        if token is None:
            if token_type == TokenType.ACCESS:
                expires: datetime = datetime.now() + cls.ACCESS_KEY_EXPIRY
            else:
                expires = datetime.now() + cls.REFRESH_KEY_EXPIRY
            jti = create_access_token(identity=user.username)
            token = Token(
                user_pk=user.pk, token_type=token_type, jti=jti,
                expires=expires, revoked=False)
            db.session.add(token)
        return token

    @classmethod
    def is_revoked(cls, decoded_token: DecodedJwtToken) -> bool:
        """
        Has the specified token been revoked?
        """
        jti = decoded_token['jti']
        token_type = decoded_token['type']
        try:
            token = db.session.query(cls).filter_by(jti=jti).one()
            return token.revoked
        except NoResultFound:
            return token_type != 'access'

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
