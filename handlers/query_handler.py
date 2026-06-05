"""
So'rov handlerlari
Yangilik: cmd_clients — barcha mijozlarni PDF qilib yuboradi
"""

import io
import os
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_payment_history, get_all_clients_with_status,
    get_overdue_payments, get_today_payments, get_statistics
)

SEARCH_QUERY = 50


def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", "").strip() or 0)
    except:
        return 0


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def generate_clients_pdf(clients: list) -> bytes:
    """Mijozlar ro'yxatini PDF formatida yaratadi"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1*cm, rightMargin=1*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles  = getSampleStyleSheet()
    story   = []
    today   = date.today().strftime("%d.%m.%Y")

    # Sarlavha
    title_style = ParagraphStyle(
        "title", parent=styles["Normal"],
        fontSize=14, fontName="Helvetica-Bold",
        alignment=TA_CENTER, spaceAfter=6
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica",
        alignment=TA_CENTER, spaceAfter=12, textColor=colors.grey
    )

    story.append(Paragraph("TexnoVibe — Mijozlar Royxati", title_style))
    story.append(Paragraph(f"Sana: {today} | Jami: {len(clients)} ta mijoz", sub_style))
    story.append(Spacer(1, 0.3*cm))

    # Jadval sarlavhasi
    col_widths = [1*cm, 4.5*cm, 3*cm, 2.5*cm, 3*cm, 2.5*cm, 2*cm]
    headers    = ["#", "FIO", "Telefon", "Tovar", "Qoldiq", "Keyingi\nTo'lov", "Reyting"]

    header_style = ParagraphStyle(
        "th", parent=styles["Normal"],
        fontSize=7, fontName="Helvetica-Bold",
        alignment=TA_CENTER
    )
    cell_style = ParagraphStyle(
        "td", parent=styles["Normal"],
        fontSize=7, fontName="Helvetica",
        alignment=TA_LEFT
    )
    center_style = ParagraphStyle(
        "tdc", parent=styles["Normal"],
        fontSize=7, fontName="Helvetica",
        alignment=TA_CENTER
    )

    data = [[Paragraph(h, header_style) for h in headers]]

    for i, rec in enumerate(clients, 1):
        fio     = str(rec.get("FIO", ""))[:25]
        phone   = str(rec.get("Telefon", ""))
        tovar   = str(rec.get("Tovar", ""))[:20]
        qoldiq  = format_money(rec.get("Qoldiq", 0)) + " so'm"
        keyingi = str(rec.get("Keyingi To'lov Sanasi", ""))
        reyting = str(rec.get("Reyting", ""))

        # Reyting rangi
        if "🟢" in reyting or "Alo" in reyting:
            r_color = colors.green
        elif "🔴" in reyting or "Xavfli" in reyting:
            r_color = colors.red
        else:
            r_color = colors.orange

        reyting_clean = reyting.replace("🟢","").replace("🟡","").replace("🔴","").strip()

        row = [
            Paragraph(str(i), center_style),
            Paragraph(fio, cell_style),
            Paragraph(phone, cell_style),
            Paragraph(tovar, cell_style),
            Paragraph(qoldiq, center_style),
            Paragraph(keyingi, center_style),
            Paragraph(reyting_clean, center_style),
        ]
        data.append(row)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Sarlavha
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1565C0")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  7),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUND",(0, 1), (-1, -1), [colors.white, colors.HexColor("#EBF5FB")]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.5*cm))

    # Statistika
    jami_qoldiq = sum(safe_float(r.get("Qoldiq", 0)) for r in clients)
    stat_style  = ParagraphStyle(
        "stat", parent=styles["Normal"],
        fontSize=8, fontName="Helvetica-Bold",
        alignment=TA_LEFT
    )
    story.append(Paragraph(
        f"Jami qoldiq: {format_money(jami_qoldiq)} so'm  |  "
        f"Faol mijozlar: {len(clients)} ta",
        stat_style
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        context.user_data["search_text"] = " ".join(context.args)
        return await search_query(update, context)
    await update.message.reply_text("Qidirish\n\nIsm yoki telefon raqamini yozing:")
    return SEARCH_QUERY


async def search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("search_text"):
        query_text = context.user_data.pop("search_text").lower().strip()
    else:
        query_text = update.message.text.strip().lower()

    try:
        all_clients = get_all_clients_with_status()
        results = []
        for client in all_clients:
            fio          = str(client.get("FIO", "")).lower()
            phone        = str(client.get("Telefon", "")).replace("+", "").replace(" ", "")
            search_clean = query_text.replace("+", "").replace(" ", "")
            if query_text in fio or search_clean in phone:
                results.append(client)

        if not results:
            await update.message.reply_text(f"'{query_text}' boyicha hech narsa topilmadi.\n\nQaytadan yozing:")
            return SEARCH_QUERY

        text = f"QIDIRUV NATIJALARI ({len(results)} ta)\n\n"
        for rec in results[:10]:
            fio     = rec.get("FIO", "")
            phone   = rec.get("Telefon", "")
            tovar   = rec.get("Tovar", "")
            qoldiq  = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "")
            text += (
                f"👤 {fio}\n📞 {phone}\n🛍 {tovar}\n"
                f"💰 Qoldiq: {qoldiq} som\n📅 Keyingi: {keyingi}\n⭐ {reyting}\n---\n"
            )
        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")

    context.user_data.clear()
    return ConversationHandler.END


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Foydalanish:\n/tarix +998901234567")
        return
    phone = args[0]
    await update.message.reply_text("Malumotlar yuklanmoqda...")
    try:
        history = get_payment_history(phone)
        if not history:
            await update.message.reply_text(f"'{phone}' uchun tolov tarixi topilmadi.")
            return
        total_paid     = sum(safe_float(r.get("To'lov Summasi", 0)) for r in history)
        last_remaining = history[-1].get("Qoldiq", 0) if history else 0
        text = f"TOLOV TARIXI\nTelefon: {phone}\n\n"
        for i, rec in enumerate(history, 1):
            sana  = rec.get("To'lov Sanasi", "")
            summa = format_money(rec.get("To'lov Summasi", 0))
            text += f"{i}. {sana} - {summa} som\n"
        text += f"\nJami tolangan: {format_money(total_paid)} som\n"
        text += f"Hozirgi qoldiq: {format_money(last_remaining)} som"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Foydalanish:\n/qidir Anvarov\n/qidir +998901234567")
        return
    context.user_data["search_text"] = " ".join(args)
    await search_query(update, context)


async def cmd_debtors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Malumotlar yuklanmoqda...")
    try:
        overdue = get_overdue_payments(1)
        if not overdue:
            await update.message.reply_text("Hozircha hech kim kechiktirayotgani yoq!")
            return
        text = f"KECHIKAYOTGANLAR ({len(overdue)} ta)\n\n"
        for rec in overdue:
            keyingi   = rec.get("Keyingi To'lov Sanasi", "")
            days      = rec.get("Kechikish Kunlari", 0)
            emoji     = "🔴" if days >= 3 else "🟡"
            pay_type  = rec.get("To'lov Turi", "Oylik")
            oylik     = format_money(rec.get("To'lov Summasi", 0))
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            text += (
                f"{emoji} {rec.get('FIO','')}\n"
                f"📞 {rec.get('Telefon','')}\n"
                f"💰 Qoldiq: {format_money(rec.get('Qoldiq',0))} som\n"
                f"{pay_emoji} {pay_type} | 💳 {oylik} som\n"
                f"⏰ Kechikish: {days} kun\n"
                f"\U0001f4c5 Tolashi kerak edi: {keyingi}\\n\\n"
            )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Qora royxat yuklanmoqda...")
    try:
        blacklist = get_overdue_payments(3)
        if not blacklist:
            await update.message.reply_text("Qora royxat bosh!")
            return
        text = f"QORA ROYXAT ({len(blacklist)} ta)\n\n"
        for rec in blacklist:
            text += (
                f"🔴 {rec.get('FIO','')}\n"
                f"📞 {rec.get('Telefon','')}\n"
                f"🛍 {rec.get('Tovar','')}\n"
                f"💰 Qoldiq: {format_money(rec.get('Qoldiq',0))} som\n"
                f"⏰ Kechikish: {rec.get('Kechikish Kunlari',0)} kun\n\n"
            )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Reyting hisoblanmoqda...")
    try:
        clients = get_all_clients_with_status()
        green  = [c for c in clients if "🟢" in str(c.get("Reyting",""))]
        yellow = [c for c in clients if "🟡" in str(c.get("Reyting",""))]
        red    = [c for c in clients if "🔴" in str(c.get("Reyting",""))]
        text = (
            f"MIJOZLAR REYTINGI\n\n"
            f"🟢 Alo: {len(green)} ta\n"
            f"🟡 Ortacha: {len(yellow)} ta\n"
            f"🔴 Xavfli: {len(red)} ta\n\n"
        )
        if red:
            text += "🔴 XAVFLI:\n"
            for c in red[:5]:
                text += f"• {c.get('FIO')} - {c.get('Telefon')}\n"
            text += "\n"
        if green:
            text += "🟢 ENG YAXSHI:\n"
            for c in green[:5]:
                text += f"• {c.get('FIO')} - {c.get('Telefon')}\n"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha faol mijozlarni PDF qilib yuboradi"""
    await update.message.reply_text("⏳ PDF tayyorlanmoqda...")
    try:
        clients = get_all_clients_with_status()
        if not clients:
            await update.message.reply_text("Hozircha faol mijozlar yo'q.")
            return

        pdf_bytes = generate_clients_pdf(clients)
        filename  = f"Mijozlar_{date.today().strftime('%d-%m-%Y')}.pdf"

        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=filename,
            caption=(
                f"👥 *Faol Mijozlar Ro'yxati*\n"
                f"📅 Sana: {date.today().strftime('%d.%m.%Y')}\n"
                f"📊 Jami: {len(clients)} ta mijoz"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bugungi tolovlar yuklanmoqda...")
    try:
        today_payments = get_today_payments()
        if not today_payments:
            await update.message.reply_text("Bugun tolov qilishi kerak bolgan mijoz yoq.")
            return
        total_expected = sum(safe_float(r.get("To'lov Summasi", 0)) for r in today_payments)
        text = (
            f"BUGUNGI TOLOVLAR ({len(today_payments)} ta)\n"
            f"Kutilayotgan: {format_money(total_expected)} som\n\n"
        )
        for i, rec in enumerate(today_payments, 1):
            pay_type  = rec.get("To'lov Turi", "Oylik")
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            text += (
                f"{i}. {pay_emoji} {rec.get('FIO','')}\n"
                f"   📞 {rec.get('Telefon','')}\n"
                f"   💳 {format_money(rec.get('To'+'lov Summasi',0))} som | "
                f"Qoldiq: {format_money(rec.get('Qoldiq',0))} som\n\n"
            )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Statistika hisoblanmoqda...")
    try:
        stats = get_statistics()
        text = (
            f"UMUMIY STATISTIKA\n\n"
            f"📦 Jami savdolar: {stats['total_sales']} ta\n"
            f"🔄 Faol kreditlar: {stats['active']} ta\n"
            f"✅ Yopilgan: {stats['closed']} ta\n\n"
            f"💰 Jami qoldiq: {format_money(stats['total_debt'])} som\n"
            f"💵 Jami sotuv: {format_money(stats['total_revenue'])} som\n\n"
            f"⚠️ Kechikayotganlar: {stats['overdue_count']} ta\n"
            f"🚫 Qora royxat: {stats['blacklist_count']} ta\n"
        )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")
