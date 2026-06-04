"""
Mijoz paneli
Tuzatildi:
  - Bekor qilingan savdolar ko'rsatilmaydi
  - To'lovlar tarixi to'g'ri ustundan o'qiladi
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    get_payment_history, save_client_chat_id, ws_to_records
)
from datetime import date
import os

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


async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 *Royxatdan otish*\n\n"
        "Telefon raqamingizni yozing:\n"
        "_(Masalan: 998901234567 yoki +998901234567)_",
        parse_mode="Markdown"
    )
    return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone_input = update.message.text.strip()
    user        = update.effective_user
    chat_id     = user.id
    username    = user.username or ""

    phone_clean = phone_input.replace("+", "").replace(" ", "").replace("-", "")
    if not phone_clean.isdigit() or len(phone_clean) < 9:
        await update.message.reply_text(
            "❌ Telefon raqami noto'g'ri.\nQaytadan kiriting:\n_(Masalan: 998901234567)_",
            parse_mode="Markdown"
        )
        return REGISTER_PHONE

    phone = ("+" + phone_clean) if not phone_input.startswith("+") else phone_input

    try:
        sh      = get_spreadsheet()
        sheets  = ensure_worksheets(sh)
        records = ws_to_records(sheets["Savdolar"])

        found_rec = None
        for rec in records:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            holat     = str(rec.get("Holat", "")).strip()
            if rec_phone == phone_clean and holat == "Faol":
                found_rec = rec
                break

        if not found_rec:
            await update.message.reply_text(
                f"❌ `{phone}` raqami bazada topilmadi.\n\n"
                "Telefon raqamingiz to'g'riligini tekshiring\n"
                "yoki do'konimizga murojaat qiling.\n\nQaytadan kiriting:",
                parse_mode="Markdown"
            )
            return REGISTER_PHONE

        save_client_chat_id(phone, chat_id, username)

        fio     = found_rec.get("FIO", "")
        tovar   = found_rec.get("Tovar", "")
        qoldiq  = format_money(found_rec.get("Qoldiq", 0))
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
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 Bosh menyuga qaytildi.", reply_markup=get_client_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        context.args = args
        await register_phone(update, context)
    else:
        await start_register(update, context)


async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id

    try:
        sh      = get_spreadsheet()
        sheets  = ensure_worksheets(sh)

        # Mijozni topish
        phone = None
        fio   = None
        for rec in ws_to_records(sheets["Mijozlar"]):
            if str(rec.get("Chat ID", "")).strip() == str(chat_id):
                phone = str(rec.get("Telefon", ""))
                fio   = rec.get("FIO", "")
                break

        if not phone:
            await update.message.reply_text(
                "❌ Siz hali royxatdan otmagansiz!\n\nRoyxatdan otish tugmasini bosing.",
                reply_markup=get_client_keyboard()
            )
            return

        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")

        # Savdolarni olish — FAQAT faol va yopilgan (bekor qilinganlar chiqmaydi)
        all_sales = ws_to_records(sheets["Savdolar"])
        korsatish = []
        for rec in all_sales:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            holat     = str(rec.get("Holat", "")).strip()
            if rec_phone == phone_clean and holat != "Bekor qilindi":
                korsatish.append(rec)

        if not korsatish:
            await update.message.reply_text(
                f"👤 *{fio}*\n\n📋 Hozirda faol kreditingiz yo'q.\n\n🏪 TexnoVibe",
                parse_mode="Markdown",
                reply_markup=get_client_keyboard()
            )
            return

        text = f"👤 *{fio}*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in korsatish:
            holat = str(rec.get("Holat", "")).strip()
            if holat == "Yopildi":
                holat_emoji = "✅"
            else:
                holat_emoji = "🔄"

            tovar        = rec.get("Tovar", "")
            jami         = format_money(rec.get("Jami Summa", 0))
            qoldiq       = format_money(rec.get("Qoldiq", 0))
            tolov_turi   = rec.get("To'lov Turi", "")
            # Oylik to'lov miqdori
            oylik        = format_money(rec.get("To'lov Summasi", rec.get("Oylik To'lov", 0)))
            keyingi      = rec.get("Keyingi To'lov Sanasi", "")
            reyting      = rec.get("Reyting", "")
            bonus        = format_money(rec.get("Kredit Bonusu", 0))
            tolangan     = format_money(rec.get("To'langan Summa", 0))

            text += (
                f"{holat_emoji} *{tovar}*\n"
                f"💵 Jami: *{jami} so'm*\n"
                f"✅ To'langan: *{tolangan} so'm*\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"📅 {tolov_turi} | 💳 Oylik: *{oylik} so'm*\n"
                f"📆 Keyingi to'lov: *{keyingi}*\n"
                f"⭐ Reyting: {reyting}\n"
                f"🎁 Bonus: *{bonus} so'm*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
            )

        # To'lovlar tarixi — Tolovlar varag'idan
        try:
            tolovlar = ws_to_records(sheets["Tolovlar"])
            mijoz_tolovlar = [
                r for r in tolovlar
                if str(r.get("Telefon", "")).replace("+","").replace(" ","").replace("-","") == phone_clean
            ]
            if mijoz_tolovlar:
                # To'lov Summasi ustuni Tolovlar varag'ida
                total_paid = sum(safe_float(r.get("To'lov Summasi", 0)) for r in mijoz_tolovlar)
                text += f"📋 *SO'NGGI TO'LOVLAR:*\n"
                for r in mijoz_tolovlar[-5:]:
                    sana  = r.get("To'lov Sanasi", "")
                    summa = format_money(r.get("To'lov Summasi", 0))
                    text += f"• {sana} — *{summa} so'm*\n"
                text += f"\n✅ Jami to'langan: *{format_money(total_paid)} so'm*\n"
        except Exception:
            pass

        text += "\n🏪 TexnoVibe"

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")
