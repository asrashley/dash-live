"""
Database table for storing refresh tokens and expired access tokens
"""

from datetime import datetime, timedelta
from enum import IntEnum
import hashlib
from typing import ClassVar, Optional, TypedDict, TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, String, Integer,
    ForeignKey, func, delete
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.orm.exc import NoResultFound
from flask_jwt_extended import create_access_token

from .base import Base
from .db import db
from .session import DatabaseSession
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


KEY_LIFETIMES: dict[TokenType, timedelta] = {
    TokenType.ACCESS: timedelta(hours=2),
    TokenType.GUEST: timedelta(hours=6),
    TokenType.REFRESH: timedelta(days=7),
    TokenType.CSRF: timedelta(minutes=20),
}

class Token(ModelMixin["Token"], Base):
    """
    Database table for storing refresh tokens and expired access tokens
    """
    __tablename__: ClassVar[str] = 'Token'
    __plural__: ClassVar[str] = 'Tokens'
    API_KEY_LENGTH: ClassVar[int] = 32
    CSRF_KEY_LENGTH: ClassVar[int] = 32
    CSRF_SALT_LENGTH: ClassVar[int] = 8
    MAX_TOKEN_LENGTH: ClassVar[int] = max(
        36, 2 + CSRF_SALT_LENGTH + (3 * hashlib.sha1().digest_size // 2))

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(MAX_TOKEN_LENGTH), nullable=False)
    token_type: Mapped[int] = mapped_column(Integer, nullable=False)
    user_pk: Mapped[int | None] = mapped_column("user_pk", Integer, ForeignKey('User.pk'), nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="tokens")

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
            expires: datetime = datetime.now() + KEY_LIFETIMES[token_type]
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
    def prune_database(cls, all_csrf: bool, session: DatabaseSession) -> None:
        """
        Delete tokens that have expired from the database.
        """
        now = datetime.now()
        stmt = delete(cls).where(cls.expires < now)
        session.execute(stmt)
        if all_csrf:
            stmt = delete(cls).where(cls.token_type == TokenType.CSRF)
            session.execute(stmt)
        session.commit()
