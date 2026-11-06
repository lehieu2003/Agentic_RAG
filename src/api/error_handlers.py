"""Map domain exceptions onto the HTTP ``{"detail": ...}`` contract.

Registering the handler here keeps ``HTTPException`` raising out of the
application layer: services raise ``DomainError`` subclasses and this is
the single place that decides the HTTP shape.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain.exceptions import DomainError


def register_error_handlers(app: FastAPI) -> None:
    """Attach the domain-to-HTTP exception mapping to the application."""

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
