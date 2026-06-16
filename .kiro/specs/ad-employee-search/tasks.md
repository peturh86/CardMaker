# Tasks

## Task 1: Add dependencies

- [x] 1.1 Add `msal` and `httpx` to `requirements.txt`

## Task 2: Create AD Service module

- [x] 2.1 Create `app/ad_service.py` with the `ADService` class implementing token acquisition via MSAL client credentials flow
- [x] 2.2 Implement the `search_employees` method with Graph API query, OData filter on `displayName`, `$select` for `displayName,jobTitle,extension_19112b3298ff422598d40f15c3ca3fba_employeeNumber`, and `$top=20`
- [x] 2.3 Implement `is_configured()` helper that checks for `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` environment variables
- [x] 2.4 Implement input sanitization (single quote escaping for OData injection prevention)
- [x] 2.5 Implement error handling: timeout (10s), auth failure, Graph API errors, missing attribute values default to empty string

## Task 3: Add search endpoint to FastAPI app

- [x] 3.1 Add `/search-employees` GET endpoint to `app/main.py` with query parameter `q`
- [x] 3.2 Add input validation: strip whitespace, reject queries under 2 chars or over 100 chars with 422 responses
- [x] 3.3 Initialize `ADService` at startup only if environment variables are present; log warning if not configured
- [x] 3.4 Return proper error responses: 503 for auth failures, 504 for timeouts, 502 for Graph API errors

## Task 4: Update environment configuration

- [x] 4.1 Add `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` placeholder entries to `.env`

## Task 5: Verify existing endpoints unchanged

- [x] 5.1 Confirm `/generate-card` and `/generate-and-print-card` endpoints still accept the same parameters and produce the same responses (no regressions)

