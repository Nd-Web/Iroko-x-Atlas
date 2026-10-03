"""Cap document request bodies before FastAPI buffers multipart uploads."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class DocumentBodyLimit:
    def __init__(self, app, max_bytes=51 * 1024 * 1024):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path", "").rstrip("/") not in {"/api/documents", "/api/documents/upload"}
        ):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = -1
        if length < 0 or length > self.max_bytes:
            return await JSONResponse(
                {"detail": "Document request exceeds upload limit"}, status_code=413
            )(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(413, "Document request exceeds upload limit")
            return message

        await self.app(scope, bounded_receive, send)
