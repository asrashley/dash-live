"""
Database model for a user of the app
"""
from datetime import datetime
import logging
import secrets
from typing import AbstractSet, ClassVar, NotRequired, Optional, TypedDict, cast, TYPE_CHECKING

from passlib.context import CryptContext  # type: ignore
from sqlalchemy import DateTime, String, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column

from dashlive.utils.json_object import JsonObject

from .base import Base
from .db import db
from .group import Group
from .mixin import ModelMixin
from .session import DatabaseSession

password_context = CryptContext(
    schemes=["sha512_crypt", "bcrypt", "pbkdf2_sha256"],
    deprecated="auto",
)

if TYPE_CHECKING:
    from .token import Token

class UserSummaryJson(TypedDict):
    pk: int
    email: str
    username: str
    lastLogin: str | None
    mustChange: NotRequired[bool]
    groups: list[str]

class User(ModelMixin["User"], Base):
    """
    Database model for a user of the app
    """
    __tablename__: str = 'User'
    __plural__: str = 'Users'

    __RESET_TOKEN_LENGTH: ClassVar[int] = 16
    __GUEST_USERNAME: ClassVar[str] = '_AnonymousUser_'

    pk: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(512), nullable=False)
    must_change: Mapped[bool] = mapped_column(default=False)
    # See http://tools.ietf.org/html/rfc5321#section-4.5.3 for email length limit
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    groups_mask: Mapped[int] = mapped_column(Integer, nullable=False, default=Group.USER.value)
    reset_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reset_token: Mapped[str | None] = mapped_column(String(__RESET_TOKEN_LENGTH * 2), nullable=True)
    tokens: Mapped[list["Token"]] = relationship(
        "Token", back_populates="user", lazy='dynamic', cascade="all, delete")

    @classmethod
    def get(cls, **kwargs) -> Optional["User"]:
        """
        Get one user, or None if not found
        """
        return cast("User", cls.get_one(**kwargs))

    @classmethod
    def all(cls, **kwargs) -> list["User"]:
        """
        Return all users
        """
        return cast(list["User"], cls.get_all(**kwargs))

    def to_dict(self, exclude: AbstractSet[str] | None = None,
                only: AbstractSet[str] | None = None,
                with_collections: bool = False) -> JsonObject:
        """
        Convert this model into a dictionary
        :exclude: set of attributes to exclude
        :only: set of attributes to include
        """
        if exclude is None:
            exclude = set({'tokens'})
        return super().to_dict(exclude=exclude,
                               only=only, with_collections=with_collections)

    def get_id(self) -> str:
        """
        This method must return a string that uniquely identifies this user.
        """
        return self.username

    @property
    def is_active(self) -> bool:
        return True

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def set_password(self, password: str) -> None:
        """
        Set the password of this user.
        The password is converted using a one-way hash to make it hard to reverse
        """
        self.password = self.hash_password(password)

    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Perform one-way hash of supplied plain text password
        """
        return password_context.hash(password)

    def check_password(self, password: str) -> bool:
        """
        Check the given password is correct
        """
        try:
            if not password_context.verify(password, self.password):
                return False
        except ValueError:
            return False
        if password_context.needs_update(self.password):
            # password is valid but using a deprecated hash
            self.set_password(password)
        return True

    @property
    def is_admin(self) -> bool:
        """
        Is this user an admin?
        """
        return (self.groups_mask & Group.ADMIN.value) == Group.ADMIN.value

    def is_member_of(self, group: Group):
        """
        Check if the user is a member of the specified group
        """
        return (self.groups_mask & group.value) == group.value

    def has_permission(self, group: Group | str) -> bool:
        """
        Check if the user has the permission associated with a group
        """
        if isinstance(group, str):
            group = Group[group.upper()]
        return ((self.groups_mask & group.value) == group.value or
                self.is_admin)

    def get_groups(self) -> list[str]:
        """
        get the list of group names assigned to this user
        """
        groups: list[str] = []
        for group in cast(list[Group], list(Group)):
            if (self.groups_mask & group.value or (
                    self.is_admin and group.value <= Group.MEDIA.value)):
                groups.append(group.name)
        return groups

    def set_groups(self, groups: list[Group | str]) -> None:
        """
        set list of groups for this user
        """
        value = 0
        for group in groups:
            if isinstance(group, str):
                group = Group[group.upper()]
            value += group.value
        self.groups_mask = value

    groups = property(get_groups, set_groups)

    def summary(self) -> UserSummaryJson:
        user_json: UserSummaryJson = {
            "pk": self.pk,
            "email": self.email,
            "username": self.username,
            "mustChange": self.must_change,
            "lastLogin": self.last_login.isoformat() if self.last_login else None,
            "groups": self.get_groups(),
        }
        return user_json

    @classmethod
    def populate_if_empty(cls, default_username: str, default_password: str, session: DatabaseSession) -> None:
        count: int = cls.count()
        logging.debug('User count: %d', count)
        if count == 0:
            admin = User(
                username=default_username,
                must_change=True,
                email=default_username,
                groups_mask=Group.ADMIN,
            )
            admin.set_password(default_password)
            logging.info('Adding default user account username="%s"', default_username)
            session.add(admin)

    @classmethod
    def get_guest_user(cls) -> "User":
        guest = cls.get(username=cls.__GUEST_USERNAME, groups_mask=0)
        if guest:
            return guest
        guest = User(username=cls.__GUEST_USERNAME, groups_mask=0,
                     must_change=False, email=cls.__GUEST_USERNAME)
        guest.set_password(secrets.token_urlsafe(16))
        db.session.add(guest)
        db.session.commit()
        return guest

    def get_fields(self, with_must_change: bool = True,
                   with_confirm_password: bool = False, **kwargs) -> list[JsonObject]:
        fields = [{
            "name": "username",
            "title": "Username",
            "type": "text",
            "value": kwargs.get('username', self.username),
            "minlength": 5,
            "maxlength": 31,
            "pattern": r'[A-Za-z0-9._-]+',
            "placeholder": 'user name',
            "spellcheck": False,
        }, {
            "name": "password",
            "title": "Password",
            "type": "password",
            "value": kwargs.get('password', ''),
            "placeholder": '*****',
            "minlength": 5,
            "maxlength": 31,
        }, {
            "name": "email",
            "title": "Email address",
            "type": "email",
            "value": kwargs.get('email', self.email),
            "maxlength": 250,
            "placeholder": 'email address',
            "spellcheck": False,
        }]
        if with_must_change:
            fields.append({
                "name": "must_change",
                "title": "Must change password?",
                "type": "checkbox",
                "value": kwargs.get('must_change', self.must_change),
            })
        if with_confirm_password:
            fields.insert(2, {
                "name": "confirm_password",
                "title": "Confirm Password",
                "type": "password",
                "value": kwargs.get('confirm_password', ''),
                "placeholder": '*****',
                "minlength": 5,
                "maxlength": 31,
            })
        return fields
