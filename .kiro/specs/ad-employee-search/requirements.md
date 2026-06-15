# Requirements Document

## Introduction

This feature adds an Azure Active Directory (Entra ID) employee search capability to the existing CardMaker FastAPI application. Instead of manually typing employee details (name, kennitala, title) into the card generation form, users can search the company's Azure AD by name and auto-fill the relevant card fields from the matching employee record. The goal is a minimal addition that reduces manual data entry errors and speeds up card creation.

The application authenticates to Microsoft Graph API using an Azure App Registration with the OAuth2 client credentials flow. The search maps Entra ID attributes directly to card fields: `displayName` for name, `jobTitle` for title, and `extension_19112b3298ff422598d40f15c3ca3fba_employeeNumber` for kennitala.

## Glossary

- **CardMaker_API**: The existing FastAPI application that generates and prints employee ID cards
- **AD_Service**: A module responsible for authenticating with Azure AD and querying users via Microsoft Graph API
- **Search_Endpoint**: The new API endpoint that accepts a search query and returns matching employee records
- **Employee_Record**: A data structure containing the employee fields retrieved from Entra ID: name (from `displayName`), kennitala (from `extension_19112b3298ff422598d40f15c3ca3fba_employeeNumber`), and title (from `jobTitle`)
- **Microsoft_Graph**: Microsoft's RESTful API for accessing Azure AD and Microsoft 365 resources
- **App_Registration**: An Azure AD application identity used to authenticate the CardMaker_API with client credentials
- **Kennitala**: Icelandic national identification number in the format DDMMYY-XXXX
- **Client_Credentials_Flow**: An OAuth2 flow where the application authenticates using its own identity (client ID + client secret) without user interaction

## Requirements

### Requirement 1: Search Employees by Name

**User Story:** As a card operator, I want to search Azure AD by employee name, so that I can find the correct employee without knowing their exact details.

#### Acceptance Criteria

1. WHEN a search query of at least 2 characters is submitted, THE Search_Endpoint SHALL query AD_Service for users whose `displayName` starts with or contains the search query
2. WHEN matching users are found, THE Search_Endpoint SHALL return a list of Employee_Records containing name (from `displayName`), kennitala (from `extension_19112b3298ff422598d40f15c3ca3fba_employeeNumber`), and title (from `jobTitle`) for each match
3. WHEN no matching users are found, THE Search_Endpoint SHALL return an empty list with a 200 status code
4. THE Search_Endpoint SHALL limit results to a maximum of 20 Employee_Records per query

### Requirement 2: Azure AD App Registration Configuration

**User Story:** As a system administrator, I want to configure the Azure AD connection via environment variables, so that the application can authenticate and query Microsoft Graph.

#### Acceptance Criteria

1. THE AD_Service SHALL read the Azure AD tenant ID from the AZURE_TENANT_ID environment variable
2. THE AD_Service SHALL read the application (client) ID from the AZURE_CLIENT_ID environment variable
3. THE AD_Service SHALL read the client secret from the AZURE_CLIENT_SECRET environment variable
4. IF any of the AZURE_TENANT_ID, AZURE_CLIENT_ID, or AZURE_CLIENT_SECRET environment variables are missing, THEN THE CardMaker_API SHALL start without the AD search feature and log a warning message

### Requirement 3: Microsoft Graph Authentication

**User Story:** As the system, I want to authenticate to Microsoft Graph using the client credentials flow, so that the application can query Azure AD without user interaction.

#### Acceptance Criteria

1. THE AD_Service SHALL obtain an OAuth2 access token from the Microsoft identity platform token endpoint using the client credentials flow
2. THE AD_Service SHALL cache the access token and reuse it until the token expires
3. WHEN the cached token has expired, THE AD_Service SHALL request a new access token before executing the query
4. IF the token request fails, THEN THE AD_Service SHALL return a 503 Service Unavailable response with a descriptive error message

### Requirement 4: Graph API Query Execution

**User Story:** As a card operator, I want search results returned promptly, so that the card creation workflow is not slowed down.

#### Acceptance Criteria

1. WHEN a search query is submitted, THE AD_Service SHALL call the Microsoft Graph `/users` endpoint with a `$filter` on `displayName`
2. THE AD_Service SHALL request only the `displayName`, `jobTitle`, and `extension_19112b3298ff422598d40f15c3ca3fba_employeeNumber` fields using the `$select` parameter
3. THE AD_Service SHALL limit results using the `$top` parameter set to 20
4. IF the Graph API returns an error response, THEN THE AD_Service SHALL return a descriptive error message with the appropriate HTTP status code
5. IF the Graph API does not respond within 10 seconds, THEN THE AD_Service SHALL return a 504 Gateway Timeout response
6. WHEN a user record lacks a value for `extension_19112b3298ff422598d40f15c3ca3fba_employeeNumber` or `jobTitle`, THE AD_Service SHALL return an empty string for that field in the Employee_Record

### Requirement 5: Preserve Manual Entry

**User Story:** As a card operator, I want to still be able to type employee details manually, so that I can create cards for people not in Azure AD or correct auto-filled data.

#### Acceptance Criteria

1. THE CardMaker_API SHALL continue to accept manually typed name, kennitala, and title values on the existing card generation endpoints
2. THE Search_Endpoint SHALL be an independent, optional endpoint that does not modify or gate the existing card generation workflow
3. THE existing `/generate-card` and `/generate-and-print-card` endpoints SHALL remain unchanged in their request parameters and behavior

### Requirement 6: Input Validation

**User Story:** As a card operator, I want the search to reject invalid queries, so that unnecessary Graph API calls are avoided.

#### Acceptance Criteria

1. IF a search query shorter than 2 characters is submitted, THEN THE Search_Endpoint SHALL return a 422 validation error with a descriptive message
2. THE Search_Endpoint SHALL strip leading and trailing whitespace from the search query before processing
3. IF the search query exceeds 100 characters after trimming, THEN THE Search_Endpoint SHALL return a 422 validation error with a descriptive message
4. THE Search_Endpoint SHALL sanitize the search query to prevent OData injection by escaping single quotes

