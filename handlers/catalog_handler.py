"""
TexnoVibe — handlers/catalog_handler.py
Yakuniy universal talqin: order_handler va bot.py talab qilgan barcha importlarni o'z ichiga oladi.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
import html

logger = logging.getLogger(__name__)

# === CONVERSATION STATES ===
CAT_NAME    = 0
CAT_PRICE   = 1
CAT_DESC    = 2
CAT_PHOTO   = 3   # Rasm yuklash bosqichi
CAT_CONFIRM = 4


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


def escape_html(text) -> str:
    return html.escape(str(text)) if text else ""


def ensure_catalog_sheet():
    """
    order_handler.py yoki boshqa modullar talab qiladigan varoqni tekshirish funksiyasi.
    'Tovarlar' varog'i borligini ta'minlaydi va qaytaradi.
    """
    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        return sheets["Tovarlar"]
    except Exception as e:
        logger.error(f"ensure_catalog_sheet'da xatolik: {e}")
        raise e


# ─────────────────────────────────────────────
# 1. TOVAR QO'SHISH — BOSHLASH
# ─────────────────────────────────────────────
async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "📦 <b>Yangi tovar qo'shish</b>\n\n"
        "1️⃣ Tovar nomini yozing:",
        parse_mode="HTML",
    )
    return CAT_NAME


# ─────────────────────────────────────────────
# 2. NOMNI QABUL QILISH
# ─────────────────────────────────────────────
async def cat_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_name"] = update.message.text.strip()
    await update.message.reply_text(
        "2️⃣ Narxini yozing (so'mda):\nMasalan: <code>3500000</code>",
        parse_mode="HTML",
    )
    return CAT_PRICE


# ─────────────────────────────────────────────
# 3. NARXNI QABUL QILISH
# ─────────────────────────────────────────────
async def cat_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "").replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("❌ Faqat raqam kiriting! Masalan: <code>3500000</code>", parse_mode="HTML")
        return CAT_PRICE

    context.user_data["cat_price"] = int(text)
    await update.message.reply_text(
        "3️⃣ Qisqacha tavsif yozing:\nMasalan: <code>Samsung 55\" 4K OLED TV</code>",
        parse_mode="HTML",
    )
    return CAT_DESC


# ─────────────────────────────────────────────
# 4. TAVSIFNI QABUL QILISH
# ─────────────────────────────────────────────
async def cat_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_desc"] = update.message.text.strip()

    keyboard = [[InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="cat_skip_photo")]]
    await update.message.reply_text(
        "4️⃣ Tovar rasmini yuboring 📸\n\n"
        "<i>(Rasm bo'lmasa pastdagi tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CAT_PHOTO


# ─────────────────────────────────────────────
# 5. RASMNI QABUL QILISH YOKI O'TKAZIB YUBORISH
# ─────────────────────────────────────────────
async def cat_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data["cat_photo_id"] = photo.file_id
        await update.message.reply_text("✅ Rasm qabul qilindi!")
    else:
        context.user_data["cat_photo_id"] = None

    return await _show_confirm(update, context)


async def cat_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["cat_photo_id"] = None
    await query.edit_message_text("⏭ Rasm o'tkazib yuborildi.")
    return await _show_confirm(update, context, via_query=True)


async def _show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, via_query=False):
    d = context.user_data
    narx_formatlangan = format_money(d['cat_price'])
    photo_info = "✅ Rasm bor" if d.get("cat_photo_id") else "🚫 Rasmsiz"

    text = (
        "📋 <b>Tovar ma'lumotlari:</b>\n\n"
        f"📦 Nom: <code>{escape_html(d['cat_name'])}</code>\n"
        f"💰 Narx: <b>{narx_formatlangan} so'm</b>\n"
        f"📝 Tavsif: <i>{escape_html(d['cat_desc'])}</i>\n"
        f"🖼 Rasm: <b>{photo_info}</b>\n\n"
        "Tasdiqlaysizmi?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Ha, saqlash", callback_data="cat_confirm_yes"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data="cat_confirm_no"),
        ]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if via_query:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup,
        )
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)

    return CAT_CONFIRM


# ─────────────────────────────────────────────
# 6. TASDIQLASH VA GOOGLE SHEETS'GA YOZISH
# ─────────────────────────────────────────────
async def cat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cat_confirm_no":
        await query.edit_message_text("❌ Tovar qo'shish bekor qilindi.")
        return ConversationHandler.END

    d = context.user_data
    await query.edit_message_text("⏳ Google Sheets yangilanmoqda...")

    try:
        ws = ensure_catalog_sheet()

        # [Nom, Narx, Tavsif, Photo_ID] tartibida yozish
        ws.append_row([
            d["cat_name"], 
            d["cat_price"], 
            d["cat_desc"], 
            d.get("cat_photo_id") or ""
        ])

        await query.edit_message_text(
            f"✅ <b>{escape_html(d['cat_name'])}</b> katalogga muvaffaqiyatli qo'shildi!",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Katalog saqlashda xato: {e}")
        await query.edit_message_text(f"❌ Xato yuz berdi: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────────────────────────
# KATALOGNI KO'RISH (Barcha foydalanuvchilar uchun)
# ─────────────────────────────────────────────
async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ Katalog yuklanmoqda...")
    try:
        ws = ensure_catalog_sheet()
        records = ws.get_all_records()
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Katalog olishda xato: {e}")
        await status_msg.edit_text("❌ Katalogni yuklab bo'lmadi.")
        return

    if not records:
        await update.message.reply_text("📦 Katalog hozircha bo'm-bo'sh.")
        return

    await update.message.reply_text(
        f"🛍 <b>Katalog — {len(records)} ta tovar</b>",
        parse_mode="HTML",
    )

    for i, p in enumerate(records, 1):
        nom = p.get("Tovar Nomi") or p.get("nom") or p.get("Nom") or "—"
        narxi = p.get("Narxi") or p.get("narx") or p.get("Narx") or 0
        tavsif = p.get("Tavsif") or p.get("tavsif") or ""
        photo_id = p.get("Photo_ID") or p.get("photo_id") or p.get("Rasm") or None

        narx_str = format_money(narxi)
        caption = (
            f"<b>{i}. {escape_html(nom)}</b>\n"
            f"💰 Narx: <code>{narx_str} so'm</code>\n"
            f"📝 <i>{escape_html(tavsif)}</i>"
        )

        if photo_id:
            try:
                await update.message.reply_photo(
                    photo=str(photo_id),
                    caption=caption,
                    parse_mode="HTML",
                )
            except Exception:
                await update.message.reply_text(caption, parse_mode="HTML")
        else:
            await update.message.reply_text(caption, parse_mode="HTML")


# ─────────────────────────────────────────────
# TOVAR O'CHIRISH (Admin uchun)
# ─────────────────────────────────────────────
async def cmd_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❗ Tovar nomini yozing:\n<code>/tovarchiqar Samsung TV</code>",
            parse_mode="HTML",
        )
        return

    nom_qidiruv = " ".join(context.args).strip().lower()
    status_msg = await update.message.reply_text("⏳ Tovar o'chirilmoqda...")

    try:
        ws = ensure_catalog_sheet()
        cells = ws.get_all_values()
        row_to_delete = None
        real_name = ""

        for idx, row in enumerate(cells, start=1):
            if idx == 1:
                continue
            if row and row[0].strip().lower() == nom_qidiruv:
                row_to_delete = idx
                real_name = row[0]
                break

        if row_to_delete:
            ws.delete_rows(row_to_delete)
            await status_msg.edit_text(f"✅ <b>{escape_html(real_name)}</b> katalogdan muvaffaqiyatli o'chirildi!", parse_mode="HTML")
        else:
            await status_msg.edit_text(f"❌ '{escape_html(nom_qidiruv)}' nomli tovar topilmadi.", parse_mode="HTML")

    except Exception as e:
        logger.error(f"O'chirishda xato: {e}")
        await status_msg.edit_text(f"❌ Xatolik: <code>{escape_html(str(e))}</code>", parse_mode="HTML")