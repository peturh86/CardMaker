import subprocess
import os
import sys


def print_image(image_path: str, printer_name: str = "ZC300"):
    """
    Print an image using the lp command.

    Args:
        image_path: Path to the image file to print
        printer_name: Name of the printer (defaults to ZC300)
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    print(f"[INFO] Using printer: {printer_name}")

    try:
        # Use lp command to print the image
        cmd = [
            "lp",
            "-d",
            printer_name,  # destination printer
            "-o",
            "fit-to-page",  # fit image to page
            "-o",
            "media=Custom.85.6x54mm",  # CR80 card size (optional)
            "-t",
            "EmployeeCard",  # job title
            image_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if result.stdout:
            print(f"[INFO] Print job submitted: {result.stdout.strip()}")
        else:
            print("[INFO] Print job submitted successfully")

    except subprocess.CalledProcessError as e:
        error_msg = f"Print command failed: {e.stderr.strip() if e.stderr else str(e)}"
        print(f"[ERROR] {error_msg}")
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Failed to print image: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise RuntimeError(error_msg)


def get_available_printers():
    """
    Get list of available printers using lpstat command.

    Returns:
        list: List of printer names
    """
    try:
        result = subprocess.run(
            ["lpstat", "-p"], capture_output=True, text=True, check=True
        )
        printers = []
        for line in result.stdout.split("\n"):
            if line.startswith("printer "):
                # Extract printer name from "printer printername is ..." format
                printer_name = line.split()[1]
                printers.append(printer_name)
        return printers
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to get printer list: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to get printer list: {e}")
        return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python print.py <image_path> [printer_name]")
        print("Available printers:")
        for printer in get_available_printers():
            print(f"  - {printer}")
        sys.exit(1)

    image_path = sys.argv[1]
    printer = sys.argv[2] if len(sys.argv) > 2 else "ZC300"

    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)

    try:
        print_image(image_path, printer)
        print("[SUCCESS] Card sent to printer")
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
