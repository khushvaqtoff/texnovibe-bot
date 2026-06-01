"""
Hisobot, Ombor nazorati va Excel eksport handleri
"""

from telegram import Update
from telegram.ext import ContextTypes
from sheets.google_sheets import get_spreadsheet, ensure_worksheets, ws_to_records
from datetime import date, datetime
import io
import os

def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)

def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", "").strip() or 0)
    except:
        return 0


async def cmd_daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Bugungi hisobot yuklanmoqda...")
    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        today_str = date.today().strftime("%d.%m.%Y")

        all_sales = ws_to_records(sheets["Savdolar"])
        all_payments = ws_to_records(sheets["Tolovlar"])

        today_sales = [r for r in all_sales if r.get("Sana") == today_str]
        today_payments = [r for r in all_payments if r.get("To'lov Sanasi") == today_str]

        today_sales_sum = sum(safe_float(r.get("Jami Summa", 0)) for r in today_sales)
        today_sales_avans = sum(safe_float(r.get("Boshlang'ich To'lov", 0)) for r in today_sales)
        today_payments_sum = sum(safe_float(r.get("To'lov Summasi", 0)) for r in today_payments)
        total_income = today_sales_avans + today_payments_sum

        text = (
            f"📊 BUGUNGI HISOBOT\n"
            f"📅 Sana: {today_str}\n"
            f"{'='*30}\n\n"
            f"🆕 YANGI SAVDOLAR ({len(today_sales)} ta)\n"
            f"{'─'*25}\n"
        )
        if today_sales:
            for rec in today_sales:
                fio = rec.get("FIO", "")
                tovar = rec.get("Tovar", "")
                jami = format_money(rec.get("Jami Summa", 0))
                avans = format_money(rec.get("Boshlang'ich To'lov", 0))
                turi = rec.get("To'lov Turi", "")
                text += f"+ {fio}\n  {tovar}\n  Jami: {jami} so'm | Avans: {avans} so'm\n  {turi}\n\n" 
        else:
            text += "Bugun yangi savdo yo'q\n\n"

        text += f"💰 TUSHGAN TO'LOVLAR ({len(today_payments)} ta)\n{'─'*25}\n"
        if today_payments:
            for rec in today_payments:
                text += (
                    f"+ {rec.get('FIO', '')}\n"
                    f"  To'landi: {format_money(rec.get("To'lov Summasi", 0))} so'm\n"
                    f"  Qoldiq: {format_money(rec.get('Qoldiq', 0))} so'm\n\n"
                )
        else:
            text += "Bugun to'lov tushgani yo'q\n\n"

        text += (
            f"{'='*30}\n"
            f"📈 BUGUNGI NATIJA\n"
            f"Yangi savdolar: {format_money(today_sales_sum)} so'm\n"
            f"Avans tushdi: {format_money(today_sales_avans)} so'm\n"
            f"To'lovlar tushdi: {format_money(today_payments_sum)} so'm\n"
            f"💵 Jami kassa: {format_money(total_income)} so'm\n"
        )

        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await update.message.reply_text(text[i:i+4000])
        else:
            await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")


async def cmd_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ombor ma'lumotlari yuklanmoqda...")
    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        today_str = date.today().strftime("%d.%m.%Y")

        all_sales = ws_to_records(sheets["Savdolar"])
        all_payments = ws_to_records(sheets["Tolovlar"])

        faol = [r for r in all_sales if r.get("Holat") == "Faol"]
        yopilgan = [r for r in all_sales if r.get("Holat") == "Yopildi"]
        bekor = [r for r in all_sales if r.get("Holat") == "Bekor qilindi"]
        hisob = [r for r in all_sales if r.get("Holat") in ("Faol", "Yopildi")]

        jami_nasiya = sum(safe_float(r.get("Jami Summa", 0)) for r in hisob)
        jami_qoldiq = sum(safe_float(r.get("Qoldiq", 0)) for r in faol)
        jami_tolangan = sum(safe_float(r.get("To'langan Summa", 0)) for r in hisob)
        jami_avans = sum(safe_float(r.get("Boshlang'ich To'lov", 0)) for r in hisob)

        bugungi = [r for r in all_payments if r.get("To'lov Sanasi") == today_str]
        bugungi_sum = sum(safe_float(r.get("To'lov Summasi", 0)) for r in bugungi)

        tovar_stats = {}
        for rec in all_sales:
            if rec.get("Holat") == "Bekor qilindi":
                continue
            tovar = rec.get("Tovar", "Noma'lum")
            if tovar not in tovar_stats:
                tovar_stats[tovar] = {"faol": 0, "yopilgan": 0}
            if rec.get("Holat") == "Faol":
                tovar_stats[tovar]["faol"] += 1
            elif rec.get("Holat") == "Yopildi":
                tovar_stats[tovar]["yopilgan"] += 1

        text = (
            f"🏪 OMBOR NAZORATI\n📅 {today_str}\n{'='*30}\n\n"
            f"📦 UMUMIY HOLAT\n{'─'*25}\n"
            f"Jami sotilgan: {len(all_sales)} ta\n"
            f"Faol nasiya: {len(faol)} ta\n"
            f"Yopilgan: {len(yopilgan)} ta\n"
            f"Bekor qilingan: {len(bekor)} ta\n\n"
            f"💰 MOLIYAVIY HOLAT\n{'─'*25}\n"
            f"Jami nasiya: {format_money(jami_nasiya)} so'm\n"
            f"Jami avans: {format_money(jami_avans)} so'm\n"
            f"Jami to'langan: {format_money(jami_tolangan)} so'm\n"
            f"Qolgan qarz: {format_money(jami_qoldiq)} so'm\n\n"
            f"📅 BUGUNGI TO'LOVLAR ({len(bugungi)} ta)\n{'─'*25}\n"
            f"Bugun tushdi: {format_money(bugungi_sum)} so'm\n"
        )
        for rec in bugungi:
            text += f"  + {rec.get('FIO', '')}: {format_money(rec.get('Tolov Summasi', 0))} so'm\n"

        text += f"\n🛍 TOVAR BO'YICHA\n{'─'*25}\n"
        for tovar, s in sorted(tovar_stats.items(), key=lambda x: x[1]["faol"]+x[1]["yopilgan"], reverse=True)[:10]:
            text += f"{tovar}: Faol {s['faol']} | Yopilgan {s['yopilgan']}\n"

        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await update.message.reply_text(text[i:i+4000])
        else:
            await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")


async def cmd_excel_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qarzdorlar, mijozlar va bugungi hisobotni Excel formatida yuboradi"""
    await update.message.reply_text("⏳ Excel fayl tayyorlanmoqda...")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        today_str = date.today().strftime("%d.%m.%Y")

        all_sales = ws_to_records(sheets["Savdolar"])
        all_payments = ws_to_records(sheets["Tolovlar"])
        all_clients = ws_to_records(sheets["Mijozlar"])

        wb = Workbook()

        # Ranglar
        HEADER_FILL = PatternFill("solid", start_color="2E86AB")
        RED_FILL = PatternFill("solid", start_color="FF6B6B")
        YELLOW_FILL = PatternFill("solid", start_color="FFE66D")
        GREEN_FILL = PatternFill("solid", start_color="A8E6CF")
        WHITE_FONT = Font(bold=True, color="FFFFFF", name="Arial", size=11)
        BOLD = Font(bold=True, name="Arial", size=10)
        NORMAL = Font(name="Arial", size=10)
        CENTER = Alignment(horizontal="center", vertical="center")
        thin = Side(style="thin", color="CCCCCC")
        BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

        def style_header(cell, fill=None):
            cell.font = WHITE_FONT
            cell.fill = fill or HEADER_FILL
            cell.alignment = CENTER
            cell.border = BORDER

        def style_cell(cell, bold=False):
            cell.font = BOLD if bold else NORMAL
            cell.alignment = Alignment(vertical="center")
            cell.border = BORDER

        def set_col_widths(ws, widths):
            for col, w in widths.items():
                ws.column_dimensions[col].width = w

        # ── 1. QARZDORLAR ────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "Qarzdorlar"
        ws1.row_dimensions[1].height = 22

        headers1 = ["#", "FIO", "Telefon", "Tovar", "Jami Summa", "Qoldiq",
                    "To'lov Turi", "Keyingi To'lov", "Kechikish (kun)", "Agent"]
        for j, h in enumerate(headers1, 1):
            c = ws1.cell(row=1, column=j, value=h)
            style_header(c)

        from datetime import datetime as dt
        today_date = date.today()
        faol = [r for r in all_sales if r.get("Holat") == "Faol"]
        row = 2
        overdue_count = 0
        for rec in faol:
            try:
                next_pay_str = rec.get("Keyingi To'lov Sanasi", "")
                next_pay = dt.strptime(next_pay_str, "%d.%m.%Y").date() if next_pay_str else None
                delay = (today_date - next_pay).days if next_pay else 0
            except:
                delay = 0

            if delay < 0:
                delay = 0
            overdue_count += 1
            fill = RED_FILL if delay >= 3 else (YELLOW_FILL if delay >= 1 else GREEN_FILL)

            vals = [
                overdue_count,
                rec.get("FIO", ""),
                rec.get("Telefon", ""),
                rec.get("Tovar", ""),
                safe_float(rec.get("Jami Summa", 0)),
                safe_float(rec.get("Qoldiq", 0)),
                rec.get("To'lov Turi", ""),
                rec.get("Keyingi To'lov Sanasi", ""),
                delay,
                rec.get("Agent", ""),
            ]
            for j, val in enumerate(vals, 1):
                c = ws1.cell(row=row, column=j, value=val)
                c.fill = fill
                style_cell(c, bold=(j == 2))
            row += 1

        # Jami qator
        ws1.cell(row=row, column=1, value="JAMI").font = BOLD
        ws1.cell(row=row, column=5, value=f'=SUM(E2:E{row-1})').font = BOLD
        ws1.cell(row=row, column=6, value=f'=SUM(F2:F{row-1})').font = BOLD

        set_col_widths(ws1, {"A": 5, "B": 22, "C": 16, "D": 18, "E": 14,
                              "F": 14, "G": 12, "H": 14, "I": 14, "J": 14})

        # ── 2. MIJOZLAR ───────────────────────────────────────────
        ws2 = wb.create_sheet("Mijozlar")
        ws2.row_dimensions[1].height = 22

        headers2 = ["#", "FIO", "Telefon", "Jami Savdolar", "Status",
                    "Kredit Bali", "Ish Joyi", "Ro'yxatga Olingan"]
        for j, h in enumerate(headers2, 1):
            c = ws2.cell(row=1, column=j, value=h)
            style_header(c)

        for i, rec in enumerate(all_clients, 1):
            vals = [
                i,
                rec.get("FIO", ""),
                rec.get("Telefon", ""),
                safe_float(rec.get("Jami Savdolar", 0)),
                rec.get("Status", "Bronze"),
                safe_float(rec.get("Kredit Bali", 0)),
                rec.get("Ish Joyi", ""),
                rec.get("Ro'yxatga Olingan Sana", ""),
            ]
            for j, val in enumerate(vals, 1):
                c = ws2.cell(row=i+1, column=j, value=val)
                style_cell(c, bold=(j == 2))

        set_col_widths(ws2, {"A": 5, "B": 22, "C": 16, "D": 14,
                              "E": 12, "F": 12, "G": 18, "H": 18})

        # ── 3. BUGUNGI HISOBOT ────────────────────────────────────
        ws3 = wb.create_sheet("Bugungi Hisobot")
        ws3.row_dimensions[1].height = 22

        # Sarlavha
        ws3.merge_cells("A1:G1")
        c = ws3.cell(row=1, column=1, value=f"BUGUNGI HISOBOT — {today_str}")
        c.font = Font(bold=True, color="FFFFFF", name="Arial", size=13)
        c.fill = HEADER_FILL
        c.alignment = CENTER

        # Yangi savdolar
        ws3.cell(row=2, column=1, value="YANGI SAVDOLAR").font = BOLD
        headers3a = ["#", "FIO", "Telefon", "Tovar", "Jami Summa", "Avans", "To'lov Turi"]
        for j, h in enumerate(headers3a, 1):
            c = ws3.cell(row=3, column=j, value=h)
            style_header(c, GREEN_FILL)

        today_sales = [r for r in all_sales if r.get("Sana") == today_str]
        sr = 4
        for i, rec in enumerate(today_sales, 1):
            vals = [
                i, rec.get("FIO", ""), rec.get("Telefon", ""), rec.get("Tovar", ""),
                safe_float(rec.get("Jami Summa", 0)),
                safe_float(rec.get("Boshlang'ich To'lov", 0)),
                rec.get("To'lov Turi", ""),
            ]
            for j, val in enumerate(vals, 1):
                c = ws3.cell(row=sr, column=j, value=val)
                style_cell(c)
            sr += 1

        # Jami savdo
        ws3.cell(row=sr, column=4, value="JAMI:").font = BOLD
        ws3.cell(row=sr, column=5, value=f"=SUM(E4:E{sr-1})").font = BOLD
        ws3.cell(row=sr, column=6, value=f"=SUM(F4:F{sr-1})").font = BOLD
        sr += 2

        # To'lovlar
        ws3.cell(row=sr, column=1, value="TUSHGAN TO'LOVLAR").font = BOLD
        sr += 1
        headers3b = ["#", "FIO", "Telefon", "Savdo ID", "To'lov Summasi", "Qoldiq", "Sana"]
        for j, h in enumerate(headers3b, 1):
            c = ws3.cell(row=sr, column=j, value=h)
            style_header(c, YELLOW_FILL)
        sr += 1

        today_payments = [r for r in all_payments if r.get("To'lov Sanasi") == today_str]
        pr = sr
        for i, rec in enumerate(today_payments, 1):
            vals = [
                i, rec.get("FIO", ""), rec.get("Telefon", ""), rec.get("Savdo ID", ""),
                safe_float(rec.get("To'lov Summasi", 0)),
                safe_float(rec.get("Qoldiq", 0)),
                rec.get("To'lov Sanasi", ""),
            ]
            for j, val in enumerate(vals, 1):
                c = ws3.cell(row=sr, column=j, value=val)
                style_cell(c)
            sr += 1

        ws3.cell(row=sr, column=4, value="JAMI:").font = BOLD
        ws3.cell(row=sr, column=5, value=f"=SUM(E{pr}:E{sr-1})").font = BOLD
        sr += 2

        # Natija bloki
        avans_sum = sum(safe_float(r.get("Boshlang'ich To'lov", 0)) for r in today_sales)
        pay_sum = sum(safe_float(r.get("To'lov Summasi", 0)) for r in today_payments)

        summary = [
            ("Yangi savdolar soni:", len(today_sales)),
            ("Tushgan to'lovlar soni:", len(today_payments)),
            ("Avans tushdi:", avans_sum),
            ("To'lovlar tushdi:", pay_sum),
            ("💵 JAMI KASSA:", avans_sum + pay_sum),
        ]
        ws3.cell(row=sr, column=1, value="NATIJA").font = Font(bold=True, size=12, name="Arial")
        sr += 1
        for label, val in summary:
            ws3.cell(row=sr, column=1, value=label).font = BOLD
            c = ws3.cell(row=sr, column=2, value=val)
            c.font = Font(bold=True, name="Arial", size=11, color="1A1A2E")
            sr += 1

        set_col_widths(ws3, {"A": 5, "B": 22, "C": 16, "D": 14,
                              "E": 16, "F": 14, "G": 14})

        # Faylni xotiraga saqlash va yuborish
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"texnovibe_{today_str.replace('.', '_')}.xlsx"
        await update.message.reply_document(
            document=buf,
            filename=filename,
            caption=(
                f"📊 Excel hisobot — {today_str}\n"
                f"📋 Varaqlar: Qarzdorlar | Mijozlar | Bugungi Hisobot"
            )
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")
