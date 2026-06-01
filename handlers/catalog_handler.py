"""
TexnoVibe — handlers/catalog_handler.py
Katalog sahifasi va Tovar qo'shish mantiqlari birlashtirilgan xavfsiz talqin.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
import html
import os

# Konversiya holatlari
CATALOG_MAIN, CATALOG_VIEW = range(40, 42)
ADD_PROD_NAME, ADD_PROD_PRICE, ADD_PROD_CONFIRM = range(45, 48)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


def escape_html(text) -> str:
    return html.escape(str(text)) if text else ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. KATALOGNI KO'RISH BO'LIMI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def start_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Katalog bo'limini boshlash"""
    status_msg = await update.message.reply_text("⏳ Tovar katalogi yuklanmoqda...")
    
    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws = sheets["Tovarlar"]
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
    """Katalogni inline sahifalab ko'rsatish"""
    items = context.user_data.get("catalog_items", [])
    page = context.user_data.get("catalog_page", 0)
    per_page = 5
    
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
        
        tovar_id = item.get("ID", tovar_nomi)
        keyboard.append([InlineKeyboardButton(f"🔎 {tovar_nomi}", callback_data=f"catview_{tovar_id}")])
        
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    
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
    """Sahifalash tugmalari bosilganda"""
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. YANGI TOVAR QO'SHISH BO'LIMI (Import xatosini tuzatish)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yangi tovar qo'shish jarayonini boshlash"""
    context.user_data.clear()
    await update.message.reply_text(
        "➕ <b>Yangi tovar qo'shish</b>\n\n"
        "Tovar nomini kiriting:",
        parse_mode="HTML"
    )
    return ADD_PROD_NAME


async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tovar nomini qabul qilish"""
    name = update.message.text.strip()
    context.user_data["new_prod_name"] = name
    
    await update.message.reply_text(
        f"🛍 Tovar nomi: <b>{escape_html(name)}</b>\n\n"
        "Endi ushbu tovarni narxini kiriting (faqat raqamlarda, masalan: 2500000):",
        parse_mode="HTML"
    )
    return ADD_PROD_PRICE


async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tovar narxini qabul qilish va tasdiqlash so'rash"""
    price_text = update.message.text.strip().replace(" ", "").replace(",", "")
    
    if not price_text.isdigit():
        await update.message.reply_text("❌ Iltimos narxni faqat raqamlarda kiriting:")
        return ADD_PROD_PRICE
        
    context.user_data["new_prod_price"] = int(price_text)
    name = context.user_data.get("new_prod_name")
    formatted_price = format_money(price_text)
    
    keyboard = [[
        InlineKeyboardButton("✅ Saqlash", callback_data="save_prod"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_prod")
    ]]
    
    await update.message.reply_text(
        "📝 <b>Ma'lumotlarni tasdiqlang:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Tovar: <b>{escape_html(name)}</b>\n"
        f"💵 Narxi: <b>{formatted_price} so'm</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Google Sheets'ga saqlashni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_PROD_CONFIRM


async def add_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tasdiqlangandan so'ng Google Sheets'ga yozish"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_prod":
        await query.edit_message_text("❌ Tovar qo'shish bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END
        
    await query.edit_message_text("⏳ Ma'lumot jadvalga yozilmoqda...")
    
    try:
        name = context.user_data.get("new_prod_name")
        price = context.user_data.get("new_prod_price")
        
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws = sheets["Tovarlar"]
        
        # Dinamik ID yaratish (qatorlar soniga qarab)
        existing_rows = len(ws.get_all_values())
        new_id = f"PRD-{str(existing_rows).zfill(3)}"
        
        # Google jadvalga yangi qator qo'shish [ID, Tovar Nomi, Narxi]
        ws.append_row([new_id, name, price])
        
        await query.edit_message_text(
            "✅ <b>TOVAR MUVAFFAQIYATLI QO'SHILDI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{new_id}</code>\n"
            f"📦 Tovar: <b>{escape_html(name)}</b>\n"
            f"💵 Narxi: <b>{format_money(price)} so'm</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Google Sheets muvaffaqiyatli yangilandi! 💾",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Sheets'ga yozishda xatolik: <code>{escape_html(str(e))}</code>", parse_mode="HTML")
        
    context.user_data.clear()
    return ConversationHandler.END