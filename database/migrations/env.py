from alembic import context
from medlm_api.config import Settings
from sqlalchemy import create_engine, pool

settings = Settings()
if not settings.database_url:
    raise RuntimeError("MEDLM_DATABASE_URL is required for migrations")
url = settings.database_url.get_secret_value()

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
