from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AsyncJob,
    AuditLog,
    CallbackEvent,
    EncryptedCredential,
    LlmExecution,
    NodeExecution,
    NormalizedEntity,
    OnboardingSession,
    OutboxMessage,
    ReportRun,
    ReportVersion,
    SideEffectOperation,
    SourceDataBatch,
    ToolExecution,
)

SessionFactory = Callable[[], Session]

DEFAULT_RUN_LEASE_SECONDS = 60
DEFAULT_OPERATION_LEASE_SECONDS = 300

RUN_TERMINAL_STATUSES = {"completed", "cancelled", "blocked", "rejected", "partial_failed"}
WAITING_RUN_STATUSES = {"waiting"}
ACTIVE_OPERATION_STATUSES = {"pending", "claimed", "running", "retry_pending", "unknown"}
TERMINAL_OPERATION_STATUSES = {"succeeded", "failed", "cancelled"}
TERMINAL_ONBOARDING_STATUSES = {"completed", "cancelled", "expired"}


class RunLeaseConflictError(ValueError):
    pass


@dataclass(slots=True)
class DataLifecycleResult:
    dry_run: bool
    skipped_run_ids: list[str] = field(default_factory=list)
    pruned_payload_counts: dict[str, int] = field(default_factory=dict)
    deleted_row_counts: dict[str, int] = field(default_factory=dict)
    audited: bool = False


class RunLeaseService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        lease_seconds: int = DEFAULT_RUN_LEASE_SECONDS,
        operation_lease_seconds: int = DEFAULT_OPERATION_LEASE_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._lease_seconds = lease_seconds
        self._operation_lease_seconds = operation_lease_seconds

    def acquire_run_lease(
        self,
        run_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> ReportRun:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            if run.lease_owner and run.lease_owner != worker_id:
                if run.lease_expires_at is None or _as_utc(run.lease_expires_at) > current_time:
                    raise RunLeaseConflictError(f"run lease is held by {run.lease_owner}")
            self._refresh_run_lease(run, worker_id=worker_id, now=current_time)
            session.commit()
            session.refresh(run)
            run.lease_expires_at = current_time + timedelta(seconds=self._lease_seconds)
            run.heartbeat_at = current_time
            return run

    def heartbeat_run_lease(
        self,
        run_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> ReportRun:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            if run.lease_owner != worker_id:
                raise RunLeaseConflictError("run lease is held by another worker")
            self._refresh_run_lease(run, worker_id=worker_id, now=current_time)
            session.commit()
            session.refresh(run)
            run.lease_expires_at = current_time + timedelta(seconds=self._lease_seconds)
            run.heartbeat_at = current_time
            return run

    def release_run_lease(
        self,
        run_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> ReportRun:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            if run.lease_owner not in {None, worker_id}:
                raise RunLeaseConflictError("run lease is held by another worker")
            run.lease_owner = None
            run.lease_expires_at = None
            run.heartbeat_at = current_time
            session.commit()
            session.refresh(run)
            run.heartbeat_at = current_time
            return run

    def recover_expired_run_ids(self, *, now: datetime | None = None) -> list[str]:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            runs = session.scalars(
                select(ReportRun)
                .where(
                    ~ReportRun.status.in_(RUN_TERMINAL_STATUSES | WAITING_RUN_STATUSES),
                    ReportRun.lease_expires_at.is_not(None),
                    ReportRun.lease_expires_at <= current_time,
                )
                .order_by(ReportRun.created_at, ReportRun.id)
            ).all()
            return [run.id for run in runs]

    def acquire_operation_lease(
        self,
        operation_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> SideEffectOperation:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            operation = self._load_operation(session, operation_id)
            self._assert_operation_lease_can_move(operation, worker_id=worker_id, now=current_time)
            self._refresh_operation_lease(operation, worker_id=worker_id, now=current_time)
            session.commit()
            session.refresh(operation)
            operation.lease_expires_at = current_time + timedelta(
                seconds=self._operation_lease_seconds
            )
            operation.heartbeat_at = current_time
            return operation

    def heartbeat_operation_lease(
        self,
        operation_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> SideEffectOperation:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            operation = self._load_operation(session, operation_id)
            if operation.lease_owner != worker_id:
                raise RunLeaseConflictError("operation lease is held by another worker")
            self._refresh_operation_lease(operation, worker_id=worker_id, now=current_time)
            session.commit()
            session.refresh(operation)
            operation.lease_expires_at = current_time + timedelta(
                seconds=self._operation_lease_seconds
            )
            operation.heartbeat_at = current_time
            return operation

    def release_operation_lease(
        self,
        operation_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> SideEffectOperation:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            operation = self._load_operation(session, operation_id)
            if operation.lease_owner not in {None, worker_id}:
                raise RunLeaseConflictError("operation lease is held by another worker")
            operation.lease_owner = None
            operation.lease_expires_at = None
            operation.heartbeat_at = current_time
            session.commit()
            session.refresh(operation)
            operation.heartbeat_at = current_time
            return operation

    def recover_expired_operation_ids(self, *, now: datetime | None = None) -> list[str]:
        current_time = _as_utc(now or datetime.now(UTC))
        with self._session_factory() as session:
            operations = session.scalars(
                select(SideEffectOperation)
                .where(
                    SideEffectOperation.status.in_(ACTIVE_OPERATION_STATUSES),
                    SideEffectOperation.lease_expires_at.is_not(None),
                    SideEffectOperation.lease_expires_at <= current_time,
                )
                .order_by(SideEffectOperation.started_at, SideEffectOperation.id)
            ).all()
            return [operation.id for operation in operations]

    def _load_run(self, session: Session, run_id: str) -> ReportRun:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise ValueError(f"unknown run_id: {run_id}")
        return run

    def _load_operation(self, session: Session, operation_id: str) -> SideEffectOperation:
        operation = session.get(SideEffectOperation, operation_id)
        if operation is None:
            raise ValueError(f"unknown operation_id: {operation_id}")
        return operation

    def _refresh_run_lease(self, run: ReportRun, *, worker_id: str, now: datetime) -> None:
        run.lease_owner = worker_id
        run.lease_expires_at = now + timedelta(seconds=self._lease_seconds)
        run.heartbeat_at = now
        run.version = (run.version or 0) + 1

    def _refresh_operation_lease(
        self, operation: SideEffectOperation, *, worker_id: str, now: datetime
    ) -> None:
        operation.lease_owner = worker_id
        operation.lease_expires_at = now + timedelta(seconds=self._operation_lease_seconds)
        operation.heartbeat_at = now
        operation.version = (operation.version or 0) + 1

    def _assert_operation_lease_can_move(
        self, operation: SideEffectOperation, *, worker_id: str, now: datetime
    ) -> None:
        if operation.status in TERMINAL_OPERATION_STATUSES:
            raise RunLeaseConflictError("operation is terminal")
        if operation.lease_owner and operation.lease_owner != worker_id:
            if operation.lease_expires_at is None or _as_utc(operation.lease_expires_at) > now:
                raise RunLeaseConflictError(f"operation lease is held by {operation.lease_owner}")


class DataLifecycleService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def cleanup(self, *, now: datetime | None = None, dry_run: bool = False) -> DataLifecycleResult:
        current_time = _as_utc(now or datetime.now(UTC))
        result = DataLifecycleResult(
            dry_run=dry_run,
            pruned_payload_counts=_zero_counts(
                "source_data_batches",
                "normalized_entities",
            ),
            deleted_row_counts=_zero_counts(
                "node_executions",
                "tool_executions",
                "llm_executions",
                "outbox_messages",
                "callback_events",
                "onboarding_sessions",
                "encrypted_credentials",
                "async_jobs",
                "report_versions",
                "report_claims",
                "report_evidence",
                "evidence_sets",
                "evidence_items",
                "audit_logs",
            ),
        )
        with self._session_factory() as session:
            eligible_run_ids, skipped_run_ids = self._eligible_cleanup_runs(session, current_time)
            result.skipped_run_ids = skipped_run_ids

            source_cutoff = current_time - timedelta(days=30)
            normalized_cutoff = current_time - timedelta(days=90)
            node_cutoff = current_time - timedelta(days=180)
            report_cutoff = current_time - timedelta(days=730)

            result.pruned_payload_counts["source_data_batches"] = self._prune_source_batches(
                session,
                eligible_run_ids=eligible_run_ids,
                cutoff=source_cutoff,
                dry_run=dry_run,
            )
            result.pruned_payload_counts["normalized_entities"] = self._prune_normalized_entities(
                session,
                eligible_run_ids=eligible_run_ids,
                cutoff=normalized_cutoff,
                dry_run=dry_run,
            )

            result.deleted_row_counts["node_executions"] = self._delete_rows(
                session,
                NodeExecution,
                NodeExecution.run_id.in_(eligible_run_ids),
                NodeExecution.started_at <= node_cutoff,
                dry_run=dry_run,
            )
            result.deleted_row_counts["tool_executions"] = self._delete_rows(
                session,
                ToolExecution,
                ToolExecution.run_id.in_(eligible_run_ids),
                ToolExecution.started_at <= node_cutoff,
                dry_run=dry_run,
            )
            result.deleted_row_counts["llm_executions"] = self._delete_rows(
                session,
                LlmExecution,
                LlmExecution.run_id.in_(eligible_run_ids),
                LlmExecution.created_at <= node_cutoff,
                dry_run=dry_run,
            )
            result.deleted_row_counts["outbox_messages"] = self._delete_outbox_messages(
                session,
                eligible_run_ids=eligible_run_ids,
                current_time=current_time,
                dry_run=dry_run,
            )
            result.deleted_row_counts["callback_events"] = self._delete_callback_events(
                session,
                eligible_run_ids=eligible_run_ids,
                current_time=current_time,
                dry_run=dry_run,
            )
            result.deleted_row_counts["async_jobs"] = self._delete_async_jobs(
                session,
                current_time=current_time,
                dry_run=dry_run,
            )
            result.deleted_row_counts["report_versions"] = self._delete_rows(
                session,
                ReportVersion,
                ReportVersion.run_id.in_(eligible_run_ids),
                ReportVersion.created_at <= report_cutoff,
                dry_run=dry_run,
            )
            onboarding_deleted, onboarding_credential_deleted = self._cleanup_onboarding_sessions(
                session,
                current_time=current_time,
                dry_run=dry_run,
            )
            result.deleted_row_counts["onboarding_sessions"] = onboarding_deleted
            result.deleted_row_counts["encrypted_credentials"] = (
                onboarding_credential_deleted
                + self._cleanup_expired_credentials(
                    session, current_time=current_time, dry_run=dry_run
                )
            )

            if not dry_run:
                self._write_audit_log(session, current_time=current_time, result=result)
                session.commit()
                result.audited = True
            return result

    def _eligible_cleanup_runs(
        self, session: Session, current_time: datetime
    ) -> tuple[list[str], list[str]]:
        runs = session.scalars(select(ReportRun).order_by(ReportRun.created_at, ReportRun.id)).all()
        eligible_run_ids: list[str] = []
        skipped_run_ids: list[str] = []
        for run in runs:
            if run.status not in RUN_TERMINAL_STATUSES:
                skipped_run_ids.append(run.id)
                continue
            if self._has_unresolved_operation(session, run.id, current_time):
                skipped_run_ids.append(run.id)
                continue
            eligible_run_ids.append(run.id)
        return eligible_run_ids, skipped_run_ids

    def _has_unresolved_operation(
        self, session: Session, run_id: str, current_time: datetime
    ) -> bool:
        operations = session.scalars(
            select(SideEffectOperation)
            .where(
                SideEffectOperation.run_id == run_id,
                SideEffectOperation.status.in_(("running", "unknown")),
            )
            .order_by(SideEffectOperation.sequence)
        ).all()
        for operation in operations:
            if operation.status == "running":
                if operation.lease_expires_at is None:
                    return True
                if _as_utc(operation.lease_expires_at) > current_time:
                    return True
            if operation.status == "unknown" and operation.verification_status != "confirmed":
                return True
        return False

    def _prune_source_batches(
        self,
        session: Session,
        *,
        eligible_run_ids: Iterable[str],
        cutoff: datetime,
        dry_run: bool,
    ) -> int:
        rows = session.scalars(
            select(SourceDataBatch)
            .where(
                SourceDataBatch.run_id.in_(list(eligible_run_ids)),
                SourceDataBatch.fetched_at <= cutoff,
            )
            .order_by(SourceDataBatch.fetched_at, SourceDataBatch.id)
        ).all()
        if not dry_run:
            for row in rows:
                row.payload = {}
        return len(rows)

    def _prune_normalized_entities(
        self,
        session: Session,
        *,
        eligible_run_ids: Iterable[str],
        cutoff: datetime,
        dry_run: bool,
    ) -> int:
        rows = session.scalars(
            select(NormalizedEntity)
            .where(
                NormalizedEntity.run_id.in_(list(eligible_run_ids)),
                NormalizedEntity.fetched_at <= cutoff,
            )
            .order_by(NormalizedEntity.fetched_at, NormalizedEntity.id)
        ).all()
        if not dry_run:
            for row in rows:
                row.attributes = {}
                row.raw_summary = None
        return len(rows)

    def _delete_outbox_messages(
        self,
        session: Session,
        *,
        eligible_run_ids: Iterable[str],
        current_time: datetime,
        dry_run: bool,
    ) -> int:
        rows = session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.aggregate_id.in_(list(eligible_run_ids)))
            .order_by(OutboxMessage.created_at, OutboxMessage.id)
        ).all()
        success_cutoff = current_time - timedelta(days=30)
        failure_cutoff = current_time - timedelta(days=90)
        deletions = [
            row
            for row in rows
            if (
                row.status == "published"
                and row.published_at is not None
                and _as_utc(row.published_at) <= success_cutoff
            )
            or (
                row.status in {"failed", "dead_lettered"}
                and (
                    (
                        row.dead_lettered_at is not None
                        and _as_utc(row.dead_lettered_at) <= failure_cutoff
                    )
                    or _as_utc(row.created_at) <= failure_cutoff
                )
            )
        ]
        if not dry_run and deletions:
            session.execute(
                delete(OutboxMessage).where(OutboxMessage.id.in_([row.id for row in deletions]))
            )
        return len(deletions)

    def _delete_callback_events(
        self,
        session: Session,
        *,
        eligible_run_ids: Iterable[str],
        current_time: datetime,
        dry_run: bool,
    ) -> int:
        rows = session.scalars(
            select(CallbackEvent)
            .where(CallbackEvent.run_id.in_(list(eligible_run_ids)))
            .order_by(CallbackEvent.received_at, CallbackEvent.id)
        ).all()
        cutoff = current_time - timedelta(days=90)
        deletions = [
            row
            for row in rows
            if row.status in {"processed", "failed", "duplicate", "rejected"}
            and _as_utc(row.received_at) <= cutoff
        ]
        if not dry_run and deletions:
            session.execute(
                delete(CallbackEvent).where(CallbackEvent.id.in_([row.id for row in deletions]))
            )
        return len(deletions)

    def _delete_async_jobs(
        self,
        session: Session,
        *,
        current_time: datetime,
        dry_run: bool,
    ) -> int:
        rows = session.scalars(
            select(AsyncJob)
            .where(
                AsyncJob.status.in_(("succeeded", "cancelled")),
                AsyncJob.completed_at.is_not(None),
                AsyncJob.completed_at <= current_time - timedelta(days=30),
            )
            .order_by(AsyncJob.completed_at, AsyncJob.id)
        ).all()
        failed_rows = session.scalars(
            select(AsyncJob)
            .where(
                AsyncJob.status == "failed",
                AsyncJob.completed_at.is_not(None),
                AsyncJob.completed_at <= current_time - timedelta(days=90),
            )
            .order_by(AsyncJob.completed_at, AsyncJob.id)
        ).all()
        rows.extend(failed_rows)
        if not dry_run and rows:
            session.execute(delete(AsyncJob).where(AsyncJob.id.in_([row.id for row in rows])))
        return len(rows)

    def _cleanup_onboarding_sessions(
        self,
        session: Session,
        *,
        current_time: datetime,
        dry_run: bool,
    ) -> tuple[int, int]:
        rows = session.scalars(
            select(OnboardingSession)
            .where(
                OnboardingSession.status.in_(TERMINAL_ONBOARDING_STATUSES),
                OnboardingSession.created_at <= current_time - timedelta(days=90),
            )
            .order_by(OnboardingSession.created_at, OnboardingSession.id)
        ).all()
        if dry_run:
            credential_deletes = sum(
                1 for row in rows if row.status in {"cancelled", "expired"} and row.credential_ref
            )
            return len(rows), credential_deletes

        deleted = 0
        credential_deleted = 0
        for row in rows:
            if row.status in {"cancelled", "expired"} and row.credential_ref:
                credential = session.get(EncryptedCredential, row.credential_ref)
                if credential is not None:
                    session.delete(credential)
                    credential_deleted += 1
            session.delete(row)
            deleted += 1
        return deleted, credential_deleted

    def _cleanup_expired_credentials(
        self,
        session: Session,
        *,
        current_time: datetime,
        dry_run: bool,
    ) -> int:
        rows = session.scalars(
            select(EncryptedCredential)
            .where(
                EncryptedCredential.status.in_(("revoked", "invalid", "expired")),
            )
            .order_by(EncryptedCredential.updated_at, EncryptedCredential.id)
        ).all()
        rows = [
            row
            for row in rows
            if _as_utc(row.updated_at) <= current_time - timedelta(days=90)
            or (row.expires_at is not None and _as_utc(row.expires_at) <= current_time)
        ]
        if not dry_run and rows:
            for row in rows:
                session.delete(row)
        return len(rows)

    def _write_audit_log(
        self,
        session: Session,
        *,
        current_time: datetime,
        result: DataLifecycleResult,
    ) -> None:
        session.add(
            AuditLog(
                occurred_at=current_time,
                request_id=None,
                run_id=None,
                actor_type="system",
                actor_id="data-lifecycle",
                action="data_lifecycle_cleanup",
                resource_type="retention",
                resource_id="cleanup",
                before_summary={},
                after_summary={},
                result="success",
                ip_hash=None,
                metadata_={
                    "dry_run": result.dry_run,
                    "skipped_run_ids": list(result.skipped_run_ids),
                    "pruned_payload_counts": dict(result.pruned_payload_counts),
                    "deleted_row_counts": dict(result.deleted_row_counts),
                },
            )
        )

    def _delete_rows(
        self,
        session: Session,
        model: type,
        *conditions,
        dry_run: bool,
    ) -> int:
        rows = session.scalars(select(model).where(*conditions)).all()
        if not dry_run and rows:
            session.execute(delete(model).where(model.id.in_([row.id for row in rows])))
        return len(rows)


def _zero_counts(*keys: str) -> dict[str, int]:
    return {key: 0 for key in keys}


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
