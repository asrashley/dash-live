"""
Database model for a user of the app
"""
from typing import AbstractSet, List, Optional, Union, cast

from passlib.context import CryptContext  # type: ignore
from sqlalchemy import (  # type: ignore
    Boolean, Column, DateTime, String, Integer, func,
)
from sqlalchemy.orm import relationship  # type: ignore

from dashlive.utils.json_object import JsonObject
from .db import db
from .group import Group
from .mixin import ModelMixin

password_context = CryptContext(
    schemes=["bcrypt", "pbkdf2_sha256"],
    deprecated="auto",
)


class User(db.Model, ModelMixin):  # type: ignore
    """
    Database model for a user of the app
    """
    __tablename__ = 'User'
    __plural__ = 'Users'

    __RESET_TOKEN_LENGTH = 16

    # TODO: add "must_change" bool field
    pk = Column(Integer, primary_key=True)
    username = Column(String(32), nullable=False, unique=True)
    password = Column(String(512), nullable=False)
    must_change = Column(Boolean, default=False)
    # See http://tools.ietf.org/html/rfc5321#section-4.5.3 for email length limit
    email = Column(String(256), unique=True, nullable=False)
    last_login = Column(DateTime, nullable=True)
    groups_mask = Column(Integer, nullable=False, default=Group.USER.value)
    reset_expires = Column(DateTime, nullable=True)
    reset_token = Column(String(__RESET_TOKEN_LENGTH * 2), nullable=True)
    tokens = relationship("Token", back_populates="user", lazy='dynamic')

    def to_dict(self, exclude: Optional[AbstractSet[str]] = None,
                only: Optional[AbstractSet[str]] = None,
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
        return self.is_member_of(Group.GUEST)

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

    def has_permission(self, group: Group):
        """
        Check if the user has the permission associated with a group
        """
        return ((self.groups_mask & group.value) == group.value or
                self.is_admin)

    def get_groups(self) -> List[Group]:
        """
        get the list of groups assigned to this user
        """
        groups: List[Group] = []
        for group in cast(List[Group], list(Group)):
            if (self.groups_mask & group.value or (
                    self.is_admin and group.value <= Group.EDITOR.value)):
                groups.append(group.name)
        return groups

    def set_groups(self, groups: List[Union[Group, str]]) -> None:
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

    @classmethod
    def check_if_empty(cls, default_username: str, default_password: str):
        count = db.session.execute(db.session.query(func.count(User.pk))).scalar_one()
        print('user count', count)
        if count == 0:
            admin = User(
                username=default_username,
                must_change=True,
                email=default_username,
                groups_mask=Group.ADMIN,
            )
            admin.set_password(default_password)
            print(f'Adding default user account username="{default_username}"')
            db.session.add(admin)
            db.session.commit()
