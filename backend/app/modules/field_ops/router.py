from fastapi import APIRouter

from app.modules.field_ops import (
    checklist_templates_router,
    evidence_router,
    operations_router,
    permits_inspections_router,
    projects_router,
    reviews_router,
    tasks_router,
)

router = APIRouter(tags=["field-ops"])
router.include_router(projects_router.router)
router.include_router(checklist_templates_router.router)
router.include_router(tasks_router.router)
router.include_router(evidence_router.router)
router.include_router(operations_router.router)
router.include_router(permits_inspections_router.router)
router.include_router(reviews_router.router)
