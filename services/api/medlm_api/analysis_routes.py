"""Mounted only by explicit synthetic test-harness injection."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from medlm_api.analysis_lifecycle_contracts import (
    AnalysisVersion,
    AnalysisView,
    CreateAnalysis,
    LeaseRequest,
    LeaseView,
    TransitionRequest,
)
from medlm_api.auth_dependencies import current_identity


def analysis_router(service):
    router = APIRouter(prefix="/analyses", tags=["synthetic-analysis-lifecycle"])

    @router.post("", response_model=AnalysisView, status_code=201)
    def create(
        body: CreateAnalysis,
        request: Request,
        idempotency_key: str | None = Header(None),
        identity=Depends(current_identity),
    ):
        return service.create(request.app.state.database, identity.principal, body, idempotency_key)

    @router.get("/{analysis_id}", response_model=AnalysisView)
    def status(analysis_id: UUID, request: Request, identity=Depends(current_identity)):
        return service.refresh(request.app.state.database, identity.principal, analysis_id)

    @router.post("/{analysis_id}/jobs", response_model=AnalysisView, status_code=201)
    def retry(
        analysis_id: UUID,
        body: AnalysisVersion,
        request: Request,
        idempotency_key: str | None = Header(None),
        identity=Depends(current_identity),
    ):
        return service.mutate(
            request.app.state.database,
            identity.principal,
            analysis_id,
            "retry",
            idempotency_key,
            body,
        )

    @router.post("/{analysis_id}/cancel", response_model=AnalysisView)
    def cancel(
        analysis_id: UUID,
        body: AnalysisVersion,
        request: Request,
        idempotency_key: str | None = Header(None),
        identity=Depends(current_identity),
    ):
        return service.mutate(
            request.app.state.database,
            identity.principal,
            analysis_id,
            "cancel",
            idempotency_key,
            body,
        )

    @router.post("/{analysis_id}/jobs/{job_id}/lease", response_model=LeaseView)
    def lease(
        analysis_id: UUID,
        job_id: UUID,
        body: LeaseRequest,
        request: Request,
        idempotency_key: str | None = Header(None),
        identity=Depends(current_identity),
    ):
        return service.mutate(
            request.app.state.database,
            identity.principal,
            analysis_id,
            "lease",
            idempotency_key,
            body,
            job_id,
        )

    @router.post("/{analysis_id}/jobs/{job_id}/transitions", response_model=AnalysisView)
    def advance(
        analysis_id: UUID,
        job_id: UUID,
        body: TransitionRequest,
        request: Request,
        idempotency_key: str | None = Header(None),
        identity=Depends(current_identity),
    ):
        return service.mutate(
            request.app.state.database,
            identity.principal,
            analysis_id,
            "transition",
            idempotency_key,
            body,
            job_id,
        )

    return router
