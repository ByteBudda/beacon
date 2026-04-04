import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# This file is kept for potential future use.
# Ad settings are managed via /api/admin/settings/ads
