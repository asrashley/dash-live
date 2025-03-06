from typing import NotRequired, TypedDict, cast, AbstractSet, ClassVar, Optional, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.utils.json_object import JsonObject

from .base import Base
from .db import db
from .mixin import ModelMixin
from .mediafile_keys import mediafile_keys

if TYPE_CHECKING:
    from .mediafile import MediaFile

class KeyJson(TypedDict):
    kid: str
    key: str
    alg: str
    computed: bool
    b64Key: NotRequired[str]
    guidKid: NotRequired[str]


class Key(ModelMixin["Key"], Base):
    __plural__: ClassVar[str] = 'Keys'
    __tablename__: ClassVar[str] = 'key'

    pk: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    hkid: Mapped[str] = mapped_column(sa.String(34), nullable=False, unique=True, index=True)
    hkey: Mapped[str] = mapped_column(sa.String(34), nullable=False)
    computed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    halg: Mapped[str] = mapped_column(sa.String(16), nullable=True)
    mediafiles: Mapped[list["MediaFile"]] = relationship(  # noqa: F821
        secondary=mediafile_keys, back_populates='encryption_keys')

    @property
    def KID(self) -> KeyMaterial:
        return KeyMaterial(self.hkid)

    @property
    def KEY(self) -> KeyMaterial:
        return KeyMaterial(self.hkey)

    @property
    def ALG(self) -> str:
        if self.halg is None:
            return "AESCTR"
        return self.halg

    @classmethod
    def get_kids(clz, kids: AbstractSet[KeyMaterial | str]) -> dict[str, "Key"]:
        def to_hex(kid: KeyMaterial | str) -> str:
            if isinstance(kid, KeyMaterial):
                return kid.hex
            return kid.lower()
        kids = list(map(to_hex, kids))
        query = db.select(Key)
        if len(kids) == 1:
            query = query.filter_by(hkid=kids[0])
        else:
            query = query.filter(Key.hkid.in_(kids))
        rv = {}
        for k in db.session.execute(query).scalars():
            rv[k.hkid.lower()] = k
        return rv

    @classmethod
    def all(clz, order_by: tuple | None = None) -> list["Key"]:
        return cast(list[Key], clz.get_all())

    @classmethod
    def get(clz, **kwargs) -> Optional["Key"]:
        return cast(clz, clz.get_one(**kwargs))

    @classmethod
    def all_as_dict(clz) -> list[dict[str, "Key"]]:
        rv = {}
        for k in clz.all():
            rv[k.hkid.lower()] = k
        return rv

    def toJSON(self, pure: bool = False,
               exclude: AbstractSet[str] | None = None) -> KeyJson:
        js: KeyJson = {
            'kid': self.KID.hex,
            'key': self.KEY.hex,
            'alg': self.ALG,
            'computed': self.computed,
        }
        if exclude is None:
            return js
        for ex in exclude:
            del js[ex]
        return js

    def get_fields(self) -> list[JsonObject]:
        return [{
            "name": "hkid",
            "title": "KID (in hex)",
            "type": "text",
            "value": self.hkid,
            "minlength": KeyMaterial.length * 2,
            "maxlength": KeyMaterial.length * 2,
            "pattern": f'[A-Fa-f0-9]{{{KeyMaterial.length * 2}}}',
            "placeholder": f'{KeyMaterial.length * 2} hexadecimal digits',
            "spellcheck": False,
            "columns": ["col-3", "col-7", ""],
        }, {
            "name": "hkey",
            "title": "Key (in hex)",
            "type": "text",
            "minlength": KeyMaterial.length * 2,
            "maxlength": KeyMaterial.length * 2,
            "pattern": f'[A-Fa-f0-9]{{{KeyMaterial.length * 2}}}',
            "spellcheck": False,
            "placeholder": f'{KeyMaterial.length * 2} hexadecimal digits',
            "value": self.hkey,
            "columns": ["col-3", "col-7", ""],
        }, {
            "name": "computed",
            "title": "Key is auto-computed?",
            "type": "checkbox",
            "value": self.computed,
            "columns": ["col-3", "col-6", ""],
        }]
