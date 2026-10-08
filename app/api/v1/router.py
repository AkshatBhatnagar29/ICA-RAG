from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.agent import router as agent_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.contracts import router as contracts_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.search import router as search_router
from app.api.v1.endpoints.ui import router as ui_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(documents_router)
router.include_router(search_router)
router.include_router(chat_router)
router.include_router(agent_router)
router.include_router(contracts_router)
router.include_router(ui_router)
