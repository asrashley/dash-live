import re
from typing import cast, Dict, List, Optional, Union

import sqlalchemy as sa

from dashlive.drm.keymaterial import KeyMaterial

from .db import db
from .mediafile_keys import mediafile_keys
from .mixin import ModelMixin

def kid_validator(prop, value):
    if not re.match(r'^[0-9a-f-]+$', value, re.IGNORECASE):
        raise TypeError('Expected a hex value, not {:s}'.format(value))
    return value.replace('-', '').lower()

class Key(db.Model, ModelMixin):
    __plural__ = 'Keys'

    pk = sa.Column(sa.Integer, primary_key=True)
    hkid = sa.Column(sa.String(34), nullable=False, unique=True, index=True)
    hkey = sa.Column(sa.String(34), nullable=False)
    computed = sa.Column(sa.Boolean, nullable=False)
    halg = sa.Column(sa.String(16), nullable=True)
    mediafiles: db.Mapped["MediaFile"] = db.relationship(  # noqa: F821
        secondary=mediafile_keys, back_populates='encryption_keys')

    @property
    def KID(self):
        return KeyMaterial(self.hkid)

    @property
    def KEY(self):
        return KeyMaterial(self.hkey)

    @property
    def ALG(self):
        if self.halg is None:
            return "AESCTR"
        return self.halg

    @classmethod
    def get_kids(clz, kids: List[Union[KeyMaterial, str]]) -> Dict[str, "Key"]:
        def to_hex(kid: Union[KeyMaterial, str]) -> str:
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
    def all(clz, order_by: Optional[tuple] = None) -> List["Key"]:
        return cast(List[Key], clz.get_all())

    @classmethod
    def get(clz, **kwargs) -> Optional["Key"]:
        return cast(clz, clz.get_one(**kwargs))

    @classmethod
    def all_as_dict(clz) -> List[Dict[str, "Key"]]:
        rv = {}
        for k in clz.all():
            rv[k.hkid.lower()] = k
        return rv

    def toJSON(self, pure=False):
        return {
            'kid': self.hkid,
            'key': self.hkey,
            'alg': self.ALG,
            'computed': self.computed,
        }
