from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.billing.program_router import router as billing_program_router
from app.modules.billing.claims_router import router as billing_claims_router
from app.modules.billing.quotes_router import router as billing_quotes_router
from app.modules.cases.router import router as cases_router
from app.modules.crm.router import router as crm_router
from app.modules.field_ops.router import router as field_ops_router
from app.modules.organizations.audit_router import router as audit_router
from app.modules.organizations.router import router as organizations_router
from app.modules.users.roles_router import router as roles_router
from app.modules.users.router import router as users_router
from app.modules.programs.router import router as programs_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(organizations_router)
api_router.include_router(audit_router)
api_router.include_router(crm_router)
api_router.include_router(field_ops_router)
api_router.include_router(billing_router)
api_router.include_router(billing_program_router)
api_router.include_router(billing_claims_router)
api_router.include_router(billing_quotes_router)
api_router.include_router(cases_router)
api_router.include_router(programs_router)
