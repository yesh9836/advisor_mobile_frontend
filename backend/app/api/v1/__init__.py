"""
API v1 router aggregation.
"""

from fastapi import APIRouter

from app.api.v1 import auth, licenses

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(licenses.router)

# Future routers will be included here:
# api_router.include_router(licenses.router)
# api_router.include_router(subscriptions.router)
# api_router.include_router(leads.router)
# api_router.include_router(admin.router)
# api_router.include_router(webhooks.router)