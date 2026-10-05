import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from medlm_api.auth_dependencies import current_identity
from medlm_api.errors import AppError
from medlm_api.uploads import (
    CompletionRequest,
    ReceiptList,
    SyntheticUploadRequest,
    UploadIntent,
    UploadState,
)

TRANSFER_SECONDS = 30


def upload_router(service):
    router = APIRouter(prefix="/uploads", tags=["synthetic-uploads"])
    # Local harness memory bound: four <=10MiB input buffers; no disk spool.
    slots = asyncio.Semaphore(4)

    @router.post("", response_model=UploadIntent, status_code=201)
    def create(
        body: SyntheticUploadRequest,
        request: Request,
        idempotency_key: UUID = Header(),
        identity=Depends(current_identity),
    ):
        return service.create(request.app.state.database, identity.principal, body, idempotency_key)

    @router.get("/{upload_id}", response_model=UploadState)
    def get(
        upload_id: UUID, request: Request, response: Response, identity=Depends(current_identity)
    ):
        result = service.get(request.app.state.database, identity.principal, upload_id)
        response.headers["ETag"] = f'"{result.version}"'
        return result

    @router.put(
        "/{upload_id}/content",
        status_code=204,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    mime: {"schema": {"type": "string", "format": "binary"}}
                    for mime in ("image/png", "image/jpeg", "image/webp")
                },
            }
        },
    )
    async def content(
        upload_id: UUID,
        request: Request,
        x_upload_ticket: str = Header(max_length=128),
        identity=Depends(current_identity),
    ):
        db, principal = request.app.state.database, identity.principal
        reserved = False
        try:
            async with asyncio.timeout(TRANSFER_SECONDS):
                async with slots:
                    size = await run_in_threadpool(
                        service.reserve,
                        db,
                        principal,
                        upload_id,
                        x_upload_ticket,
                        request.headers.get("content-type"),
                    )
                    reserved = True
                    data = bytearray()
                    async for chunk in request.stream():
                        if len(data) + len(chunk) > min(
                            size, request.app.state.settings.max_image_bytes
                        ):
                            raise AppError(413, "image_size", "Image exceeds the permitted size.")
                        data.extend(chunk)
                    # Revalidate cookie absolute expiry/provider identity after receiving bytes.
                    fresh = await run_in_threadpool(current_identity, request)
                    await run_in_threadpool(
                        service.write,
                        db,
                        fresh.principal,
                        upload_id,
                        bytes(data),
                        request.app.state.settings,
                    )
        except (TimeoutError, ClientDisconnect) as exc:
            if reserved:
                await run_in_threadpool(service.reject, db, principal, upload_id)
            raise AppError(408, "upload_interrupted", "Upload did not finish in time.") from exc
        except Exception:
            if reserved:
                await run_in_threadpool(service.reject, db, principal, upload_id)
            raise

    @router.post("/{upload_id}/complete", response_model=UploadState)
    def complete(
        upload_id: UUID,
        body: CompletionRequest,
        request: Request,
        idempotency_key: UUID = Header(),
        if_match: str | None = Header(default=None),
        identity=Depends(current_identity),
    ):
        # Completion is inherently idempotent by immutable upload/source checksum.
        return service.complete(
            request.app.state.database, identity.principal, upload_id, body, if_match
        )

    @router.delete(
        "/{upload_id}",
        response_model=UploadState,
        status_code=202,
        responses={204: {"description": "Already deleted"}},
    )
    def delete(
        upload_id: UUID,
        request: Request,
        if_match: str | None = Header(default=None),
        identity=Depends(current_identity),
    ):
        result = service.delete(request.app.state.database, identity.principal, upload_id, if_match)
        return Response(status_code=204) if result.status == "deleted" else result

    @router.get(
        "/{upload_id}/preview",
        response_class=Response,
        responses={200: {"content": {"image/png": {}}}},
    )
    def preview(upload_id: UUID, request: Request, identity=Depends(current_identity)):
        return Response(
            service.preview(request.app.state.database, identity.principal, upload_id),
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/{upload_id}/receipts", response_model=ReceiptList)
    def receipts(upload_id: UUID, request: Request, identity=Depends(current_identity)):
        return service.receipts(request.app.state.database, identity.principal, upload_id)

    return router
