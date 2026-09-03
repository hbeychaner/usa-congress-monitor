from fastapi import APIRouter

from cdm.backend.api.routes import bills
from cdm.backend.api.routes.admin import router as admin_router
from cdm.backend.api.routes.members import router as members_router
from cdm.backend.api.routes.search import router as search_router
from cdm.backend.api.routes.states import router as states_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(admin_router)
api_router.include_router(states_router)
api_router.include_router(members_router)
api_router.include_router(search_router)
api_router.include_router(bills.router)
