"""Run with the separate expiry-only role; never logs response contents."""

from sqlalchemy import text

from medlm_api.config import Settings
from medlm_api.database import Database


def purge(database):
    with database.transaction() as conn:
        return conn.execute(
            text("DELETE FROM medlm.idempotency_records WHERE expires_at<=now()")
        ).rowcount


if __name__ == "__main__":
    db = Database(Settings())
    try:
        print(f"Expired request records removed: {purge(db)}")
    finally:
        db.close()
