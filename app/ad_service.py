import os
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

# Fields to select from Graph (include id and userPrincipalName for photo lookup)
SELECT_FIELDS = f"id,displayName,userPrincipalName,jobTitle,{KT_ATTRIBUTE}"

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
        Search for employees by userPrincipalName.

        Returns a list of dicts with keys: id, name, kt, title, upn, has_photo
        """
        token = await self._get_token()
        sanitized = self._sanitize_query(query)

        # Filter by exact userPrincipalName match (append @domain if not included)
        if "@" in sanitized:
            odata_filter = f"userPrincipalName eq '{sanitized}'"
        else:
            odata_filter = f"startsWith(userPrincipalName,'{sanitized}@')"

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

        results = []
        for user in users:
            user_id = user.get("id", "")
            has_photo = await self._check_has_photo(token, user_id) if user_id else False
            results.append({
                "id": user_id,
                "name": user.get("displayName", "") or "",
                "upn": user.get("userPrincipalName", "") or "",
                "kt": user.get(KT_ATTRIBUTE, "") or "",
                "title": user.get("jobTitle", "") or "",
                "has_photo": has_photo,
            })

        return results

    async def _check_has_photo(self, token: str, user_id: str) -> bool:
        """Check if a user has a profile photo (metadata check, no download)."""
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = await self._http_client.get(
                f"{GRAPH_BASE_URL}/users/{user_id}/photo",
                headers=headers,
            )
            return response.status_code == 200
        except httpx.TimeoutException:
            return False

    async def get_user_photo(self, user_id: str) -> bytes | None:
        """
        Fetch a user's profile photo from Graph API.

        Returns the photo bytes (JPEG) if the user has a photo, or None if not.
        """
        token = await self._get_token()

        headers = {
            "Authorization": f"Bearer {token}",
        }

        try:
            response = await self._http_client.get(
                f"{GRAPH_BASE_URL}/users/{user_id}/photo/$value",
                headers=headers,
            )

            if response.status_code == 200:
                return response.content
            elif response.status_code == 404:
                logger.info(f"No photo found for user {user_id}")
                return None
            else:
                logger.warning(f"Unexpected status fetching photo for {user_id}: {response.status_code}")
                return None
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching photo for user {user_id}")
            return None

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()
