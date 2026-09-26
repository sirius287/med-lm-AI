"""Bounded local maintenance. Never deletes provider-session revocation tombstones."""

import argparse
import json

from sqlalchemy import text

from medlm_api.config import Settings
from medlm_api.database import Database


def cleanup(database: Database, batch_size: int = 500) -> dict[str, int]:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    result = {}
    with database.transaction() as conn:
        for table, key, predicate in (
            ("web_sessions", "id_hash", "expires_at <= now()"),
            ("auth_throttles", "key_hash", "window_end <= now()"),
        ):
            result[table] = conn.execute(
                text(f"""WITH expired AS (
                SELECT {key} FROM medlm_auth.{table} WHERE {predicate}
                ORDER BY {key} LIMIT :limit FOR UPDATE SKIP LOCKED)
                DELETE FROM medlm_auth.{table} t USING expired e WHERE t.{key}=e.{key}"""),
                {"limit": batch_size},
            ).rowcount
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    db = Database(Settings())
    try:
        print(json.dumps(cleanup(db, args.batch_size)))
    finally:
        db.close()


if __name__ == "__main__":
    main()
