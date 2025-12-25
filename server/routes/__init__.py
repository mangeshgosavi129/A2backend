from fastapi import APIRouter
from . import auth, tasks, clients, messages, users, prometheus, organisations, internals

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
router.include_router(clients.router, prefix="/clients", tags=["Clients"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(messages.router, prefix="/messages", tags=["Messages"])
router.include_router(prometheus.router, prefix="/metrics", tags=["Metrics"])
router.include_router(organisations.router, prefix="/organisations", tags=["Organisations"])
router.include_router(internals.router, prefix="/internals", tags=["Internals"])