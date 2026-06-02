"""
TexnoVibe — Mijoz paneli
Bekor qilingan savdolarni hisobga olmaydigan xatosiz versiya
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    get_payment_history, save_client_chat_id, ws_to_records
)

REGISTER_PHONE = 40

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

def get_client_keyboard():
    keyboard = [
        [KeyboardButton("📊 Mening Nasiyam")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.registration import start_register
    return await start_register(update, context)

async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_clients = sheets["Mijozlar"]
        ws_sales = sheets["Savdolar"]

        client_records = ws_to_records(ws_clients)
        phone = next((str(r.get("Telefon", "")) for r in client_records if str(r.get("Chat ID", "")) == str(chat_id)), None)

        if not phone:
            await update.message.reply_text("❌ Siz hali ro'yxatdan o'tmagansiz!", reply_markup=get_client_keyboard())
            return

        sale_records = ws_to_records(ws_sales)
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        # Bekor qilinganlarni filtrlab, faqat faollarini olish
        active_sales = [r for r in sale_records if str(r.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "") == phone_clean and "bekor" not in str(r.get("Holat", "")).lower()]

        if not active_sales:
            await update.message.reply_text("📋 Hozirda faol kreditingiz yo'q.", reply_markup=get_client_keyboard())
            return

        text = f"👤 *Mening Nasiyam*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"
        for rec in active_sales:
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += f"🛍 *{tovar}*\n💰 Qoldiq: {qoldiq} so'm\n━━━━━━━━━━━━━━━━━━━━\n"

        history = get_payment_history(phone)
        if history:
            text += "📋 *SO'NGGI TO'LOVLAR:*\n"
            for rec in history[-5:]:
                sana = rec.get("To'lov Sanasi", "")
                summa = format_money(rec.get("To'lov Summasi", 0))
                text += f"• {sana} — *{summa} so'm*\n"
        
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_client_keyboard())

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")