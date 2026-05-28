"""
Mijoz paneli
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    get_payment_history, save_client_chat_id
)
from datetime import date
import os

REGISTER_PHONE = 40

def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_client_keyboard():
    keyboard = [
        [KeyboardButton("📊 Mening Kreditim")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ro'yxatdan o'tish — telefon so'raydi"""
    await update.message.reply_text(
        "📝 *Royxatdan otish*\n\n"
        "Telefon raqamingizni yozing:\n"
        "_(Masalan: 998901234567 yoki +998901234567)_",
        parse_mode="Markdown"
    )
    return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telefon raqamini qabul qiladi va bazada tekshiradi"""
    phone_input = update.message.text.strip()
    user = update.effective_user
    chat_id = user.id
    username = user.username or ""

    # Telefon raqamini tozalash
    phone_clean = phone_input.replace("+", "").replace(" ", "").replace("-", "")

    if not phone_clean.isdigit() or len(phone_clean) < 9:
        await update.message.reply_text(
            "❌ Telefon raqami noto'g'ri.\n"
            "Qaytadan kiriting:\n"
            "_(Masalan: 998901234567)_",
            parse_mode="Markdown"
        )
        return REGISTER_PHONE

    # + qo'shish
    if not phone_input.startswith("+"):
        phone = "+" + phone_clean
    else:
        phone = phone_input

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_sales = sheets["Savdolar"]
        records = ws_sales.get_all_records()

        found_rec = None
        for rec in records:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            if rec_phone == phone_clean and rec.get("Holat") == "Faol":
                found_rec = rec
                break

        if not found_rec:
            await update.message.reply_text(
                f"❌ `{phone}` raqami bazada topilmadi.\n\n"
                "Telefon raqamingiz to'g'riligini tekshiring\n"
                "yoki do'konimizga murojaat qiling.\n\n"
                "Qaytadan kiriting:",
                parse_mode="Markdown"
            )
            return REGISTER_PHONE

        # Chat ID ni saqlash
        save_client_chat_id(phone, chat_id, username)

        fio = found_rec.get("FIO", "")
        tovar = found_rec.get("Tovar", "")
        qoldiq = format_money(found_rec.get("Qoldiq", 0))
        keyingi = found_rec.get("Keyingi To'lov Sanasi", "")

        await update.message.reply_text(
            f"✅ *Muvaffaqiyatli royxatdan otdingiz!*\n\n"
            f"👤 Ism: *{fio}*\n"
            f"📞 Telefon: `{phone}`\n\n"
            f"📋 *Joriy kredit:*\n"
            f"🛍 {tovar}\n"
            f"💰 Qoldiq: *{qoldiq} so'm*\n"
            f"📅 Keyingi to'lov: *{keyingi}*\n\n"
            f"Endi to'lov eslatmalarini olasiz!\n"
            f"🏪 TexnoVibe",
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Bosh menyuga qaytildi.",
        reply_markup=get_client_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/royhattan_otish buyrug'i"""
    args = context.args
    if args:
        # Argument bilan kelsa — bevosita ro'yxatdan o'tkazish
        context.args = args
        await register_phone(update, context)
    else:
        await start_register(update, context)


async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/mening_malumotlarim"""
    chat_id = update.effective_user.id

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_clients = sheets["Mijozlar"]
        ws_sales = sheets["Savdolar"]

        client_records = ws_clients.get_all_records()
        phone = None
        fio = None

        for rec in client_records:
            if str(rec.get("Chat ID", "")).strip() == str(chat_id):
                phone = str(rec.get("Telefon", ""))
                fio = rec.get("FIO", "")
                break

        if not phone:
            await update.message.reply_text(
                "❌ Siz hali royxatdan otmagansiz!\n\n"
                "Royxatdan otish tugmasini bosing.",
                reply_markup=get_client_keyboard()
            )
            return

        sale_records = ws_sales.get_all_records()
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        active_sales = []

        for rec in sale_records:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            if rec_phone == phone_clean:
                active_sales.append(rec)

        if not active_sales:
            await update.message.reply_text(
                f"👤 *{fio}*\n\n"
                "📋 Hozirda faol kreditingiz yoq.\n\n"
                "🏪 TexnoVibe",
                parse_mode="Markdown",
                reply_markup=get_client_keyboard()
            )
            return

        text = f"👤 *{fio}*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in active_sales:
            holat = rec.get("Holat", "")
            if holat == "Yopildi":
                holat_emoji = "✅"
            elif holat == "Bekor qilindi":
                holat_emoji = "❌"
            else:
                holat_emoji = "🔄"

            tovar = rec.get("Tovar", "")
            jami = format_money(rec.get("Jami Summa", 0))
            qoldiq = format_money(rec.get("Qoldiq", 0))
            tolov_turi = rec.get("To'lov Turi", "")
            tolov_summasi = format_money(rec.get("To'lov Summasi", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "")
            bonus = format_money(rec.get("Kredit Bonusu", 0))

            text += (
                f"{holat_emoji} *{tovar}*\n"
                f"💵 Jami: *{jami} so'm*\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"📅 {tolov_turi} | 💳 {tolov_summasi} so'm\n"
                f"📆 Keyingi to'lov: *{keyingi}*\n"
                f"⭐ Reyting: {reyting}\n"
                f"🎁 Bonus: *{bonus} so'm*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
            )

        history = get_payment_history(phone)
        if history:
            total_paid = sum(float(r.get("To'lov Summasi", 0)) for r in history)
            text += f"📋 *SO'NGGI TO'LOVLAR:*\n"
            for rec in history[-5:]:
                sana = rec.get("To'lov Sanasi", "")
                summa = format_money(rec.get("To'lov Summasi", 0))
                text += f"• {sana} — *{summa} so'm*\n"
            text += f"\n✅ Jami tolangan: *{format_money(total_paid)} so'm*\n"

        text += "\n🏪 TexnoVibe"

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )
