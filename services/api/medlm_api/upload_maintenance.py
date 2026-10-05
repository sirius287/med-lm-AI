"""Independent local synthetic deletion worker, sweep and object reconciliation.

Use a separate restricted medlm_upload_worker database connection, never API/owner
credentials. Each run is bounded; an external scheduler invokes each independently.
"""

from datetime import timedelta
from uuid import uuid4

from medlm_api.uploads import audit, queue_delete, sql, storage_lock, utcnow


class UploadMaintenance:
    def __init__(self, db, storage, *, clock=utcnow):
        self.db, self.storage, self.clock = db, storage, clock

    def check_role(self, conn):
        role = sql(
            conn,
            """SELECT current_user AS name,rolsuper,rolbypassrls FROM pg_roles
            WHERE rolname=current_user""",
        ).one()
        if role.name != "medlm_upload_worker" or role.rolsuper or role.rolbypassrls:
            raise ValueError("Restricted upload maintenance role required")

    def receipt(self, conn, key, user=None):
        # Must follow actual deletion AND an independent existence query.
        if self.storage.exists(key):
            raise OSError("Deletion verification failed")
        now = self.clock()
        self.storage.record_deletion(key, now, now + timedelta(days=90))
        sql(
            conn,
            """INSERT INTO medlm.upload_deletion_receipts
            (id,user_id,object_key,verified_at,expires_at)
            VALUES (:id,:uid,:key,:now,:expiry) ON CONFLICT(object_key) DO NOTHING""",
            id=uuid4(),
            uid=user,
            key=key,
            now=now,
            expiry=now + timedelta(days=90),
        )

    def purge(self, conn, obj, row):
        self.storage.delete(obj.object_key)
        self.receipt(conn, obj.object_key, row.user_id)
        if obj.purged_at is None:
            sql(
                conn,
                "UPDATE medlm.upload_objects SET purged_at=:now WHERE id=:id",
                now=self.clock(),
                id=obj.id,
            )
        audit(conn, row, "purge_verified")

    def finish(self, conn, row):
        remaining = sql(
            conn,
            """SELECT 1 FROM medlm.upload_objects
            WHERE upload_id=:id AND purged_at IS NULL LIMIT 1""",
            id=row.id,
        ).first()
        if not remaining:
            sql(
                conn,
                """UPDATE medlm.uploads SET status='deleted',purged_at=:now
                WHERE id=:id AND status='deleting'""",
                now=self.clock(),
                id=row.id,
            )

    def sweep(self, limit):
        # Independent of queue/lease state: expiry or cancellation always wins.
        with self.db.transaction() as conn:
            storage_lock(conn)
            rows = sql(
                conn,
                """SELECT * FROM medlm.uploads WHERE status <> 'deleted'
                AND (expires_at<=:now OR status IN ('deleting','rejected')
                     OR (status='initiated' AND ticket_expires_at<=:now))
                ORDER BY expires_at LIMIT :limit FOR UPDATE SKIP LOCKED""",
                now=self.clock(),
                limit=limit,
            ).all()
            for row in rows:
                queue_delete(conn, row, "expiry")
                objects = sql(
                    conn, "SELECT * FROM medlm.upload_objects WHERE upload_id=:id", id=row.id
                ).all()
                for obj in objects:
                    if obj.purged_at is None or self.storage.exists(obj.object_key):
                        self.purge(conn, obj, row)
                self.finish(conn, row)

    def worker(self, limit):
        for _ in range(limit):
            token = uuid4()
            with self.db.transaction() as conn:
                job = sql(
                    conn,
                    """SELECT * FROM medlm.upload_deletion_jobs
                    WHERE (state IN ('pending','retry') AND available_at<=:now)
                       OR (state='leased' AND lease_until<=:now)
                    ORDER BY available_at LIMIT 1 FOR UPDATE SKIP LOCKED""",
                    now=self.clock(),
                ).first()
                if job is None:
                    return
                fence = job.fencing_token + 1
                sql(
                    conn,
                    """UPDATE medlm.upload_deletion_jobs SET state='leased',
                    lease_token=:token,lease_until=:until,fencing_token=:fence,attempts=attempts+1
                    WHERE id=:id""",
                    token=token,
                    until=self.clock() + timedelta(seconds=60),
                    fence=fence,
                    id=job.id,
                )
            try:
                with self.db.transaction() as conn:
                    storage_lock(conn)
                    row = sql(
                        conn,
                        "SELECT * FROM medlm.uploads WHERE id=:id FOR UPDATE",
                        id=job.upload_id,
                    ).one()
                    leased = sql(
                        conn,
                        """SELECT * FROM medlm.upload_deletion_jobs
                        WHERE id=:id AND lease_token=:token AND fencing_token=:fence
                        AND state='leased' AND lease_until>:now FOR UPDATE""",
                        id=job.id,
                        token=token,
                        fence=fence,
                        now=self.clock(),
                    ).first()
                    if leased is None:
                        continue
                    # No storage operation is allowed just because a stale job exists.
                    if row.status not in ("deleting", "deleted"):
                        raise OSError("Upload is not cancelled")
                    obj = sql(
                        conn, "SELECT * FROM medlm.upload_objects WHERE id=:id", id=job.object_id
                    ).one()
                    self.purge(conn, obj, row)
                    sql(
                        conn,
                        """UPDATE medlm.upload_deletion_jobs SET state='completed',
                        lease_token=NULL,lease_until=NULL,completed_at=:now WHERE id=:id
                        AND lease_token=:token AND fencing_token=:fence""",
                        now=self.clock(),
                        id=job.id,
                        token=token,
                        fence=fence,
                    )
                    self.finish(conn, row)
            except OSError:
                with self.db.transaction() as conn:
                    sql(
                        conn,
                        """UPDATE medlm.upload_deletion_jobs SET state='retry',
                        available_at=:later,lease_token=NULL,lease_until=NULL,
                        last_error_code='verification_failed' WHERE id=:id
                        AND lease_token=:token AND fencing_token=:fence""",
                        later=self.clock() + timedelta(seconds=60),
                        id=job.id,
                        token=token,
                        fence=fence,
                    )
                raise

    def reconcile(self, limit):
        with self.db.transaction() as conn:
            storage_lock(conn)
            # Ledger directory is excluded from image/DB restores. Reapply before admitting work.
            for receipt in self.storage.deletion_ledger():
                if receipt["expires_at"] <= self.clock():
                    continue
                sql(
                    conn,
                    """INSERT INTO medlm.upload_deletion_receipts
                    (id,object_key,user_id,verified_at,expires_at)
                    VALUES (:id,:key,(SELECT user_id FROM medlm.upload_objects WHERE object_key=:key),
                            :verified,:expiry) ON CONFLICT(object_key) DO NOTHING""",
                    id=uuid4(),
                    key=receipt["object_key"],
                    verified=receipt["verified_at"],
                    expiry=receipt["expires_at"],
                )
            # Enumerate real storage independently, including objects restored after purge.
            keys = self.storage.keys()
            candidates = []
            for key in keys:
                obj = sql(
                    conn, "SELECT * FROM medlm.upload_objects WHERE object_key=:key", key=key
                ).first()
                receipt = sql(
                    conn,
                    "SELECT 1 FROM medlm.upload_deletion_receipts WHERE object_key=:key",
                    key=key,
                ).first()
                if obj is None or receipt or obj.purged_at:
                    candidates.append((key, obj))
                else:
                    row = sql(
                        conn,
                        "SELECT * FROM medlm.uploads WHERE id=:id FOR UPDATE",
                        id=obj.upload_id,
                    ).one()
                    if (
                        row.status in ("deleting", "deleted", "rejected")
                        or min(row.expires_at, obj.expires_at) <= self.clock()
                    ):
                        queue_delete(conn, row, "reconciliation")
                        candidates.append((key, obj))
            for key, obj in candidates[:limit]:
                self.storage.delete(key)
                self.receipt(conn, key, obj.user_id if obj else None)
                if obj and obj.purged_at is None:
                    row = sql(
                        conn,
                        "SELECT * FROM medlm.uploads WHERE id=:id FOR UPDATE",
                        id=obj.upload_id,
                    ).one()
                    # A restored receipt overrides an older DB snapshot's active lifecycle.
                    queue_delete(conn, row, "reconciliation")
                    sql(
                        conn,
                        "UPDATE medlm.upload_objects SET purged_at=:now WHERE id=:id",
                        now=self.clock(),
                        id=obj.id,
                    )
                    self.finish(conn, row)
            if len(candidates) > limit:
                return len(candidates) - limit
        return 0

    def run(self, kind, limit=100):
        if (
            kind not in ("deletion_worker", "independent_sweep", "reconciliation")
            or not 1 <= limit <= 100
        ):
            raise ValueError("Invalid maintenance bounds")
        run_id = uuid4()
        with self.db.transaction() as conn:
            self.check_role(conn)
            sql(
                conn,
                """INSERT INTO medlm.upload_safeguard_runs(id,kind,expires_at)
                VALUES (:id,:kind,now()+interval '30 days')""",
                id=run_id,
                kind=kind,
            )
        failure, backlog = False, 0
        try:
            if kind == "deletion_worker":
                self.worker(limit)
            elif kind == "independent_sweep":
                self.sweep(limit)
            else:
                backlog = self.reconcile(limit)
        except OSError:
            failure = True
        with self.db.transaction() as conn:
            storage_lock(conn)
            overdue = sql(
                conn,
                """SELECT count(*) FROM medlm.upload_objects o
                JOIN medlm.uploads u ON u.id=o.upload_id WHERE o.purged_at IS NULL
                AND (least(o.expires_at,u.expires_at)<=:now OR u.status='deleting')""",
                now=self.clock(),
            ).scalar_one()
            sql(
                conn,
                """UPDATE medlm.upload_safeguard_runs SET finished_at=clock_timestamp(),
                outcome=:outcome,overdue_objects=:overdue WHERE id=:id""",
                outcome="failed" if failure else "ok",
                overdue=overdue + backlog,
                id=run_id,
            )
            # Bounded nonclinical ledgers; unexpired receipts are never shortened/deleted.
            for table in (
                "upload_audit_events",
                "upload_deletion_receipts",
                "upload_safeguard_runs",
            ):
                sql(
                    conn,
                    f"""DELETE FROM medlm.{table} WHERE id IN
                    (SELECT id FROM medlm.{table} WHERE expires_at<clock_timestamp()
                     LIMIT :limit)""",
                    limit=limit,
                )
            sql(
                conn,
                """DELETE FROM medlm.uploads WHERE id IN
                (SELECT id FROM medlm.uploads WHERE status='deleted'
                 AND created_at < clock_timestamp()-interval '90 days'
                 LIMIT :limit FOR UPDATE SKIP LOCKED)""",
                limit=limit,
            )
            self.storage.expire_receipts(utcnow())
        return {"outcome": "failed" if failure else "ok", "overdue_objects": overdue + backlog}


def main():
    import argparse
    import json
    import os
    import time
    from pathlib import Path

    from medlm_api.config import Settings
    from medlm_api.database import Database
    from medlm_api.upload_storage import LocalSyntheticStorage

    parser = argparse.ArgumentParser(description="Synthetic-only local deletion safeguards")
    parser.add_argument("kind", choices=["deletion_worker", "independent_sweep", "reconciliation"])
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    if os.environ.get("MEDLM_ENVIRONMENT") != "test" or not 1 <= args.interval <= 300:
        parser.error("Explicit test environment and interval between 1 and 300 seconds required")
    db = Database(
        Settings(
            _env_file=None,
            environment="test",
            database_url=os.environ["MEDLM_UPLOAD_WORKER_DATABASE_URL"],
        )
    )
    storage = LocalSyntheticStorage(
        Path(os.environ["MEDLM_SYNTHETIC_STORAGE_ROOT"]),
        os.environ["MEDLM_SYNTHETIC_STORAGE_KEY"].encode(),
    )
    worker = UploadMaintenance(db, storage)
    try:
        while True:
            result = worker.run(args.kind)
            print(json.dumps({"kind": args.kind, **result}), flush=True)
            if not args.loop:
                if result["outcome"] != "ok" or result["overdue_objects"]:
                    raise SystemExit(1)
                return
            time.sleep(args.interval)
    finally:
        db.close()


if __name__ == "__main__":
    main()
