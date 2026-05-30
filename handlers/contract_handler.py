"""
Shartnoma PDF yaratish va yuborish
Savdo qilinganda avtomatik shakllantiriladi
"""

import io
import os
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_styles():
    """Shrift uslublarini qaytaradi"""
    # Oddiy shriftlar bilan ishlash (emoji va lotin)
    title_style = ParagraphStyle(
        'Title',
        fontSize=14,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        'Heading',
        fontSize=11,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
        spaceBefore=8,
        spaceAfter=4,
    )
    normal_style = ParagraphStyle(
        'Normal',
        fontSize=10,
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceAfter=3,
    )
    center_style = ParagraphStyle(
        'Center',
        fontSize=10,
        fontName='Helvetica',
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    bold_style = ParagraphStyle(
        'Bold',
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
        spaceAfter=3,
    )
    return {
        'title': title_style,
        'heading': heading_style,
        'normal': normal_style,
        'center': center_style,
        'bold': bold_style,
    }


def create_contract_pdf(sale_data: dict, result: dict) -> bytes:
    """
    Shartnoma PDF yaratadi va bytes qaytaradi
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles = get_styles()
    story = []

    today = date.today().strftime("%d.%m.%Y")
    sale_id = result.get("sale_id", "")
    fio = sale_data.get("fio", "")
    phone = sale_data.get("phone", "")
    work_place = sale_data.get("work_place", "Korsatilmagan")
    product = sale_data.get("product", "")
    total_price = float(sale_data.get("total_price", 0))
    down_payment = float(sale_data.get("down_payment", 0))
    remaining = total_price - down_payment
    payment_type = sale_data.get("payment_type", "Oylik")
    period = int(sale_data.get("installment_period", 1))
    pay_per = result.get("payment_per_period", 0)
    agent = sale_data.get("agent", "")
    pay_day = sale_data.get("pay_day", "")
    schedule = result.get("schedule", [])

    period_word = "oy" if payment_type == "Oylik" else "hafta"

    # ===== SARLAVHA =====
    story.append(Paragraph("TEXNOVIBE DO'KONI", styles['title']))
    story.append(Paragraph("NASIYA SAVDO SHARTNOMASI", styles['title']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.darkblue))
    story.append(Spacer(1, 0.3*cm))

    # Shartnoma raqami va sana
    header_data = [
        [f"Shartnoma: {sale_id}", f"Sana: {today}"],
    ]
    header_table = Table(header_data, colWidths=[9*cm, 9*cm])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.4*cm))

    # ===== MIJOZ MA'LUMOTLARI =====
    story.append(Paragraph("MIJOZ MA'LUMOTLARI", styles['heading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))

    client_data = [
        ["Mijoz ismi:", fio],
        ["Telefon raqami:", phone],
        ["Ish joyi:", work_place or "Korsatilmagan"],
    ]
    if agent:
        client_data.append(["Agent:", agent])

    client_table = Table(client_data, colWidths=[5*cm, 13*cm])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.whitesmoke, colors.white]),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.3*cm))

    # ===== TOVAR MA'LUMOTLARI =====
    story.append(Paragraph("TOVAR VA TO'LOV SHARTLARI", styles['heading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))

    product_data = [
        ["Tovar:", product],
        ["Jami narx:", f"{format_money(total_price)} so'm"],
        ["Boshlangich tolov (avans):", f"{format_money(down_payment)} so'm"],
        ["Nasiya qoldiq:", f"{format_money(remaining)} so'm"],
        ["Tolov turi:", payment_type],
        [f"Muddat:", f"{period} {period_word}"],
        [f"Har {period_word} tolov:", f"{format_money(pay_per)} so'm"],
    ]
    if pay_day:
        product_data.append(["Tolov kuni:", f"Har oyning {pay_day}-si"])

    product_table = Table(product_data, colWidths=[7*cm, 11*cm])
    product_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.whitesmoke, colors.white]),
        ('TEXTCOLOR', (1,2), (1,2), colors.darkred),  # Avans
        ('TEXTCOLOR', (1,3), (1,3), colors.darkblue),  # Qoldiq
        ('TEXTCOLOR', (1,6), (1,6), colors.darkgreen),  # Har oylik
    ]))
    story.append(product_table)
    story.append(Spacer(1, 0.3*cm))

    # ===== TO'LOV JADVALI =====
    story.append(Paragraph("TO'LOV JADVALI", styles['heading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))

    schedule_data = [["#", "To'lov sanasi", "To'lov summasi", "Qoldiq", "Imzo"]]
    for item in schedule:
        schedule_data.append([
            str(item["num"]),
            item["date"],
            f"{format_money(item['amount'])} so'm",
            f"{format_money(item['remaining'])} so'm",
            "",  # Imzo uchun bo'sh joy
        ])

    col_widths = [1*cm, 4*cm, 4.5*cm, 4.5*cm, 4*cm]
    schedule_table = Table(schedule_data, colWidths=col_widths)
    schedule_table.setStyle(TableStyle([
        # Sarlavha
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        # Ma'lumotlar
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('ALIGN', (0,1), (0,-1), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'CENTER'),
        ('ALIGN', (2,1), (3,-1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.lightblue]),
        # Chegara
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(schedule_table)
    story.append(Spacer(1, 0.4*cm))

    # ===== SHARTLAR =====
    story.append(Paragraph("SHARTNOMA SHARTLARI", styles['heading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))

    shartlar = [
        "1. Mijoz tolovni belgilangan sana va summada amalga oshirishi shart.",
        "2. Tolov 3 kundan ortiq kechiktirilsa, do'kon bilan kelishiladi.",
        "3. Tovar yetkazib berilgandan keyin mijozda qoladi.",
        "4. Shartnoma ikki tomon uchun ham majburiydir.",
        "5. Barcha nizolar muzokaralar yo'li bilan hal etiladi.",
    ]
    for shart in shartlar:
        story.append(Paragraph(shart, styles['normal']))

    story.append(Spacer(1, 0.5*cm))

    # ===== IMZOLAR =====
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    imzo_data = [
        ["DO'KON VAKILI:", "", "MIJOZ:"],
        ["", "", ""],
        ["", "", ""],
        ["________________", "", "________________"],
        [f"Sana: {today}", "", f"Sana: {today}"],
    ]
    imzo_table = Table(imzo_data, colWidths=[7*cm, 4*cm, 7*cm])
    imzo_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(imzo_table)

    # ===== PASTKI QISM =====
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.darkblue))
    story.append(Paragraph(
        "TexnoVibe - Ishonchli do'koningiz | Murojaat uchun: @texnovibe_bot",
        styles['center']
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


async def send_contract(bot, sale_data: dict, result: dict, admin_chat_id: int, client_chat_id: str = ""):
    """
    Shartnomani PDF sifatida admin va mijozga yuboradi
    """
    try:
        pdf_bytes = create_contract_pdf(sale_data, result)
        fio = sale_data.get("fio", "mijoz")
        filename = f"shartnoma_{result.get('sale_id', 'new')}.pdf"

        caption = (
            f"NASIYA SHARTNOMASI\n"
            f"Mijoz: {fio}\n"
            f"Tovar: {sale_data.get('product', '')}\n"
            f"Shartnoma: {result.get('sale_id', '')}"
        )

        # Adminga yuborish
        await bot.send_document(
            chat_id=admin_chat_id,
            document=pdf_bytes,
            filename=filename,
            caption=caption
        )

        # Mijozga yuborish (agar Chat ID bo'lsa)
        if client_chat_id and client_chat_id.strip():
            try:
                await bot.send_document(
                    chat_id=int(client_chat_id),
                    document=pdf_bytes,
                    filename=filename,
                    caption=(
                        f"Hurmatli {fio}!\n\n"
                        f"TexnoVibe do'konidan nasiya shartnomangiz.\n"
                        f"To'lov jadvalini yuqoridagi fayldan ko'ring.\n\n"
                        f"Savol bo'lsa: @texnovibe_bot"
                    )
                )
            except Exception as e:
                await bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"Mijozga shartnoma yuborib bolmadi:\n{str(e)}"
                )

        return True

    except Exception as e:
        await bot.send_message(
            chat_id=admin_chat_id,
            text=f"Shartnoma yaratishda xato:\n{str(e)}"
        )
        return False
