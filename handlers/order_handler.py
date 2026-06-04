"""
Buyurtma berish handleri
Yangilik:
  - Admin inline tugma bilan "Yetkazildi" belgilaydi
  - Savdo kiritilganda buyurtma avtomatik "Yetkazildi" ga o'tadi
  - cmd_orders faqat "Yangi" buyurtmalarni ko'rsatadi
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ws_to_records, get_sheet
from datetime import datetime
import os

ORDER_SELECT, ORDER_WORKPLACE, ORDER_CONFIRM = range(70, 73)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_active_products():
    ws      = get_sheet("Katalog")
    records = ws_to_records(ws)
    return [r for r in records if str(r.get("Holat", "")).strip() == "Faol"]


def get_orders_ws():
    """Buyurtmalar varag'ini oladi yoki yaratadi"""
    sh       = get_spreadsheet()
    existing = [ws.title for ws in sh.worksheets()]
    if "Buyurtmalar" not in existing:
        ws_orders = sh.add_worksheet(title="Buyurtmalar", rows=500, cols=9)
        ws_orders.append_row(["ID", "Sana", "FIO", "Telefon", "Chat ID", "Tovar", "Narx", "Holat", "Ish Joyi"])
        ws_orders.format("A1:I1", {"textFormat": {"bold": True},
                                    "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
    else:
        ws_orders = sh.worksheet("Buyurtmalar")
    return ws_orders


def set_order_status(order_id: str, status: str) -> bool:
    """Buyurtma holatini yangilaydi"""
    try:
        ws      = get_orders_ws()
        records = ws.get_all_values()
        headers = records[0] if records else []
        try:
            id_col    = headers.index("ID") + 1
            holat_col = headers.index("Holat") + 1
        except ValueError:
            id_col, holat_col = 1, 8

        for i, row in enumerate(records[1:], start=2):
            if len(row) >= id_col and row[id_col - 1] == order_id:
                ws.update_cell(i, holat_col, status)
                return True
    except Exception:
        pass
    return False


def auto_complete_order(phone: str, product_name: str):
    """
    Savdo kiritilganda shu telefon + tovar nomi bo'yicha
    'Yangi' buyurtmani 'Yetkazildi' ga o'tkazadi
    """
    try:
        ws      = get_orders_ws()
        records = ws.get_all_values()
        if len(records) < 2:
            return

        headers = records[0]
        try:
            tel_col   = headers.index("Telefon") + 1
            tovar_col = headers.index("Tovar") + 1
            holat_col = headers.index("Holat") + 1
        except ValueError:
            tel_col, tovar_col, holat_col = 4, 6, 8

        phone_clean = phone.replace("+","").replace(" ","").replace("-","")

        for i, row in enumerate(records[1:], start=2):
            if len(row) < max(tel_col, tovar_col, holat_col):
                continue
            r_phone = row[tel_col-1].replace("+","").replace(" ","").replace("-","")
            r_tovar = row[tovar_col-1].strip().lower()
            r_holat = row[holat_col-1].strip()

            if r_phone == phone_clean and r_tovar == product_name.strip().lower() and r_holat == "Yangi":
                ws.update_cell(i, holat_col, "Yetkazildi")
                break
    except Exception:
        pass


# ─── BUYURTMA BERISH ────────────────────────────────────────
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    try:
        products = get_active_products()
        if not products:
            await update.message.reply_text("🛍 Hozircha katalogda tovar yo'q.\nKeyinroq qaytib ko'ring!")
            return ConversationHandler.END

        keyboard = []
        for i, rec in enumerate(products):
            name  = rec.get("Tovar Nomi", rec.get("Nom", ""))
            price = format_money(rec.get("Narx", 0))
            keyboard.append([InlineKeyboardButton(f"🛍 {name} — {price} so'm", callback_data=f"order_{i}")])
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="order_cancel")])

        await update.message.reply_text(
            "🛒 Buyurtma berish\n\nQaysi tovarni olmoqchisiz?\nTanlang 👇",
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

    try:
        idx      = int(query.data.replace("order_", ""))
        products = get_active_products()
        if idx >= len(products):
            await query.edit_message_text("❌ Tovar topilmadi.")
            return ConversationHandler.END

        selected = products[idx]
        context.user_data["order_product"] = selected

        name  = selected.get("Tovar Nomi", selected.get("Nom", ""))
        price = format_money(selected.get("Narx", 0))
        desc  = selected.get("Tavsif", "")

        text = f"✅ Tanlangan tovar:\n━━━━━━━━━━━━━━━━━━━━\n🛍 Nomi: {name}\n💵 Narx: {price} so'm\n"
        if desc:
            text += f"📝 Tavsif: {desc}\n"
        text += "━━━━━━━━━━━━━━━━━━━━"

        await query.edit_message_text(text)
        await query.message.reply_text(
            "🏢 Ish joyingizni kiriting:\n(Masalan: Bozor, Maktab)\n(Yo'q bo'lsa: - yozing)"
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
    name     = selected.get("Tovar Nomi", selected.get("Nom", ""))
    price    = format_money(selected.get("Narx", 0))

    text = (
        f"📋 Buyurtma tasdiqlash:\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍 Tovar: {name}\n"
        f"💵 Narx: {price} so'm\n"
        f"🏢 Ish joyi: {work_place or 'Korsatilmagan'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\nTasdiqlaysizmi?"
    )
    keyboard = [[
        InlineKeyboardButton("✅ Ha, buyurtma beraman", callback_data="order_yes"),
        InlineKeyboardButton("❌ Yo'q, bekor",          callback_data="order_no")
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ORDER_CONFIRM


async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_no":
        await query.edit_message_text("❌ Bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    user       = query.from_user
    selected   = context.user_data.get("order_product", {})
    name       = selected.get("Tovar Nomi", selected.get("Nom", ""))
    price      = format_money(selected.get("Narx", 0))
    work_place = context.user_data.get("order_workplace", "")
    today      = datetime.now().strftime("%d.%m.%Y %H:%M")

    await query.edit_message_text(
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"🛍 Tovar: {name}\n💵 Narx: {price} so'm\n\n"
        f"📞 Tez orada siz bilan bog'lanamiz.\nTexnoVibe 🏪"
    )

    try:
        sh             = get_spreadsheet()
        from sheets.google_sheets import ensure_worksheets
        sheets         = ensure_worksheets(sh)
        client_records = ws_to_records(sheets["Mijozlar"])

        client_phone = ""
        client_fio   = ""
        for rec in client_records:
            if str(rec.get("Chat ID", "")).strip() == str(user.id):
                client_phone = rec.get("Telefon", "")
                client_fio   = rec.get("FIO", "")
                break

        ws_orders  = get_orders_ws()
        all_orders = ws_orders.get_all_values()
        order_id   = f"ORD-{len(all_orders):03d}"

        ws_orders.append_row([
            order_id, today,
            client_fio or user.full_name,
            client_phone, str(user.id),
            name, selected.get("Narx", 0),
            "Yangi", work_place
        ])

        tg_username = f"@{user.username}" if user.username else "Yo'q"
        admin_msg = (
            f"🆕 YANGI BUYURTMA!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: {order_id}\n"
            f"📅 Sana: {today}\n"
            f"👤 Mijoz: {client_fio or user.full_name}\n"
            f"📞 Telefon: {client_phone or 'Royxatdan otmagan'}\n"
            f"💬 Telegram: {tg_username}\n"
            f"🛍 Tovar: {name}\n"
            f"💵 Narx: {price} so'm\n"
        )
        if work_place:
            admin_msg += f"🏢 Ish joyi: {work_place}\n"
        admin_msg += "━━━━━━━━━━━━━━━━━━━━"

        # Admin xabariga "Yetkazildi" tugmasi
        keyboard = [[InlineKeyboardButton(
            "✅ Yetkazildi", callback_data=f"ord_done_{order_id}"
        )]]
        await query.get_bot().send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_msg,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        await query.get_bot().send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ Yangi buyurtma keldi lekin saqlashda xatolik: {str(e)}\n"
                 f"Mijoz: {user.full_name} (ID: {user.id})"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def order_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin 'Yetkazildi' tugmasini bosganda"""
    query    = update.callback_query
    await query.answer()

    order_id = query.data.replace("ord_done_", "")
    success  = set_order_status(order_id, "Yetkazildi")

    if success:
        # Xabarni yangilash — tugmani olib tashlash
        original = query.message.text
        await query.edit_message_text(
            original + "\n\n✅ *Yetkazildi deb belgilandi!*",
            parse_mode="Markdown"
        )
    else:
        await query.answer("❌ Yangilashda xato!", show_alert=True)


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("📊 Mening Nasiyam")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ], resize_keyboard=True)
    await update.message.reply_text("🏠 Bosh menyuga qaytildi.", reply_markup=keyboard)
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faqat 'Yangi' buyurtmalarni ko'rsatadi"""
    await update.message.reply_text("⏳ Buyurtmalar yuklanmoqda...")
    try:
        sh       = get_spreadsheet()
        existing = [ws.title for ws in sh.worksheets()]
        if "Buyurtmalar" not in existing:
            await update.message.reply_text("📋 Hali hech qanday buyurtma yo'q.")
            return

        ws      = sh.worksheet("Buyurtmalar")
        records = ws_to_records(ws)
        if not records:
            await update.message.reply_text("📋 Hali hech qanday buyurtma yo'q.")
            return

        # Faqat yangi buyurtmalar
        yangi = [r for r in records if str(r.get("Holat","")).strip() == "Yangi"]

        if not yangi:
            jami = len(records)
            await update.message.reply_text(
                f"📋 Yangi buyurtma yo'q.\n"
                f"(Jami {jami} ta buyurtma, hammasi yetkazilgan)"
            )
            return

        text = f"📋 YANGI BUYURTMALAR ({len(yangi)} ta)\n\n"
        for rec in yangi:
            narx  = format_money(rec.get("Narx", 0))
            phone = rec.get("Telefon", "") or "Ro'yxatdan o'tmagan"
            text += (
                f"🆕 {rec.get('ID','')} | {rec.get('Sana','')}\n"
                f"👤 {rec.get('FIO','')}\n"
                f"📞 {phone}\n"
                f"🛍 {rec.get('Tovar','')} — {narx} so'm\n"
                f"🏢 {rec.get('Ish Joyi','') or 'Korsatilmagan'}\n\n"
            )

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")
