import os
from pathlib import Path

from logging.config import fileConfig

from sqlalchemy import Engine

from alembic import context

from dashlive.server.models.db import db

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = db.Model.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    from sqlalchemy import create_engine
    from dotenv import load_dotenv
    from dashlive.server.models.connection import make_db_connection_string

    load_dotenv(os.getenv('DASHLIVE_SETTINGS', '.env'))
    instance_path = Path(os.getenv('FLASK_INSTANCE_PATH', '.'))

    connection = config.attributes.get('connection', None)
    if connection is None:
        url_template: str | None = config.get_main_option("sqlalchemy.url")
        assert url_template is not None
        url: str = make_db_connection_string(instance_path, url_template)
        engine: Engine = create_engine(url)
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
