import logging
import traceback
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling middleware"""

    @staticmethod
    async def handle(request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except Exception as e:
            return await ErrorHandler._handle_error(request, e)

    @staticmethod
    async def _handle_error(request: Request, exc: Exception) -> JSONResponse:
        """Handle uncaught exceptions"""
        path = request.url.path
        method = request.method
        
        # Log full traceback for debugging
        logger.error(
            f"Unhandled error: {exc}\n"
            f"Path: {path} {method}\n"
            f"Traceback: {traceback.format_exc()}"
        )

        # Don't expose internal errors in production
        from app.core.config import config
        if config.DEBUG:
            detail = str(exc)
        else:
            detail = "Internal server error"

        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": detail,
                "path": path,
            }
        )


class RequestValidator:
    """Validate and sanitize incoming requests"""

    @staticmethod
    async def validate(request: Request, call_next):
        """Validate request before processing"""
        
        # Check Content-Type for POST/PUT/PATCH
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if content_type and "application/json" not in content_type:
                # Allow multipart/form-data for file uploads
                if "multipart/form-data" not in content_type:
                    pass  # Could reject here but let FastAPI handle it

        # Sanitize query parameters
        for key, value in request.query_params.items():
            if value and len(value) > 10000:
                logger.warning(f" oversized parameter: {key} ({len(value)} chars)")

        return await call_next(request)


class SecurityHeaders:
    """Add security headers to all responses"""

    @staticmethod
    async def add(request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Remove server identification
        response.headers["Server"] = "Beacon"
        
        return response