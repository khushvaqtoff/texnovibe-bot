"""
Mijoz paneli
Yangilik:
  - Ro'yxatdan o'tgan foydalanuvchi qayta bosса — tasdiq xabari
  - Kontakt tugmasi bilan avtomatik telefon yuborish
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestContact
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    get_payment_history, save_client_chat_id, ws_to_records
)
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


def get_contact_keyboard():
    """Kontakt yuborish tugmasi"""
    keyboard = [
        [KeyboardButton("📱 Raqamimni yuborish", request_contact=True)],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def is_registered(chat_id: int) -> dict | None:
    """Foydalanuvchi ro'yxatdan o'tganmi tekshiradi"""
    try:
        sh     = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        for rec in ws_to_records(sheets["Mijozlar"]):
            if str(rec.get("Chat ID", "")).strip() == str(chat_id):
                return rec
    except Exception:
        pass
    return None


async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_user.id
    registered = is_registered(chat_id)

    if registered:
        # Allaqachon ro'yxatdan o'tgan
        phone = registered.get("Telefon", "")
        fio   = registered.get("FIO", "")

        # Faol savdosini topish
        try:
            sh      = get_spreadsheet()
            sheets  = ensure_worksheets(sh)
            records = ws_to_records(sheets["Savdolar"])
            phone_clean = phone.replace("+","").replace(" ","").replace("-","")
            faol = [
                r for r in records
                if str(r.get("Telefon","")).replace("+","").replace(" ","").replace("-","") == phone_clean
                and str(r.get("Holat","")).strip() == "Faol"
            ]
            if faol:
                rec     = faol[0]
                qoldiq  = format_money(rec.get("Qoldiq", 0))
                keyingi = rec.get("Keyingi To'lov Sanasi", "")
                tovar   = rec.get("Tovar", "")
                await update.message.reply_text(
                    f"✅ *Siz allaqachon ro'yxatdan o'tgansiz!*\n\n"
                    f"👤 Ism: *{fio}*\n"
                    f"📞 Telefon: `{phone}`\n\n"
                    f"📋 *Joriy kredit:*\n"
                    f"🛍 {tovar}\n"
                    f"💰 Qoldiq: *{qoldiq} so'm*\n"
                    f"📅 Keyingi to'lov: *{keyingi}*\n\n"
                    f"🏪 TexnoVibe",
                    parse_mode="Markdown",
                    reply_markup=get_client_keyboard()
                )
            else:
                await update.message.reply_text(
                    f"✅ *Siz allaqachon ro'yxatdan o'tgansiz!*\n\n"
                    f"👤 Ism: *{fio}*\n"
                    f"📞 Telefon: `{phone}`\n\n"
                    f"📋 Hozirda faol kreditingiz yo'q.\n\n"
                    f"🏪 TexnoVibe",
                    parse_mode="Markdown",
                    reply_markup=get_client_keyboard()
                )
        except Exception:
            await update.message.reply_text(
                f"✅ *Siz allaqachon ro'yxatdan o'tgansiz!*\n\n"
                f"👤 {fio} | 📞 {phone}",
                parse_mode="Markdown",
                reply_markup=get_client_keyboard()
            )
        return ConversationHandler.END

    # Yangi foydalanuvchi — kontakt tugmasi bilan
    await update.message.reply_text(
        "📝 *Ro'yxatdan o'tish*\n\n"
        "Pastdagi tugmani bosib telefon raqamingizni yuboring 👇\n\n"
        "_(Yoki qo'lda ham yozishingiz mumkin)_",
        parse_mode="Markdown",
        reply_markup=get_contact_keyboard()
    )
    return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    chat_id  = user.id
    username = user.username or ""

    # Kontakt yuborilgan bo'lsa
    if update.message.contact:
        phone_input = update.message.contact.phone_number or ""
        phone_clean = phone_input.replace("+", "").replace(" ", "").replace("-", "")
    else:
        # Qo'lda yozilgan
        phone_input = update.message.text.strip()
        phone_clean = phone_input.replace("+", "").replace(" ", "").replace("-", "")

    if not phone_clean.isdigit() or len(phone_clean) < 9:
        await update.message.reply_text(
            "❌ Telefon raqami noto'g'ri.\nQaytadan kiriting:",
            reply_markup=get_contact_keyboard()
        )
        return REGISTER_PHONE

    phone = ("+" + phone_clean) if not phone_input.startswith("+") else phone_input

    try:
        sh      = get_spreadsheet()
        sheets  = ensure_worksheets(sh)
        records = ws_to_records(sheets["Savdolar"])

        found_rec = None
        for rec in records:
            rec_phone = str(rec.get("Telefon", "")).replace("+","").replace(" ","").replace("-","")
            if rec_phone == phone_clean and str(rec.get("Holat","")).strip() == "Faol":
                found_rec = rec
                break

        if not found_rec:
            await update.message.reply_text(
                f"❌ `{phone}` raqami bazada topilmadi.\n\n"
                "Telefon raqamingiz to'g'riligini tekshiring\n"
                "yoki do'konimizga murojaat qiling.\n\nQaytadan kiriting:",
                parse_mode="Markdown",
                reply_markup=get_contact_keyboard()
            )
            return REGISTER_PHONE

        save_client_chat_id(phone, chat_id, username)

        fio     = found_rec.get("FIO", "")
        tovar   = found_rec.get("Tovar", "")
        qoldiq  = format_money(found_rec.get("Qoldiq", 0))
        keyingi = found_rec.get("Keyingi To'lov Sanasi", "")

        await update.message.reply_text(
            f"✅ *Muvaffaqiyatli ro'yxatdan o'tdingiz!*\n\n"
            f"👤 Ism: *{fio}*\n"
            f"📞 Telefon: `{phone}`\n\n"
            f"📋 *Joriy kredit:*\n"
            f"🛍 {tovar}\n"
            f"💰 Qoldiq: *{qoldiq} so'm*\n"
            f"📅 Keyingi to'lov: *{keyingi}*\n\n"
            f"Endi to'lov eslatmalarini olasiz! 🔔\n"
            f"🏪 TexnoVibe",
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 Bosh menyuga qaytildi.", reply_markup=get_client_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_register(update, context)


async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id

    try:
        sh      = get_spreadsheet()
        sheets  = ensure_worksheets(sh)

        phone = None
        fio   = None
        for rec in ws_to_records(sheets["Mijozlar"]):
            if str(rec.get("Chat ID", "")).strip() == str(chat_id):
                phone = str(rec.get("Telefon", ""))
                fio   = rec.get("FIO", "")
                break

        if not phone:
            await update.message.reply_text(
                "❌ Siz hali ro'yxatdan o'tmagansiz!\n\nRo'yxatdan o'tish tugmasini bosing.",
                reply_markup=get_client_keyboard()
            )
            return

        phone_clean = phone.replace("+","").replace(" ","").replace("-","")
        all_sales   = ws_to_records(sheets["Savdolar"])

        # Bekor qilinganlar chiqmaydi
        korsatish = [
            r for r in all_sales
            if str(r.get("Telefon","")).replace("+","").replace(" ","").replace("-","") == phone_clean
            and str(r.get("Holat","")).strip() != "Bekor qilindi"
        ]

        if not korsatish:
            await update.message.reply_text(
                f"👤 *{fio}*\n\n📋 Hozirda faol kreditingiz yo'q.\n\n🏪 TexnoVibe",
                parse_mode="Markdown",
                reply_markup=get_client_keyboard()
            )
            return

        text = f"👤 *{fio}*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in korsatish:
            holat        = str(rec.get("Holat","")).strip()
            holat_emoji  = "✅" if holat == "Yopildi" else "🔄"
            tovar        = rec.get("Tovar", "")
            jami         = format_money(rec.get("Jami Summa", 0))
            qoldiq       = format_money(rec.get("Qoldiq", 0))
            tolov_turi   = rec.get("To'lov Turi", "")
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

        # To'lovlar tarixi
        try:
            tolovlar = ws_to_records(sheets["Tolovlar"])
            mijoz_tolovlar = [
                r for r in tolovlar
                if str(r.get("Telefon","")).replace("+","").replace(" ","").replace("-","") == phone_clean
            ]
            if mijoz_tolovlar:
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
