"""
TexnoVibe — handlers/catalog_handler.py
Katalog sahifasi — tovarlar va narxlar ro'yxati, inline sahifalash.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
import html

CATALOG_MAIN, CATALOG_VIEW = range(40, 42)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


def escape_html(text) -> str:
    return html.escape(str(text)) if text else ""


async def start_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Katalog bo'limini boshlash"""
    status_msg = await update.message.reply_text("⏳ Tovar katalogi yuklanmoqda...")
    
    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws = sheets["Tovarlar"]  # "Tovarlar" varog'i
        records = ws.get_all_records()
        
        if not records:
            await status_msg.edit_text("📭 Hozircha katalogda tovarlar mavjud emas.")
            return ConversationHandler.END
            
        context.user_data["catalog_items"] = records
        context.user_data["catalog_page"] = 0
        
        await status_msg.delete()
        await send_catalog_page(update.message, context)
        return CATALOG_MAIN
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Katalog yuklashda xatolik: <code>{escape_html(str(e))}</code>", parse_mode="HTML")
        return ConversationHandler.END


async def send_catalog_page(message, context: ContextTypes.DEFAULT_TYPE, edit=False):
    """Katalogni sahifalab (pagination) ko'rsatish"""
    items = context.user_data.get("catalog_items", [])
    page = context.user_data.get("catalog_page", 0)
    per_page = 5  # Har bir sahifada 5 tadan tovar
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_items = items[start_idx:end_idx]
    
    total_pages = (len(items) + per_page - 1) // per_page
    
    text = f"🛍 <b>TexnoVibe — Tovar Katalogi</b> (Sahifa {page + 1}/{total_pages})\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    keyboard = []
    for item in page_items:
        tovar_nomi = item.get("Tovar Nomi", "Noma'lum tovar")
        narxi = format_money(item.get("Narxi", 0))
        text += f"▪️ <b>{escape_html(tovar_nomi)}</b> — {narxi} so'm\n"
        
        # Har bir tovar uchun alohida ko'rish tugmasi (ixtiyoriy)
        tovar_id = item.get("ID", tovar_nomi)
        keyboard.append([InlineKeyboardButton(f"🔎 {tovar_nomi}", callback_data=f"catview_{tovar_id}")])
        
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    
    # Sahifalash tugmalari (Orqaga / Oldinga)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Orqaga", callback_data="catprev"))
    if end_idx < len(items):
        nav_buttons.append(InlineKeyboardButton("Oldinga ➡️", callback_data="catnext"))
        
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    keyboard.append([InlineKeyboardButton("❌ Katalogni yopish", callback_data="catclose")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)


async def catalog_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sahifadan sahifaga o'tish hodisalarini boshqarish"""
    query = update.callback_query
    await query.answer()
    
    page = context.user_data.get("catalog_page", 0)
    
    if query.data == "catnext":
        context.user_data["catalog_page"] = page + 1
        await send_catalog_page(query.message, context, edit=True)
        return CATALOG_MAIN
        
    elif query.data == "catprev":
        context.user_data["catalog_page"] = page - 1
        await send_catalog_page(query.message, context, edit=True)
        return CATALOG_MAIN
        
    elif query.data == "catclose":
        await query.edit_message_text("🏠 Katalog yopildi.")
        context.user_data.clear()
        return ConversationHandler.END
        
    return CATALOG_MAIN