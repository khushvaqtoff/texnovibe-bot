"""
Savdo kiritish handleri
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import add_sale, check_duplicate
import os

# MUHIM: Holatlar ketma-ketligi bot.py bilan bir xil bo'lishi shart!
NAME, PHONE, WORK_PLACE, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE, \
    INSTALLMENT_PERIOD, DOWN_PAYMENT, AGENT, PAY_DAY, CONFIRM = range(11)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def start_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Yangi Nasiya Savdo\n\n"
        "1. Mijozning toliq ismini kiriting:\n"
        "(Masalan: Anvarov Ali Karimovich)"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("Ism juda qisqa. Qaytadan kiriting:")
        return NAME
    context.user_data["fio"] = name
    await update.message.reply_text(
        f"Ism: {name}\n\n"
        "2. Telefon raqamini kiriting:\n"
        "(Masalan: +998901234567)"
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.isdigit() or len(clean_phone) < 9:
        await update.message.reply_text("Telefon raqami notogri. Qaytadan kiriting:")
        return PHONE

    dup = check_duplicate(phone)
    if dup["exists"]:
        fio = dup["fio"]
        product = dup["product"]
        remaining = format_money(dup["remaining"])
        keyboard = [[
            InlineKeyboardButton("Ha, qoshaman", callback_data="dup_yes"),
            InlineKeyboardButton("Yoq, bekor", callback_data="dup_no")
        ]]
        await update.message.reply_text(
            f"Diqqat! Bu telefon bazada bor!\n\n"
            f"Mijoz: {fio}\n"
            f"Tovar: {product}\n"
            f"Qoldiq: {remaining} som\n\n"
            f"Shunda ham yangi savdo qoshaveraymi?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["phone"] = phone
        context.user_data["awaiting_dup_confirm"] = True
        return WORK_PLACE  # Tugma bosilishini WORK_PLACE ichida kutadi

    context.user_data["phone"] = phone
    await update.message.reply_text(
        f"Telefon: {phone}\n\n"
        "3. Mijozning ish joyini kiriting:\n"
        "(Masalan: Bozor, Maktab, Xususiy)\n"
        "(Yoq bolsa: - yozing)"
    )
    return WORK_PLACE


async def get_work_place(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Callback query (Dublikat tekshiruvi tugmasi) kelganini tekshirish
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "dup_no":
            await query.edit_message_text("Savdo bekor qilindi.")
            context.user_data.clear()
            return ConversationHandler.END
        elif query.data == "dup_yes":
            context.user_data["awaiting_dup_confirm"] = False
            phone = context.user_data["phone"]
            await query.edit_message_text(
                f"Telefon: {phone}\n\n"
                "3. Mijozning ish joyini kiriting:\n"
                "(Masalan: Bozor, Maktab, Xususiy)\n"
                "(Yoq bolsa: - yozing)"
            )
            return WORK_PLACE

    # Agar foydalanuvchi oddiy matn yozgan bo'lsa
    work_place = update.message.text.strip()
    if work_place == "-":
        work_place = ""
    context.user_data["work_place"] = work_place

    await update.message.reply_text(
        f"Ish joyi: {work_place or 'Korsatilmagan'}\n\n"
        "4. Tovar nomini kiriting:\n"
        "(Masalan: Samsung Galaxy A55)"
    )
    return PRODUCT


async def get_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product = update.message.text.strip()
    context.user_data["product"] = product

    await update.message.reply_text(
        f"Tovar: {product}\n\n"
        "5. Tovarning jami narxini kiriting (somda):\n"
        "(Masalan: 3500000)"
    )
    return TOTAL_PRICE


async def get_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_text = update.message.text.strip().replace(" ", "").replace(",", "")
        price = float(price_text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Narx notogri. Faqat raqam kiriting:")
        return TOTAL_PRICE

    context.user_data["total_price"] = price

    keyboard = [[
        InlineKeyboardButton("Oylik", callback_data="pay_monthly"),
        InlineKeyboardButton("Haftalik", callback_data="pay_weekly")
    ]]
    await update.message.reply_text(
        f"Jami narx: {format_money(price)} som\n\n"
        "6. Tolov turini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT_TYPE


async def get_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pay_monthly":
        context.user_data["payment_type"] = "Oylik"
        period_word = "oyga"
    else:
        context.user_data["payment_type"] = "Haftalik"
        period_word = "haftaga"

    pay_type = context.user_data["payment_type"]
    await query.edit_message_text(
        f"Tolov turi: {pay_type}\n\n"
        f"6. Necha {period_word}?\n"
        "(Masalan: 6)"
    )
    return INSTALLMENT_PERIOD


async def get_installment_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        period = int(update.message.text.strip())
        if period <= 0 or period > 60:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Notogri muddat. 1-60 oraligida kiriting:")
        return INSTALLMENT_PERIOD

    context.user_data["installment_period"] = period
    pay_type = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    await update.message.reply_text(
        f"Muddat: {period} {period_word}\n\n"
        "7. Boshlangich tolov (avans) summasini kiriting:\n"
        "(Avans yoq bolsa 0 kiriting)"
    )
    return DOWN_PAYMENT


async def get_down_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        down = float(update.message.text.strip().replace(" ", "").replace(",", ""))
        total = context.user_data["total_price"]
        if down < 0 or down >= total:
            raise ValueError
    except ValueError:
        total_str = format_money(context.user_data["total_price"])
        await update.message.reply_text(f"Notogri summa. 0 dan {total_str} gacha kiriting:")
        return DOWN_PAYMENT

    context.user_data["down_payment"] = down
    remaining = context.user_data["total_price"] - down
    period = context.user_data["installment_period"]
    pay_per = round(remaining / period)
    pay_type = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    await update.message.reply_text(
        f"Avans: {format_money(down)} som\n"
        f"Qoldiq: {format_money(remaining)} som\n"
        f"Har {period_word}: {format_money(pay_per)} som\n\n"
        "8. Agent ismini kiriting:\n"
        "(Yoq bolsa: - yozing)"
    )
    return AGENT


async def get_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = update.message.text.strip()
    if agent.lower() in ["yo'q", "yoq", "-", "none"]:
        agent = ""
    context.user_data["agent"] = agent

    pay_type = context.user_data["payment_type"]

    if pay_type == "Oylik":
        keyboard = []
        row = []
        for day in range(1, 29):
            row.append(InlineKeyboardButton(str(day), callback_data=f"payday_{day}"))
            if len(row) == 7:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        await update.message.reply_text(
            "9. Har oy necha-sida tolov qiladi?\n"
            "Tolov kunini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PAY_DAY
    else:
        context.user_data["pay_day"] = 0
        return await show_confirm(update, context)


async def get_pay_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    day = int(query.data.replace("payday_", ""))
    context.user_data["pay_day"] = day

    await query.edit_message_text(f"Tolov kuni: har oyning {day}-si")
    return await show_confirm_callback(query, context)


async def show_confirm(update, context):
    data = context.user_data
    remaining = data["total_price"] - data.get("down_payment", 0)
    pay_per = round(remaining / data["installment_period"])
    pay_type = data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    summary = (
        f"SAVDO MALUMOTLARI\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Mijoz: {data['fio']}\n"
        f"Telefon: {data['phone']}\n"
        f"Ish joyi: {data.get('work_place', '') or 'Korsatilmagan'}\n"
        f"Tovar: {data['product']}\n"
        f"Jami narx: {format_money(data['total_price'])} som\n"
        f"Avans: {format_money(data.get('down_payment', 0))} som\n"
        f"Qoldiq: {format_money(remaining)} som\n"
        f"Tolov turi: {pay_type}\n"
        f"Muddat: {data['installment_period']} {period_word}\n"
        f"Har {period_word}: {format_money(pay_per)} som\n"
    )
    if data.get("pay_day"):
        summary += f"Tolov kuni: har oyning {data['pay_day']}-si\n"
    if data.get("agent"):
        summary += f"Agent: {data['agent']}\n"
    summary += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = [[
        InlineKeyboardButton("Tasdiqlash", callback_data="confirm_yes"),
        InlineKeyboardButton("Bekor qilish", callback_data="confirm_no")
    ]]
    await update.message.reply_text(
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def show_confirm_callback(query, context):
    data = context.user_data
    remaining = data["total_price"] - data.get("down_payment", 0)
    pay_per = round(remaining / data["installment_period"])
    pay_type = data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    summary = (
        f"SAVDO MALUMOTLARI\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Mijoz: {data['fio']}\n"
        f"Telefon: {data['phone']}\n"
        f"Ish joyi: {data.get('work_place', '') or 'Korsatilmagan'}\n"
        f"Tovar: {data['product']}\n"
        f"Jami narx: {format_money(data['total_price'])} som\n"
        f"Avans: {format_money(data.get('down_payment', 0))} som\n"
        f"Qoldiq: {format_money(remaining)} som\n"
        f"Tolov turi: {pay_type}\n"
        f"Muddat: {data['installment_period']} {period_word}\n"
        f"Har {period_word}: {format_money(pay_per)} som\n"
    )
    if data.get("pay_day"):
        summary += f"Tolov kuni: har oyning {data['pay_day']}-si\n"
    if data.get("agent"):
        summary += f"Agent: {data['agent']}\n"
    summary += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = [[
        InlineKeyboardButton("Tasdiqlash", callback_data="confirm_yes"),
        InlineKeyboardButton("Bekor qilish", callback_data="confirm_no")
    ]]
    await query.message.reply_text(
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def confirm_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "payday_" or query.data.startswith("payday_"):
        return await get_pay_day(update, context)

    if query.data == "confirm_no":
        await query.edit_message_text("Savdo bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("Malumotlar saqlanmoqda...")

    try:
        result = add_sale(context.user_data)
        schedule_text = "TOLOV JADVALI:\n"
        for item in result["schedule"][:6]:
            amount_str = format_money(item["amount"])
            remaining_str = format_money(item["remaining"])
            schedule_text += (
                f"{item['num']}. {item['date']} - "
                f"{amount_str} som "
                f"(qoldiq: {remaining_str})\n"
            )
        if len(result["schedule"]) > 6:
            schedule_text += f"... va yana {len(result['schedule'])-6} ta tolov\n"

        success_msg = (
            f"SAVDO SAQLANDI!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Savdo ID: {result['sale_id']}\n"
            f"Qoldiq: {format_money(result['remaining'])} som\n"
            f"Har tolov: {format_money(result['payment_per_period'])} som\n"
            f"Birinchi tolov: {result['next_payment']}\n\n"
            f"{schedule_text}\n"
            f"Google Sheets ga saqlandi"
        )
        await query.edit_message_text(success_msg)

    except Exception as e:
        await query.edit_message_text(f"Xatolik: {str(e)}\n\nQaytadan: /savdo")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import ReplyKeyboardMarkup, KeyboardButton
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
            [KeyboardButton("📦 Tovar Qoshish"), KeyboardButton("🛍 Katalog")],
            [KeyboardButton("🛒 Buyurtmalar"), KeyboardButton("🏠 Bosh Menyu")],
        ], resize_keyboard=True)
    else:
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