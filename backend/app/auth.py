import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer = HTTPBearer(auto_error=False)


def require_token(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    """Every request must send `Authorization: Bearer <APP_TOKEN>`."""
    # compare_digest takes the same time however much of the token matches,
    # so the token can't be guessed character by character from response times.
    if creds is None or not secrets.compare_digest(creds.credentials, settings.app_token):
        raise HTTPException(401, "Invalid or missing token", headers={"WWW-Authenticate": "Bearer"})
