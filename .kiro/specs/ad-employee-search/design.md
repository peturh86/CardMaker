# Design Document

## Overview

This design adds a single new module (`app/ad_service.py`) and one new endpoint (`/search-employees`) to the existing CardMaker FastAPI application. The implementation uses the `msal` library for OAuth2 client credentials authentication and the `httpx` library for async HTTP calls to Microsoft Graph. The design is intentionally minimal — no changes to existing endpoints or card generation logic.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Application                     │
├──────────────────┬───────────────────────────────────────┤
│  Existing        │  New                                   │
│  /generate-card  │  /search-employees?q=<query>           │
│  /generate-and-  │         │                              │
│   print-card     │         ▼                              │
│  /printers       │  ┌─────────────────┐                  │
│                  │  │  AD_Service      │                  │
│                  │  │  (ad_service.py) │                  │
│                  │  └────────┬────────┘                  │
│                  │           │                            │
│                  │           ▼                            │
│                  │  ┌─────────────────┐                  │
│                  │  │ Microsoft Graph  │                  │
│                  │  │ (via MSAL+httpx) │                  │
│                  │  └─────────────────┘                  │
└──────────────────┴───────────────────────────────────────┘
```

## File Changes

### New Files

| File | Purpose |
|------|---------|
| `app/ad_service.py` | AD_Service module — token acquisition, Graph API queries, response mapping |

### Modified Files

| File | Change |
|------|--------|
| `app/main.py` | Add `/search-employees` GET endpoint, import AD_Service |
| `requirements.txt` | Add `msal` and `httpx` dependencies |
| `.env` | Add `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` variables |

### Unchanged Files

| File | Reason |
|------|--------|
| `app/card.py` | No changes — card generation logic is untouched |
| `app/print.py` | No changes — printing logic is untouched |
| `docker-compose.yml` | No changes — no new services or ports needed |

## Detailed Design

### 1. `app/ad_service.py` — AD_Service Module

```python
import os
import time
import logging
import httpx
from msal import ConfidentialClientApplication

logger = logging.getLogger(__name__)

# Configuration from environment
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

# Extension attribute for kennitala
KT_ATTRIBUTE = "extension_19112b3298ff422598d40f15c3ca3fba_employeeNumber"

# Fields to select from Graph
SELECT_FIELDS = f"displayName,jobTitle,{KT_ATTRIBUTE}"

MAX_RESULTS = 20
REQUEST_TIMEOUT = 10.0


def is_configured() -> bool:
    """Check if all required Azure AD environment variables are set."""
    return all([AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET])


class ADService:
    def __init__(self):
        if not is_configured():
            raise RuntimeError("Azure AD environment variables not configured")
        
        self._msal_app = ConfidentialClientApplication(
            client_id=AZURE_CLIENT_ID,
            client_credential=AZURE_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{AZURE_TENANT_ID}",
        )
        self._http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    async def _get_token(self) -> str:
        """Acquire access token using client credentials (with MSAL caching)."""
        result = self._msal_app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        
        if "access_token" in result:
            return result["access_token"]
        
        error_desc = result.get("error_description", "Unknown authentication error")
        logger.error(f"Token acquisition failed: {error_desc}")
        raise RuntimeError(f"Failed to authenticate with Azure AD: {error_desc}")

    def _sanitize_query(self, query: str) -> str:
        """Escape single quotes to prevent OData injection."""
        return query.replace("'", "''")

    async def search_employees(self, query: str) -> list[dict]:
        """
        Search for employees by displayName.
        
        Returns a list of dicts with keys: name, kt, title
        """
        token = await self._get_token()
        sanitized = self._sanitize_query(query)
        
        # Use startsWith for better performance, fall back to contains behavior
        odata_filter = f"startsWith(displayName,'{sanitized}')"
        
        params = {
            "$filter": odata_filter,
            "$select": SELECT_FIELDS,
            "$top": str(MAX_RESULTS),
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "ConsistencyLevel": "eventual",
        }
        
        response = await self._http_client.get(
            f"{GRAPH_BASE_URL}/users",
            params=params,
            headers=headers,
        )
        
        if response.status_code != 200:
            error_body = response.text
            logger.error(f"Graph API error ({response.status_code}): {error_body}")
            raise RuntimeError(
                f"Graph API error: {response.status_code}"
            )
        
        data = response.json()
        users = data.get("value", [])
        
        return [
            {
                "name": user.get("displayName", ""),
                "kt": user.get(KT_ATTRIBUTE, "") or "",
                "title": user.get("jobTitle", "") or "",
            }
            for user in users
        ]

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()
```

**Key design decisions:**
- **MSAL handles token caching** — `acquire_token_for_client` automatically caches and refreshes tokens. No manual expiry tracking needed.
- **`httpx.AsyncClient`** — async HTTP client works natively with FastAPI's async endpoints, with built-in timeout support.
- **OData `startsWith`** — more performant than `contains` for Graph API queries. If users need substring matching, this can be switched to a `search` query later.
- **Singleton pattern** — one instance created at startup, reused across requests.

### 2. Changes to `app/main.py`

Add the search endpoint at the bottom of the existing file:

```python
from app.ad_service import ADService, is_configured

# Initialize AD service (only if configured)
ad_service = None
if is_configured():
    ad_service = ADService()
else:
    import logging
    logging.warning("Azure AD not configured — /search-employees endpoint disabled")


@app.get(
    "/search-employees",
    summary="Search Azure AD for employees",
    description="Search employees by name to auto-fill card fields. Returns matching employees with name, kennitala, and title.",
    tags=["Employee Search"],
)
async def search_employees(q: str):
    if ad_service is None:
        return {"error": "AD search is not configured", "status": 503}
    
    # Validate query
    query = q.strip()
    if len(query) < 2:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Search query must be at least 2 characters")
    if len(query) > 100:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Search query must not exceed 100 characters")
    
    try:
        results = await ad_service.search_employees(query)
        return {"results": results, "count": len(results)}
    except RuntimeError as e:
        if "authenticate" in str(e).lower():
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=str(e))
    except httpx.TimeoutException:
        from fastapi import HTTPException
        raise HTTPException(status_code=504, detail="Azure AD request timed out")
```

### 3. `requirements.txt` additions

```
msal
httpx
```

### 4. `.env` additions

```
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
```

## Response Format

### Success (200)

```json
{
  "results": [
    {
      "name": "Jón Jónsson",
      "kt": "010190-2389",
      "title": "Upplýsingatæknideild"
    },
    {
      "name": "Jóna Jónsdóttir",
      "kt": "150285-4521",
      "title": "Fjármáladeild"
    }
  ],
  "count": 2
}
```

### No results (200)

```json
{
  "results": [],
  "count": 0
}
```

### Validation error (422)

```json
{
  "detail": "Search query must be at least 2 characters"
}
```

## Azure App Registration Setup

The following permissions are required on the App Registration:

| Permission | Type | Purpose |
|---|---|---|
| `User.Read.All` | Application | Read all user profiles including extension attributes |

Admin consent is required for application permissions.

## Testing Strategy

- Unit tests mock the Graph API responses to verify response mapping, error handling, and input validation
- Integration testing requires a configured Azure AD tenant with test users
- The existing `/generate-card` and `/generate-and-print-card` endpoints remain untested by this feature (no changes)

