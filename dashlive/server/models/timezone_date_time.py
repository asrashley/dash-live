
from datetime import datetime, timezone
from typing import Any

import sqlalchemy.types as types
from sqlalchemy import DateTime, Dialect

# @see https://github.com/sqlalchemy/sqlalchemy/issues/1985
# @see https://docs.sqlalchemy.org/en/20/core/custom_types.html#typedecorator-recipes

class TimezoneForcingDateTime(types.TypeDecorator):

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime:
        if value is not None and value.tzinfo:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime:
        if value is not None:
            return value.replace(tzinfo=timezone.utc)

        return value
