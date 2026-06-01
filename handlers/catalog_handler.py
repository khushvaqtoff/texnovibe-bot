"""
TexnoVibe — handlers/catalog_handler.py
Yangilik: Tovar qo'shishda rasm yuklash qo'shildi (CAT_PHOTO state)
Tuzatish: Bot import qila oladigan barcha funksiya nomlari tartibga solindi.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from sheets.catalog_sheets import (
    add_product_to_sheet,
    get_all_products,
    remove_product_from_sheet,
)

logger = logging.getLogger(__name__)

# === CONVERSATION STATES ===
CAT_NAME    = 0
CAT_PRICE   = 1
CAT_DESC    = 2
CAT_PHOTO   = 3   # rasm yuklash bosqichi
CAT_CONFIRM = 4


# ─────────────────────────────────────────────
# TOVAR QO'SHISH — boshlash
# ─────────────────────────────────────────────
async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "📦 *Yangi tovar qo'shish*\n\n"
        "1️⃣ Tovar nomini yozing:",
        parse_mode="Markdown",
    )
    return CAT_NAME


# ─────────────────────────────────────────────
# 1. Nom
# ─────────────────────────────────────────────
async def cat_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_name"] = update.message.text.strip()
    await update.message.reply_text(
        "2️⃣ Narxini yozing (so'mda):\nMasalan: `3500000`",
        parse_mode="Markdown",
    )
    return CAT_PRICE


# ─────────────────────────────────────────────
# 2. Narx
# ─────────────────────────────────────────────
async def cat_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "").replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("❌ Faqat raqam kiriting! Masalan: `3500000`", parse_mode="Markdown")
        return CAT_PRICE

    context.user_data["cat_price"] = int(text)
    await update.message.reply_text(
        "3️⃣ Qisqacha tavsif yozing:\nMasalan: `Samsung 55\" 4K OLED TV`",
        parse_mode="Markdown",
    )
    return CAT_DESC


# ─────────────────────────────────────────────
# 3. Tavsif
# ─────────────────────────────────────────────
async def cat_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_desc"] = update.message.text.strip()

    keyboard = [[InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="cat_skip_photo")]]
    await update.message.reply_text(
        "4️⃣ Tovar rasmini yuboring 📸\n\n"
        "_(Rasm bo'lmasa pastdagi tugmani bosing)_",
        "Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CAT_PHOTO


# ─────────────────────────────────────────────
# 4. Rasm
# ─────────────────────────────────────────────
async def cat_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi rasm yuborsa saqlaydi"""
    if update.message and update.message.photo:
        # Eng yuqori sifatli rasmni olish
        photo = update.message.photo[-1]
        context.user_data["cat_photo_id"] = photo.file_id
        await update.message.reply_text("✅ Rasm qabul qilindi!")
    else:
        context.user_data["cat_photo_id"] = None

    return await _show_confirm(update, context)


async def cat_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'O'tkazib yuborish' tugmasi bosilsa"""
    query = update.callback_query
    await query.answer()
    context.user_data["cat_photo_id"] = None
    await query.edit_message_text("⏭ Rasm o'tkazib yuborildi.")
    return await _show_confirm(update, context, via_query=True)


async def _show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, via_query=False):
    """Tasdiqlash xabarini ko'rsatish"""
    d = context.user_data
    narx_formatlangan = f"{d['cat_price']:,}".replace(",", " ")
    photo_info = "✅ Rasm bor" if d.get("cat_photo_id") else "🚫 Rasmsiz"

    text = (
        "📋 *Tovar ma'lumotlari:*\n\n"
        f"📦 Nom: `{d['cat_name']}`\n"
        f"💰 Narx: `{narx_formatlangan} so'm`\n"
        f"📝 Tavsif: `{d['cat_desc']}`\n"
        f"🖼 Rasm: {photo_info}\n\n"
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
            parse_mode="Markdown",
            reply_markup=markup,
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)

    return CAT_CONFIRM


# ─────────────────────────────────────────────
# 5. Tasdiqlash
# ─────────────────────────────────────────────
async def cat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cat_confirm_no":
        await query.edit_message_text("❌ Tovar qo'shish bekor qilindi.")
        return ConversationHandler.END

    d = context.user_data
    try:
        add_product_to_sheet(
            name=d["cat_name"],
            price=d["cat_price"],
            desc=d["cat_desc"],
            photo_id=d.get("cat_photo_id"),
        )
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


# ─────────────────────────────────────────────
# KATALOGNI KO'RISH
# ─────────────────────────────────────────────
async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha tovarlarni rasmli yoki rasmsiz ko'rsatish"""
    try:
        products = get_all_products()
    except Exception as e:
        logger.error(f"Katalog olishda xato: {e}")
        await update.message.reply_text("❌ Katalogni yuklab bo'lmadi.")
        return

    if not products:
        await update.message.reply_text("📦 Katalog hozircha bo'm-bo'sh.")
        return

    await update.message.reply_text(
        f"🛍 *Katalog — {len(products)} ta tovar*",
        parse_mode="Markdown",
    )

    for i, p in enumerate(products, 1):
        narx = f"{int(p.get('narx', 0)):,}".replace(",", " ")
        caption = (
            f"*{i}. {p.get('nom', '—')}*\n"
            f"💰 Narx: `{narx} so'm`\n"
            f"📝 {p.get('tavsif', '')}"
        )

        photo_id = p.get("photo_id")
        if photo_id:
            await update.message.reply_photo(
                photo=photo_id,
                caption=caption,
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(caption, parse_mode="Markdown")


# ─────────────────────────────────────────────
# TOVAR O'CHIRISH (admin)
# ─────────────────────────────────────────────
async def cmd_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❗ Tovar nomini yozing:\n`/tovarchiqar Samsung TV`",
            parse_mode="Markdown",
        )
        return

    nom = " ".join(context.args)
    try:
        result = remove_product_from_sheet(nom)
        if result:
            await update.message.reply_text(f"✅ *{nom}* katalogdan o'chirildi.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ *{nom}* topilmadi.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"O'chirishda xato: {e}")
        await update.message.reply_text("❌ Xato yuz berdi.")