from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import DATABASE_URL
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# configparser (which backs alembic.ini) treats "%" as its own
# interpolation syntax, so a URL-encoded password containing a literal
# "%" (e.g. from % -> %25) must be escaped as "%%" before being stored
# via set_main_option — otherwise it raises "invalid interpolation
# syntax". See Alembic's cookbook entry on this exact issue.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
