"""
Buyurtma berish handleri
Mijoz katalogdan tovar tanlaydi
Admin Telegramga xabar oladi
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet
from handlers.catalog_handler import ensure_catalog_sheet
from datetime import date
import os

ORDER_SELECT, ORDER_WORKPLACE, ORDER_CONFIRM = range(70, 73)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_active_products():
    sh = get_spreadsheet()
    ws = ensure_catalog_sheet(sh)
    records = ws.get_all_records()
    return [r for r in records if r.get("Holat") == "Faol"]


async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    try:
        products = get_active_products()

        if not products:
            await update.message.reply_text(
                "Hozircha katalogda tovar yoq.\n"
                "Keyinroq qaytib koring!"
            )
            return ConversationHandler.END

        # Tovarlar ro'yxatini tugmalar sifatida ko'rsatish
        keyboard = []
        for rec in products:
            name = rec.get("Tovar Nomi", "")
            price = format_money(rec.get("Narx", 0))
            cat_id = rec.get("ID", "")
            keyboard.append([
                InlineKeyboardButton(
                    f"{name} — {price} som",
                    callback_data=f"order_{cat_id}"
                )
            ])
        keyboard.append([InlineKeyboardButton("Bekor qilish", callback_data="order_cancel")])

        await update.message.reply_text(
            "Buyurtma berish\n\n"
            "Qaysi tovarni olmoqchisiz?\n"
            "Tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ORDER_SELECT

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")
        return ConversationHandler.END


async def order_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_cancel":
        await query.edit_message_text("Bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    cat_id = query.data.replace("order_", "")

    try:
        products = get_active_products()
        selected = None
        for rec in products:
            if rec.get("ID") == cat_id:
                selected = rec
                break

        if not selected:
            await query.edit_message_text("Tovar topilmadi.")
            return ConversationHandler.END

        context.user_data["order_product"] = selected

        name = selected.get("Tovar Nomi", "")
        price = format_money(selected.get("Narx", 0))
        desc = selected.get("Tavsif", "")

        text = (
            "Tanlangan tovar:"
            f"Nomi: {name}"
            f"Narx: {price} som"
        )
        if desc:
            text += f"Tavsif: {desc}"

        await query.edit_message_text(text)
        await query.message.reply_text(
            "Ish joyingizni kiriting:"
            "(Masalan: Bozor, Maktab, Xususiy)"
            "(Yoq bolsa: - yozing)"
        )
        return ORDER_WORKPLACE

    except Exception as e:
        await query.edit_message_text(f"Xatolik: {str(e)}")
        return ConversationHandler.END


async def order_workplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ish joyini qabul qiladi"""
    work_place = update.message.text.strip()
    if work_place == "-":
        work_place = ""
    context.user_data["order_workplace"] = work_place

    selected = context.user_data.get("order_product", {})
    name = selected.get("Tovar Nomi", "")
    price = format_money(selected.get("Narx", 0))

    text = (
        "Buyurtma tasdiqlash:"
        f"Tovar: {name}"
        f"Narx: {price} som"
        f"Ish joyi: {work_place or 'Korsatilmagan'}"
        f"Tasdiqlaysizmi?"
    )
    keyboard = [
        [
            InlineKeyboardButton("Ha, buyurtma beraman", callback_data="order_yes"),
            InlineKeyboardButton("Yoq, bekor", callback_data="order_no")
        ]
    ]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ORDER_CONFIRM


async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_no":
        await query.edit_message_text("Bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    user = query.from_user
    selected = context.user_data.get("order_product", {})
    name = selected.get("Tovar Nomi", "")
    price = format_money(selected.get("Narx", 0))
    cat_id = selected.get("ID", "")
    today = date.today().strftime("%d.%m.%Y %H:%M")

    # Mijozga tasdiqlash xabari
    await query.edit_message_text(
        f"Buyurtmangiz qabul qilindi!\n\n"
        f"Tovar: {name}\n"
        f"Narx: {price} som\n\n"
        f"Tez orada siz bilan boglanamiz.\n"
        f"TexnoVibe"
    )

    # Mijoz ma'lumotlarini topish
    try:
        sh = get_spreadsheet()
        from sheets.google_sheets import ensure_worksheets
        sheets = ensure_worksheets(sh)
        ws_clients = sheets["Mijozlar"]
        client_records = ws_clients.get_all_records()

        client_phone = ""
        client_fio = ""
        for rec in client_records:
            if str(rec.get("Chat ID", "")).strip() == str(user.id):
                client_phone = rec.get("Telefon", "")
                client_fio = rec.get("FIO", "")
                break

        # Buyurtmani Google Sheets ga saqlash
        ws_orders = None
        existing = [ws.title for ws in sh.worksheets()]
        if "Buyurtmalar" not in existing:
            ws_orders = sh.add_worksheet(title="Buyurtmalar", rows=500, cols=8)
            ws_orders.append_row(["ID", "Sana", "FIO", "Telefon", "Chat ID", "Tovar", "Narx", "Holat", "Ish Joyi"])
            ws_orders.format("A1:H1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
        else:
            ws_orders = sh.worksheet("Buyurtmalar")

        all_orders = ws_orders.get_all_values()
        order_id = f"ORD-{len(all_orders):03d}"

        work_place = context.user_data.get("order_workplace", "")
        ws_orders.append_row([
            order_id,
            today,
            client_fio or user.full_name,
            client_phone,
            str(user.id),
            name,
            selected.get("Narx", 0),
            "Yangi",
            work_place
        ])

        # Adminga xabar
        tg_username = f"@{user.username}" if user.username else "Yo'q"
        work_place = context.user_data.get("order_workplace", "")
        admin_msg = (
            "YANGI BUYURTMA!

"
            f"Buyurtma ID: {order_id}
"
            f"Sana: {today}

"
            f"Mijoz: {client_fio or user.full_name}
"
            f"Telefon: {client_phone or 'Royxatdan otmagan'}
"
            f"Telegram: {tg_username}
"
            f"Chat ID: {user.id}

"
            f"Tovar: {name}
"
            f"Narx: {price} som
"
        )
        if work_place:
            admin_msg += f"Ish joyi: {work_place}
"

        await query.get_bot().send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_msg
        )

    except Exception as e:
        await query.get_bot().send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"Yangi buyurtma keldi lekin xatolik: {str(e)}\nMijoz: {user.full_name}"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("📊 Mening Kreditim")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ], resize_keyboard=True)
    await update.message.reply_text("Bosh menyuga qaytildi.", reply_markup=keyboard)
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin uchun buyurtmalar royxati"""
    await update.message.reply_text("Buyurtmalar yuklanmoqda...")

    try:
        sh = get_spreadsheet()
        from sheets.google_sheets import ensure_worksheets
        existing = [ws.title for ws in sh.worksheets()]

        if "Buyurtmalar" not in existing:
            await update.message.reply_text("Hali hech qanday buyurtma yoq.")
            return

        ws = sh.worksheet("Buyurtmalar")
        records = ws.get_all_records()

        if not records:
            await update.message.reply_text("Hali hech qanday buyurtma yoq.")
            return

        # Yangi buyurtmalar
        yangi = [r for r in records if r.get("Holat") == "Yangi"]
        all_orders = records

        text = f"BUYURTMALAR ({len(all_orders)} ta jami | {len(yangi)} ta yangi)\n\n"

        # Oxirgi 20 ta
        for rec in reversed(all_orders[-20:]):
            holat = rec.get("Holat", "")
            if holat == "Yangi":
                emoji = "🆕"
            elif holat == "Tasdiqlangan":
                emoji = "✅"
            elif holat == "Bekor":
                emoji = "❌"
            else:
                emoji = "📋"

            order_id = rec.get("ID", "")
            sana = rec.get("Sana", "")
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "") or "Royxatdan otmagan"
            tovar = rec.get("Tovar", "")
            narx = format_money(rec.get("Narx", 0))

            text += (
                f"{emoji} {order_id} | {sana}\n"
                f"👤 {fio}\n"
                f"📞 {phone}\n"
                f"🛍 {tovar} — {narx} som\n"
                f"Holat: {holat}\n\n"
            )

        if len(all_orders) > 20:
            text += f"... va yana {len(all_orders)-20} ta buyurtma\n"

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")
