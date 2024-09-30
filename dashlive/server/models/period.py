#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
from typing import TYPE_CHECKING, Optional, cast

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashlive.server.template_tags import timeDelta
from dashlive.server.options.form_input_field import FormInputContext, FieldOption

from .db import db
from .mixin import ModelMixin
from .stream import Stream

if TYPE_CHECKING:
    from .adaptation_set import AdaptationSet

class Period(db.Model, ModelMixin):
    __plural__ = 'Periods'

    pk: Mapped[int] = mapped_column(primary_key=True)
    pid = sa.Column(sa.String(62), nullable=False)
    parent_pk: Mapped[int] = mapped_column(sa.ForeignKey("mp_stream.pk"))
    parent: Mapped["MultiPeriodStream"] = relationship(back_populates="periods")  # noqa
    ordering: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    stream_pk: Mapped[int] = mapped_column(sa.ForeignKey("Stream.pk"))
    stream: Mapped[Stream] = relationship()
    start: Mapped[datetime.timedelta] = mapped_column(sa.Interval(), nullable=False)
    duration: Mapped[datetime.timedelta] = mapped_column(
        sa.Interval(), nullable=False)
    adaptation_sets: Mapped[list["AdaptationSet"]] = relationship(
        back_populates="period", cascade="all, delete")

    __table_args__ = (
        sa.UniqueConstraint("parent_pk", "pid",
                            name="single_period_id_per_mp_stream"),
    )

    @classmethod
    def get(cls, **kwargs) -> Optional["Period"]:
        return cast(Period | None, cls.get_one(**kwargs))

    def get_fields(self) -> list[FormInputContext]:
        ordering: FormInputContext = {
            'name': self.field_name('ordering'),
            'type': 'number',
            'minvalue': 0,
            'maxvalue': 999,
            'value': self.ordering,
        }
        pid: FormInputContext = {
            'name': self.field_name('pid'),
            'type': 'text',
            'pattern': r'[A-Za-z0-9_.\-]{1,60}',
            'maxlength': 60,
            'minlength': 1,
            'value': self.pid,
        }
        start: FormInputContext = self.get_time_input('start', self.start)
        if start['value'] == '':
            start['value'] = '00:00:00'
        fields: list[FormInputContext] = [
            ordering,
            pid,
            start,
            self.get_time_input('duration', self.duration),
            self.get_stream_select(),
        ]
        return fields

    def field_name(self, name: str) -> str:
        if not self.pk:
            return f'new_period_{name}'
        return f'period_{self.pk}_{name}'

    def get_stream_select(self) -> FormInputContext:
        options: list[FieldOption] = []
        for stream in Stream.all():
            options.append(FieldOption(
                title=stream.title,
                value=stream.directory,
                selected=(self.stream_pk == stream.pk)
            ))
        stream_select_field: FormInputContext = {
            'name': self.field_name('stream'),
            'type': 'select',
            'options': options,
        }
        return stream_select_field

    def get_time_input(self,
                       name: str,
                       value: datetime.timedelta | None) -> FormInputContext:
        field: FormInputContext = {
            'name': self.field_name(name),
            'type': 'time',
            'step': 1,
            'value': timeDelta(value, full_tc=True),
        }
        return field
