"""
Katalog tizimi
Admin: tovar qoshish, tahrirlash, ochirish
Mijoz: katalogni korish
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date
import os

# Conversation states
CAT_NAME, CAT_PRICE, CAT_DESC, CAT_CONFIRM = range(60, 64)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

CATALOG_HEADERS = ["ID", "Tovar Nomi", "Narx", "Tavsif", "Holat", "Qoshilgan Sana"]


def ensure_catalog_sheet(sh):
    existing = [ws.title for ws in sh.worksheets()]
    if "Katalog" not in existing:
        ws = sh.add_worksheet(title="Katalog", rows=500, cols=10)
        ws.append_row(CATALOG_HEADERS)
        ws.format("A1:F1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.5, "green": 0.2, "blue": 0.8}
        })
    return sh.worksheet("Katalog")


def generate_cat_id(ws):
    records = ws.get_all_values()
    if len(records) <= 1:
        return "CAT-001"
    last = records[-1]
    if last[0].startswith("CAT-"):
        num = int(last[0].split("-")[1]) + 1
        return f"CAT-{num:03d}"
    return f"CAT-{len(records):03d}"


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


# ===== ADMIN: TOVAR QOSHISH =====

async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Yangi tovar qoshish\n\n"
        "Tovar nomini kiriting:\n"
        "(Masalan: Samsung Galaxy A55)"
    )
    return CAT_NAME


async def cat_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Nom juda qisqa. Qaytadan kiriting:")
        return CAT_NAME
    context.user_data["cat_name"] = name
    await update.message.reply_text(
        f"Tovar: {name}\n\n"
        "Narxini kiriting (somda):\n"
        "(Masalan: 3500000)"
    )
    return CAT_PRICE


async def cat_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Narx noto'g'ri. Qaytadan kiriting:")
        return CAT_PRICE

    context.user_data["cat_price"] = price
    await update.message.reply_text(
        f"Narx: {format_money(price)} som\n\n"
        "Tovar tavsifini kiriting:\n"
        "(Qisqacha malumot, xususiyatlari)\n"
        "(O'tkazib yuborish uchun: -)"
    )
    return CAT_DESC


async def cat_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc == "-":
        desc = ""
    context.user_data["cat_desc"] = desc

    name = context.user_data["cat_name"]
    price = format_money(context.user_data["cat_price"])

    text = (
        f"TOVAR MALUMOTLARI\n\n"
        f"Nomi: {name}\n"
        f"Narx: {price} som\n"
    )
    if desc:
        text += f"Tavsif: {desc}\n"
    text += "\nSaqlaymizmi?"

    keyboard = [
        [
            InlineKeyboardButton("Saqlash", callback_data="cat_save"),
            InlineKeyboardButton("Bekor", callback_data="cat_cancel")
        ]
    ]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CAT_CONFIRM


async def cat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cat_cancel":
        await query.edit_message_text("Bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        sh = get_spreadsheet()
        ws = ensure_catalog_sheet(sh)
        cat_id = generate_cat_id(ws)
        today = date.today().strftime("%d.%m.%Y")

        ws.append_row([
            cat_id,
            context.user_data["cat_name"],
            context.user_data["cat_price"],
            context.user_data.get("cat_desc", ""),
            "Faol",
            today
        ])

        await query.edit_message_text(
            f"Tovar muvaffaqiyatli qoshildi!\n\n"
            f"ID: {cat_id}\n"
            f"Nomi: {context.user_data['cat_name']}\n"
            f"Narx: {format_money(context.user_data['cat_price'])} som"
        )

    except Exception as e:
        await query.edit_message_text(f"Xatolik: {str(e)}")

    context.user_data.clear()
    return ConversationHandler.END


# ===== KATALOGNI KORISH (admin va mijoz) =====

async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Katalog yuklanmoqda...")

    try:
        sh = get_spreadsheet()
        ws = ensure_catalog_sheet(sh)
        records = ws.get_all_records()

        active = [r for r in records if r.get("Holat") == "Faol"]

        if not active:
            await update.message.reply_text(
                "Katalog hozircha bosh.\n"
                "Admin tovarlarni qoshishi kerak."
            )
            return

        text = f"TEXNOVIBE KATALOGI ({len(active)} ta tovar)\n\n"

        for i, rec in enumerate(active, 1):
            name = rec.get("Tovar Nomi", "")
            price = format_money(rec.get("Narx", 0))
            desc = rec.get("Tavsif", "")
            cat_id = rec.get("ID", "")

            text += f"{i}. {name}\n"
            text += f"   💰 Narx: {price} som\n"
            if desc:
                text += f"   📝 {desc}\n"
            text += f"   🆔 {cat_id}\n\n"

            # Har 10 ta da yangi xabar
            if i % 10 == 0 and i < len(active):
                await update.message.reply_text(text)
                text = ""

        if text:
            text += "Nasiyaga olish uchun dokonga tashrif buyuring!\nTexnoVibe"
            await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


# ===== ADMIN: TOVAR OCHIRISH =====

async def cmd_remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Foydalanish:\n/tovarchiqar CAT-001"
        )
        return

    cat_id = args[0].strip().upper()

    try:
        sh = get_spreadsheet()
        ws = ensure_catalog_sheet(sh)
        records = ws.get_all_records()

        for i, rec in enumerate(records, start=2):
            if str(rec.get("ID", "")).upper() == cat_id:
                ws.update_cell(i, 5, "Nofaol")
                await update.message.reply_text(
                    f"'{rec.get('Tovar Nomi')}' katalogdan olindi."
                )
                return

        await update.message.reply_text(f"'{cat_id}' topilmadi.")

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")
