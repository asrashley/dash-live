"""
Database table for storing refresh tokens and expired access tokens
"""

from datetime import datetime, timedelta
from enum import IntEnum
import hashlib
from typing import ClassVar, NamedTuple, TypedDict, TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, String, Integer,
    ForeignKey, func, delete
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.orm.exc import NoResultFound
from flask_jwt_extended import create_access_token, create_refresh_token, get_jti

from .base import Base
from dashlive.utils.date_time import to_iso_datetime

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
    CSRF = 4

    @classmethod
    def from_int(cls, num: int) -> "TokenType":
        """
        Create a TokenType from its number
        """
        return cls(num)

    @classmethod
    def from_string(cls, name: str) -> "TokenType":
        """
        Create a TokenType from its name
        """
        return cls[name.upper()]


KEY_LIFETIMES: dict[TokenType, timedelta] = {
    TokenType.ACCESS: timedelta(hours=2),
    TokenType.REFRESH: timedelta(days=7),
    TokenType.CSRF: timedelta(minutes=20),
}

class DecodedJwtToken(TypedDict):
    jti: str
    type: str  # 'access' or 'refresh'
    sub: str | None  # subject
    exp: str | None  # expiration


class EncodedJWTokenJson(TypedDict):
    jwt: str
    expires: str


class EncodedJWToken(NamedTuple):
    jwt: str
    expires: datetime

    def toJSON(self) -> EncodedJWTokenJson:
        js: EncodedJWTokenJson = {
            "jwt": self.jwt,
            "expires": to_iso_datetime(self.expires),
        }
        return js

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

    def to_decoded_jwt(self) -> DecodedJwtToken:
        djt: DecodedJwtToken = {
            "jti": self.jti,
            "type": TokenType.from_int(self.token_type).name.lower(),
            "sub": self.user.username if self.user is not None else None,
            "exp": to_iso_datetime(self.expires) if self.expires is not None else None,
        }
        return djt

    @classmethod
    def generate_api_token(cls, user: "User", token_type: TokenType) -> EncodedJWToken:
        expires: datetime = datetime.now() + KEY_LIFETIMES[token_type]
        if token_type == TokenType.REFRESH:
            jwt: str = create_refresh_token(identity=user.username)
            jti: str | None = get_jti(jwt)
            assert jti is not None
            token = Token(
                user=user, token_type=token_type.value, jti=jti,
                expires=expires, revoked=False)
            db.session.add(token)
            db.session.commit()
        else:
            jwt = create_access_token(identity=user.username)
        return EncodedJWToken(jwt=jwt, expires=expires)

    @classmethod
    def is_revoked(cls, decoded_token: DecodedJwtToken) -> bool:
        """
        Has the specified token been revoked?
        """
        jti: str = decoded_token['jti']
        try:
            tok_type: TokenType = TokenType.from_string(decoded_token["type"])
            token: Token = db.session.query(cls).filter_by(jti=jti, token_type=tok_type.value).one()
            return token.revoked
        except NoResultFound:
            return tok_type == TokenType.REFRESH

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
