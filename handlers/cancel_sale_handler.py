"""
TexnoVibe — handlers/cancel_sale_handler.py
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date
import html
import os

# Konstantalar
STATUS_COLUMN = 14       # N ustuni - Holat
CANCEL_DATE_COLUMN = 17  # Q ustuni - Bekor qilingan sana

CANCEL_SEARCH, CANCEL_SELECT, CANCEL_CONFIRM = range(30, 33)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


def escape_html(text) -> str:
    """Telegram HTML formati buzilmasligi uchun"""
    return html.escape(str(text)) if text else ""


def find_active_sales(phone_or_id: str) -> list[tuple]:
    """Telefon yoki savdo ID bo'yicha BARCHA faol savdolarni topadi."""
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Savdolar"]
    records = ws.get_all_records()

    search = phone_or_id.strip().upper()
    natija = []

    for i, rec in enumerate(records, start=2):
        if str(rec.get("ID", "")).upper() == search:
            if rec.get("Holat") == "Faol":
                return [(rec, i)]

        phone_clean = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
        search_clean = search.replace(" ", "").replace("-", "").replace("+", "")

        if phone_clean == search_clean and rec.get("Holat") == "Faol":
            natija.append((rec, i))

    return natija


def _sale_card_text(rec: dict) -> str:
    """Bitta savdo ma'lumotlari matni (HTML formatida)"""
    jami = format_money(rec.get("Jami Summa", 0))
    qoldiq = format_money(rec.get("Qoldiq", 0))
    avans = format_money(rec.get("Boshlang'ich To'lov", 0))

    to_lov_turi = rec.get("To'lov Turi") or rec.get("To\'lov Turi") or ""
    keyingi_sana = rec.get("Keyingi To'lov Sanasi") or rec.get("Keyingi To\'lov Sanasi") or ""

    return (
        "🔍 <b>SAVDO TOPILDI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{escape_html(rec.get('ID'))}</code>\n"
        f"📅 Sana: {escape_html(rec.get('Sana'))}\n"
        f"👤 Mijoz: <b>{escape_html(rec.get('FIO'))}</b>\n"
        f"📞 Telefon: <code>{escape_html(rec.get('Telefon'))}</code>\n"
        f"🛍 Tovar: <b>{escape_html(rec.get('Tovar'))}</b>\n"
        f"💵 Jami: <b>{jami} so'm</b>\n"
        f"💰 Avans: <b>{avans} so'm</b>\n"
        f"📊 Qoldiq: <b>{qoldiq} so'm</b>\n"
        f"💳 To'lov turi: <b>{escape_html(to_lov_turi)}</b>\n"
        f"📅 Keyingi to'lov: {escape_html(keyingi_sana)}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Bu savdoni bekor qilmoqchimisiz?"
    )


# 1. BOSHLASH
async def start_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ <b>Savdoni Bekor Qilish</b>\n\n"
        "Savdo ID yoki telefon raqamini kiriting:\n"
        "<i>(Masalan: TXN-001 yoki +998901234567)</i>",
        parse_mode="HTML"
    )
    return CANCEL_SEARCH


# 2. QIDIRISH
async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_text = update.message.text.strip()
    status_msg = await update.message.reply_text("⏳ Qidirilmoqda...")

    try:
        natija = find_active_sales(search_text)

        if not natija:
            await status_msg.edit_text(
                f"❌ <b>'{escape_html(search_text)}'</b> bo'yicha faol savdo topilmadi.\n\n"
                "Savdo ID (TXN-001) yoki telefon raqamini to'g'ri kiriting.",
                parse_mode="HTML"
            )
            return CANCEL_SEARCH

        if len(natija) == 1:
            rec, row_index = natija[0]
            context.user_data["cancel_row"] = row_index
            context.user_data["cancel_rec"] = rec

            keyboard = [[
                InlineKeyboardButton("✅ Ha, bekor qilish", callback_data="do_cancel"),
                InlineKeyboardButton("❌ Yo'q, saqlab qolish", callback_data="keep_sale")
            ]]
            await status_msg.delete()
            await update.message.reply_text(
                _sale_card_text(rec),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CANCEL_CONFIRM

        context.user_data["cancel_natija"] = [
            {"rec": r, "row_index": ri} for r, ri in natija
        ]
        fio = natija[0][0].get("FIO", "Mijoz")

        keyboard = []
        for r, ri in natija:
            tovar = r.get("Tovar", "Tovar")
            sale_id = r.get("ID", f"row-{ri}")
            qoldiq = format_money(r.get("Qoldiq", 0))
            sana = r.get("Sana", "")
            label = f"🛍 {tovar} | Qoldiq: {qoldiq} so'm | {sana}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"cnlsel_{sale_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cnlsel_cancel")])

        await status_msg.delete()
        await update.message.reply_text(
            f"👤 <b>{escape_html(fio)}</b> — {len(natija)} ta faol savdo topildi.\n\n"
            "Qaysi savdoni bekor qilmoqchisiz?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CANCEL_SELECT

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi: <code>{escape_html(str(e))}</code>",
            parse_mode="HTML"
        )
        return ConversationHandler.END


# 3. TOVAR TANLASH
async def cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cnlsel_cancel":
        await query.edit_message_text("❌ Bekor qilish to'xtatildi.")
        context.user_data.clear()
        return ConversationHandler.END

    sale_id = query.data.replace("cnlsel_", "")
    natija = context.user_data.get("cancel_natija", [])

    tanlangan = next(
        (item for item in natija if str(item["rec"].get("ID", "")) == sale_id),
        None
    )

    if not tanlangan:
        await query.edit_message_text("❌ Savdo topilmadi yoki sessiya muddati tugadi.")
        return ConversationHandler.END

    context.user_data["cancel_row"] = tanlangan["row_index"]
    context.user_data["cancel_rec"] = tanlangan["rec"]

    keyboard = [[
        InlineKeyboardButton("✅ Ha, bekor qilish", callback_data="do_cancel"),
        InlineKeyboardButton("❌ Yo'q, saqlab qolish", callback_data="keep_sale")
    ]]
    
    await query.edit_message_text(
        _sale_card_text(tanlangan["rec"]),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CANCEL_CONFIRM


# 4. TASDIQLASH
async def cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "keep_sale":
        await query.edit_message_text("✅ Savdo saqlab qolindi. Hech narsa o'zgarmadi.")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("⏳ Google Sheets yangilanmoqda, kuting...")

    try:
        rec = context.user_data.get("cancel_rec")
        row_index = context.user_data.get("cancel_row")

        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws = sheets["Savdolar"]

        today = date.today().strftime("%d.%m.%Y")
        
        ws.update_cell(row_index, STATUS_COLUMN, "Bekor qilindi")
        ws.update_cell(row_index, CANCEL_DATE_COLUMN, f"Bekor qilindi: {today}")

        try:
            row_range = f"A{row_index}:U{row_index}"
            ws.format(row_range, {
                "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8},
                "textFormat": {"strikethrough": True}
            })
        except Exception:
            pass

        fio = rec.get("FIO", "")
        tovar = rec.get("Tovar", "")
        sid = rec.get("ID", "")
        jami = format_money(rec.get("Jami Summa", 0))
        qoldiq = format_money(rec.get("Qoldiq", 0))

        await query.edit_message_text(
            "✅ <b>SAVDO BEKOR QILINDI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{escape_html(sid)}</code>\n"
            f"👤 Mijoz: <b>{escape_html(fio)}</b>\n"
            f"🛍 Tovar: <b>{escape_html(tovar)}</b>\n"
            f"💵 Jami: {jami} so'm\n"
            f"💰 Qoldiq edi: {qoldiq} so'm\n"
            f"📅 Bekor qilindi: {today}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Google Sheets muvaffaqiyatli yangilandi! ✅",
            parse_mode="HTML"
        )

    except Exception as e:
        await query.edit_message_text(
            f"❌ Sheets'ga yozishda xatolik: <code>{escape_html(str(e))}</code>",
            parse_mode="HTML"
        )

    context.user_data.clear()
    return ConversationHandler.END


# BOSH MENYU / CANCEL
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = int(os.getenv("ADMIN_CHAT_ID", "0"))
    user_id = update.effective_user.id

    if user_id == admin_id:
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("➕ Yangi Savdo"),     KeyboardButton("💰 To'lov Qabul")],
            [KeyboardButton("❌ Bekor Qilish"),    KeyboardButton("📅 Bugungi To'lovlar")],
            [KeyboardButton("👥 Mijozlar"),        KeyboardButton("📊 Statistika")],
            [KeyboardButton("⚠️ Qarzdorlar"),      KeyboardButton("🚫 Qora Ro'yxat")],
            [KeyboardButton("⭐ Reyting"),          KeyboardButton("🔍 Qidirish")],
            [KeyboardButton("🎯 Auksion"),          KeyboardButton("📥 Excel Eksport")],
            [KeyboardButton("🏠 Bosh Menyu")],
        ], resize_keyboard=True)
    else:
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("📊 Mening Kreditim")],
            [KeyboardButton("📝 Ro'yxatdan O'tish")],
            [KeyboardButton("🏠 Bosh Menyu")],
        ], resize_keyboard=True)

    await update.message.reply_text("🏠 Bosh menyuga qaytildi.", reply_markup=keyboard)
    context.user_data.clear()
    return ConversationHandler.END