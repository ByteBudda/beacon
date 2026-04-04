import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, create_engine

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your models' Base for autogenerate
from app.core.database import SQLITE_SCHEMA, PG_SCHEMA

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Determine if we're using PostgreSQL
is_postgres = config.get_main_option("sqlalchemy.url", "").startswith("postgresql")

# Set target metadata for autogenerate
target_metadata = None  # Will be set by migrations


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = config.attributes.get("connection", None)
    
    if connectable is None:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# Get the right schema based on database type
def get_schema():
    return PG_SCHEMA if is_postgres else SQLITE_SCHEMA


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()