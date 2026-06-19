from fastapi import APIRouter

from app.api.v1.appointments import router as appointments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.diagnoses import router as diagnoses_router
from app.api.v1.patients import router as patients_router
from app.api.v1.uploads import router as uploads_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(patients_router)
router.include_router(uploads_router)
router.include_router(diagnoses_router)
router.include_router(appointments_router)
