"""
Autodesk Helpdesk UI Screenshot Dataset Generator
Generates clean, pixel-perfect 1280x800 Autodesk Helpdesk screenshots
(English, German, Spanish, Japanese) for UI Quality validation.
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
    draw.rounded_rectangle([x, y, x + 30, y + 30], radius=6, fill="#0696D7")
    draw.polygon([(x + 7, y + 23), (x + 15, y + 7), (x + 23, y + 23), (x + 18, y + 23), (x + 15, y + 14), (x + 12, y + 23)], fill="#FFFFFF")
    draw.polygon([(x + 15, y + 14), (x + 20, y + 20), (x + 17, y + 20)], fill="#E0F2FE")

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

def generate_helpdesk_screenshot(scenario="en_baseline", width=1280, height=800):
    img = Image.new("RGB", (width, height), color="#F4F6F9")
    draw = ImageDraw.Draw(img)

    f_title = get_font(18, bold=True)
    f_header = get_font(15, bold=True)
    f_body = get_font(13, bold=False)
    f_body_bold = get_font(13, bold=True)
    f_label = get_font(12, bold=True)
    f_small = get_font(11, bold=False)
    f_brand = get_font(16, bold=True)

    # 1. TOP HEADER (56px)
    header_h = 56
    header_y = 0
    if scenario == "ja_shift_overlap":
        header_y = 28  # Major Defect: Header shifted 28px downward

    draw.rectangle([0, header_y, width, header_y + header_h], fill="#0F172A")
    
    draw_autodesk_logo(draw, 24, header_y + 13)
    draw.text((64, header_y + 17), "AUTODESK", fill="#FFFFFF", font=f_brand)
    draw.text((160, header_y + 18), "Helpdesk Portal", fill="#94A3B8", font=f_body)

    search_w = 400
    search_x = width // 2 - search_w // 2
    draw.rounded_rectangle([search_x, header_y + 10, search_x + search_w, header_y + 46], radius=6, fill="#1E293B", outline="#334155")
    draw_icon(draw, "search", search_x + 12, header_y + 20, size=16, color="#94A3B8")
    search_ph = {
        "en_baseline": "Search Knowledge Network, AutoCAD, Revit issues...",
        "de_perfect": "Knowledge Network, AutoCAD, Revit durchsuchen...",
        "de_expansion_defect": "Knowledge Network, AutoCAD, Revit Probleme durchsuchen...",
        "es_missing_misaligned": "Buscar en Knowledge Network, AutoCAD, Revit...",
        "ja_shift_overlap": "オートデスク Knowledge Network、Revit を検索..."
    }.get(scenario, "Search...")
    draw.text((search_x + 36, header_y + 18), search_ph, fill="#64748B", font=f_small)

    draw_icon(draw, "bell", width - 150, header_y + 19, size=18, color="#CBD5E1")
    if scenario != "ja_shift_overlap":
        draw_icon(draw, "help", width - 115, header_y + 19, size=18, color="#CBD5E1")
    draw_icon(draw, "user", width - 75, header_y + 17, size=20, color="#38BDF8")
    draw.text((width - 48, header_y + 19), "Admin", fill="#E2E8F0", font=f_body_bold)

    # 2. SUB-NAVIGATION (44px)
    subnav_y = header_y + header_h
    subnav_h = 44
    draw.rectangle([0, subnav_y, width, subnav_y + subnav_h], fill="#FFFFFF", outline="#E2E8F0")

    tabs_en = ["Overview", "Create Case", "Product Support", "Knowledge Base", "System Status"]
    tabs_de = ["Übersicht", "Fall erstellen", "Produktsupport", "Knowledge Base", "Systemstatus"]
    tabs_es = ["Resumen", "Crear caso", "Soporte", "Knowledge Base", "Estado"]
    tabs_ja = ["概要", "ケース作成", "製品サポート", "ナレッジベース", "ステータス"]

    tabs = tabs_en
    if scenario in ["de_perfect", "de_expansion_defect"]:
        tabs = tabs_de
    elif scenario == "es_missing_misaligned":
        tabs = tabs_es
    elif scenario == "ja_shift_overlap":
        tabs = tabs_ja

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
    sidebar_h = height - content_y - 20
    draw.rounded_rectangle([sidebar_x, content_y, sidebar_x + sidebar_w, content_y + sidebar_h], radius=8, fill="#FFFFFF", outline="#E2E8F0")
    
    sb_title = {"en_baseline": "Product Suite", "de_perfect": "Produktpalette", "de_expansion_defect": "Produktpalette", "es_missing_misaligned": "Suite de productos", "ja_shift_overlap": "製品スイート"}.get(scenario)
    draw.text((sidebar_x + 18, content_y + 18), sb_title, fill="#0F172A", font=f_header)

    products = [
        ("AutoCAD 2026", "#0696D7", "v24.1"),
        ("Autodesk Revit", "#0696D7", "v2026.2"),
        ("Fusion 360", "#F97316", "Cloud"),
        ("Autodesk Inventor", "#E11D48", "v2026"),
        ("Autodesk Maya", "#8B5CF6", "v2026"),
        ("Civil 3D", "#10B981", "v2026")
    ]
    py = content_y + 56
    for prod, col, ver in products:
        draw.ellipse([sidebar_x + 18, py + 4, sidebar_x + 28, py + 14], fill=col)
        draw.text((sidebar_x + 36, py), prod, fill="#1E293B", font=f_body)
        draw.text((sidebar_x + sidebar_w - 55, py + 2), ver, fill="#94A3B8", font=f_small)
        py += 36

    # 4. MAIN FORM CARD
    card_x = sidebar_x + sidebar_w + 24
    card_w = 620
    card_h = height - content_y - 20

    if scenario == "ja_shift_overlap":
        card_w = 690  # Critical Defect: Card expands and overlaps right widget

    draw.rounded_rectangle([card_x, content_y, card_x + card_w, content_y + card_h], radius=8, fill="#FFFFFF", outline="#E2E8F0")

    form_title = {
        "en_baseline": "Create Technical Support Case",
        "de_perfect": "Technischen Support-Fall erstellen",
        "de_expansion_defect": "Technischen Support-Fall erstellen",
        "es_missing_misaligned": "Crear caso de soporte técnico",
        "ja_shift_overlap": "テクニカルサポートケースの作成"
    }.get(scenario)
    draw.text((card_x + 28, content_y + 24), form_title, fill="#0F172A", font=f_title)
    
    sub_title = {
        "en_baseline": "Submit your product logs, crash reports, and system diagnostics to Autodesk engineers.",
        "de_perfect": "Senden Sie Produktprotokolle, Absturzberichte und Systemdiagnosen an Autodesk-Techniker.",
        "de_expansion_defect": "Senden Sie Produktprotokolle, Absturzberichte und Systemdiagnosen an Autodesk-Techniker.",
        "es_missing_misaligned": "Envíe registros de productos, informes de fallos y diagnósticos a los ingenieros de Autodesk.",
        "ja_shift_overlap": "製品ログ、クラッシュレポート、システム診断をオートデスクのエンジニアに送信します。"
    }.get(scenario)
    draw.text((card_x + 28, content_y + 52), sub_title, fill="#64748B", font=f_small)

    # Form Field 1: Product Dropdown
    fy = content_y + 88
    lbl1 = {"en_baseline": "Affected Product *", "de_perfect": "Betroffenes Produkt *", "de_expansion_defect": "Betroffenes Produkt *", "es_missing_misaligned": "Producto afectado *", "ja_shift_overlap": "対象製品 *"}.get(scenario)
    draw.text((card_x + 28, fy), lbl1, fill="#334155", font=f_label)
    
    box1_x = card_x + 28
    box1_w = card_w - 56
    if scenario == "es_missing_misaligned":
        box1_x = card_x + 58  # Minor Defect: Misaligned input box indented +30px
        box1_w = card_w - 90

    draw.rounded_rectangle([box1_x, fy + 22, box1_x + box1_w, fy + 62], radius=6, fill="#FFFFFF", outline="#CBD5E1")
    draw.text((box1_x + 14, fy + 34), "AutoCAD 2026 (Architecture Toolset)", fill="#0F172A", font=f_body)
    draw_icon(draw, "chevron", box1_x + box1_w - 24, fy + 36, size=12, color="#64748B")

    # Form Field 2: Severity Level
    fy += 78
    lbl2 = {"en_baseline": "Severity Level *", "de_perfect": "Schweregrad *", "de_expansion_defect": "Schweregrad *", "es_missing_misaligned": "Nivel de gravedad *", "ja_shift_overlap": "重要度レベル *"}.get(scenario)
    draw.text((card_x + 28, fy), lbl2, fill="#334155", font=f_label)

    sev_btns = [("Low", "#F1F5F9", "#475569"), ("Medium", "#F1F5F9", "#475569"), ("Critical (Workstopping)", "#FEF2F2", "#DC2626")]
    if scenario in ["de_perfect", "de_expansion_defect"]:
        sev_btns = [("Niedrig", "#F1F5F9", "#475569"), ("Mittel", "#F1F5F9", "#475569"), ("Kritisch (Arbeitsunterbrechung)", "#FEF2F2", "#DC2626")]
    elif scenario == "es_missing_misaligned":
        sev_btns = [("Bajo", "#F1F5F9", "#475569"), ("Medio", "#F1F5F9", "#475569"), ("Crítico (Trabajo detenido)", "#FEF2F2", "#DC2626")]
    elif scenario == "ja_shift_overlap":
        sev_btns = [("低", "#F1F5F9", "#475569"), ("中", "#F1F5F9", "#475569"), ("重大 (業務停止)", "#FEF2F2", "#DC2626")]

    bx = card_x + 28
    for btn_t, bg, fg in sev_btns:
        btw = int(draw.textlength(btn_t, font=f_body)) + 24
        draw.rounded_rectangle([bx, fy + 22, bx + btw, fy + 58], radius=6, fill=bg, outline="#CBD5E1" if fg != "#DC2626" else "#FCA5A5")
        draw.text((bx + 12, fy + 32), btn_t, fill=fg, font=f_body)
        bx += btw + 12

    # Form Field 3: Subject
    fy += 74
    lbl3 = {"en_baseline": "Subject / Summary *", "de_perfect": "Betreff / Zusammenfassung *", "de_expansion_defect": "Betreff / Zusammenfassung *", "es_missing_misaligned": "Asunto / Resumen *", "ja_shift_overlap": "件名 / 概要 *"}.get(scenario)
    draw.text((card_x + 28, fy), lbl3, fill="#334155", font=f_label)
    
    val3 = {
        "en_baseline": "Fatal error 0xC0000005 during DWG direct export on Windows 11",
        "de_perfect": "Schwerwiegender Fehler 0xC0000005 beim DWG-Direktexport unter Windows 11",
        "de_expansion_defect": "Schwerwiegender Fehler 0xC0000005 beim DWG-Direktexport unter Windows 11",
        "es_missing_misaligned": "Error fatal 0xC0000005 durante la exportación directa DWG en Windows 11",
        "ja_shift_overlap": "Windows 11 での DWG 直接エクスポート中の致命的なエラー 0xC0000005"
    }.get(scenario)
    draw.rounded_rectangle([card_x + 28, fy + 22, card_x + card_w - 28, fy + 62], radius=6, fill="#FFFFFF", outline="#CBD5E1")
    draw.text((card_x + 40, fy + 34), val3, fill="#0F172A", font=f_body)

    # Form Field 4: Description
    fy += 78
    lbl4 = {"en_baseline": "Steps to Reproduce & Description", "de_perfect": "Schritte zur Reproduktion und Beschreibung", "de_expansion_defect": "Schritte zur Reproduktion und Beschreibung", "es_missing_misaligned": "Pasos para reproducir y descripción", "ja_shift_overlap": "再現手順と説明"}.get(scenario)
    draw.text((card_x + 28, fy), lbl4, fill="#334155", font=f_label)

    draw.rounded_rectangle([card_x + 28, fy + 22, card_x + card_w - 28, fy + 160], radius=6, fill="#FFFFFF", outline="#CBD5E1")
    desc_sample = {
        "en_baseline": "1. Open AutoCAD 2026 with hardware acceleration enabled.\n2. Execute batch export command on sample architectural layout.\n3. Application terminates abruptly with crash log generated in %TEMP%.",
        "de_perfect": "1. Öffnen Sie AutoCAD 2026 mit aktivierter Hardwarebeschleunigung.\n2. Führen Sie den Stapel-Exportbefehl für das Architekturbeispiel aus.\n3. Die Anwendung wird unerwartet beendet mit Absturzprotokoll in %TEMP%.",
        "de_expansion_defect": "1. Öffnen Sie AutoCAD 2026 mit aktivierter Hardwarebeschleunigung.\n2. Führen Sie den Stapel-Exportbefehl für das Architekturbeispiel aus.\n3. Die Anwendung wird unerwartet beendet mit Absturzprotokoll in %TEMP%.",
        "es_missing_misaligned": "1. Abra AutoCAD 2026 con aceleración de hardware habilitada.\n2. Ejecute el comando de exportación por lotes en el plano arquitectónico.\n3. La aplicación se cierra abruptamente con informe en %TEMP%.",
        "ja_shift_overlap": "1. ハードウェア アクセラレーションを有効にして AutoCAD 2026 を開きます。\n2. サンプル建築レイアウトでバッチ エクスポート コマンドを実行します。\n3. アプリケーションが突然終了し、%TEMP% にクラッシュ ログが生成されます。"
    }.get(scenario)
    
    dy = fy + 32
    for line in desc_sample.split("\n"):
        draw.text((card_x + 40, dy), line, fill="#334155", font=f_small)
        dy += 22

    # 5. ACTION BUTTONS (AT BOTTOM OF CARD)
    btn_y = content_y + card_h - 70

    if scenario == "en_baseline":
        draw.rounded_rectangle([card_x + 28, btn_y, card_x + 180, btn_y + 44], radius=6, fill="#0696D7")
        draw.text((card_x + 50, btn_y + 13), "Submit Case", fill="#FFFFFF", font=f_body_bold)
        
        draw.rounded_rectangle([card_x + 196, btn_y, card_x + 360, btn_y + 44], radius=6, fill="#FFFFFF", outline="#0696D7")
        draw_icon(draw, "clip", card_x + 208, btn_y + 14, size=16, color="#0696D7")
        draw.text((card_x + 232, btn_y + 13), "Attach Log File", fill="#0696D7", font=f_body_bold)

        draw.rounded_rectangle([card_x + 376, btn_y, card_x + 480, btn_y + 44], radius=6, fill="#F1F5F9")
        draw.text((card_x + 408, btn_y + 13), "Cancel", fill="#475569", font=f_body)

    elif scenario == "de_perfect":
        draw.rounded_rectangle([card_x + 28, btn_y, card_x + 200, btn_y + 44], radius=6, fill="#0696D7")
        draw.text((card_x + 45, btn_y + 13), "Fall übermitteln", fill="#FFFFFF", font=f_body_bold)

        draw.rounded_rectangle([card_x + 216, btn_y, card_x + 416, btn_y + 44], radius=6, fill="#FFFFFF", outline="#0696D7")
        draw_icon(draw, "clip", card_x + 228, btn_y + 14, size=16, color="#0696D7")
        draw.text((card_x + 252, btn_y + 13), "Protokolldatei anhängen", fill="#0696D7", font=f_body_bold)

        draw.rounded_rectangle([card_x + 432, btn_y, card_x + 540, btn_y + 44], radius=6, fill="#F1F5F9")
        draw.text((card_x + 458, btn_y + 13), "Abbrechen", fill="#475569", font=f_body)

    elif scenario == "de_expansion_defect":
        # Critical Defect: Text overflows fixed button boundary & collides
        btn_w_broken = 145
        draw.rounded_rectangle([card_x + 28, btn_y, card_x + 28 + btn_w_broken, btn_y + 44], radius=6, fill="#0696D7")
        overflow_text = "Technischen Support-Fall jetzt sofort absenden"
        draw.text((card_x + 36, btn_y + 13), overflow_text, fill="#FFFFFF", font=f_body_bold)
        draw.rectangle([card_x + 28 + btn_w_broken - 2, btn_y + 4, card_x + 28 + btn_w_broken + 2, btn_y + 40], fill="#DC2626")

        draw.rounded_rectangle([card_x + 200, btn_y, card_x + 370, btn_y + 44], radius=6, fill="#FFFFFF", outline="#0696D7")
        draw_icon(draw, "clip", card_x + 212, btn_y + 14, size=16, color="#0696D7")
        draw.text((card_x + 236, btn_y + 13), "Datei anhängen", fill="#0696D7", font=f_body_bold)

        draw.rounded_rectangle([card_x + 386, btn_y, card_x + 490, btn_y + 44], radius=6, fill="#F1F5F9")
        draw.text((card_x + 418, btn_y + 13), "Abbrechen", fill="#475569", font=f_body)

    elif scenario == "es_missing_misaligned":
        # Critical Defect: 'Attach Log File' button is completely missing
        draw.rounded_rectangle([card_x + 28, btn_y, card_x + 190, btn_y + 44], radius=6, fill="#0696D7")
        draw.text((card_x + 48, btn_y + 13), "Enviar caso", fill="#FFFFFF", font=f_body_bold)

        draw.rounded_rectangle([card_x + 210, btn_y, card_x + 320, btn_y + 44], radius=6, fill="#F1F5F9")
        draw.text((card_x + 245, btn_y + 13), "Cancelar", fill="#475569", font=f_body)

    elif scenario == "ja_shift_overlap":
        draw.rounded_rectangle([card_x + 28, btn_y + 10, card_x + 180, btn_y + 54], radius=6, fill="#0696D7")
        draw.text((card_x + 50, btn_y + 23), "ケースを送信", fill="#FFFFFF", font=f_body_bold)

        draw.rounded_rectangle([card_x + 196, btn_y + 10, card_x + 360, btn_y + 54], radius=6, fill="#FFFFFF", outline="#0696D7")
        draw_icon(draw, "clip", card_x + 208, btn_y + 23)
        draw.text((card_x + 232, btn_y + 23), "ログを添付", fill="#0696D7", font=f_body_bold)

        draw.rounded_rectangle([card_x + 376, btn_y + 10, card_x + 480, btn_y + 54], radius=6, fill="#F1F5F9")
        draw.text((card_x + 408, btn_y + 23), "キャンセル", fill="#475569", font=f_body)

    # 6. RIGHT WIDGET (Need Urgent Help)
    right_x = card_x + card_w + 24
    right_w = width - right_x - 32
    
    if right_w > 150:
        if scenario == "ja_shift_overlap":
            right_x = card_x + card_w - 60  # Collision overlap defect
            right_w = 260

        draw.rounded_rectangle([right_x, content_y, right_x + right_w, content_y + 360], radius=8, fill="#FFFFFF", outline="#E2E8F0")
        
        rw_title = {"en_baseline": "Need Urgent Help?", "de_perfect": "Dringende Hilfe?", "de_expansion_defect": "Dringende Hilfe?", "es_missing_misaligned": "¿Ayuda urgente?", "ja_shift_overlap": "お急ぎですか？"}.get(scenario)
        draw.text((right_x + 18, content_y + 18), rw_title, fill="#0F172A", font=f_header)

        draw.rounded_rectangle([right_x + 16, content_y + 56, right_x + right_w - 16, content_y + 96], radius=6, fill="#F0FDF4", outline="#86EFAC")
        draw.text((right_x + 28, content_y + 68), "Live Chat: Online", fill="#166534", font=f_body_bold)

        draw.rounded_rectangle([right_x + 16, content_y + 108, right_x + right_w - 16, content_y + 148], radius=6, fill="#F8FAFC", outline="#CBD5E1")
        draw.text((right_x + 28, content_y + 120), "Call Autodesk Support", fill="#334155", font=f_body)

        draw.text((right_x + 18, content_y + 175), "Top Solved Articles", fill="#0F172A", font=f_label)
        articles = [
            "AutoCAD 2026 Licensing Fix",
            "Revit Cloud Worksharing Error",
            "Fusion 360 Export Guidelines"
        ]
        ay = content_y + 200
        for art in articles:
            draw.text((right_x + 18, ay), "• " + art, fill="#0284C7", font=f_small)
            ay += 28

    return img

def generate_all_presets(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    presets = [
        ("en_baseline", "English Baseline (Reference)", "Official English Autodesk Helpdesk Portal"),
        ("de_perfect", "German - Clean Quality", "German localization with properly resized containers and expected translations"),
        ("de_expansion_defect", "German - Button Text Overflow", "German translation causes button text overflow, boundary truncation, and collision"),
        ("es_missing_misaligned", "Spanish - Missing Action Button", "Spanish localization has missing 'Attach Log File' button and misaligned input form"),
        ("ja_shift_overlap", "Japanese - Layout Shift & Overlap", "Japanese localization with header displacement downward by 28px, missing help icon, and widget collision")
    ]
    
    generated_files = {}
    for name, title, desc in presets:
        img = generate_helpdesk_screenshot(name)
        path = os.path.join(output_dir, f"{name}.png")
        img.save(path, format="PNG")
        generated_files[name] = {
            "id": name,
            "title": title,
            "description": desc,
            "filename": f"{name}.png",
            "path": path
        }
    return generated_files

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "sample_data")
    generate_all_presets(out)
