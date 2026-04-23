from fastapi import APIRouter, Depends

from src.deps import require_scope

router = APIRouter(
    prefix="/v1/tools/outlook",
    tags=["outlook"],
    dependencies=[Depends(require_scope("outlook"))],
)


@router.get("/status")
def outlook_status() -> dict:
    return {
        "tool": "outlook",
        "status": "stub",
        "message": "Outlook tool is not implemented yet. Add handlers under tools/outlook/.",
    }
