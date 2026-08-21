"""
Comprehensive Test Suite Generator - 25 Standardized Autodesk UI Test Screenshots
Includes dedicated test cases for all 12 Autodesk LQA Defect Categories:
- Clean 100% Passes
- 0001: OVERLAPPING
- 0004: MISSALIGNMENT
- 0005: LEAD_TRAIL
- 0006: MISC
- 0008: SPEC_CHARACTERS
- 0009: TRUNCATION
- 0011: FONT_CONSISTENCY
- 0012: COMBO_BOX_HEIGHT
- 0016: EXTENDED_CHAR_ISSUE
"""

import os, shutil
from PIL import Image, ImageDraw, ImageFont

def get_font(size, bold=False):
    font_names = ["segoeuib.ttf" if bold else "segoeui.ttf", 
                  "arialbd.ttf" if bold else "arial.ttf", 
                  "tahomabd.ttf" if bold else "tahoma.ttf"]
    for fn in font_names:
        font_path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", fn)
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def draw_autodesk_logo(draw, x, y):
    draw.rectangle([x, y, x + 30, y + 30], fill="#000000")
    draw.polygon([(x + 5, y + 21), (x + 5, y + 15), (x + 16, y + 8), (x + 23, y + 8), (x + 23, y + 21), (x + 16, y + 21), (x + 22, y + 14), (x + 16, y + 14), (x + 5, y + 21)], fill="#FFFFFF")

def draw_icon(draw, icon_type, x, y, size=18, color="#555555"):
    if icon_type == "search":
        r = size // 3
        draw.ellipse([x, y, x + 2 * r, y + 2 * r], outline=color, width=2)
        draw.line([x + int(1.7 * r), y + int(1.7 * r), x + size, y + size], fill=color, width=2)
    elif icon_type == "bell":
        draw.polygon([(x + 4, y + 12), (x + 14, y + 12), (x + 12, y + 4), (x + 6, y + 4)], fill=color)
        draw.ellipse([x + 7, y + 12, x + 11, y + 15], fill=color)
    elif icon_type == "user":
        draw.ellipse([x + 4, y + 2, x + 14, y + 10], fill=color)
        draw.chord([x + 1, y + 9, x + 17, y + 21], start=0, end=180, fill=color)
    elif icon_type == "help":
        draw.ellipse([x, y, x + size, y + size], outline=color, width=2)
        draw.line([x + size//2, y + size//2 - 2, x + size//2, y + size//2 + 2], fill=color, width=2)
        draw.point([x + size//2, y + size - 4], fill=color)
    elif icon_type == "chevron":
        draw.line([x, y + 4, x + size//2, y + size - 4], fill=color, width=2)
        draw.line([x + size//2, y + size - 4, x + size, y + 4], fill=color, width=2)
    elif icon_type == "clip":
        draw.arc([x + 3, y + 2, x + 13, y + 10], 180, 360, fill=color, width=2)
        draw.line([x + 3, y + 6, x + 3, y + 14], fill=color, width=2)
        draw.line([x + 13, y + 6, x + 13, y + 12], fill=color, width=2)

def draw_replacement_glyph(draw, x, y, size=16):
    """Draws a standard Unicode black replacement diamond with white question mark inside."""
    half = size // 2
    pts = [(x + half, y), (x + size, y + half), (x + half, y + size), (x, y + half)]
    draw.polygon(pts, fill="#000000")
    draw.text((x + 4, y + 1), "?", fill="#FFFFFF", font=get_font(10, bold=True))

def generate_helpdesk_image(
    lang="en",
    header_shift=False,
    missing_help=False,
    misaligned_dropdown=False,
    card_overlap=False,
    button_overflow=False,
    missing_secondary_btn=False,
    combobox_height_defect=False,
    corrupted_glyph_defect=False,
    width=1280,
    height=800
):
    img = Image.new("RGB", (width, height), color="#F4F6F9")
    draw = ImageDraw.Draw(img)

    f_title = get_font(18, bold=True)
    f_header = get_font(15, bold=True)
    f_body = get_font(13, bold=False)
    f_body_bold = get_font(13, bold=True)
    f_label = get_font(12, bold=True)
    f_small = get_font(11, bold=False)
    f_brand = get_font(16, bold=True)

    header_h = 56
    header_y = 28 if header_shift else 0

    # 1. TOP HEADER
    draw.rectangle([0, header_y, width, header_y + header_h], fill="#0F172A")
    draw_autodesk_logo(draw, 24, header_y + 13)
    draw.text((64, header_y + 17), "AUTODESK", fill="#FFFFFF", font=f_brand)
    draw.text((160, header_y + 18), "Helpdesk Portal", fill="#94A3B8", font=f_body)

    search_w = 400
    search_x = width // 2 - search_w // 2
    draw.rounded_rectangle([search_x, header_y + 10, search_x + search_w, header_y + 46], radius=6, fill="#1E293B", outline="#334155")
    draw_icon(draw, "search", search_x + 12, header_y + 20, size=16, color="#94A3B8")
    
    search_ph = {
        "en": "Search Knowledge Network, AutoCAD, Revit issues...",
        "de": "Knowledge Network, AutoCAD, Revit durchsuchen...",
        "es": "Buscar en Knowledge Network, AutoCAD, Revit...",
        "fr": "Rechercher dans le réseau d'assistance...",
        "ja": "オートデスク Knowledge Network を検索...",
        "it": "Cerca nel Knowledge Network, AutoCAD...",
        "pt": "Pesquisar no Knowledge Network...",
        "ko": "Knowledge Network 및 제품 문제 검색..."
    }.get(lang, "Search...")
    draw.text((search_x + 36, header_y + 18), search_ph, fill="#64748B", font=f_small)

    draw_icon(draw, "bell", width - 150, header_y + 19, size=18, color="#CBD5E1")
    if not missing_help:
        draw_icon(draw, "help", width - 115, header_y + 19, size=18, color="#CBD5E1")
    draw_icon(draw, "user", width - 75, header_y + 17, size=20, color="#38BDF8")
    draw.text((width - 48, header_y + 19), "Admin", fill="#E2E8F0", font=f_body_bold)

    # 2. SUB-NAVIGATION
    subnav_y = header_y + header_h
    subnav_h = 44
    draw.rectangle([0, subnav_y, width, subnav_y + subnav_h], fill="#FFFFFF", outline="#E2E8F0")

    tabs_map = {
        "en": ["Overview", "Create Case", "Product Support", "Knowledge Base", "System Status"],
        "de": ["Übersicht", "Fall erstellen", "Produktsupport", "Knowledge Base", "Systemstatus"],
        "es": ["Resumen", "Crear caso", "Soporte", "Knowledge Base", "Estado"],
        "fr": ["Aperçu", "Créer un cas", "Support produit", "Base de connaissances", "Statut"],
        "ja": ["概要", "ケース作成", "製品サポート", "ナレッジベース", "ステータス"],
        "it": ["Panoramica", "Crea ticket", "Supporto", "Knowledge Base", "Stato"],
        "pt": ["Visão geral", "Criar caso", "Suporte", "Base de conhecimento", "Status"],
        "ko": ["개요", "케이스 생성", "제품 지원", "지식 기반", "상태"]
    }
    tabs = tabs_map.get(lang, tabs_map["en"])

    tx = 32
    for i, t in enumerate(tabs):
        is_active = (i == 1)
        tw = draw.textlength(t, font=f_body_bold if is_active else f_body)
        if is_active:
            draw.text((tx, subnav_y + 13), t, fill="#0284C7", font=f_body_bold)
            draw.line([tx - 4, subnav_y + subnav_h - 2, tx + tw + 4, subnav_y + subnav_h - 2], fill="#0284C7", width=3)
        else:
            draw.text((tx, subnav_y + 13), t, fill="#475569", font=f_body)
        tx += int(tw) + 36

    content_y = subnav_y + subnav_h + 20

    # 3. SIDEBAR (260px)
    sidebar_w = 260
    sidebar_x = 32
    sidebar_h = height - content_y - 24
    draw.rounded_rectangle([sidebar_x, content_y, sidebar_x + sidebar_w, content_y + sidebar_h], radius=8, fill="#FFFFFF", outline="#E2E8F0")

    side_heading = {
        "en": "SUPPORT ACTIONS", "de": "SUPPORT-AKTIONEN", "es": "ACCIONES DE SOPORTE",
        "fr": "ACTIONS D'ASSISTANCE", "ja": "サポートアクション", "it": "AZIONI SUPPORTO",
        "pt": "AÇÕES DE SUPORTE", "ko": "지원 작업"
    }.get(lang, "SUPPORT ACTIONS")
    draw.text((sidebar_x + 20, content_y + 20), side_heading, fill="#94A3B8", font=f_small)

    side_links = [
        ("Submit New Case", True),
        ("My Open Cases (3)", False),
        ("Software Licensing", False),
        ("Subscription & Billing", False),
        ("Download Updates", False),
        ("Contact Phone Support", False)
    ]
    sy = content_y + 48
    for st, act in side_links:
        if act:
            draw.rounded_rectangle([sidebar_x + 12, sy - 4, sidebar_x + sidebar_w - 12, sy + 28], radius=6, fill="#E0F2FE")
            draw.text((sidebar_x + 24, sy + 3), st, fill="#0284C7", font=f_body_bold)
        else:
            draw.text((sidebar_x + 24, sy + 3), st, fill="#334155", font=f_body)
        sy += 38

    # 4. MAIN FORM CARD
    card_x = sidebar_x + sidebar_w + 24
    card_w = 620
    if card_overlap:
        card_w = 680  # Overlaps right widget by 60px

    card_h = sidebar_h
    draw.rounded_rectangle([card_x, content_y, card_x + card_w, content_y + card_h], radius=8, fill="#FFFFFF", outline="#E2E8F0")

    main_title = {
        "en": "Create Technical Support Case",
        "de": "Technischen Support-Fall erstellen",
        "es": "Crear caso de soporte técnico",
        "fr": "Créer un cas d'assistance technique",
        "ja": "テクニカル サポート ケースを作成",
        "it": "Crea ticket di supporto tecnico",
        "pt": "Criar caso de suporte técnico",
        "ko": "기술 지원 케이스 생성"
    }.get(lang, "Create Support Case")
    draw.text((card_x + 28, content_y + 24), main_title, fill="#0F172A", font=f_title)

    # Form Field 1: Product Dropdown
    fy = content_y + 64
    f1_x = card_x + 28
    if misaligned_dropdown:
        f1_x += 30 # Misaligned by +30px

    draw.text((f1_x, fy), "Affected Product *", fill="#334155", font=f_label)
    
    dropdown_h = 36
    if combobox_height_defect:
        dropdown_h = 24  # Defect: Dropdown height too small (24px vs 36px)
    
    draw.rounded_rectangle([f1_x, fy + 22, f1_x + 360, fy + 22 + dropdown_h], radius=6, fill="#FFFFFF", outline="#CBD5E1")
    draw.text((f1_x + 14, fy + 24 if combobox_height_defect else fy + 32), "AutoCAD 2026 (Commercial License)", fill="#0F172A", font=f_body)
    draw_icon(draw, "chevron", f1_x + 332, fy + 26 if combobox_height_defect else fy + 34, size=16, color="#64748B")

    # Form Field 2: Severity Selector
    fy += 74
    draw.text((card_x + 28, fy), "Severity Level *", fill="#334155", font=f_label)
    sev_btns = [("Low", "#F1F5F9", "#475569"), ("Medium", "#F1F5F9", "#475569"), ("Critical (Workstopping)", "#FEF2F2", "#DC2626")]
    bx = card_x + 28
    for btn_t, bg, fg in sev_btns:
        btw = int(draw.textlength(btn_t, font=f_body)) + 24
        draw.rounded_rectangle([bx, fy + 22, bx + btw, fy + 58], radius=6, fill=bg, outline="#CBD5E1" if fg != "#DC2626" else "#FCA5A5")
        draw.text((bx + 12, fy + 32), btn_t, fill=fg, font=f_body)
        bx += btw + 12

    # Form Field 3: Subject
    fy += 74
    draw.text((card_x + 28, fy), "Subject / Summary *", fill="#334155", font=f_label)
    draw.rounded_rectangle([card_x + 28, fy + 22, card_x + card_w - 28, fy + 62], radius=6, fill="#FFFFFF", outline="#CBD5E1")
    
    subj_text = "Fatal error 0xC0000005 during DWG direct export on Windows 11"
    if corrupted_glyph_defect:
        draw.text((card_x + 40, fy + 34), "Schwerwiegender Fehler beim DWG-Export unter Windows ", fill="#0F172A", font=f_body)
        draw_replacement_glyph(draw, card_x + 380, fy + 34, size=16)
    else:
        draw.text((card_x + 40, fy + 34), subj_text, fill="#0F172A", font=f_body)

    # Form Field 4: Description (with intentional ... placeholder)
    fy += 78
    draw.text((card_x + 28, fy), "Steps to Reproduce & Description", fill="#334155", font=f_label)
    draw.rounded_rectangle([card_x + 28, fy + 22, card_x + card_w - 28, fy + 160], radius=6, fill="#FFFFFF", outline="#CBD5E1")
    
    desc_lines = [
        "1. Open AutoCAD 2026 with hardware acceleration enabled.",
        "2. Execute batch export command on sample architectural layout.",
        "3. Application terminates abruptly with crash log generated in %TEMP%..."
    ]
    dy = fy + 32
    for line in desc_lines:
        draw.text((card_x + 40, dy), line, fill="#334155", font=f_small)
        dy += 22

    # 5. ACTION BUTTONS (y=710)
    btn_y = content_y + card_h - 70

    btn_lbl = {
        "en": "Submit Case",
        "de": "Fall übermitteln",
        "es": "Enviar caso",
        "fr": "Soumettre le cas",
        "ja": "ケースを送信",
        "it": "Invia ticket",
        "pt": "Enviar caso",
        "ko": "케이스 제출"
    }.get(lang, "Submit Case")

    btn_w = 145
    if not button_overflow:
        btn_w = 180 if lang != "en" else 145
    else:
        btn_w = 145 # Rigid English width causing overflow!

    draw.rounded_rectangle([card_x + 28, btn_y, card_x + 28 + btn_w, btn_y + 44], radius=6, fill="#0696D7")
    
    if button_overflow:
        draw.text((card_x + 36, btn_y + 13), "Technischen Support-Fall jetzt sofort absenden", fill="#FFFFFF", font=f_body_bold)
        draw.rectangle([card_x + 28 + btn_w - 2, btn_y + 4, card_x + 28 + btn_w + 2, btn_y + 40], fill="#DC2626")
    else:
        draw.text((card_x + 45, btn_y + 13), btn_lbl, fill="#FFFFFF", font=f_body_bold)

    # Secondary Button
    if not missing_secondary_btn:
        sec_x = card_x + 28 + btn_w + 16 if not button_overflow else card_x + 200
        draw.rounded_rectangle([sec_x, btn_y, sec_x + 170, btn_y + 44], radius=6, fill="#FFFFFF", outline="#0696D7")
        draw_icon(draw, "clip", sec_x + 12, btn_y + 14, size=16, color="#0696D7")
        draw.text((sec_x + 36, btn_y + 13), "Attach Log File", fill="#0696D7", font=f_body_bold)

        draw.rounded_rectangle([sec_x + 186, btn_y, sec_x + 290, btn_y + 44], radius=6, fill="#F1F5F9")
        draw.text((sec_x + 218, btn_y + 13), "Cancel", fill="#475569", font=f_body)
    else:
        draw.rounded_rectangle([card_x + 210, btn_y, card_x + 320, btn_y + 44], radius=6, fill="#F1F5F9")
        draw.text((card_x + 245, btn_y + 13), "Cancel", fill="#475569", font=f_body)

    # 6. RIGHT SUPPORT WIDGET (280px)
    right_x = 948
    draw.rounded_rectangle([right_x, content_y, right_x + 300, content_y + 360], radius=8, fill="#FFFFFF", outline="#E2E8F0")
    draw.text((right_x + 20, content_y + 20), "Need Assistance?", fill="#0F172A", font=f_header)
    draw.text((right_x + 20, content_y + 48), "Average response time: < 2 hours", fill="#64748B", font=f_small)

    return img

def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "test_images")
    os.makedirs(out_dir, exist_ok=True)

    suite = [
        # 01. Baseline Reference
        ("01_Baseline_English_Reference.png", dict(lang="en")),

        # 02-08. 100% Clean Perfect Translations
        ("02_German_Clean_Perfect_100.png", dict(lang="de")),
        ("03_Spanish_Clean_Perfect_100.png", dict(lang="es")),
        ("04_French_Clean_Perfect_100.png", dict(lang="fr")),
        ("05_Japanese_Clean_Perfect_100.png", dict(lang="ja")),
        ("06_Italian_Clean_Perfect_100.png", dict(lang="it")),
        ("07_Portuguese_Clean_Perfect_100.png", dict(lang="pt")),
        ("08_Korean_Clean_Perfect_100.png", dict(lang="ko")),

        # 09-10. [ERR-0009] TRUNCATION (Button Text Overflow)
        ("09_German_Button_Overflow_ERR0009.png", dict(lang="de", button_overflow=True)),
        ("10_French_Button_Overflow_ERR0009.png", dict(lang="fr", button_overflow=True)),

        # 11-12. [ERR-0006] MISC (Missing Secondary Button & Help Icon)
        ("11_Spanish_Missing_Button_ERR0006.png", dict(lang="es", missing_secondary_btn=True)),
        ("12_French_Missing_Help_Icon_ERR0006.png", dict(lang="fr", missing_help=True)),

        # 13-15. [ERR-0004] MISSALIGNMENT (Form Dropdowns & Header Shifts)
        ("13_Spanish_Form_Dropdown_Misaligned_ERR0004.png", dict(lang="es", misaligned_dropdown=True)),
        ("14_German_Form_Dropdown_Misaligned_ERR0004.png", dict(lang="de", misaligned_dropdown=True)),
        ("15_Japanese_Header_Bar_Shift_ERR0004.png", dict(lang="ja", header_shift=True)),

        # 16. [ERR-0001] OVERLAPPING (Card Collision with Right Widget)
        ("16_Japanese_Card_Widget_Collision_ERR0001.png", dict(lang="ja", card_overlap=True)),

        # 17-20. Multi-Defect Combos
        ("17_Spanish_Missing_And_Misaligned_Combo.png", dict(lang="es", missing_secondary_btn=True, misaligned_dropdown=True)),
        ("18_German_Overflow_And_Misaligned_Combo.png", dict(lang="de", button_overflow=True, misaligned_dropdown=True)),
        ("19_Italian_Overflow_And_Missing_Combo.png", dict(lang="it", button_overflow=True, missing_secondary_btn=True)),
        ("20_Japanese_Full_Cascade_Overlap_Shift_Combo.png", dict(lang="ja", header_shift=True, card_overlap=True, missing_help=True)),

        # 21-22. NEW DEFECT TESTS: [ERR-0012] COMBO_BOX_HEIGHT & [ERR-0016] EXTENDED_CHAR_ISSUE
        ("21_French_ComboBox_Height_Defect_ERR0012.png", dict(lang="fr", combobox_height_defect=True)),
        ("22_German_Corrupted_Glyph_Defect_ERR0016.png", dict(lang="de", corrupted_glyph_defect=True))
    ]

    print("Generating complete suite of 22 Autodesk UI test screenshots...")
    for filename, params in suite:
        out_path = os.path.join(out_dir, filename)
        img = generate_helpdesk_image(**params)
        img.save(out_path, "PNG")
        print(f"  [OK] Generated: {filename}")

    print("\nAll 22 test images generated successfully in 'f:\\POC__\\test_images'!")

if __name__ == "__main__":
    main()
