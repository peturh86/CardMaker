try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from io import BytesIO
from PIL import Image
import tempfile
import os
import logging
import httpx


from app.ad_service import ADService, is_configured

from app.card import create_card_jpg
from app.print import print_image

app = FastAPI()


@app.get("/")
def root():
    return RedirectResponse("/docs")


@app.post(
    "/generate-card",
    summary="Generate employee ID card",
    description="""
Generates a custom employee card based on:
- Name (displayed prominently)
- National ID (kennitala), used for barcode
- Job title
- Uploaded photo
- Background removal option

Returns a JPEG image suitable for printing.
""",
    tags=["Card Generation"],
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"image/jpeg": {}},
            "description": "Generated card image",
        },
        422: {"description": "Validation error"},
    },
)
async def generate_and_print_card(
    name: str = Form(..., description="Full name of the employee"),
    kt: str = Form(..., description="Kennitala (1234567-1234)"),
    title: str = Form(..., description="Job title or role"),
    photo: UploadFile = File(
        None, description="Image of the employee (face photo, PNG/JPEG) - Optional"
    ),
    remove_bg: bool = Form(
        False,
        description="Remove background from the photo",
    ),
):
    # Read image file if provided
    image_bytes = None
    if photo is not None:
        image_bytes = await photo.read()

    # Create card using in-memory bytes instead of file path
    output_buffer = BytesIO()
    print("[INFO] Generating card for:", name)
    create_card_jpg(
        name=name,
        kt=kt,
        title=title,
        photo_path=image_bytes,
        output_path=output_buffer,
        remove_bg=remove_bg,
    )
    output_buffer.seek(0)
    return StreamingResponse(output_buffer, media_type="image/jpeg")


@app.post(
    "/generate-and-print-card",
    summary="Generate employee ID card and send for printing",
    description="""
Generates a custom employee card based on:
- Name (displayed prominently)
- National ID (kennitala), used for barcode
- Job title
- Uploaded photo
- Background removal option

Returns a JPEG image suitable for printing.
""",
    tags=["Card Generation"],
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"image/jpeg": {}},
            "description": "Generated card image",
        },
        422: {"description": "Validation error"},
    },
)
async def generate_and_print_card_endpoint(
    name: str = Form(..., description="Full name of the employee"),
    kt: str = Form(..., description="Kennitala (1234567-1234)"),
    title: str = Form(..., description="Job title or role"),
    photo: UploadFile = File(
        None, description="Image of the employee (face photo, PNG/JPEG) - Optional"
    ),
    remove_bg: bool = Form(
        False,
        description="Remove background from the photo",
    ),
    printer_name: str = Form(
        "ZC300",
        description="Name of the printer to use (defaults to ZC300)",
    ),
):
    # Read image file if provided
    image_bytes = None
    if photo is not None:
        image_bytes = await photo.read()

    # Create card using in-memory bytes instead of file path
    output_buffer = BytesIO()
    print("[INFO] Generating and printing card for:", name)

    # Generate the card
    create_card_jpg(
        name=name,
        kt=kt,
        title=title,
        photo_path=image_bytes,
        output_path=output_buffer,
        remove_bg=remove_bg,
    )

    # Save to temporary file for printing
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        temp_file.write(output_buffer.getvalue())
        temp_file_path = temp_file.name

    try:
        # Print the card
        print(f"[INFO] Sending card to printer: {temp_file_path}")
        print(f"[INFO] Using printer: {printer_name}")
        print_image(temp_file_path, printer_name)
        print("[INFO] Card sent to printer successfully")
    except Exception as e:
        print(f"[ERROR] Failed to print card: {e}")
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_file_path)
        except Exception as e:
            print(f"[WARNING] Failed to delete temporary file: {e}")

    # Return the image as well
    output_buffer.seek(0)
    return StreamingResponse(output_buffer, media_type="image/jpeg")


@app.get(
    "/printers",
    summary="List available printers",
    description="Returns a list of available CUPS printers",
    tags=["Printer Management"],
)
async def list_printers():
    """List all available CUPS printers"""
    try:
        from print import get_available_printers

        printers = get_available_printers()

        printer_list = []
        for name in printers:
            printer_info = {
                "name": name,
                "is_default": name == "ZC300",  # ZC300 is our default
            }
            printer_list.append(printer_info)

        return {
            "printers": printer_list,
            "default_printer": "ZC300",
            "total_count": len(printer_list),
        }
    except Exception as e:
        return {
            "error": f"Failed to list printers: {str(e)}",
            "printers": [],
            "total_count": 0,
        }

# --- Azure AD Employee Search ---

logger = logging.getLogger(__name__)

# Initialize AD service (only if configured)
ad_service = None
if is_configured():
    ad_service = ADService()
else:
    logger.warning("Azure AD not configured — /search-employees endpoint will return 503")


@app.get(
    "/search-employees",
    summary="Search Azure AD for employees",
    description="Search employees by name to auto-fill card fields. Returns matching employees with name, kennitala, and title.",
    tags=["Employee Search"],
)
async def search_employees(q: str):
    if ad_service is None:
        raise HTTPException(status_code=503, detail="AD search is not configured")

    # Validate query
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search query must be at least 2 characters")
    if len(query) > 100:
        raise HTTPException(status_code=422, detail="Search query must not exceed 100 characters")

    try:
        results = await ad_service.search_employees(query)
        return {"results": results, "count": len(results)}
    except RuntimeError as e:
        if "authenticate" in str(e).lower():
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=502, detail=str(e))
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Azure AD request timed out")


@app.get(
    "/search-employees/{user_id}/photo",
    summary="Get employee photo from Azure AD",
    description="Returns the profile photo for a given user ID, or 404 if no photo exists.",
    tags=["Employee Search"],
    responses={
        200: {"content": {"image/jpeg": {}}, "description": "User profile photo"},
        404: {"description": "No photo available"},
    },
)
async def get_employee_photo(user_id: str):
    if ad_service is None:
        raise HTTPException(status_code=503, detail="AD search is not configured")

    try:
        photo_bytes = await ad_service.get_user_photo(user_id)
        if photo_bytes is None:
            raise HTTPException(status_code=404, detail="No photo available for this user")
        return StreamingResponse(BytesIO(photo_bytes), media_type="image/jpeg")
    except RuntimeError as e:
        if "authenticate" in str(e).lower():
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=502, detail=str(e))


@app.post(
    "/print-employee",
    summary="Search and print employee card",
    description="""
Search Azure AD by name and print the employee's card.
- If exactly 1 match is found, the card is generated and printed immediately.
- If multiple matches are found, returns the list so you can pick one and call /print-employee/{user_id}.
- Uses the employee's AD photo if available.
""",
    tags=["Employee Search & Print"],
)
async def print_employee_search(
    q: str = Form(..., description="Employee name to search for"),
    printer_name: str = Form("ZC300", description="Printer name (defaults to ZC300)"),
    remove_bg: bool = Form(False, description="Remove background from the AD photo"),
):
    if ad_service is None:
        raise HTTPException(status_code=503, detail="AD search is not configured")

    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search query must be at least 2 characters")
    if len(query) > 100:
        raise HTTPException(status_code=422, detail="Search query must not exceed 100 characters")

    try:
        results = await ad_service.search_employees(query)
    except RuntimeError as e:
        if "authenticate" in str(e).lower():
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=502, detail=str(e))
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Azure AD request timed out")

    if len(results) == 0:
        raise HTTPException(status_code=404, detail="No employees found matching the query")

    if len(results) > 1:
        return {
            "action": "pick_one",
            "message": f"Multiple matches found ({len(results)}). Call POST /print-employee/{{user_id}} with the desired user's id.",
            "results": results,
            "count": len(results),
        }

    # Exactly 1 result — print immediately
    employee = results[0]
    return await _print_employee_card(employee, printer_name, remove_bg)


@app.post(
    "/print-employee/{user_id}",
    summary="Print card for a specific employee by AD user ID",
    description="Generates and prints a card for the specified user, fetching their info and photo from Azure AD.",
    tags=["Employee Search & Print"],
)
async def print_employee_by_id(
    user_id: str,
    printer_name: str = Form("ZC300", description="Printer name (defaults to ZC300)"),
    remove_bg: bool = Form(False, description="Remove background from the AD photo"),
):
    if ad_service is None:
        raise HTTPException(status_code=503, detail="AD search is not configured")

    # Look up this specific user by ID via Graph API
    try:
        token = await ad_service._get_token()
        from app.ad_service import GRAPH_BASE_URL, SELECT_FIELDS, KT_ATTRIBUTE

        headers = {
            "Authorization": f"Bearer {token}",
            "ConsistencyLevel": "eventual",
        }
        response = await ad_service._http_client.get(
            f"{GRAPH_BASE_URL}/users/{user_id}",
            params={"$select": SELECT_FIELDS},
            headers=headers,
        )

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Graph API error: {response.status_code}")

        user = response.json()
        raw_kt = (user.get(KT_ATTRIBUTE, "") or "").replace("-", "")
        employee = {
            "id": user.get("id", ""),
            "name": user.get("displayName", "") or "",
            "kt": f"{raw_kt[:6]}-{raw_kt[6:]}" if len(raw_kt) == 10 else raw_kt,
            "kt_barcode": raw_kt,
            "title": user.get("jobTitle", "") or "",
        }
    except RuntimeError as e:
        if "authenticate" in str(e).lower():
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=502, detail=str(e))
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Azure AD request timed out")

    return await _print_employee_card(employee, printer_name, remove_bg)


async def _print_employee_card(employee: dict, printer_name: str, remove_bg: bool):
    """Internal helper: generate and print a card for an employee dict."""
    name = employee["name"]
    kt = employee["kt"]
    title = employee["title"]
    user_id = employee.get("id", "")

    # Try to fetch photo from AD
    image_bytes = None
    if user_id:
        try:
            photo = await ad_service.get_user_photo(user_id)
            if photo:
                image_bytes = photo
                print(f"[INFO] Using AD photo for {name}")
            else:
                print(f"[INFO] No AD photo for {name}, proceeding without photo")
        except Exception as e:
            print(f"[WARNING] Failed to fetch photo for {name}: {e}")

    # Generate the card
    output_buffer = BytesIO()
    print(f"[INFO] Generating card for: {name}")
    create_card_jpg(
        name=name,
        kt=kt,
        title=title,
        photo_path=image_bytes,
        output_path=output_buffer,
        remove_bg=remove_bg,
    )

    # Print the card
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        temp_file.write(output_buffer.getvalue())
        temp_file_path = temp_file.name

    try:
        print(f"[INFO] Sending card to printer: {printer_name}")
        print_image(temp_file_path, printer_name)
        print("[INFO] Card sent to printer successfully")
    except Exception as e:
        print(f"[ERROR] Failed to print card: {e}")
    finally:
        try:
            os.unlink(temp_file_path)
        except Exception:
            pass

    # Return the card image as well
    output_buffer.seek(0)
    return StreamingResponse(output_buffer, media_type="image/jpeg")
