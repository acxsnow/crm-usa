from fastapi import APIRouter
router = APIRouter()

@router.get("/_boom_cors")
async def boom():
    raise RuntimeError("fallo de prueba")
