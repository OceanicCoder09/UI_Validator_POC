"""
Generate a complete suite of test images for UI Validator testing.
"""
import os
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

def generate_screenshot(scenario="en_baseline", width=1280, height=800):
    img = Image.new("RGB", (width, height), color="#F8FAFC")
    draw = ImageDraw.Draw(img)

    f_title = get_font(18, bold=True)
    f_header = get_font(15, bold=True)
    f_body = get_font(13, bold=False)
    f_body_bold = get_font(13, bold=True)
    f_label = get_font(12, bold=True)
    f_small = get_font(11, bold=False)
    f_brand = get_font(16, bold=True)

    header_h = 56
    header_y = 28 if scenario == "ja_shift_overlap" else 0

    # Top Header
    draw.rectangle([0, header_y, width, header_y + header_h], fill="#000000")
    draw_autodesk_logo(draw, 24, header_y + 13)
    draw.text((64, header_y + 17), "AUTODESK", fill="#FFFFFF", font=f_brand)
    draw.text((165, header_y + 19), "Helpdesk Portal", fill="#94A3B8", font=f_body)

    # Search Bar
    search_w = 400
    search_x = width // 2 - search_w // 2
    draw.rectangle([search_x, header_y + 10, search_x + search_w, header_y + 46], fill="#1E293B", outline="#334155")
    draw_icon(draw, "search", search_x + 12, header_y + 20, size=16, color="#94A3B8")
    
    search_text = {
        "en_baseline": "Search Knowledge Network, AutoCAD, Revit issues...",
        "de_clean": "Knowledge Network, AutoCAD, Revit durchsuchen...",
        "de_truncation": "Knowledge Network, AutoCAD, Revit Probleme durchsuchen...",
        "es_missing": "Buscar en Knowledge Network, AutoCAD, Revit...",
        "ja_shift": "オートデスク Knowledge Network、Revit を検索..."
    }.get(scenario, "Search...")
    draw.text((search_x + 36, header_y + 18), search_text, fill="#64748B", font=f_small)

    draw_icon(draw, "bell", width - 150, header_y + 19, size=18, color="#CBD5E1")
    if scenario != "ja_shift":
        draw_icon(draw, "help", width - 115, header_y + 19, size=18, color="#CBD5E1")
    draw_icon(draw, "user", width - 75, header_y + 17, size=20, color="#38BDF8")
    draw.text((width - 48, header_y + 19), "Admin", fill="#E2E8F0", font=f_body_bold)

    # Sub-nav
    subnav_y = header_y + header_h
    subnav_h = 44
    draw.rectangle([0, subnav_y, width, subnav_y + subnav_h], fill="#FFFFFF", outline="#E2E8F0")
    
    nav_links = {
        "en_baseline": ["Support Home", "My Tickets (3)", "Product Downloads", "Knowledge Base", "System Health"],
        "de_clean": ["Support-Startseite", "Meine Tickets (3)", "Downloads", "Wissensdatenbank", "Systemstatus"],
        "de_truncation": ["Support-Startseite", "Meine Support-Tickets (3)", "Produkt-Downloads", "Wissensdatenbank", "Systemstatus"],
        "es_missing": ["Inicio de Soporte", "Mis Casos (3)", "Descargas", "Base de Conocimiento", "Estado"],
        "ja_shift": ["サポートホーム", "マイチケット (3)", "ダウンロード", "ナレッジベース", "システム状態"]
    }.get(scenario, ["Support Home", "My Tickets", "Downloads"])

    nx = 24
    for idx, item in enumerate(nav_links):
        is_active = (idx == 1)
        color = "#0696D7" if is_active else "#475569"
        draw.text((nx, subnav_y + 13), item, fill=color, font=f_body_bold if is_active else f_body)
        if is_active:
            draw.rectangle([nx, subnav_y + subnav_h - 3, nx + 90, subnav_y + subnav_h], fill="#0696D7")
        nx += 180

    # Left Sidebar (240px)
    sidebar_y = subnav_y + subnav_h
    draw.rectangle([0, sidebar_y, 240, height], fill="#FFFFFF", outline="#E2E8F0")
    
    side_heading = {
        "en_baseline": "SUPPORT ACTIONS",
        "de_clean": "SUPPORT-AKTIONEN",
        "de_truncation": "SUPPORT-AKTIONEN",
        "es_missing": "ACCIONES DE SOPORTE",
        "ja_shift": "サポートアクション"
    }.get(scenario, "SUPPORT ACTIONS")
    draw.text((24, sidebar_y + 24), side_heading, fill="#94A3B8", font=f_small)

    side_items = {
        "en_baseline": ["Submit New Ticket", "View Open Cases (3)", "Software Licensing", "Subscription & Billing", "Contact Phone Support"],
        "de_clean": ["Neues Ticket erstellen", "Offene Fälle anzeigen (3)", "Software-Lizenzierung", "Abonnement & Abrechnung", "Telefonischer Support"],
        "de_truncation": ["Neues Support-Ticket erfassen", "Offene Support-Fälle (3)", "Software-Lizenzverwaltung", "Abonnement und Abrechnung", "Telefon-Support kontaktieren"],
        "es_missing": ["Crear Nuevo Ticket", "Ver Casos Abiertos (3)", "Licencias de Software", "Suscripción y Facturas", "Soporte Telefónico"],
        "ja_shift": ["新規チケット作成", "対応中の案件 (3)", "ライセンス管理", "契約と請求", "電話サポート"]
    }.get(scenario, ["Submit Ticket", "View Cases"])

    sy = sidebar_y + 55
    for idx, sitem in enumerate(side_items):
        is_active = (idx == 0)
        draw.rectangle([12, sy - 6, 228, sy + 28], fill="#E0F2FE" if is_active else "#FFFFFF")
        draw.text((24, sy), sitem, fill="#0284C7" if is_active else "#334155", font=f_body_bold if is_active else f_body)
        sy += 40

    # Main Card
    main_x = 264
    main_y = sidebar_y + 24
    main_w = 660
    if scenario == "ja_shift":
        main_w = 720 # Overlaps right widget

    draw.rectangle([main_x, main_y, main_x + main_w, main_y + 610], fill="#FFFFFF", outline="#E2E8F0")

    card_title = {
        "en_baseline": "Create Technical Support Ticket",
        "de_clean": "Technisches Support-Ticket erstellen",
        "de_truncation": "Technisches Support-Ticket erfassen",
        "es_missing": "Crear Caso de Soporte Técnico",
        "ja_shift": "技術サポートチケットを作成"
    }.get(scenario, "Create Support Ticket")
    draw.text((main_x + 24, main_y + 24), card_title, fill="#0F172A", font=f_title)

    # Form Fields
    form_y = main_y + 70

    # Product Dropdown
    lbl_prod = {
        "en_baseline": "Affected Autodesk Product *",
        "de_clean": "Betroffenes Autodesk-Produkt *",
        "de_truncation": "Betroffenes Autodesk-Produkt *",
        "es_missing": "Producto de Autodesk Afectado *",
        "ja_shift": "対象製品 *"
    }.get(scenario, "Product *")

    dropdown_x = main_x + 24
    if scenario == "es_missing":
        dropdown_x += 28 # Misalignment defect

    draw.text((dropdown_x, form_y), lbl_prod, fill="#334155", font=f_label)
    draw.rectangle([dropdown_x, form_y + 20, dropdown_x + 400, form_y + 56], fill="#F8FAFC", outline="#CBD5E1")
    
    val_prod = {
        "en_baseline": "AutoCAD 2026 (Commercial License)",
        "de_clean": "AutoCAD 2026 (Kommerzielle Lizenz)",
        "de_truncation": "AutoCAD 2026 (Kommerzielle Lizenz)",
        "es_missing": "AutoCAD 2026 (Licencia Comercial)",
        "ja_shift": "AutoCAD 2026 (商用ライセンス)"
    }.get(scenario, "AutoCAD 2026")
    draw.text((dropdown_x + 14, form_y + 28), val_prod, fill="#0F172A", font=f_body)
    draw_icon(draw, "chevron", dropdown_x + 372, form_y + 30, size=16, color="#64748B")

    # Issue Subject
    form_y += 75
    lbl_subj = {
        "en_baseline": "Issue Subject *",
        "de_clean": "Betreff des Problems *",
        "de_truncation": "Betreff des Support-Falls *",
        "es_missing": "Asunto del Problema *",
        "ja_shift": "問題の件名 *"
    }.get(scenario, "Subject *")
    draw.text((main_x + 24, form_y), lbl_subj, fill="#334155", font=f_label)
    draw.rectangle([main_x + 24, form_y + 20, main_x + 600, form_y + 56], fill="#F8FAFC", outline="#CBD5E1")
    
    val_subj = {
        "en_baseline": "License activation error code 0x80070005 on Windows 11",
        "de_clean": "Lizenzaktivierungsfehler 0x80070005 unter Windows 11",
        "de_truncation": "Lizenzaktivierungsfehler 0x80070005 auf Windows 11 Arbeitsstation",
        "es_missing": "Error de activación de licencia 0x80070005 en Windows 11",
        "ja_shift": "Windows 11 でのライセンス認証エラー 0x80070005"
    }.get(scenario, "License error")
    draw.text((main_x + 38, form_y + 28), val_subj, fill="#0F172A", font=f_body)

    # Description Textarea with intentional placeholder
    form_y += 75
    lbl_desc = {
        "en_baseline": "Detailed Description *",
        "de_clean": "Detaillierte Fehlerbeschreibung *",
        "de_truncation": "Detaillierte Fehlerbeschreibung *",
        "es_missing": "Descripción Detallada *",
        "ja_shift": "詳細な説明 *"
    }.get(scenario, "Description *")
    draw.text((main_x + 24, form_y), lbl_desc, fill="#334155", font=f_label)
    draw.rectangle([main_x + 24, form_y + 20, main_x + 600, form_y + 110], fill="#F8FAFC", outline="#CBD5E1")
    
    ph_desc = {
        "en_baseline": "Please provide detailed steps to reproduce the issue, exact error messages, and workflow...",
        "de_clean": "Bitte geben Sie detaillierte Schritte zur Reproduktion des Fehlers und genaue Meldungen an...",
        "de_truncation": "Bitte geben Sie detaillierte Schritte zur Reproduktion des Problems und genaue Meldungen an...",
        "es_missing": "Por favor proporcione pasos detallados para reproducir el problema y mensajes de error...",
        "ja_shift": "問題を再現するための詳細な手順と正確なエラーメッセージを入力してください..."
    }.get(scenario, "Please describe...")
    draw.text((main_x + 38, form_y + 30), ph_desc, fill="#64748B", font=f_small)

    # Buttons Bar
    btn_y = form_y + 130
    
    # Primary Button
    btn_w = 145 # Fixed English width
    btn_text = {
        "en_baseline": "Submit Ticket",
        "de_clean": "Ticket senden",
        "de_truncation": "Support-Ticket jetzt absenden", # Overflows 145px
        "es_missing": "Enviar Ticket",
        "ja_shift": "チケット送信"
    }.get(scenario, "Submit")

    if scenario == "de_clean":
        btn_w = 160 # German clean expands properly
    
    draw.rectangle([main_x + 24, btn_y, main_x + 24 + btn_w, btn_y + 44], fill="#0284C7")
    draw.text((main_x + 40, btn_y + 12), btn_text, fill="#FFFFFF", font=f_body_bold)

    # If German overflow defect, draw spill
    if scenario == "de_truncation":
        draw.text((main_x + 24 + btn_w + 5, btn_y + 12), "-> Overflow past border!", fill="#DC2626", font=f_body_bold)

    # Secondary Button
    if scenario != "es_missing":
        sec_text = {
            "en_baseline": "Attach Log File",
            "de_clean": "Protokolldatei anhängen",
            "de_truncation": "Log-Datei anhängen",
            "ja_shift": "ログファイルを添付"
        }.get(scenario, "Attach Log")
        draw.rectangle([main_x + 24 + btn_w + 16, btn_y, main_x + 24 + btn_w + 180, btn_y + 44], fill="#FFFFFF", outline="#0284C7")
        draw_icon(draw, "clip", main_x + 36 + btn_w, btn_y + 13, size=16, color="#0284C7")
        draw.text((main_x + 58 + btn_w, btn_y + 12), sec_text, fill="#0284C7", font=f_body_bold)

    # Right Support Widget (280px)
    right_x = 948
    draw.rectangle([right_x, sidebar_y + 24, right_x + 280, sidebar_y + 400], fill="#FFFFFF", outline="#E2E8F0")
    draw.text((right_x + 20, sidebar_y + 44), "Need Urgent Assistance?", fill="#0F172A", font=f_header)
    draw.text((right_x + 20, sidebar_y + 75), "Average response time: < 2 hours", fill="#64748B", font=f_small)

    return img

def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "test_images")
    os.makedirs(out_dir, exist_ok=True)

    scenarios = [
        ("01_Baseline_English.png", "en_baseline"),
        ("02_German_Clean_Perfect.png", "de_clean"),
        ("03_German_Button_Truncation_Overflow.png", "de_truncation"),
        ("04_Spanish_Missing_Button_And_Misalignment.png", "es_missing"),
        ("05_Japanese_Header_Shift_And_Collision.png", "ja_shift"),
    ]

    print("Generating complete UI test images suite...")
    for filename, scenario in scenarios:
        out_path = os.path.join(out_dir, filename)
        img = generate_screenshot(scenario)
        img.save(out_path, "PNG")
        print(f"  [OK] Created: {out_path}")

    print("\nAll test images successfully created in 'f:\\POC__\\test_images'!")

if __name__ == "__main__":
    main()
