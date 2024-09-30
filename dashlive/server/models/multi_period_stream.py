#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
import re
from typing import TYPE_CHECKING, Iterable, Optional, cast

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sqlalchemy_jsonfield  # type: ignore

from dashlive.server.options.form_input_field import FormInputContext

from .db import db
from .mixin import ModelMixin
from .session import DatabaseSession

if TYPE_CHECKING:
    from .period import Period

class MultiPeriodStream(db.Model, ModelMixin):
    __ALLOWED_NAME_CHARS = r'A-Za-z0-9_.\-'
    __tablename__ = "mp_stream"
    __plural__ = 'MultiPeriodStreams'

    pk: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(64), nullable=False,
                                      index=True, unique=True)
    title: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    periods: Mapped[list["Period"]] = relationship(
        back_populates='parent', order_by='Period.ordering', cascade="all, delete")
    options = sa.Column(
        'options',
        sqlalchemy_jsonfield.JSONField(
            enforce_string=True,
            enforce_unicode=False
        ),
        nullable=True)

    def total_duration(self) -> datetime.timedelta:
        total: datetime.timedelta = datetime.timedelta()
        for period in self.periods:
            total += period.duration
        return total

    def get_fields(self, **kwargs) -> list[FormInputContext]:
        fields: list[FormInputContext] = [{
            "name": "name",
            "title": "Name",
            "type": "text",
            "required": True,
            "minlength": 3,
            "maxlength": 62,
            "pattern": f'[{ self.__ALLOWED_NAME_CHARS }]{{3,62}}',
            "value": kwargs.get("name", self.name),
        }, {
            "name": "title",
            "title": "Title",
            "type": "text",
            "required": True,
            "minlength": 3,
            "maxlength": 118,
            "value": kwargs.get('title', self.title),
        }]
        if self.pk:
            fields.append({
                "name": "pk",
                "type": "hidden",
                "value": self.pk,
            })
        return fields

    @classmethod
    def get(cls, **kwargs) -> Optional["MultiPeriodStream"]:
        """
        Get one object from this model, or None if not found
        """
        return cls.get_one(**kwargs)

    @classmethod
    def all(cls,
            session: DatabaseSession | None = None,
            order_by: list[sa.Column] | None = None
            ) -> Iterable["MultiPeriodStream"]:
        """
        Return all items from this table
        """
        return cast(
            Iterable[cls], cls.get_all(session=session, order_by=order_by))

    @classmethod
    def validate_values(cls,
                        name: str | None = None,
                        title: str | None = None,
                        pk: str | int | None = None,
                        **kwargs) -> dict[str, str]:
        errors: dict[str, str] = {}
        allowed_name_re = re.compile(f'^[{cls.__ALLOWED_NAME_CHARS}]+$')
        if name is None:
            errors['name'] = 'A name must be provided'
        elif len(name) < 3:
            errors['name'] = 'Name must be at least 3 characters'
        elif not allowed_name_re.match(name):
            errors['name'] = f'Name can only use the characters "{ cls.__ALLOWED_NAME_CHARS }"'
        else:
            model: MultiPeriodStream | None
            ipk: int = 0
            if isinstance(pk, int):
                ipk = pk
            elif pk is not None:
                try:
                    ipk = int(pk, 10)
                except ValueError:
                    errors['pk'] = 'Invalid primary key'
            model = cls.get_one(name=name)
            if model is not None:
                if pk is None or model.pk != ipk:
                    errors['name'] = f'Name "{name}" is already in use'

        if title is None:
            errors['title'] = 'A title must be provided'
        elif len(title) < 3:
            errors['title'] = 'Title must be at least 3 characters'

        return errors
