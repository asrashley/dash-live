
from typing import AbstractSet, List, Optional

from sqlalchemy.orm import class_mapper, ColumnProperty, RelationshipProperty  # type: ignore
from sqlalchemy.engine import Engine  # type: ignore
from sqlalchemy.schema import CreateColumn  # type: ignore
from sqlalchemy.orm.query import Query  # type: ignore
from sqlalchemy.orm.dynamic import AppenderQuery  # type: ignore
from sqlalchemy import func

from dashlive.utils.json_object import JsonObject

from .db import db
from .session import DatabaseSession

class ModelMixin:
    """
    Common utility functions to add to all models
    """
    
    @classmethod
    def get_all(cls, order_by: Optional[tuple] = None) -> List["ModelMixin"]:
        """
        Return all items from this table
        """
        query = db.select(cls)
        if order_by is not None:
            query = query.order_by(*order_by)
        return db.session.execute(query).scalars()

    @classmethod
    def get_one(cls, **kwargs) -> Optional["ModelMixin"]:
        """
        Get one object from a model, or None if not found
        """
        return db.session.execute(
            db.select(cls).filter_by(**kwargs)).scalar_one_or_none()
        # return session.query(cls).filter_by(**kwargs).one_or_none()

    @classmethod
    def search(clz, max_items: Optional[int] = None,
               **kwargs) -> List[db.Model]:
        query = db.select(clz)
        if kwargs:
            query = query.filter_by(**kwargs)
        if max_items is not None:
            query = query.limit(max_items)
        return list(db.session.execute(query).scalars())
    
    @classmethod
    def count(cls, **kwargs) -> int:
        query = db.select(cls)
        if kwargs:
            query = query.filter_by(**kwargs)
        query = query.with_only_columns(db.func.count(cls.pk))
        #query = db.select(db.func.count()).select_from(select)
        #query = db.session.query(func.count(cls.pk))
        #if kwargs:
        #    query = query.filter_by(**kwargs)
        return db.session.execute(query).scalar_one()
                            
    def to_dict(self, exclude: Optional[AbstractSet[str]] = None,
                only: Optional[AbstractSet[str]] = None,
                with_collections: bool = False) -> JsonObject:
        """
        Convert this model into a dictionary
        :exclude: set of attributes to exclude
        :only: set of attributes to include
        """
        retval = {}
        for prop in class_mapper(self.__class__).iterate_properties:
            if only is not None and prop.key not in only:
                continue
            if exclude is not None and prop.key in exclude:
                continue
            if isinstance(prop, ColumnProperty):
                retval[prop.key] = getattr(self, prop.key)
            elif isinstance(prop, RelationshipProperty) and with_collections:
                value = getattr(self, prop.key)
                if value is not None:
                    if isinstance(value, (AppenderQuery, list)):
                        value = [v.pk for v in value]
                    elif isinstance(value, Base):
                        value = value.pk
                retval[prop.key] = value
        # If the collection has been included in the output, remove the
        # "xxx_pk" version of the column.
        # If the collection has not been included, rename the "xxx_pk"
        # version of the column to "xxx".
        for prop in class_mapper(self.__class__).iterate_properties:
            if not isinstance(prop, RelationshipProperty):
                continue
            pk_name = f'{prop.key}_pk'
            if prop.key in retval and pk_name in retval:
                del retval[pk_name]
            elif pk_name in retval and prop.key not in retval:
                if exclude is None or prop.key not in exclude:
                    retval[prop.key] = retval[pk_name]
                del retval[pk_name]
        return retval
                        

    def add(self, commit: bool = False) -> None:
        db.session.add(self)
        if commit:
            db.session.commit()
