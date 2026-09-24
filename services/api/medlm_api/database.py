from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text

from medlm_api.config import Settings
from medlm_api.errors import unavailable


class Database:
    def __init__(self, settings: Settings):
        self.engine = (
            create_engine(
                settings.database_url.get_secret_value(),
                pool_pre_ping=True,
                hide_parameters=True,
                connect_args={"connect_timeout": 5},
            )
            if settings.database_url
            else None
        )

    @contextmanager
    def transaction(self, user_id: UUID | None = None):
        if self.engine is None:
            raise unavailable("Database")
        with self.engine.begin() as connection:
            connection.execute(
                text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": str(user_id) if user_id else ""},
            )
            yield connection

    def ping(self) -> bool:
        with self.transaction() as connection:
            return connection.scalar(text("SELECT 1")) == 1

    def close(self):
        if self.engine:
            self.engine.dispose()
