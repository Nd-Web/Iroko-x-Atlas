"""
core/exceptions.py — Custom HTTP exceptions for Iroko AI.

Provides semantically named exception classes that subclass FastAPI's
HTTPException.  Each carries the correct status code and a sensible
default detail message so callers can simply ``raise NotFoundException()``
without repeating boilerplate.

Usage::

    from core.exceptions import NotFoundException, ForbiddenException

    raise NotFoundException("Document not found")
    raise ForbiddenException()  # uses default message
"""

from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    """404 — Resource not found."""

    def __init__(self, detail: str = "The requested resource was not found."):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedException(HTTPException):
    """401 — Authentication required or invalid credentials."""

    def __init__(self, detail: str = "Authentication required."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(HTTPException):
    """403 — Authenticated but insufficient permissions."""

    def __init__(self, detail: str = "You do not have permission to perform this action."):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BadRequestException(HTTPException):
    """400 — Malformed or invalid request."""

    def __init__(self, detail: str = "Bad request."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ConflictException(HTTPException):
    """409 — Resource conflict (e.g. duplicate email, already exists)."""

    def __init__(self, detail: str = "Resource conflict — this item already exists."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnprocessableEntityException(HTTPException):
    """422 — Request is syntactically valid but semantically incorrect."""

    def __init__(self, detail: str = "Unprocessable entity — validation failed."):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )


class ServiceUnavailableException(HTTPException):
    """503 — An upstream service is temporarily unavailable."""

    def __init__(self, detail: str = "Service temporarily unavailable. Please try again later."):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail
        )


class AzureServiceException(HTTPException):
    """503 — Azure OpenAI, Azure AI Search, or another Azure service failed.

    Use this when an Azure SDK call raises an unexpected error that the
    caller cannot recover from.  Provides a user-friendly message while
    logging the real cause upstream.
    """

    def __init__(
        self,
        detail: str = "An Azure AI service is currently unavailable. Please try again shortly.",
        service: str = "Azure",
    ):
        # Prefix with the service name if the caller provides one
        final_detail = f"{service}: {detail}" if service != "Azure" else detail
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=final_detail,
        )
