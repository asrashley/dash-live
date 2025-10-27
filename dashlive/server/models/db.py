from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

from .base import Base
from .timezone_date_time import TimezoneForcingDateTime

db = SQLAlchemy(model_class=Base)
db.Model.registry.update_type_annotation_map({
    datetime: TimezoneForcingDateTime
})
