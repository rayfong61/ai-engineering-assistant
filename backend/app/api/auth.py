from fastapi import APIRouter, Depends

from app.core.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)) -> dict:
    return user
