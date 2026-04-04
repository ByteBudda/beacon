import uuid
import time
import json
import logging

from fastapi import Request

from app.core.config import config

logger = logging.getLogger(__name__)


class RequestLogger:
    """Structured request logging with request ID"""

    @staticmethod
    async def log(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Log incoming request
        logger.info(
            f"[{request_id}] {method} {path}",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "client_ip": request.client.host if request.client else "unknown",
            }
        )

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            status = response.status_code
            
            # Log response
            log_level = "info" if status < 400 else "warning"
            logger.log(
                log_level,
                f"[{request_id}] {method} {path} {status} {duration_ms:.0f}ms",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status,
                    "duration_ms": round(duration_ms),
                }
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{request_id}] {method} {path} ERROR: {e}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "error": str(e),
                    "duration_ms": round(duration_ms),
                },
                exc_info=True
            )
            raise


class MetricsCollector:
    """Collect basic metrics for monitoring"""

    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.start_time = time.time()

    def record_request(self, status_code: int):
        self.requests += 1
        if status_code >= 500:
            self.errors += 1

    def get_stats(self) -> dict:
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": round(uptime),
            "total_requests": self.requests,
            "total_errors": self.errors,
            "error_rate": round(self.errors / max(self.requests, 1) * 100, 2),
        }


metrics = MetricsCollector()


async def log_request(request: Request, call_next):
    """Middleware to log all requests"""
    return await RequestLogger.log(request, call_next)