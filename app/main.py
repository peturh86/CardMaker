from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from io import BytesIO
from PIL import Image
import tempfile
import os

from .card import create_card_jpg
from .print import print_image

app = FastAPI()


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
        from .print import get_available_printers

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
