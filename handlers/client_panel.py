"""
TexnoVibe — Mijoz paneli
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    save_client_chat_id, ws_to_records
)

REGISTER_PHONE = 40

def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", ".").strip() or 0)
    except:
        return 0

def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)

def get_client_keyboard():
    keyboard = [
        [KeyboardButton("📊 Mening Nasiyam")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    try:
        sh = get_spreadsheet()
        ws_sales = sh.worksheet("Savdolar")
        records = ws_to_records(ws_sales)
        
        # Telefon raqamni topish
        ws_clients = sh.worksheet("Mijozlar")
        client_recs = ws_to_records(ws_clients)
        phone = next((r.get("Telefon") for r in client_recs if str(r.get("Chat ID")) == str(chat_id)), None)

        if not phone:
            await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz!")
            return

        # Bekor qilinganlarni filtrlab, faollarini olish
        active_sales = [r for r in records if str(r.get("Telefon", "")) == str(phone) and "bekor" not in str(r.get("Holat", "")).lower()]

        if not active_sales:
            await update.message.reply_text("📋 Hozirda faol kreditingiz yo'q.")
            return

        text = "👤 *Mening Nasiyam*\n━━━━━━━━━━━━━━━━━━━━\n"
        for rec in active_sales:
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += f"🛍 *{tovar}*\n💰 Qoldiq: {qoldiq} so'm\n━━━━━━━━━━━━━━━━━━━━\n"
        
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_client_keyboard())

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")