"""
Generate verified test images with realistic polybags, suffocation warnings,
FNSKU labels, barcodes, and package elements for CUBE Prep Manager testing.
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIRS = [
    "cube_prep_dataset/images",
    "frontend/public/test_samples",
    "frontend/public/images"
]

for d in OUTPUT_DIRS:
    os.makedirs(d, exist_ok=True)

def get_font(size=14, bold=False):
    """Load default or system TrueType font."""
    font_names = [
        "arial.ttf", "arialbd.ttf" if bold else "arial.ttf",
        "consola.ttf", "calibri.ttf", "DejaVuSans.ttf"
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            pass
    return ImageFont.load_default()

def draw_barcode(draw, x, y, w, h, code_text):
    """Draw a realistic 1D Code128-style barcode pattern."""
    import hashlib
    # Generate deterministic bar pattern from text
    h_bytes = hashlib.md5(code_text.encode('utf-8')).digest()
    bits = ""
    for b in h_bytes:
        bits += f"{b:08b}"
    
    # Ensure guard bars at start and end: 101
    full_pattern = "101001" + bits[:48] + "101001"
    bar_w = max(1.5, w / len(full_pattern))
    
    cur_x = x
    for bit in full_pattern:
        if bit == '1':
            draw.rectangle([cur_x, y, cur_x + bar_w - 0.5, y + h], fill=(15, 15, 15))
        cur_x += bar_w

def create_polybag_unit(
    unit_id="UNIT-POLY-0001",
    product_name="TOY PUZZLE SET",
    fnsku="X001POLYBAG01",
    sealed=True,
    has_warning=True,
    warning_obscured=False,
    barcode_covered=True,
    fnsku_on_seam=False,
    handling_mark="LIQUID",
    bg_tint=(228, 235, 240)
):
    """
    Creates front, back, and label camera images at standard 768x576 resolution.
    """
    w, h = 768, 576
    font_title = get_font(18, bold=True)
    font_body = get_font(13, bold=False)
    font_bold = get_font(14, bold=True)
    font_small = get_font(11, bold=False)
    font_tiny = get_font(10, bold=False)

    # ==========================================
    # 1. FRONT VIEW
    # ==========================================
    front_img = Image.new("RGB", (w, h), color=(222, 222, 222))
    f_draw = ImageDraw.Draw(front_img)

    # Background bench / surface
    f_draw.rectangle([0, 410, w, h], fill=(185, 188, 192))
    f_draw.line([0, 410, w, 410], fill=(160, 163, 168), width=2)

    # Product Box inside polybag
    # Coordinates: [148, 75, 475, 385] -> x1=148, y1=75, x2=623, y2=460
    f_draw.rounded_rectangle([148, 85, 623, 445], radius=8, fill=(205, 175, 135), outline=(130, 95, 60), width=2)
    # Box center fold / seam
    f_draw.line([384, 85, 384, 445], fill=(150, 115, 80), width=2)
    # Inner box text
    f_draw.text((170, 105), product_name, fill=(80, 55, 30), font=font_title)

    # Transparent Polybag Enclosure overlay
    # Coordinates: [125, 55, 520, 425] -> x1=125, y1=55, x2=645, y2=480
    poly_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(poly_overlay)

    # Polybag outer translucent body with slight sheen
    poly_fill = (220, 238, 245, 110) # Translucent cyan sheen
    p_draw.rounded_rectangle([125, 55, 645, 480], radius=16, fill=poly_fill, outline=(160, 195, 215, 240), width=3)

    # Specular reflections / plastic crinkles
    p_draw.line([135, 75, 260, 465], fill=(255, 255, 255, 70), width=3)
    p_draw.line([635, 80, 530, 460], fill=(255, 255, 255, 60), width=3)

    # Heat Seal Line at top:
    if sealed:
        # Green heat seal band at y=65 to 75
        p_draw.rectangle([135, 66, 635, 73], fill=(34, 139, 34, 230), outline=(20, 90, 20, 255))
        # Micro heat seal serrations
        for sx in range(140, 630, 6):
            p_draw.line([sx, 64, sx + 2, 75], fill=(25, 100, 25, 200), width=1)
    else:
        # Broken / open seal with gap
        p_draw.rectangle([135, 66, 320, 73], fill=(200, 60, 60, 230))
        p_draw.rectangle([450, 66, 635, 73], fill=(200, 60, 60, 230))
        # Open flap
        p_draw.polygon([(320, 66), (384, 42), (450, 66)], fill=(230, 242, 248, 140), outline=(180, 200, 210, 255))

    # Composite polybag overlay onto front image
    front_img.paste(Image.alpha_composite(Image.new("RGBA", (w, h), (0,0,0,0)), poly_overlay), (0, 0), poly_overlay)
    f_draw = ImageDraw.Draw(front_img)

    # Suffocation Warning Box
    if has_warning:
        # Box placed on polybag: [185, 125, 160, 65]
        if warning_obscured:
            # Obscured by fold: only top half visible
            f_draw.rectangle([185, 125, 345, 155], fill=(245, 248, 250), outline=(50, 50, 50), width=2)
            f_draw.text((192, 130), "WARNING", fill=(0, 0, 0), font=font_bold)
            # Fold line covering rest
            f_draw.polygon([(180, 150), (350, 150), (330, 190), (170, 190)], fill=(195, 215, 225), outline=(140, 160, 175), width=2)
        else:
            f_draw.rectangle([185, 120, 360, 185], fill=(248, 250, 252), outline=(30, 30, 30), width=2)
            f_draw.text((192, 126), "WARNING", fill=(20, 20, 20), font=font_bold)
            f_draw.text((192, 145), "PLASTIC BAG", fill=(20, 20, 20), font=font_bold)
            f_draw.text((192, 165), "KEEP AWAY FROM BABIES", fill=(40, 40, 40), font=font_tiny)

    # FNSKU Label Placement
    # Coordinates: normal flat: [425, 205, 165, 115]
    if fnsku_on_seam:
        lx, ly = 320, 205
    else:
        lx, ly = 430, 205
    lw, lh = 170, 115

    # White label with crisp border
    f_draw.rectangle([lx, ly, lx + lw, ly + lh], fill=(255, 255, 255), outline=(20, 20, 20), width=2)
    f_draw.text((lx + 10, ly + 8), "FNSKU", fill=(0, 0, 0), font=font_bold)
    f_draw.text((lx + 10, ly + 25), fnsku, fill=(0, 0, 0), font=font_bold)
    # Barcode
    draw_barcode(f_draw, lx + 10, ly + 46, lw - 20, 40, fnsku)
    f_draw.text((lx + 24, ly + 90), fnsku, fill=(50, 50, 50), font=font_small)

    # Handling mark if applicable
    if handling_mark:
        f_draw.text((515, 375), handling_mark, fill=(30, 30, 30), font=font_bold)

    # ==========================================
    # 2. BACK VIEW
    # ==========================================
    back_img = Image.new("RGB", (w, h), color=(222, 222, 222))
    b_draw = ImageDraw.Draw(back_img)
    # Bench
    b_draw.rectangle([0, 410, w, h], fill=(185, 188, 192))
    b_draw.line([0, 410, w, 410], fill=(160, 163, 168), width=2)
    # Box rear
    b_draw.rounded_rectangle([148, 85, 623, 445], radius=8, fill=(205, 175, 135), outline=(130, 95, 60), width=2)
    b_draw.text((170, 105), f"{product_name} - REAR", fill=(80, 55, 30), font=font_title)

    # Polybag rear overlay
    poly_back = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pb_draw = ImageDraw.Draw(poly_back)
    pb_draw.rounded_rectangle([125, 55, 645, 480], radius=16, fill=(220, 238, 245, 110), outline=(160, 195, 215, 240), width=3)
    if sealed:
        pb_draw.rectangle([135, 66, 635, 73], fill=(34, 139, 34, 230))
    back_img.paste(Image.alpha_composite(Image.new("RGBA", (w, h), (0,0,0,0)), poly_back), (0, 0), poly_back)
    b_draw = ImageDraw.Draw(back_img)

    # Original Barcode Check
    if barcode_covered:
        # Covered with opaque blank sticker
        b_draw.rectangle([210, 385, 330, 430], fill=(250, 250, 250), outline=(80, 80, 80), width=1)
        b_draw.text((220, 398), "[BARCODE COVERED]", fill=(120, 120, 120), font=font_small)
    else:
        # Exposed original manufacturer barcode
        b_draw.rectangle([210, 385, 330, 430], fill=(255, 255, 255), outline=(0, 0, 0), width=1)
        draw_barcode(b_draw, 215, 390, 100, 26, "ORIG-UPC-998877")
        b_draw.text((220, 418), "ORIG 998877", fill=(0, 0, 0), font=font_tiny)

    # ==========================================
    # 3. LABEL MACRO VIEW
    # ==========================================
    label_img = Image.new("RGB", (w, h), color=(250, 250, 252))
    l_draw = ImageDraw.Draw(label_img)

    # Macro close-up frame
    l_draw.rectangle([60, 50, w - 60, h - 50], fill=(255, 255, 255), outline=(40, 40, 40), width=3)
    font_macro_title = get_font(30, bold=True)
    font_macro_code = get_font(26, bold=True)
    font_macro_sub = get_font(18, bold=False)

    l_draw.text((100, 90), "FNSKU", fill=(0, 0, 0), font=font_macro_title)
    l_draw.text((100, 140), fnsku, fill=(0, 0, 0), font=font_macro_code)
    l_draw.text((100, 185), f"Item: {product_name} - Amazon Inbound Ready", fill=(60, 60, 60), font=font_macro_sub)

    # Macro barcode
    draw_barcode(l_draw, 100, 240, 540, 180, fnsku)
    l_draw.text((250, 440), fnsku, fill=(30, 30, 30), font=font_macro_code)

    # Save to all target paths
    for d in OUTPUT_DIRS:
        f_p = os.path.join(d, f"{unit_id}_front.jpg")
        b_p = os.path.join(d, f"{unit_id}_back.jpg")
        l_p = os.path.join(d, f"{unit_id}_label.jpg")
        front_img.save(f_p, "JPEG", quality=95)
        back_img.save(b_p, "JPEG", quality=95)
        label_img.save(l_p, "JPEG", quality=95)

    print(f"Generated 3-view dataset images for: {unit_id}")
    return front_img, back_img, label_img

if __name__ == "__main__":
    # 1. Sealed Polybag Toy (PASS)
    create_polybag_unit(
        unit_id="UNIT-POLY-0001",
        product_name="TOY PUZZLE SET (500 PCS)",
        fnsku="X001POLYBAG",
        sealed=True,
        has_warning=True,
        barcode_covered=True,
        handling_mark="LIQUID"
    )

    # 2. Sealed Polybag Apparel / Textile (PASS)
    create_polybag_unit(
        unit_id="UNIT-POLY-0002",
        product_name="COTTON CREWNECK TEE (NAVY)",
        fnsku="X002APPAREL",
        sealed=True,
        has_warning=True,
        barcode_covered=True,
        handling_mark=""
    )

    # 3. Sealed Polybag Bottle / Cosmetics (PASS)
    create_polybag_unit(
        unit_id="UNIT-POLY-0003",
        product_name="ORGANIC SHAMPOO BOTTLE",
        fnsku="X003SHAMPOO",
        sealed=True,
        has_warning=True,
        barcode_covered=True,
        handling_mark="LIQUID"
    )

    # 4. Defective: Polybag Not Sealed (FAIL - polybag_not_sealed)
    create_polybag_unit(
        unit_id="UNIT-POLY-OPEN",
        product_name="KITCHEN TOWEL PACK",
        fnsku="X004OPENSEAL",
        sealed=False,
        has_warning=True,
        barcode_covered=True,
        handling_mark=""
    )

    # 5. Defective: Polybag Missing Suffocation Warning (FAIL - missing_warning)
    create_polybag_unit(
        unit_id="UNIT-POLY-NOWARN",
        product_name="PLUSH TEDDY BEAR",
        fnsku="X005NOWARN",
        sealed=True,
        has_warning=False,
        barcode_covered=True,
        handling_mark=""
    )
    print("All polybag test images successfully created!")
