"""
TexnoVibe — handlers/cancel_sale_handler.py
Yangilik: Telefon bo'yicha qidirilganda bir nechta faol savdo
          bo'lsa — inline tugmalar bilan tovar tanlash qo'shildi.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date
import os

CANCEL_SEARCH, CANCEL_SELECT, CANCEL_CONFIRM = range(30, 33)
# CANCEL_SELECT — YANGI: bir nechta savdo bo'lganda tanlash


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def find_active_sales(phone_or_id: str) -> list[tuple]:
    """
    Telefon yoki savdo ID bo'yicha BARCHA faol savdolarni topadi.
    Qaytaradi: [(rec, row_index, ws), ...]

    Agar savdo ID berilsa — faqat bitta natija.
    Telefon berilsa — bir nechta bo'lishi mumkin.
    """
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Savdolar"]
    records = ws.get_all_records()

    search = phone_or_id.strip().upper()
    natija = []

    for i, rec in enumerate(records, start=2):
        # Savdo ID bo'yicha aniq qidirish
        if str(rec.get("ID", "")).upper() == search:
            if rec.get("Holat") == "Faol":
                return [(rec, i, ws)]  # ID topildi — bitta qaytarish

        # Telefon bo'yicha qidirish
        phone_clean  = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
        search_clean = search.replace(" ", "").replace("-", "").replace("+", "")

        if phone_clean == search_clean and rec.get("Holat") == "Faol":
            natija.append((rec, i, ws))

    return natija


def _sale_card_text(rec: dict) -> str:
    """Bitta savdo ma'lumotlari matni"""
    jami   = format_money(rec.get("Jami Summa", 0))
    qoldiq = format_money(rec.get("Qoldiq", 0))
    avans  = format_money(rec.get("Boshlang'ich To'lov", 0))

    return (
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
        f"📅 To'lov turi: *{rec.get(\"To'lov Turi\", '')}*\n"
        f"📅 Keyingi to'lov: {rec.get('Keyingi To\'lov Sanasi', '')}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Bu savdoni bekor qilmoqchimisiz?"
    )


# ─────────────────────────────────────────────
# 1. BOSHLASH
# ─────────────────────────────────────────────
async def start_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ *Savdoni Bekor Qilish*\n\n"
        "Savdo ID yoki telefon raqamini kiriting:\n"
        "_(Masalan: TXN-001 yoki +998901234567)_",
        parse_mode="Markdown"
    )
    return CANCEL_SEARCH


# ─────────────────────────────────────────────
# 2. QIDIRISH
# ─────────────────────────────────────────────
async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_text = update.message.text.strip()
    await update.message.reply_text("⏳ Qidirilmoqda...")

    try:
        natija = find_active_sales(search_text)

        if not natija:
            await update.message.reply_text(
                f"❌ *'{search_text}'* bo'yicha faol savdo topilmadi.\n\n"
                "Savdo ID (TXN-001) yoki telefon raqamini to'g'ri kiriting.",
                parse_mode="Markdown"
            )
            return CANCEL_SEARCH

        # ── Bitta savdo ─────────────────────────────────
        if len(natija) == 1:
            rec, row_index, ws = natija[0]
            context.user_data["cancel_row"] = row_index
            context.user_data["cancel_rec"] = rec

            keyboard = [[
                InlineKeyboardButton("✅ Ha, bekor qilish",  callback_data="do_cancel"),
                InlineKeyboardButton("❌ Yo'q, saqlab qolish", callback_data="keep_sale")
            ]]
            await update.message.reply_text(
                _sale_card_text(rec),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CANCEL_CONFIRM

        # ── Bir nechta savdo — tanlash tugmalari ────────
        context.user_data["cancel_natija"] = [
            {"rec": r, "row_index": ri} for r, ri, _ in natija
        ]
        fio = natija[0][0].get("FIO", "Mijoz")

        keyboard = []
        for r, ri, _ in natija:
            tovar     = r.get("Tovar", "Tovar")
            sale_id   = r.get("ID", f"qator-{ri}")
            qoldiq    = format_money(r.get("Qoldiq", 0))
            sana      = r.get("Sana", "")
            label     = f"🛍 {tovar} | qoldiq: {qoldiq} so'm | {sana}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"cnlsel_{sale_id}")])
        keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="cnlsel_cancel")])

        await update.message.reply_text(
            f"👤 *{fio}* — {len(natija)} ta faol savdo topildi.\n\n"
            "Qaysi savdoni bekor qilmoqchisiz?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CANCEL_SELECT

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END


# ─────────────────────────────────────────────
# 3. TOVAR TANLASH (faqat bir nechta savdo bo'lganda)
# ─────────────────────────────────────────────
async def cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cnlsel_cancel":
        await query.edit_message_text("❌ Bekor qilish to'xtatildi.")
        context.user_data.clear()
        return ConversationHandler.END

    sale_id = query.data.replace("cnlsel_", "")
    natija  = context.user_data.get("cancel_natija", [])

    tanlangan = next(
        (item for item in natija if str(item["rec"].get("ID", "")) == sale_id),
        None
    )

    if not tanlangan:
        await query.edit_message_text("❌ Savdo topilmadi. Qayta urinib ko'ring.")
        return ConversationHandler.END

    context.user_data["cancel_row"] = tanlangan["row_index"]
    context.user_data["cancel_rec"] = tanlangan["rec"]

    keyboard = [[
        InlineKeyboardButton("✅ Ha, bekor qilish",    callback_data="do_cancel"),
        InlineKeyboardButton("❌ Yo'q, saqlab qolish", callback_data="keep_sale")
    ]]
    await query.edit_message_text(
        _sale_card_text(tanlangan["rec"]),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CANCEL_CONFIRM


# ─────────────────────────────────────────────
# 4. TASDIQLASH — bekor qilish
# ─────────────────────────────────────────────
async def cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "keep_sale":
        await query.edit_message_text("✅ Savdo saqlab qolindi. Hech narsa o'zgarmadi.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        rec       = context.user_data.get("cancel_rec")
        row_index = context.user_data.get("cancel_row")

        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws = sheets["Savdolar"]

        today = date.today().strftime("%d.%m.%Y")
        ws.update_cell(row_index, 14, "Bekor qilindi")
        ws.update_cell(row_index, 17, f"Bekor qilindi: {today}")

        try:
            row_range = f"A{row_index}:U{row_index}"
            ws.format(row_range, {
                "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8},
                "textFormat": {"strikethrough": True}
            })
        except Exception:
            pass

        fio    = rec.get("FIO", "")
        tovar  = rec.get("Tovar", "")
        sid    = rec.get("ID", "")
        jami   = format_money(rec.get("Jami Summa", 0))
        qoldiq = format_money(rec.get("Qoldiq", 0))

        await query.edit_message_text(
            "✅ *SAVDO BEKOR QILINDI*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: `{sid}`\n"
            f"👤 Mijoz: *{fio}*\n"
            f"🛍 Tovar: *{tovar}*\n"
            f"💵 Jami: {jami} so'm\n"
            f"💰 Qoldiq edi: {qoldiq} so'm\n"
            f"📅 Bekor qilindi: {today}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Google Sheets da yangilandi ✅",
            parse_mode="Markdown"
        )

    except Exception as e:
        await query.edit_message_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────────────────────────
# Conversation ni bekor qilish
# ─────────────────────────────────────────────
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    admin_id = int(os.getenv("ADMIN_CHAT_ID", "0"))
    user_id  = update.effective_user.id

    if user_id == admin_id:
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("➕ Yangi Savdo"),     KeyboardButton("💰 To'lov Qabul")],
            [KeyboardButton("❌ Bekor Qilish"),    KeyboardButton("📅 Bugungi To'lovlar")],
            [KeyboardButton("👥 Mijozlar"),         KeyboardButton("📊 Statistika")],
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
