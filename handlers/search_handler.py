"""
TexnoVibe — handlers/search_handler.py
Mijozlarni Ismi yoki Telefon raqami bo'yicha Google Sheets'dan qidirish paneli.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
import html

logger = logging.getLogger(__name__)

# Konversiya holati
SEARCH_QUERY = 100

def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)

def escape_html(text) -> str:
    return html.escape(str(text)) if text else ""

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qidiruv bo'limini boshlash"""
    context.user_data.clear()
    await update.message.reply_text(
        "🔍 <b>Mijozlarni qidirish paneli</b>\n\n"
        "Mijozning <b>Ism-familiyasi</b> yoki <b>Telefon raqamini</b> kiriting:\n"
        "<i>(Masalan: Anvar yoki 901234567)</i>",
        parse_mode="HTML"
    )
    return SEARCH_QUERY

async def search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiritilgan so'rov bo'yicha Google Sheets'dan ma'lumotlarni qidirish"""
    query_text = update.message.text.strip().lower()
    
    if len(query_text) < 3:
        await update.message.reply_text("⚠️ Qidiruv aniqroq bo'lishi uchun kamida 3 ta belgi kiriting:")
        return SEARCH_QUERY

    status_msg = await update.message.reply_text("⏳ Google Sheets'dan qidirilmoqda, kuting...")

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        
        # Savdolar yoki Mijozlar varog'idan qidirish (Sizda qaysi biri faol bo'lsa)
        ws = sheets["Savdolar"]
        records = ws.get_all_records()
        
        found_items = []
        for r in records:
            # Jadvaldagi ustun nomlarini tekshiramiz (Mijoz, Ismi, Telefon va hokazo)
            mijoz_ismi = str(r.get("Mijoz", r.get("Ismi", r.get("Mijoz Ismi", "")))).strip().lower()
            telefon = str(r.get("Telefon", r.get("Tel", r.get("Telefon Raqami", "")))).strip().lower()
            
            if query_text in mijoz_ismi or query_text in telefon:
                found_items.append(r)

        await status_msg.delete()

        if not found_items:
            await update.message.reply_text(
                f"📭 <code>{escape_html(update.message.text)}</code> bo'yicha hech qanday ma'lumot topilmadi.",
                parse_mode="HTML"
            )
            return ConversationHandler.END

        # Topilgan mijozlar ro'yxatini chiroyli formatda chiqarish
        response_text = f"🎯 <b>Qidiruv natijalari ({len(found_items)} ta):</b>\n"
        response_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for idx, item in enumerate(found_items, 1):
            nomi = item.get("Mijoz", item.get("Ismi", "Noma'lum"))
            tel = item.get("Telefon", item.get("Tel", "—"))
            tovar = item.get("Tovar", item.get("Tovar Nomi", "—"))
            jami = format_money(item.get("Jami", item.get("Narxi", 0)))
            holat = item.get("Holat", item.get("Status", "Faol"))
            
            response_text += (
                f"<b>{idx}. {escape_html(nomi)}</b>\n"
                f"📞 Tel: <code>{escape_html(tel)}</code>\n"
                f"📦 Tovar: <i>{escape_html(tovar)}</i>\n"
                f"💰 Narxi: <b>{jami} so'm</b>\n"
                f"📌 Holat: <code>{escape_html(holat)}</code>\n"
                f"────────────────────\n"
            )
            
            # Telegram xabar limiti (4096 belgi) oshib ketmasligi uchun xabarni bo'lib yuboramiz
            if len(response_text) > 3000:
                await update.message.reply_text(response_text, parse_mode="HTML")
                response_text = ""

        if response_text:
            await update.message.reply_text(response_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Qidiruvda xatolik: {e}")
        await status_msg.edit_text(f"❌ Qidiruv tizimida xatolik yuz berdi: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

    return ConversationHandler.END