"""
Savdo kiritish handleri
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import add_sale, check_duplicate

NAME, PHONE, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE, \
    INSTALLMENT_PERIOD, DOWN_PAYMENT, AGENT, CONFIRM = range(9)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def start_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🛒 *Yangi Nasiya Savdo*\n\n"
        "1️⃣ Mijozning to'liq ismini kiriting:\n"
        "_(Masalan: Anvarov Ali Karimovich)_",
        parse_mode="Markdown"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("❌ Ism juda qisqa. Qaytadan kiriting:")
        return NAME
    context.user_data["fio"] = name
    await update.message.reply_text(
        f"✅ Ism: *{name}*\n\n"
        "2️⃣ Telefon raqamini kiriting:\n"
        "_(Masalan: +998901234567)_",
        parse_mode="Markdown"
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.isdigit() or len(clean_phone) < 9:
        await update.message.reply_text(
            "❌ Telefon raqami noto'g'ri. Qaytadan kiriting:\n"
            "_(Masalan: +998901234567)_",
            parse_mode="Markdown"
        )
        return PHONE

    dup = check_duplicate(phone)
    if dup["exists"]:
        fio = dup["fio"]
        product = dup["product"]
        remaining = format_money(dup["remaining"])
        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, qo'shaman", callback_data="dup_yes"),
                InlineKeyboardButton("❌ Yo'q, bekor", callback_data="dup_no")
            ]
        ]
        await update.message.reply_text(
            f"⚠️ *Diqqat!* Bu telefon raqami allaqachon bazada bor!\n\n"
            f"👤 Mijoz: *{fio}*\n"
            f"🛍 Tovar: {product}\n"
            f"💰 Qoldiq: {remaining} so'm\n\n"
            f"Shunda ham yangi savdo qo'shaveraymi?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["phone"] = phone
        context.user_data["awaiting_dup_confirm"] = True
        return PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text(
        f"✅ Telefon: *{phone}*\n\n"
        "3️⃣ Tovar nomini kiriting:\n"
        "_(Masalan: Samsung Galaxy A55)_",
        parse_mode="Markdown"
    )
    return PRODUCT


async def get_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_dup_confirm"):
        return PHONE

    product = update.message.text.strip()
    context.user_data["product"] = product
    await update.message.reply_text(
        f"✅ Tovar: *{product}*\n\n"
        "4️⃣ Tovarning jami narxini kiriting (so'mda):\n"
        "_(Masalan: 3500000)_",
        parse_mode="Markdown"
    )
    return TOTAL_PRICE


async def get_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_text = update.message.text.strip().replace(" ", "").replace(",", "")
        price = float(price_text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Narx noto'g'ri. Faqat raqam kiriting:\n_(Masalan: 3500000)_",
            parse_mode="Markdown"
        )
        return TOTAL_PRICE

    context.user_data["total_price"] = price
    keyboard = [
        [
            InlineKeyboardButton("📅 Oylik", callback_data="pay_monthly"),
            InlineKeyboardButton("📆 Haftalik", callback_data="pay_weekly")
        ]
    ]
    price_str = format_money(price)
    await update.message.reply_text(
        f"✅ Jami narx: *{price_str} so'm*\n\n"
        "5️⃣ To'lov turini tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT_TYPE


async def get_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data in ["dup_yes", "dup_no"]:
        if query.data == "dup_no":
            await query.edit_message_text("❌ Savdo bekor qilindi.")
            return ConversationHandler.END
        else:
            context.user_data["awaiting_dup_confirm"] = False
            phone = context.user_data["phone"]
            await query.edit_message_text(
                f"✅ Telefon: *{phone}*\n\n"
                "3️⃣ Tovar nomini kiriting:",
                parse_mode="Markdown"
            )
            return PRODUCT

    if query.data == "pay_monthly":
        context.user_data["payment_type"] = "Oylik"
        period_hint = "_(Masalan: 6 — 6 oyga)_"
        period_word = "oyga"
    else:
        context.user_data["payment_type"] = "Haftalik"
        period_hint = "_(Masalan: 12 — 12 haftaga)_"
        period_word = "haftaga"

    pay_type = context.user_data["payment_type"]
    await query.edit_message_text(
        f"✅ To'lov turi: *{pay_type}*\n\n"
        f"6️⃣ Necha {period_word}?\n{period_hint}",
        parse_mode="Markdown"
    )
    return INSTALLMENT_PERIOD


async def get_installment_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        period = int(update.message.text.strip())
        if period <= 0 or period > 60:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri muddat. 1-60 oraligida kiriting:")
        return INSTALLMENT_PERIOD

    context.user_data["installment_period"] = period
    pay_type = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"
    await update.message.reply_text(
        f"✅ Muddat: *{period} {period_word}*\n\n"
        "7️⃣ Boshlang'ich to'lov (avans) summasini kiriting:\n"
        "_(Avans yo'q bo'lsa 0 kiriting)_",
        parse_mode="Markdown"
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
        await update.message.reply_text(
            f"❌ Noto'g'ri summa. 0 dan {total_str} gacha kiriting:"
        )
        return DOWN_PAYMENT

    context.user_data["down_payment"] = down
    remaining = context.user_data["total_price"] - down
    period = context.user_data["installment_period"]
    pay_per = round(remaining / period)
    pay_type = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    down_str = format_money(down)
    remaining_str = format_money(remaining)
    pay_per_str = format_money(pay_per)

    await update.message.reply_text(
        f"✅ Avans: *{down_str} so'm*\n"
        f"💰 Qoldiq: *{remaining_str} so'm*\n"
        f"📊 Har {period_word}: *{pay_per_str} so'm*\n\n"
        "8️⃣ Agent ismini kiriting:\n_(Yoki 'Yoq' deb yozing)_",
        parse_mode="Markdown"
    )
    return AGENT


async def get_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = update.message.text.strip()
    if agent.lower() in ["yo'q", "yoq", "-", "none"]:
        agent = ""
    context.user_data["agent"] = agent

    data = context.user_data
    remaining = data["total_price"] - data.get("down_payment", 0)
    pay_per = round(remaining / data["installment_period"])
    pay_type = data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    total_str = format_money(data["total_price"])
    down_str = format_money(data.get("down_payment", 0))
    remaining_str = format_money(remaining)
    pay_per_str = format_money(pay_per)

    summary = (
        "📋 *SAVDO MALUMOTLARI — TASDIQLANG*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: *{data['fio']}*\n"
        f"📞 Telefon: `{data['phone']}`\n"
        f"🛍 Tovar: *{data['product']}*\n"
        f"💵 Jami narx: *{total_str} so'm*\n"
        f"💰 Avans: *{down_str} so'm*\n"
        f"📊 Qoldiq: *{remaining_str} so'm*\n"
        f"📅 To'lov turi: *{pay_type}*\n"
        f"⏱ Muddat: *{data['installment_period']} {period_word}*\n"
        f"💳 Har {period_word}: *{pay_per_str} so'm*\n"
    )
    if agent:
        summary += f"👨 Agent: *{agent}*\n"
    summary += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")
        ]
    ]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def confirm_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text("❌ Savdo bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("⏳ Malumotlar saqlanmoqda...")

    try:
        result = add_sale(context.user_data)
        schedule_text = "📅 *TOLOV JADVALI:*\n"
        for item in result["schedule"][:6]:
            amount_str = format_money(item["amount"])
            remaining_str = format_money(item["remaining"])
            schedule_text += (
                f"{item['num']}. {item['date']} — "
                f"*{amount_str} so'm* "
                f"(qoldiq: {remaining_str})\n"
            )
        if len(result["schedule"]) > 6:
            schedule_text += f"... va yana {len(result['schedule'])-6} ta to'lov\n"

        remaining_str = format_money(result["remaining"])
        pay_str = format_money(result["payment_per_period"])

        success_msg = (
            "✅ *SAVDO MUVAFFAQIYATLI SAQLANDI!*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Savdo ID: `{result['sale_id']}`\n"
            f"💰 Umumiy qoldiq: *{remaining_str} so'm*\n"
            f"📊 Har tolov: *{pay_str} so'm*\n"
            f"📅 Birinchi tolov: *{result['next_payment']}*\n\n"
            f"{schedule_text}\n"
            "📊 Google Sheets ga saqlandi ✅"
        )
        await query.edit_message_text(success_msg, parse_mode="Markdown")

    except Exception as e:
        await query.edit_message_text(
            f"❌ Xatolik yuz berdi:\n`{str(e)}`\n\nQaytadan urinib koring: /savdo",
            parse_mode="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi. /start — bosh menyu")
    context.user_data.clear()
    return ConversationHandler.END
