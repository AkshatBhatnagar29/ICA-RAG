from fastapi import APIRouter

from app.api.v1.router import router as v1_router
from app.core.constants import API_V1_PREFIX

router = APIRouter()
router.include_router(v1_router, prefix=API_V1_PREFIX)
