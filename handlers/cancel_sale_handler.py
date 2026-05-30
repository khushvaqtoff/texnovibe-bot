"""
Savdoni bekor qilish handleri
/bekorqilish buyrug'i
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date

CANCEL_SEARCH, CANCEL_CONFIRM = range(30, 32)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def find_active_sale(phone_or_id: str) -> tuple:
    """
    Telefon yoki savdo ID bo'yicha faol savdoni topadi
    Qaytaradi: (record, row_index) yoki (None, None)
    """
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Savdolar"]
    records = ws.get_all_records()

    search = phone_or_id.strip().upper()

    for i, rec in enumerate(records, start=2):
        # Savdo ID bo'yicha qidirish
        if str(rec.get("ID", "")).upper() == search:
            if rec.get("Holat") == "Faol":
                return rec, i, ws

        # Telefon bo'yicha qidirish
        phone_clean = str(rec.get("Telefon", "")).replace(" ", "").replace("-", "")
        search_clean = search.replace(" ", "").replace("-", "").replace("+", "")
        phone_clean2 = phone_clean.replace("+", "")

        if phone_clean2 == search_clean and rec.get("Holat") == "Faol":
            return rec, i, ws

    return None, None, None


async def start_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/bekorqilish — Savdoni bekor qilish"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ *Savdoni Bekor Qilish*\n\n"
        "Savdo ID yoki telefon raqamini kiriting:\n"
        "_(Masalan: TXN-001 yoki +998901234567)_",
        parse_mode="Markdown"
    )
    return CANCEL_SEARCH


async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Savdoni qidiradi"""
    search_text = update.message.text.strip()

    await update.message.reply_text("⏳ Qidirilmoqda...")

    try:
        rec, row_index, ws = find_active_sale(search_text)

        if not rec:
            await update.message.reply_text(
                f"❌ *'{search_text}'* bo'yicha faol savdo topilmadi.\n\n"
                "Savdo ID (TXN-001) yoki telefon raqamini to'g'ri kiriting.",
                parse_mode="Markdown"
            )
            return CANCEL_SEARCH

        # Topilgan savdoni ko'rsatish
        context.user_data["cancel_row"] = row_index
        context.user_data["cancel_rec"] = rec

        jami = format_money(rec.get("Jami Summa", 0))
        qoldiq = format_money(rec.get("Qoldiq", 0))
        avans = format_money(rec.get("Boshlang'ich To'lov", 0))
        tolov_turi = rec.get("To'lov Turi", "")
        keyingi = rec.get("Keyingi To'lov Sanasi", "")

        text = (
            "🔍 *SAVDO TOPILDI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: `{rec.get('ID')}`\n"
            f"📅 Sana: {rec.get('Sana')}\n"
            f"👤 Mijoz: *{rec.get('FIO')}*\n"
            f"📞 Telefon: `{rec.get('Telefon')}`\n"
            f"🛍 Tovar: *{rec.get('Tovar')}*\n"
            f"💵 Jami: *{jami} so'm*\n"
            f"💰 Avans: *{avans} so'm*\n"
            f"📊 Qoldiq: *{qoldiq} so'm*\n"
            f"📅 To'lov turi: *{tolov_turi}*\n"
            f"📅 Keyingi to'lov: {keyingi}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ Bu savdoni bekor qilmoqchimisiz?"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, bekor qilish", callback_data="do_cancel"),
                InlineKeyboardButton("❌ Yo'q, saqlab qolish", callback_data="keep_sale")
            ]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CANCEL_CONFIRM

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END


async def cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekor qilishni tasdiqlaydi"""
    query = update.callback_query
    await query.answer()

    if query.data == "keep_sale":
        await query.edit_message_text(
            "✅ Savdo saqlab qolindi. Hech narsa o'zgarmadi."
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Bekor qilish
    try:
        rec = context.user_data.get("cancel_rec")
        row_index = context.user_data.get("cancel_row")

        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws = sheets["Savdolar"]

        # Holat va izohni yangilash
        today = date.today().strftime("%d.%m.%Y")
        ws.update_cell(row_index, 14, "Bekor qilindi")
        ws.update_cell(row_index, 17, f"Bekor qilindi: {today}")

        # Butun qatorni qizil rang bilan belgilash
        try:
            row_range = f"A{row_index}:U{row_index}"
            ws.format(row_range, {
                "backgroundColor": {
                    "red": 1.0,
                    "green": 0.8,
                    "blue": 0.8
                },
                "textFormat": {
                    "strikethrough": True
                }
            })
        except Exception as fmt_err:
            pass  # Format xatosi bo'lsa davom etamiz

        fio = rec.get("FIO", "")
        tovar = rec.get("Tovar", "")
        sale_id = rec.get("ID", "")
        jami = format_money(rec.get("Jami Summa", 0))
        qoldiq = format_money(rec.get("Qoldiq", 0))

        success_text = (
            "✅ *SAVDO BEKOR QILINDI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: `{sale_id}`\n"
            f"👤 Mijoz: *{fio}*\n"
            f"🛍 Tovar: {tovar}\n"
            f"💵 Jami: {jami} so'm\n"
            f"💰 Qoldiq edi: {qoldiq} so'm\n"
            f"📅 Bekor qilindi: {today}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Google Sheets da yangilandi ✅"
        )

        await query.edit_message_text(success_text, parse_mode="Markdown")

    except Exception as e:
        await query.edit_message_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Conversation ni bekor qilish"""
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    import os
    admin_id = int(os.getenv("ADMIN_CHAT_ID", "0"))
    user_id = update.effective_user.id

    if user_id == admin_id:
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("➕ Yangi Savdo"), KeyboardButton("💰 To'lov Qabul")],
            [KeyboardButton("❌ Bekor Qilish"), KeyboardButton("📅 Bugungi To'lovlar")],
            [KeyboardButton("👥 Mijozlar"), KeyboardButton("📊 Statistika")],
            [KeyboardButton("⚠️ Qarzdorlar"), KeyboardButton("🚫 Qora Ro'yxat")],
            [KeyboardButton("⭐ Reyting"), KeyboardButton("🔍 Qidirish")],
            [KeyboardButton("🎯 Auksion"), KeyboardButton("📥 Excel Eksport")],
            [KeyboardButton("🏠 Bosh Menyu")],
        ], resize_keyboard=True)
    else:
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("📊 Mening Kreditim")],
            [KeyboardButton("📝 Ro'yxatdan O'tish")],
            [KeyboardButton("🏠 Bosh Menyu")],
        ], resize_keyboard=True)

    await update.message.reply_text(
        "🏠 Bosh menyuga qaytildi.",
        reply_markup=keyboard
    )
    context.user_data.clear()
    return ConversationHandler.END
