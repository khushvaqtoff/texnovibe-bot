"""
Savdo kiritish handleri
Yangilik:
  - Tovar katalogdan inline tugmalar bilan tanlanadi
  - To'lov kunida qaysi oydan boshlanishi so'raladi
  - Bekor qilingan savdo mijozda ko'rinmaydi (Holat=Bekor qilindi)
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import add_sale, check_duplicate, get_sheet
import os
import calendar
from datetime import date, timedelta

NAME, PHONE, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE, \
    INSTALLMENT_PERIOD, DOWN_PAYMENT, AGENT, PAY_DAY, START_MONTH, CONFIRM = range(11)

WEEK_DAYS = {
    1: "Dushanba", 2: "Seshanba", 3: "Chorshanba",
    4: "Payshanba", 5: "Juma", 6: "Shanba", 7: "Yakshanba"
}

MONTHS = {
    1:"Yanvar", 2:"Fevral", 3:"Mart", 4:"Aprel",
    5:"May", 6:"Iyun", 7:"Iyul", 8:"Avgust",
    9:"Sentabr", 10:"Oktabr", 11:"Noyabr", 12:"Dekabr"
}


def normalize_phone(phone: str) -> str:
    return str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_catalog_products() -> list:
    try:
        ws   = get_sheet("Katalog")
        rows = ws.get_all_records()
        return [r for r in rows if str(r.get("Holat", "")).strip() == "Faol"]
    except:
        return []


# ─── 1. BOSHLASH ────────────────────────────────────────────
async def start_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "➕ *Yangi Nasiya Savdo*\n\n"
        "1️⃣ Mijozning to'liq ismini kiriting:\n"
        "_(Masalan: Anvarov Ali Karimovich)_",
        parse_mode="Markdown"
    )
    return NAME


# ─── 2. ISM ─────────────────────────────────────────────────
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("❌ Ism juda qisqa. Qaytadan kiriting:")
        return NAME
    context.user_data["fio"] = name
    await update.message.reply_text(
        f"✅ Ism: {name}\n\n"
        "2️⃣ Telefon raqamini kiriting:\n"
        "_(Masalan: +998901234567)_",
        parse_mode="Markdown"
    )
    return PHONE


# ─── 3. TELEFON ─────────────────────────────────────────────
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone      = update.message.text.strip()
    clean_phone = normalize_phone(phone)

    if not clean_phone.isdigit() or len(clean_phone) < 9:
        await update.message.reply_text("❌ Telefon raqami noto'g'ri. Qaytadan kiriting:")
        return PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text("⏳ Tekshirilmoqda...")

    try:
        dup = check_duplicate(clean_phone)
        if dup["exists"]:
            keyboard = [[
                InlineKeyboardButton("✅ Ha, qo'shaman", callback_data="dup_yes"),
                InlineKeyboardButton("❌ Yo'q, bekor",   callback_data="dup_no")
            ]]
            await update.message.reply_text(
                f"⚠️ Bu telefon bazada bor!\n\n"
                f"👤 Mijoz: {dup['fio']}\n"
                f"🛍 Tovar: {dup['product']}\n"
                f"💰 Qoldiq: {format_money(dup['remaining'])} so'm\n\n"
                f"Shunda ham yangi savdo qo'shaveraymi?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            context.user_data["awaiting_dup_confirm"] = True
            return PRODUCT
    except Exception as e:
        await update.message.reply_text(f"⚠️ Baza tekshirishda xato: {str(e)}\nDavom etilmoqda...")

    await _ask_product(update.message, context)
    return PRODUCT


async def _ask_product(msg_or_query, context, edit=False):
    """Katalogdan tovar tanlash tugmalarini ko'rsatish"""
    products = get_catalog_products()

    if products:
        keyboard = []
        for i, p in enumerate(products):
            nom   = p.get("Tovar Nomi", p.get("Nom", "Tovar"))
            narx  = format_money(p.get("Narx", 0))
            keyboard.append([InlineKeyboardButton(
                f"🛍 {nom} — {narx} so'm",
                callback_data=f"prod_{i}"
            )])
        keyboard.append([InlineKeyboardButton("✏️ Qo'lda kiritish", callback_data="prod_manual")])
        context.user_data["_catalog"] = products

        text = "3️⃣ Tovarni tanlang yoki qo'lda kiriting:"
        if edit:
            await msg_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg_or_query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        text = "3️⃣ Tovar nomini kiriting:\n_(Masalan: Samsung Galaxy A55)_"
        if edit:
            await msg_or_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await msg_or_query.reply_text(text, parse_mode="Markdown")


# ─── 4. TOVAR ───────────────────────────────────────────────
async def get_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Callback (katalogdan tanlash yoki dup confirm)
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        # Duplicate tasdiqlash
        if query.data == "dup_no":
            await query.edit_message_text("❌ Savdo bekor qilindi.")
            context.user_data.clear()
            return ConversationHandler.END
        elif query.data == "dup_yes":
            context.user_data["awaiting_dup_confirm"] = False
            await _ask_product(query, context, edit=True)
            return PRODUCT

        # Katalogdan tovar tanlash
        if query.data.startswith("prod_"):
            if query.data == "prod_manual":
                await query.edit_message_text(
                    "✏️ Tovar nomini yozing:\n_(Masalan: Samsung Galaxy A55)_",
                    parse_mode="Markdown"
                )
                context.user_data["_manual_product"] = True
                return PRODUCT

            idx = int(query.data.replace("prod_", ""))
            products = context.user_data.get("_catalog", [])
            if idx < len(products):
                p   = products[idx]
                nom = p.get("Tovar Nomi", p.get("Nom", ""))
                context.user_data["product"] = nom
                # Narxni ham avtomatik olish
                if p.get("Narx"):
                    context.user_data["_catalog_price"] = float(p["Narx"])

                await query.edit_message_text(
                    f"✅ Tovar: *{nom}*\n\n"
                    f"4️⃣ Ish joyini kiriting:\n_(Yo'q bo'lsa: - yozing)_",
                    parse_mode="Markdown"
                )
                return TOTAL_PRICE

        return PRODUCT

    # Duplicate hali tasdiqlanmagan
    if context.user_data.get("awaiting_dup_confirm"):
        return PRODUCT

    # Qo'lda tovar nomi kiritish
    if context.user_data.get("_manual_product"):
        product = update.message.text.strip()
        if len(product) < 2:
            await update.message.reply_text("❌ Tovar nomi juda qisqa. Qaytadan kiriting:")
            return PRODUCT
        context.user_data["product"] = product
        context.user_data["_manual_product"] = False
        await update.message.reply_text(
            f"✅ Tovar: *{product}*\n\n"
            f"4️⃣ Ish joyini kiriting:\n_(Yo'q bo'lsa: - yozing)_",
            parse_mode="Markdown"
        )
        return TOTAL_PRICE

    # Eski oqim (katalog yo'q bo'lsa bevosita matn)
    work_place = update.message.text.strip()
    if work_place in ["-", "yoq", "yo'q"]:
        work_place = ""
    context.user_data["work_place"] = work_place
    await update.message.reply_text(
        "4️⃣ Tovar nomini kiriting:\n_(Masalan: Samsung Galaxy A55)_",
        parse_mode="Markdown"
    )
    return TOTAL_PRICE


# ─── 5. ISH JOYI VA NARX ────────────────────────────────────
async def get_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Callback — price_confirm yoki price_change
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "price_confirm":
            price = context.user_data.get("_catalog_price", 0)
            context.user_data["total_price"] = price
            await query.edit_message_text(
                f"✅ Narx tasdiqlandi: *{format_money(price)} so'm*\n\n"
                "6️⃣ To'lov turini tanlang:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📅 Oylik",    callback_data="pay_monthly"),
                    InlineKeyboardButton("📆 Haftalik", callback_data="pay_weekly")
                ]])
            )
            return PAYMENT_TYPE

        if query.data == "price_change":
            await query.edit_message_text(
                "✏️ Yangi narxni kiriting (so'mda):\n_(Masalan: 3500000)_",
                parse_mode="Markdown"
            )
            return TOTAL_PRICE

        return TOTAL_PRICE

    text = update.message.text.strip()

    # Ish joyi kiritilganmi yoki narxmi?
    if "work_place" not in context.user_data:
        # Bu ish joyi
        work_place = text
        if work_place in ["-", "yoq", "yo'q"]:
            work_place = ""
        context.user_data["work_place"] = work_place

        # Katalogdan narx olindi edi
        if context.user_data.get("_catalog_price"):
            price = context.user_data["_catalog_price"]
            # Narxni saqlash — lekin foydalanuvchi o'zgartira oladi
            keyboard = [[
                InlineKeyboardButton(
                    f"✅ Ha, {format_money(price)} so'm",
                    callback_data="price_confirm"
                ),
                InlineKeyboardButton("✏️ Narxni o'zgartirish", callback_data="price_change")
            ]]
            await update.message.reply_text(
                f"✅ Ish joyi: {work_place or 'Korsatilmagan'}\n"
                f"💵 Katalog narxi: *{format_money(price)} so'm*\n\n"
                "5️⃣ Shu narxda davom etasizmi?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                f"✅ Ish joyi: {work_place or 'Korsatilmagan'}\n\n"
                "5️⃣ Tovarning jami narxini kiriting (so'mda):\n_(Masalan: 3500000)_",
                parse_mode="Markdown"
            )
        return TOTAL_PRICE

    # Bu narx
    try:
        price_text = text.replace(" ", "").replace(",", "")
        price = float(price_text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Narx noto'g'ri. Faqat raqam kiriting (masalan: 3500000):")
        return TOTAL_PRICE

    context.user_data["total_price"] = price
    keyboard = [[
        InlineKeyboardButton("📅 Oylik", callback_data="pay_monthly"),
        InlineKeyboardButton("📆 Haftalik", callback_data="pay_weekly")
    ]]
    await update.message.reply_text(
        f"✅ Jami narx: {format_money(price)} so'm\n\n"
        "6️⃣ To'lov turini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT_TYPE


# ─── 6. TO'LOV TURI VA NARX ─────────────────────────────────
async def get_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        # Narx tasdiqlash yoki o'zgartirish
        if query.data == "price_confirm":
            price = context.user_data.get("_catalog_price", 0)
            context.user_data["total_price"] = price
            await query.edit_message_text(
                f"✅ Narx tasdiqlandi: *{format_money(price)} so'm*\n\n"
                "6️⃣ To'lov turini tanlang:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📅 Oylik", callback_data="pay_monthly"),
                    InlineKeyboardButton("📆 Haftalik", callback_data="pay_weekly")
                ]])
            )
            return PAYMENT_TYPE

        if query.data == "price_change":
            await query.edit_message_text(
                "✏️ Yangi narxni kiriting (so'mda):\n_(Masalan: 3500000)_",
                parse_mode="Markdown"
            )
            return TOTAL_PRICE

        if query.data in ["pay_monthly", "pay_weekly"]:
            pay_type    = "Oylik" if query.data == "pay_monthly" else "Haftalik"
            period_word = "oyga"  if query.data == "pay_monthly" else "haftaga"
            context.user_data["payment_type"] = pay_type
            await query.edit_message_text(
                f"✅ To'lov turi: {pay_type}\n\n"
                f"7️⃣ Necha {period_word}?\n_(Masalan: 6)_",
                parse_mode="Markdown"
            )
            return INSTALLMENT_PERIOD

        # Agar narx kiritilmagan bo'lsa (katalog narxi bilan)
        if "total_price" not in context.user_data:
            return PAYMENT_TYPE

        # Narxni matn sifatida olish (eski oqim)
        return PAYMENT_TYPE

    # Matn — narx kiritish
    if "total_price" not in context.user_data:
        try:
            price_text = update.message.text.strip().replace(" ", "").replace(",", "")
            price = float(price_text)
            if price <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Narx noto'g'ri. Faqat raqam kiriting (masalan: 3500000):")
            return PAYMENT_TYPE

        context.user_data["total_price"] = price
        keyboard = [[
            InlineKeyboardButton("📅 Oylik", callback_data="pay_monthly"),
            InlineKeyboardButton("📆 Haftalik", callback_data="pay_weekly")
        ]]
        await update.message.reply_text(
            f"✅ Jami narx: {format_money(price)} so'm\n\n"
            "6️⃣ To'lov turini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PAYMENT_TYPE

    return PAYMENT_TYPE


# ─── 7. MUDDAT ──────────────────────────────────────────────
async def get_installment_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        period = int(update.message.text.strip())
        if period <= 0 or period > 60:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri muddat. 1-60 oralig'ida kiriting:")
        return INSTALLMENT_PERIOD

    context.user_data["installment_period"] = period
    pay_type    = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    await update.message.reply_text(
        f"✅ Muddat: {period} {period_word}\n\n"
        "8️⃣ Boshlang'ich to'lov (avans) summasini kiriting:\n"
        "_(Avans yo'q bo'lsa 0 kiriting)_",
        parse_mode="Markdown"
    )
    return DOWN_PAYMENT


# ─── 8. AVANS ───────────────────────────────────────────────
async def get_down_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        down  = float(update.message.text.strip().replace(" ", "").replace(",", ""))
        total = context.user_data["total_price"]
        if down < 0 or down >= total:
            raise ValueError
    except ValueError:
        total_str = format_money(context.user_data["total_price"])
        await update.message.reply_text(f"❌ Noto'g'ri summa. 0 dan {total_str} gacha kiriting:")
        return DOWN_PAYMENT

    context.user_data["down_payment"] = down
    remaining   = context.user_data["total_price"] - down
    period      = context.user_data["installment_period"]
    pay_per     = round(remaining / period)
    pay_type    = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    await update.message.reply_text(
        f"✅ Avans: {format_money(down)} so'm\n"
        f"💰 Qoldiq: {format_money(remaining)} so'm\n"
        f"📅 Har {period_word}: {format_money(pay_per)} so'm\n\n"
        "9️⃣ Agent ismini kiriting:\n_(Yo'q bo'lsa: - yozing)_",
        parse_mode="Markdown"
    )
    return AGENT


# ─── 9. AGENT ───────────────────────────────────────────────
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
            "🔟 Har oy necha-sida to'lov qiladi?\nTo'lov kunini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[
            InlineKeyboardButton("Dushanba",   callback_data="payday_1"),
            InlineKeyboardButton("Seshanba",   callback_data="payday_2"),
            InlineKeyboardButton("Chorshanba", callback_data="payday_3"),
        ], [
            InlineKeyboardButton("Payshanba",  callback_data="payday_4"),
            InlineKeyboardButton("Juma",       callback_data="payday_5"),
            InlineKeyboardButton("Shanba",     callback_data="payday_6"),
        ], [
            InlineKeyboardButton("Yakshanba",  callback_data="payday_7"),
        ]]
        await update.message.reply_text(
            "🔟 Har hafta qaysi kuni to'lov qiladi?\nTo'lov kunini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    return PAY_DAY


# ─── 10. TO'LOV KUNI → OY TANLASH ───────────────────────────
async def get_pay_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("payday_"):
        day = int(query.data.replace("payday_", ""))
        context.user_data["pay_day"] = day
        pay_type = context.user_data.get("payment_type", "Oylik")

        if pay_type == "Haftalik":
            day_name = WEEK_DAYS.get(day, str(day))
            await query.edit_message_text(f"✅ To'lov kuni: har hafta {day_name}")
            return await _ask_start_month(query, context)
        else:
            await query.edit_message_text(f"✅ To'lov kuni: har oyning {day}-si")
            return await _ask_start_month(query, context)

    if query.data.startswith("startmonth_"):
        month = int(query.data.replace("startmonth_", ""))
        context.user_data["start_month"] = month
        month_name = MONTHS.get(month, str(month))
        await query.edit_message_text(f"✅ Birinchi to'lov: {month_name} oyidan boshlanadi")
        return await _show_confirm(query, context)

    return PAY_DAY


async def _ask_start_month(query, context):
    """Qaysi oydan boshlanishi — joriy + keyingi 3 oy"""
    today = date.today()
    keyboard = []
    row = []
    for i in range(4):
        m = (today.month - 1 + i) % 12 + 1
        y = today.year + ((today.month - 1 + i) // 12)
        label = f"{MONTHS[m]} {y}"
        row.append(InlineKeyboardButton(label, callback_data=f"startmonth_{m}"))
    keyboard.append(row)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="📅 Birinchi to'lov qaysi oydan boshlanadi?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAY_DAY


# ─── 11. TASDIQLASH ─────────────────────────────────────────
async def _show_confirm(query, context):
    data        = context.user_data
    remaining   = data["total_price"] - data.get("down_payment", 0)
    pay_per     = round(remaining / data["installment_period"])
    pay_type    = data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"
    pay_day     = data.get("pay_day", 0)
    start_month = data.get("start_month", date.today().month)
    month_name  = MONTHS.get(start_month, "")

    if pay_type == "Haftalik":
        tolov_kuni = f"Har hafta {WEEK_DAYS.get(pay_day, str(pay_day))}"
    else:
        tolov_kuni = f"Har oyning {pay_day}-si"

    summary = (
        f"📋 *SAVDO MA'LUMOTLARI*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: {data['fio']}\n"
        f"📞 Telefon: {data['phone']}\n"
        f"🏢 Ish joyi: {data.get('work_place', '') or 'Korsatilmagan'}\n"
        f"🛍 Tovar: {data['product']}\n"
        f"💵 Jami narx: {format_money(data['total_price'])} so'm\n"
        f"💳 Avans: {format_money(data.get('down_payment', 0))} so'm\n"
        f"💰 Qoldiq: {format_money(remaining)} so'm\n"
        f"📅 To'lov turi: {pay_type}\n"
        f"🗓 Muddat: {data['installment_period']} {period_word}\n"
        f"📆 Har {period_word}: {format_money(pay_per)} so'm\n"
        f"🔔 To'lov kuni: {tolov_kuni}\n"
        f"📆 Boshlanish: {month_name} oyidan\n"
    )
    if data.get("agent"):
        summary += f"👨‍💼 Agent: {data['agent']}\n"
    summary += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash",   callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")
    ]]
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def confirm_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("payday_") or query.data.startswith("startmonth_"):
        return await get_pay_day(update, context)

    if query.data == "confirm_no":
        await query.edit_message_text("❌ Savdo bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    if query.data != "confirm_yes":
        return CONFIRM

    await query.edit_message_text("⏳ Ma'lumotlar saqlanmoqda...")

    try:
        # start_month ni google_sheets ga uzatish
        result = add_sale(context.user_data)

        # Buyurtma bo'lsa avtomatik "Yetkazildi" ga o'tkazish
        try:
            from handlers.order_handler import auto_complete_order
            auto_complete_order(
                phone=context.user_data.get("phone", ""),
                product_name=context.user_data.get("product", "")
            )
        except Exception:
            pass

        schedule_text = "📅 TO'LOV JADVALI:\n"
        for item in result["schedule"][:6]:
            schedule_text += (
                f"{item['num']}. {item['date']} — "
                f"{format_money(item['amount'])} so'm "
                f"(qoldiq: {format_money(item['remaining'])})\n"
            )
        if len(result["schedule"]) > 6:
            schedule_text += f"... va yana {len(result['schedule'])-6} ta to'lov\n"

        await query.edit_message_text(
            f"✅ *SAVDO SAQLANDI!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Savdo ID: {result['sale_id']}\n"
            f"💰 Qoldiq: {format_money(result['remaining'])} so'm\n"
            f"📆 Har to'lov: {format_money(result['payment_per_period'])} so'm\n"
            f"📅 Birinchi to'lov: {result['next_payment']}\n\n"
            f"{schedule_text}\n"
            f"✅ Google Sheets ga saqlandi",
            parse_mode="Markdown"
        )

        # Mijozga xabar
        try:
            from sheets.google_sheets import get_client_chat_id
            phone          = context.user_data.get("phone", "")
            client_chat_id = get_client_chat_id(phone)
            if client_chat_id and str(client_chat_id).strip():
                pay_type    = context.user_data.get("payment_type", "Oylik")
                period      = context.user_data.get("installment_period", 0)
                period_word = "oy" if pay_type == "Oylik" else "hafta"
                pay_day     = context.user_data.get("pay_day", 0)
                start_month = context.user_data.get("start_month", date.today().month)

                if pay_type == "Oylik" and pay_day:
                    tolov_kuni = f"Har oyning {pay_day}-si"
                elif pay_type == "Haftalik" and pay_day:
                    tolov_kuni = "Har hafta " + WEEK_DAYS.get(int(pay_day), str(pay_day))
                else:
                    tolov_kuni = result["next_payment"]

                # To'lov jadvalini tayyorlash
                jadval = result.get("schedule", [])
                jadval_text = "📅 *TO'LOV JADVALI:*\n"
                for item in jadval[:12]:  # max 12 ta ko'rsat
                    jadval_text += (
                        f"`{item['num']:2}.` {item['date']} — "
                        f"*{format_money(item['amount'])} so'm* "
                        f"(qoldiq: {format_money(item['remaining'])})\n"
                    )
                if len(jadval) > 12:
                    jadval_text += f"_... va yana {len(jadval)-12} ta to'lov_\n"
                

                client_msg = (
                    f"🎉 *Yangi nasiya rasmiylashtirildi!*\n\n"
                    f"Hurmatli *{context.user_data.get('fio')}!*\n\n"
                    f"🛍 Tovar: *{context.user_data.get('product')}*\n"
                    f"💵 Jami narx: *{format_money(context.user_data.get('total_price', 0))} so'm*\n"
                    f"💳 Avans: *{format_money(context.user_data.get('down_payment', 0))} so'm*\n"
                    f"💰 Qoldiq: *{format_money(result['remaining'])} so'm*\n"
                    f"📅 To'lov turi: *{pay_type}*\n"
                    f"🗓 Muddat: *{period} {period_word}*\n"
                    f"💳 Har to'lov: *{format_money(result['payment_per_period'])} so'm*\n"
                    f"🔔 To'lov kuni: *{tolov_kuni}*\n"
                    f"📆 Birinchi to'lov: *{result['next_payment']}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{jadval_text}\n"
                    f"Xaridingiz uchun rahmat! 🏪 TexnoVibe"
                )
                await query.get_bot().send_message(
                    chat_id=int(client_chat_id),
                    text=client_msg,
                    parse_mode="Markdown"
                )
        except Exception:
            pass

    except Exception as e:
        await query.edit_message_text(f"❌ Xatolik: {str(e)}\n\nQaytadan: /savdo")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    admin_id = int(os.getenv("ADMIN_CHAT_ID", "0"))
    user_id  = update.effective_user.id

    if user_id == admin_id:
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("➕ Yangi Savdo"),      KeyboardButton("💰 To'lov Qabul")],
            [KeyboardButton("❌ Bekor Qilish"),      KeyboardButton("📅 Bugungi To'lovlar")],
            [KeyboardButton("👥 Mijozlar"),           KeyboardButton("📊 Statistika")],
            [KeyboardButton("⚠️ Qarzdorlar"),        KeyboardButton("🚫 Qora Ro'yxat")],
            [KeyboardButton("⭐ Reyting"),            KeyboardButton("🔍 Qidirish")],
            [KeyboardButton("🎯 Auksion"),            KeyboardButton("📥 Excel Eksport")],
            [KeyboardButton("📦 Tovar Qoshish"),      KeyboardButton("🛍 Katalog")],
            [KeyboardButton("🛒 Buyurtmalar"),        KeyboardButton("🏠 Bosh Menyu")],
        ], resize_keyboard=True)
    else:
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
