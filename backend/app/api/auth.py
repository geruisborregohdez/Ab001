"""
QuickBooks OAuth2 re-authorization endpoints.

Flow:
  1. User visits GET /api/auth/quickbooks  → redirected to Intuit authorization page.
  2. User approves → Intuit redirects to GET /api/auth/quickbooks/callback?code=...&realmId=...
  3. Callback exchanges code for tokens, persists them, resets the QB client singleton.

Required env vars: QB_CLIENT_ID, QB_CLIENT_SECRET, QB_ENVIRONMENT, QB_REDIRECT_URI
Only active when QB_MODE=real.
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _make_auth_client():
    from intuitlib.client import AuthClient

    return AuthClient(
        client_id=os.environ["QB_CLIENT_ID"],
        client_secret=os.environ["QB_CLIENT_SECRET"],
        redirect_uri=os.environ["QB_REDIRECT_URI"],
        environment=os.getenv("QB_ENVIRONMENT", "sandbox"),
    )


@router.get("/quickbooks")
async def quickbooks_authorize():
    """Redirect to Intuit's OAuth2 authorization page."""
    if os.getenv("QB_MODE", "stub").lower() != "real":
        raise HTTPException(status_code=400, detail="QB_MODE is not 'real' — re-auth not needed")

    from intuitlib.enums import Scopes

    auth_client = _make_auth_client()
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    return RedirectResponse(url=auth_url)


@router.get("/quickbooks/callback")
async def quickbooks_callback(code: str, realmId: str, state: str = ""):
    """
    Handle Intuit's redirect after user approval.
    Exchanges the authorization code for tokens and persists them.
    """
    if os.getenv("QB_MODE", "stub").lower() != "real":
        raise HTTPException(status_code=400, detail="QB_MODE is not 'real'")

    from app.integrations.quickbooks import _TOKEN_FILE, reset_quickbooks_client
    import json
    from datetime import datetime, timezone

    auth_client = _make_auth_client()
    try:
        auth_client.get_bearer_token(code, realm_id=realmId)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {exc}") from exc

    # Persist tokens to disk (same file the QB client reads on startup)
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, "w") as f:
        json.dump(
            {
                "refresh_token": auth_client.refresh_token,
                "access_token": auth_client.access_token,
                "realm_id": realmId,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
        )

    # Reset singleton so next tool call picks up the fresh tokens
    reset_quickbooks_client()

    return JSONResponse(
        {
            "status": "authorized",
            "realm_id": realmId,
            "message": "QuickBooks tokens saved. The app will use the new tokens immediately.",
        }
    )
