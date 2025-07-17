import os
from PIL import Image, ImageDraw, ImageFont
from rembg import remove
import io
import barcode
from barcode.writer import ImageWriter


# Card dimensions (CR80 card at 300 DPI): 85.6 x 54 mm = 1016 x 638 px
CARD_WIDTH, CARD_HEIGHT = 1016, 638

# Get the directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Try different font locations
def get_font_path(font_name):
    """Try to find font in multiple locations"""
    possible_paths = [
        f"/usr/share/fonts/truetype/custom/{font_name}",  # Docker container path
        os.path.join(
            os.path.dirname(BASE_DIR), "fonts", font_name
        ),  # Local development path
        font_name,  # System font or current directory
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


FONTRES1 = get_font_path("LSANSDI.TTF")
FONTRES2 = get_font_path("CascadiaCode.ttf")

try:
    if FONTRES1:
        FONT = ImageFont.truetype(FONTRES1, 48)
        FONT2 = ImageFont.truetype(FONTRES1, 52)
    else:
        raise OSError("FONTRES1 not found")

    if FONTRES2:
        FONT3 = ImageFont.truetype(FONTRES2, 33)
    else:
        raise OSError("FONTRES2 not found")

except OSError:
    print("[WARNING] Custom fonts not found, using default fonts")
    FONT = ImageFont.load_default()
    FONT2 = ImageFont.load_default()
    FONT3 = ImageFont.load_default()
    # Set fallback paths for the fit_text_to_width function
    FONTRES1 = None
    FONTRES2 = None


def autocrop_transparent(img: Image.Image) -> Image.Image:
    """
    Crops transparent edges from an RGBA image.
    """
    if img.mode != "RGBA":
        return img
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img


def fit_text_to_width(
    text: str,
    font_path: str,
    max_width: int,
    max_font_size: int,
    min_font_size: int = 10,
) -> ImageFont.FreeTypeFont:
    """
    Finds the largest font size that fits the text within a max width.

    :param text: Text to measure
    :param font_path: Path to the TTF font file (can be None for default font)
    :param max_width: Maximum width in pixels
    :param max_font_size: Starting font size to try
    :param min_font_size: Smallest allowed font size
    :return: A resized ImageFont.FreeTypeFont object
    """
    # If no custom font path, use default font
    if font_path is None:
        return ImageFont.load_default()

    try:
        font_size = max_font_size
        while font_size >= min_font_size:
            font = ImageFont.truetype(font_path, font_size)
            left, top, right, bottom = font.getbbox(text)
            text_width = right - left
            if text_width <= max_width:
                return font
            font_size -= 1
        return ImageFont.truetype(font_path, min_font_size)
    except OSError:
        print(f"[WARNING] Could not load font {font_path}, using default")
        return ImageFont.load_default()


def sanitize_text(text: str) -> str:
    """
    Sanitizes the input text by removing non-printable characters and trimming whitespace, and removing any dashes.
    """
    sanitized = "".join(c for c in text if c.isprintable())
    sanitized = sanitized.strip().replace("-", "")
    return sanitized


def draw_barcode(card: Image.Image, code: str, top_left: tuple, size: tuple):
    """
    Draws a 1D barcode (Code128) at the specified position.

    :param card: The canvas (Pillow Image object)
    :param code: The text to encode in the barcode
    :param top_left: (x, y) for the upper-left corner
    :param size: (width, height) of the bounding box to fit into
    """
    try:
        # Generate barcode as PIL image
        CODE128 = barcode.get("code128", code, writer=ImageWriter())
        barcode_img = CODE128.render(
            writer_options={
                "module_height": 15,  # base height, will be resized anyway
                "font_size": 1,  # hide text (optional)
                "write_text": False,
                "quiet_zone": 0,  # small margins
            }
        )

        # Resize to fit the box
        barcode_img = barcode_img.resize(size, Image.LANCZOS)

        # Paste it into the card
        card.paste(barcode_img, top_left)
    except Exception as e:
        print(f"[ERROR] Failed to draw barcode: {e}")


def draw_box(
    draw: ImageDraw.Draw,
    top_left: tuple,
    size: tuple,
    fill_color="white",
    outline_color="black",
    outline_width=1,
):
    """
    Draws a rectangle box on the given draw context.

    :param draw: An ImageDraw.Draw object
    :param top_left: (x, y) tuple for the top-left corner
    :param size: (width, height) tuple for box size
    :param fill_color: Fill color (default white)
    :param outline_color: Outline color (default black)
    :param outline_width: Outline thickness in pixels
    """
    x0, y0 = top_left
    w, h = size
    x1, y1 = x0 + w, y0 + h
    draw.rectangle(
        [x0, y0, x1, y1], fill=fill_color, outline=outline_color, width=outline_width
    )


def draw_triangle(
    draw: ImageDraw.Draw,
    points: list,
    fill_color="white",
    outline_color="black",
    outline_width=1,
):
    """
    Draws a triangle (polygon with 3 points).

    :param draw: An ImageDraw.Draw object
    :param points: List of three (x, y) tuples
    :param fill_color: Fill color of the triangle
    :param outline_color: Outline color
    :param outline_width: Thickness of outline
    """
    draw.polygon(points, fill=fill_color, outline=outline_color)
    if outline_width > 1:
        # Pillow only supports 1px outline by default, so we fake thicker ones by redrawing offset lines
        for i in range(len(points)):
            start = points[i]
            end = points[(i + 1) % len(points)]
            draw.line([start, end], fill=outline_color, width=outline_width)


def draw_image_box_no_padding(
    card: Image.Image,
    image: Image.Image,
    top_left: tuple,
    size: tuple,
    debug_color="lime",
):
    if image is None:
        print("No image provided")
        return

    box_width, box_height = size
    image_ratio = image.width / image.height
    box_ratio = box_width / box_height

    if image_ratio > box_ratio:
        new_width = box_width
        new_height = round(box_width / image_ratio)
    else:
        new_height = box_height
        new_width = round(box_height * image_ratio)

    image_resized = image.resize((new_width, new_height), Image.LANCZOS)

    offset_x = top_left[0] + (box_width - new_width) // 2
    offset_y = top_left[1] + (box_height - new_height) // 2

    # Draw the debug-colored background box
    # debug_box = Image.new("RGB", (box_width, box_height), color=debug_color)
    # card.paste(debug_box, top_left)

    # Paste the resized image over the background
    if image_resized.mode == "RGBA":
        card.paste(image_resized, (offset_x, offset_y), mask=image_resized)
    else:
        card.paste(image_resized, (offset_x, offset_y))


def load_image(image_data_or_path, remove_bg=False):
    try:
        # Handle None input (no photo provided)
        if image_data_or_path is None:
            return None

        if isinstance(image_data_or_path, bytes):
            image_bytes = image_data_or_path
        else:
            with open(image_data_or_path, "rb") as f:
                image_bytes = f.read()

        if remove_bg:
            from rembg import remove

            output_bytes = remove(image_bytes)
            image = Image.open(io.BytesIO(output_bytes)).convert("RGBA")
            image = autocrop_transparent(image)
        else:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        return image
    except Exception as e:
        print(f"[ERROR] Failed to load image: {e}")
        return None


def get_text_height(font: ImageFont.FreeTypeFont, text: str) -> int:
    bbox = font.getbbox(text)
    return bbox[3] - bbox[1]  # bottom - top


def get_line_height(font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent


def create_card_jpg(name: str, kt: str, title: str, photo_path, output_path, remove_bg):
    # Draw name
    side_margin = 40

    # Create white background
    card = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), color="white")
    draw = ImageDraw.Draw(card)

    # Paste a box in the lower left corner
    box_size = (CARD_WIDTH, CARD_HEIGHT // 3)
    box_top_left = (0, 550)
    draw_box(
        draw,
        box_top_left,
        box_size,
        fill_color="#37B6FF",
        outline_color="black",
        outline_width=0,
    )

    draw.polygon(
        [
            ((CARD_WIDTH // 2) - 10, CARD_HEIGHT),
            (CARD_WIDTH, -10),
            (CARD_WIDTH, CARD_HEIGHT),
        ],
        fill="#FF0000",
    )

    # Draw the logo
    logo_path = os.path.join(BASE_DIR, "posturinn_logo.png")
    logo = load_image(logo_path, remove_bg=False)
    if logo:
        logo_size = (250, 250)
        logo = logo.resize(logo_size, Image.LANCZOS)
        logo_position = (side_margin - 30, 20 - 70)
        card.paste(logo, logo_position)

    # Draw name, kt, title
    name_box_width = 600
    extrainfosize = 38

    try:
        # Try to use custom fonts if available
        if FONTRES1:
            name_font = fit_text_to_width(name, FONTRES1, name_box_width, 52)
            kt_font = ImageFont.truetype(FONTRES1, extrainfosize)
            title_font = ImageFont.truetype(FONTRES1, extrainfosize)
        else:
            raise OSError("Custom fonts not available")
    except OSError:
        # Fallback to default font if custom fonts are not available
        print("[WARNING] Custom fonts not found, using default font")
        name_font = ImageFont.load_default()
        kt_font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    TextBlockStartingHeight = 180

    draw.text(
        (side_margin, TextBlockStartingHeight), name, font=name_font, fill="black"
    )
    TextBlockStartingHeight += get_line_height(name_font) + 2

    draw.text((side_margin, TextBlockStartingHeight), kt, font=kt_font, fill="black")
    TextBlockStartingHeight += get_line_height(kt_font) + 2

    draw.text(
        (side_margin, TextBlockStartingHeight), title, font=title_font, fill="black"
    )

    # Draw the Barcode from the kt
    barcode_width = 520
    barcode_height = 120
    draw_barcode(
        card,
        sanitize_text(kt),
        top_left=(side_margin, 400),
        size=(barcode_width, barcode_height),
    )

    image_width = 360
    image_height = 500

    # Draw the image box
    draw_image_box_no_padding(
        card,
        load_image(photo_path, remove_bg),
        (CARD_WIDTH - image_width - side_margin, 40),
        (image_width, image_height),
    )

    # Draw Card type
    draw.text((side_margin, 555), "Starfsmannakort", font=FONT2, fill="White")

    # Save to JPG with optimal settings for Zebra printers
    if hasattr(output_path, "write"):
        # BytesIO object - optimize for card printing
        card_rgb = card.convert("RGB")
        card_rgb.save(
            output_path, format="JPEG", quality=95, optimize=True, dpi=(300, 300)
        )
    else:
        # File path - save as high quality JPEG
        card_rgb = card.convert("RGB")
        card_rgb.save(
            output_path, format="JPEG", quality=95, optimize=True, dpi=(300, 300)
        )

    return card


if __name__ == "__main__":
    # Example usage
    create_card_jpg(
        "Friðjón Ástmundsson",
        "300485-2199",
        "Upplýsingatæknideild",
        "3004852199.jpg",
        "output.jpg",
        remove_bg=True,
    )
