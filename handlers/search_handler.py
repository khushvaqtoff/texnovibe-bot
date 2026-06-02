"""
TexnoVibe — handlers/search_handler.py
Mijozlar va savdolarni umumiy qidirish paneli.
Faqat FAOL savdolarni ko'rsatadigan va ism/narx ustunlarini aniq topadigan variant.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet
import html

logger = logging.getLogger(__name__)

# State
SEARCH_INPUT = 1


def format_money(amount) -> str:
    try:
        # Bo'sh yoki noto'g'ri qiymat kelsa 0 so'm deb yozmasligi uchun tekshiramiz
        if not amount or str(amount).strip() in ["", "-", "0"]:
            return "0"
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


def escape_html(text) -> str:
    return html.escape(str(text)) if text else ""


def find_column_index(headers, keys):
    """Sarlavhalar ichidan kalit so'zlarga mos keladigan ustun indeksini qaytaradi (1-boshlanadi)"""
    for idx, h in enumerate(headers, start=1):
        header_lower = str(h).strip().lower()
        for key in keys:
            if key in header_lower:
                return idx
    return None


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin qidiruv bo'limini boshlaganda"""
    await update.message.reply_text(
        "🔍 <b>Mijozlarni qidirish paneli</b>\n\n"
        "Mijozning <b>Ism-familiyasi</b> yoki <b>Telefon raqamini</b> kiriting:\n"
        "<i>(Masalan: Anvar yoki 901234567)</i>",
        parse_mode="HTML"
    )
    return SEARCH_INPUT


async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qidiruv natijalarini chiqarish"""
    query_text = update.message.text.strip().lower()
    status_msg = await update.message.reply_text("⏳ Ma'lumotlar qidirilmoqda...")

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        
        all_rows = ws.get_all_values()
        if not all_rows or len(all_rows) < 2:
            await status_msg.edit_text("📭 Savdolar jadvali bo'sh.")
            return ConversationHandler.END

        headers = all_rows[0]
        
        # Sarlavhalarga qarab ustunlarni dinamik va xatosiz aniqlaymiz
        name_col = find_column_index(headers, ["mijoz", "ism", "fio", "f.i.o"]) or 2
        phone_col = find_column_index(headers, ["tel", "telefon", "nomer"]) or 4
        tovar_col = find_column_index(headers, ["tovar", "mahsulot", "buyum"]) or 5
        price_col = find_column_index(headers, ["jami", "narxi", "summa", "narx"]) or 6
        status_col = find_column_index(headers, ["holat", "status"]) or 14

        found_results = []
        
        # 2-qatordan boshlab barcha qatorlarni ko'rib chiqamiz
        for idx, row in enumerate(all_rows[1:], start=2):
            if len(row) < 2:
                continue

            # 1. Bekor bo'lgan savdolarni filtrdan o'tkazamiz (CHIQQARMASLIK UCHUN) 🛑
            holat = str(row[status_col - 1]).strip() if len(row) >= status_col else "Faol"
            if "bekor" in holat.lower():
                continue  # Bekor qilingan bo'lsa ro'yxatga qo'shmaymiz, o'tkazib yuboramiz

            # 2. Qidiruv matnini qatordan izlaymiz (Ism yoki Telefon)
            row_dump = " ".join([str(cell).lower() for cell in row])
            if query_text in row_dump:
                mijoz_ismi = row[name_col - 1] if len(row) >= name_col else "Noma'lum"
                # Agar katak bo'sh bo'lsa, baribir Noma'lum bo'lib qolmasligi uchun zaxira
                if not mijoz_ismi or str(mijoz_ismi).strip() == "":
                    mijoz_ismi = "Noma'lum"

                found_results.append({
                    "ism": mijoz_ismi,
                    "tel": row[phone_col - 1] if len(row) >= phone_col else "—",
                    "tovar": row[tovar_col - 1] if len(row) >= tovar_col else "—",
                    "narx": row[price_col - 1] if len(row) >= price_col else "0",
                    "holat": holat if holat else "Faol"
                })

        await status_msg.delete()

        if not found_results:
            await update.message.reply_text("📭 Bunday ma'lumotga ega faol savdo topilmadi.")
            return ConversationHandler.END

        # Natijalarni chiroyli matn holatiga keltiramiz
        response_text = f"🎯 <b>Qidiruv natijalari ({len(found_results)} ta):</b>\n"
        response_text += "━━━━━━━━━━━━━━━━━━━━\n\n"

        for i, res in enumerate(found_results, start=1):
            response_text += (
                f"{i}. <b>{escape_html(res['ism'])}</b>\n"
                f"📞 Tel: <code>{escape_html(res['tel'])}</code>\n"
                f"📦 Tovar: <i>{escape_html(res['tovar'])}</i>\n"
                f"💰 Narxi: <b>{format_money(res['narx'])} so'm</b>\n"
                f"📌 Holat: <code>{escape_html(res['holat'])}</code>\n"
                f"────────────────────\n"
            )

        # Telegram xabar uzunligi chegarasidan oshib ketmasligi uchun (max 4096 belgi)
        if len(response_text) > 4000:
            response_text = response_text[:3900] + "\n\n<i>...va yana ko'plab natijalar bor.</i>"

        await update.message.reply_text(response_text, parse_mode="HTML")
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Qidiruv handlerida xatolik: {e}")
        if 'status_msg' in locals():
            await status_msg.edit_text(f"❌ Xatolik: {escape_html(str(e))}", parse_mode="HTML")
        return ConversationHandler.END


async def cancel_search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Qidiruv paneli yopildi.")
    return ConversationHandler.END