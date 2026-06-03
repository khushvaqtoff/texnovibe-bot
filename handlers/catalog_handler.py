"""
TexnoVibe — handlers/catalog_handler.py
Sheets ustunlari: ID | Tovar Nomi | Narx | Tavsif | PhotoID | Holat | Qoshilgan Sana
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_sheet

logger = logging.getLogger(__name__)

CAT_NAME    = 50
CAT_PRICE   = 51
CAT_DESC    = 52
CAT_PHOTO   = 53
CAT_CONFIRM = 54


async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "📦 *Yangi tovar qo'shish*\n\n1️⃣ Tovar nomini yozing:",
        parse_mode="Markdown",
    )
    return CAT_NAME


async def cat_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_name"] = update.message.text.strip()
    await update.message.reply_text(
        "2️⃣ Narxini yozing (so'mda):\nMasalan: `3500000`",
        parse_mode="Markdown",
    )
    return CAT_PRICE


async def cat_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "").replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("❌ Faqat raqam kiriting! Masalan: `3500000`", parse_mode="Markdown")
        return CAT_PRICE
    context.user_data["cat_price"] = int(text)
    await update.message.reply_text(
        "3️⃣ Qisqacha tavsif yozing:\nMasalan: `Samsung 55 4K OLED TV`",
        parse_mode="Markdown",
    )
    return CAT_DESC


async def cat_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_desc"] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="cat_skip_photo")]]
    await update.message.reply_text(
        "4️⃣ Tovar rasmini yuboring 📸\n\n_(Rasm bo'lmasa pastdagi tugmani bosing)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CAT_PHOTO


async def cat_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data["cat_photo_id"] = photo.file_id
        await update.message.reply_text("✅ Rasm qabul qilindi!")
    else:
        context.user_data["cat_photo_id"] = None
    return await _show_confirm(update, context, via_query=False)


async def cat_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["cat_photo_id"] = None
    await query.edit_message_reply_markup(reply_markup=None)
    return await _show_confirm(update, context, via_query=True)


async def _show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, via_query=False):
    d          = context.user_data
    narx_fmt   = f"{d['cat_price']:,}".replace(",", " ")
    photo_info = "✅ Rasm bor" if d.get("cat_photo_id") else "🚫 Rasmsiz"

    text = (
        "📋 *Tovar ma'lumotlari:*\n\n"
        f"📦 Nom: `{d['cat_name']}`\n"
        f"💰 Narx: `{narx_fmt} so'm`\n"
        f"📝 Tavsif: `{d['cat_desc']}`\n"
        f"🖼 Rasm: {photo_info}\n\n"
        "Tasdiqlaysizmi?"
    )
    keyboard = [[
        InlineKeyboardButton("✅ Ha, saqlash",  callback_data="cat_confirm_yes"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cat_confirm_no"),
    ]]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CAT_CONFIRM


async def cat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cat_confirm_no":
        await query.edit_message_text("❌ Tovar qo'shish bekor qilindi.")
        return ConversationHandler.END

    d = context.user_data
    try:
        ws      = get_sheet("Katalog")
        rows    = ws.get_all_values()
        cat_id  = f"CAT-{len(rows):03d}"
        now     = datetime.now().strftime("%d.%m.%Y")
        ws.append_row([
            cat_id,
            d["cat_name"],
            d["cat_price"],
            d["cat_desc"],
            d.get("cat_photo_id") or "",
            "Faol",
            now
        ])
    except Exception as e:
        logger.error(f"Katalog saqlashda xato: {e}")
        await query.edit_message_text("❌ Xato yuz berdi. Qayta urinib ko'ring.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"✅ *{d['cat_name']}* katalogga qo'shildi!",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ws   = get_sheet("Katalog")
        rows = ws.get_all_records()
    except Exception as e:
        logger.error(f"Katalog olishda xato: {e}")
        await update.message.reply_text("❌ Katalogni yuklab bo'lmadi.")
        return

    if not rows:
        await update.message.reply_text("📦 Katalog hozircha bo'm-bo'sh.")
        return

    # Faqat faol tovarlar
    faol = [p for p in rows if str(p.get("Holat", "")).strip() == "Faol"]
    if not faol:
        await update.message.reply_text("📦 Faol tovar yo'q.")
        return

    await update.message.reply_text(f"🛍 *Katalog — {len(faol)} ta tovar*", parse_mode="Markdown")

    for i, p in enumerate(faol, 1):
        nom = p.get("Tovar Nomi", p.get("Nom", "—"))
        try:
            narx = f"{int(float(p.get('Narx', 0))):,}".replace(",", " ")
        except:
            narx = str(p.get("Narx", ""))

        caption = (
            f"*{i}. {nom}*\n"
            f"💰 Narx: `{narx} so'm`\n"
            f"📝 {p.get('Tavsif', '')}"
        )
        photo_id = str(p.get("PhotoID", "")).strip()
        try:
            if photo_id:
                await update.message.reply_photo(photo=photo_id, caption=caption, parse_mode="Markdown")
            else:
                await update.message.reply_text(caption, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Tovar yuborishda xato: {e}")
            await update.message.reply_text(caption, parse_mode="Markdown")


async def cmd_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Tovar nomini yozing:\n`/tovarchiqar Samsung TV`", parse_mode="Markdown")
        return
    nom = " ".join(context.args)
    try:
        ws   = get_sheet("Katalog")
        rows = ws.get_all_values()
        for i, row in enumerate(rows):
            if row and row[1].strip().lower() == nom.strip().lower():  # B ustun = Tovar Nomi
                ws.delete_rows(i + 1)
                await update.message.reply_text(f"✅ *{nom}* katalogdan o'chirildi.", parse_mode="Markdown")
                return
        await update.message.reply_text(f"❌ *{nom}* topilmadi.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"O'chirishda xato: {e}")
        await update.message.reply_text("❌ Xato yuz berdi.")
