"""
Buyurtma berish handleri
Mijoz katalogdan tovar tanlaydi
Admin Telegramga xabar oladi
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ws_to_records
from handlers.catalog_handler import ensure_catalog_sheet
from datetime import datetime  # TUZATISH: date o'rniga datetime ishlatiladi
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
    records = ws_to_records(ws)
    return [r for r in records if r.get("Holat") == "Faol"]


async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    try:
        products = get_active_products()

        if not products:
            await update.message.reply_text(
                "🛍 Hozircha katalogda tovar yo'q.\n"
                "Keyinroq qaytib ko'ring!"
            )
            return ConversationHandler.END

        keyboard = []
        for rec in products:
            name = rec.get("Tovar Nomi", "")
            price = format_money(rec.get("Narx", 0))
            cat_id = rec.get("ID", "")
            keyboard.append([
                InlineKeyboardButton(
                    f"{name} — {price} so'm",
                    callback_data=f"order_{cat_id}"
                )
            ])
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="order_cancel")])

        await update.message.reply_text(
            "🛒 Buyurtma berish\n\n"
            "Qaysi tovarni olmoqchisiz?\n"
            "Tanlang 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ORDER_SELECT

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")
        return ConversationHandler.END


async def order_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_cancel":
        await query.edit_message_text("❌ Bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    cat_id = query.data.replace("order_", "")

    try:
        products = get_active_products()
        selected = None
        for rec in products:
            if str(rec.get("ID")) == str(cat_id):
                selected = rec
                break

        if not selected:
            await query.edit_message_text("❌ Tovar topilmadi.")
            return ConversationHandler.END

        context.user_data["order_product"] = selected

        name = selected.get("Tovar Nomi", "")
        price = format_money(selected.get("Narx", 0))
        desc = selected.get("Tavsif", "")

        # TUZATISH: \n qo'shildi, matn to'g'ri formatda chiqadi
        text = (
            f"✅ Tanlangan tovar:\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍 Nomi: {name}\n"
            f"💵 Narx: {price} so'm\n"
        )
        if desc:
            text += f"📝 Tavsif: {desc}\n"
        text += "━━━━━━━━━━━━━━━━━━━━"

        await query.edit_message_text(text)
        await query.message.reply_text(
            "🏢 Ish joyingizni kiriting:\n"
            "(Masalan: Bozor, Maktab, Xususiy)\n"
            "(Yo'q bo'lsa: - yozing)"
        )
        return ORDER_WORKPLACE

    except Exception as e:
        await query.edit_message_text(f"❌ Xatolik: {str(e)}")
        return ConversationHandler.END


async def order_workplace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work_place = update.message.text.strip()
    if work_place in ["-", "yoq", "yo'q"]:
        work_place = ""
    context.user_data["order_workplace"] = work_place

    selected = context.user_data.get("order_product", {})
    name = selected.get("Tovar Nomi", "")
    price = format_money(selected.get("Narx", 0))

    # TUZATISH: \n qo'shildi
    text = (
        f"📋 Buyurtma tasdiqlash:\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍 Tovar: {name}\n"
        f"💵 Narx: {price} so'm\n"
        f"🏢 Ish joyi: {work_place or 'Korsatilmagan'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tasdiqlaysizmi?"
    )
    keyboard = [[
        InlineKeyboardButton("✅ Ha, buyurtma beraman", callback_data="order_yes"),
        InlineKeyboardButton("❌ Yo'q, bekor", callback_data="order_no")
    ]]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ORDER_CONFIRM


async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_no":
        await query.edit_message_text("❌ Bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    user = query.from_user
    selected = context.user_data.get("order_product", {})
    name = selected.get("Tovar Nomi", "")
    price = format_money(selected.get("Narx", 0))
    cat_id = selected.get("ID", "")
    # TUZATISH: datetime.now() ishlatiladi, to'g'ri sana va vaqt
    today = datetime.now().strftime("%d.%m.%Y %H:%M")

    await query.edit_message_text(
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"🛍 Tovar: {name}\n"
        f"💵 Narx: {price} so'm\n\n"
        f"📞 Tez orada siz bilan bog'lanamiz.\n"
        f"TexnoVibe 🏪"
    )

    try:
        sh = get_spreadsheet()
        from sheets.google_sheets import ensure_worksheets
        sheets = ensure_worksheets(sh)
        ws_clients = sheets["Mijozlar"]
        client_records = ws_to_records(ws_clients)

        client_phone = ""
        client_fio = ""
        for rec in client_records:
            if str(rec.get("Chat ID", "")).strip() == str(user.id):
                client_phone = rec.get("Telefon", "")
                client_fio = rec.get("FIO", "")
                break

        # Buyurtmalar varaqini topish yoki yaratish
        existing = [ws.title for ws in sh.worksheets()]
        if "Buyurtmalar" not in existing:
            ws_orders = sh.add_worksheet(title="Buyurtmalar", rows=500, cols=9)
            ws_orders.append_row(["ID", "Sana", "FIO", "Telefon", "Chat ID", "Tovar", "Narx", "Holat", "Ish Joyi"])
            ws_orders.format("A1:I1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
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

        # TUZATISH: admin xabarida \n qo'shildi
        tg_username = f"@{user.username}" if user.username else "Yo'q"
        admin_msg = (
            f"🆕 YANGI BUYURTMA!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Buyurtma ID: {order_id}\n"
            f"📅 Sana: {today}\n"
            f"👤 Mijoz: {client_fio or user.full_name}\n"
            f"📞 Telefon: {client_phone or 'Royxatdan otmagan'}\n"
            f"💬 Telegram: {tg_username}\n"
            f"🔢 Chat ID: {user.id}\n"
            f"🛍 Tovar: {name}\n"
            f"💵 Narx: {price} so'm\n"
        )
        if work_place:
            admin_msg += f"🏢 Ish joyi: {work_place}\n"
        admin_msg += "━━━━━━━━━━━━━━━━━━━━"

        await query.get_bot().send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_msg
        )

    except Exception as e:
        await query.get_bot().send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ Yangi buyurtma keldi lekin saqlashda xatolik: {str(e)}\nMijoz: {user.full_name} (ID: {user.id})"
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
    await update.message.reply_text("🏠 Bosh menyuga qaytildi.", reply_markup=keyboard)
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin uchun buyurtmalar ro'yxati"""
    await update.message.reply_text("⏳ Buyurtmalar yuklanmoqda...")

    try:
        sh = get_spreadsheet()
        existing = [ws.title for ws in sh.worksheets()]

        if "Buyurtmalar" not in existing:
            await update.message.reply_text("📋 Hali hech qanday buyurtma yo'q.")
            return

        ws = sh.worksheet("Buyurtmalar")
        records = ws_to_records(ws)

        if not records:
            await update.message.reply_text("📋 Hali hech qanday buyurtma yo'q.")
            return

        yangi = [r for r in records if r.get("Holat") == "Yangi"]
        all_orders = records

        text = f"📋 BUYURTMALAR ({len(all_orders)} ta jami | {len(yangi)} ta yangi)\n\n"

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
            phone = rec.get("Telefon", "") or "Ro'yxatdan o'tmagan"
            tovar = rec.get("Tovar", "")
            narx = format_money(rec.get("Narx", 0))

            text += (
                f"{emoji} {order_id} | {sana}\n"
                f"👤 {fio}\n"
                f"📞 {phone}\n"
                f"🛍 {tovar} — {narx} so'm\n"
                f"Holat: {holat}\n\n"
            )

        if len(all_orders) > 20:
            text += f"... va yana {len(all_orders)-20} ta buyurtma\n"

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")
