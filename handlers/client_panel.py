from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

def format_money(val):
    return f"{float(val):,.0f}".replace(",", " ")

async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 Telefon raqamingizni yuboring:")
    return 1

async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Ro'yxatdan o'tildi.")
    return ConversationHandler.END

async def cancel_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Importni funksiya ichiga o'tkazish
    from sheets.google_sheets import get_spreadsheet, ensure_worksheets, ws_to_records, get_payment_history
    
    chat_id = update.effective_user.id
    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        client = next((r for r in ws_to_records(sheets["Mijozlar"]) if str(r.get("Chat ID", "")) == str(chat_id)), None)
        
        if not client:
            await update.message.reply_text("❌ Siz hali ro'yxatdan o'tmagansiz!")
            return
        
        phone = str(client.get("Telefon", ""))
        sale_records = ws_to_records(sheets["Savdolar"])
        
        def clean_phone(p):
            return "".join(filter(str.isdigit, str(p)))[-9:]

        phone_clean = clean_phone(phone)
        
        active_sales = [
            r for r in sale_records 
            if clean_phone(r.get("Telefon", "")) == phone_clean 
            and "bekor" not in str(r.get("Holat", "")).lower()
        ]

        if not active_sales:
            await update.message.reply_text("📋 Hozirda faol kreditingiz yo'q.")
            return

        text = f"👤 *Mening Nasiyam*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"
        for rec in active_sales:
            tovar = rec.get("Tovar", "Noma'lum")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += f"🛍 *{tovar}*\n💰 Qoldiq: {qoldiq} so'm\n━━━━━━━━━━━━━━━━━━━━\n"

        history = get_payment_history(phone)
        if history:
            text += "📋 *SO'NGGI TO'LOVLAR:*\n"
            history_sorted = sorted(history, key=lambda x: str(x.get("To'lov Sanasi", "")), reverse=True)
            for rec in history_sorted[:5]:
                sana = rec.get("To'lov Sanasi", "Sana yo'q")
                summa = format_money(rec.get("To'lov Summasi", 0))
                text += f"• {sana} — *{summa} so'm*\n"
        else:
            text += "\n⏳ To'lovlar tarixi topilmadi."
        
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")