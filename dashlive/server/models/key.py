import re
from typing import cast, AbstractSet, Optional

import sqlalchemy as sa

from dashlive.drm.keymaterial import KeyMaterial
from dashlive.utils.json_object import JsonObject

from .db import db
from .mediafile_keys import mediafile_keys
from .mixin import ModelMixin

def kid_validator(prop, value):
    if not re.match(r'^[0-9a-f-]+$', value, re.IGNORECASE):
        raise TypeError(f'Expected a hex value, not {value:s}')
    return value.replace('-', '').lower()

class Key(db.Model, ModelMixin):
    __plural__ = 'Keys'

    pk = sa.Column(sa.Integer, primary_key=True)
    hkid = sa.Column(sa.String(34), nullable=False, unique=True, index=True)
    hkey = sa.Column(sa.String(34), nullable=False)
    computed = sa.Column(sa.Boolean, nullable=False)
    halg = sa.Column(sa.String(16), nullable=True)
    mediafiles: db.Mapped[list["MediaFile"]] = db.relationship(  # noqa: F821
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
    def get_kids(clz, kids: list[KeyMaterial | str]) -> dict[str, "Key"]:
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
               exclude: AbstractSet[str] | None = None) -> JsonObject:
        js = {
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
        }, {
            "name": "computed",
            "title": "Key is auto-computed?",
            "type": "checkbox",
            "value": self.computed,
        }]
