"""
Savdo kiritish handleri
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import add_sale, check_duplicate
import os

NAME, PHONE, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE, \
    INSTALLMENT_PERIOD, DOWN_PAYMENT, AGENT, WORK_PLACE, PAY_DAY, CONFIRM = range(11)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def start_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "➕ Yangi Nasiya Savdo\n\n"
        "1️⃣ Mijozning to'liq ismini kiriting:\n"
        "(Masalan: Anvarov Ali Karimovich)"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("❌ Ism juda qisqa. Qaytadan kiriting:")
        return NAME
    context.user_data["fio"] = name
    await update.message.reply_text(
        f"✅ Ism: {name}\n\n"
        "2️⃣ Telefon raqamini kiriting:\n"
        "(Masalan: +998901234567)"
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.isdigit() or len(clean_phone) < 9:
        await update.message.reply_text("❌ Telefon raqami noto'g'ri. Qaytadan kiriting:")
        return PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text("⏳ Tekshirilmoqda...")

    try:
        dup = check_duplicate(phone)
        if dup["exists"]:
            fio = dup["fio"]
            product = dup["product"]
            remaining = format_money(dup["remaining"])
            keyboard = [[
                InlineKeyboardButton("✅ Ha, qo'shaman", callback_data="dup_yes"),
                InlineKeyboardButton("❌ Yo'q, bekor", callback_data="dup_no")
            ]]
            await update.message.reply_text(
                f"⚠️ Diqqat! Bu telefon bazada bor!\n\n"
                f"👤 Mijoz: {fio}\n"
                f"🛍 Tovar: {product}\n"
                f"💰 Qoldiq: {remaining} so'm\n\n"
                f"Shunda ham yangi savdo qo'shaveraymi?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            context.user_data["awaiting_dup_confirm"] = True
            return PRODUCT
    except Exception as e:
        await update.message.reply_text(f"⚠️ Baza tekshirishda xato: {str(e)}\nDavom etilmoqda...")

    await update.message.reply_text(
        f"✅ Telefon: {phone}\n\n"
        "3️⃣ Mijozning ish joyini kiriting:\n"
        "(Masalan: Bozor, Maktab, Xususiy)\n"
        "(Yo'q bo'lsa: - yozing)"
    )
    return PRODUCT


# TUZATISH: Bu funksiya ish joyini oladi (nom o'zgartirilmadi, mantiq tuzatildi)
async def get_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Duplicate tasdiqlash callback (dup_yes / dup_no)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "dup_no":
            await query.edit_message_text("❌ Savdo bekor qilindi.")
            context.user_data.clear()
            return ConversationHandler.END
        elif query.data == "dup_yes":
            context.user_data["awaiting_dup_confirm"] = False
            phone = context.user_data["phone"]
            await query.edit_message_text(
                f"✅ Telefon: {phone}\n\n"
                "3️⃣ Mijozning ish joyini kiriting:\n"
                "(Masalan: Bozor, Maktab)\n"
                "(Yo'q bo'lsa: - yozing)"
            )
            return PRODUCT
        return PRODUCT

    # Agar duplicate hali tasdiqlanmagan bo'lsa, matn kelmasin
    if context.user_data.get("awaiting_dup_confirm"):
        return PRODUCT

    work_place = update.message.text.strip()
    if work_place in ["-", "yoq", "yo'q"]:
        work_place = ""
    context.user_data["work_place"] = work_place

    await update.message.reply_text(
        f"✅ Ish joyi: {work_place or 'Korsatilmagan'}\n\n"
        "4️⃣ Tovar nomini kiriting:\n"
        "(Masalan: Samsung Galaxy A55)"
    )
    return TOTAL_PRICE


# TUZATISH: Bu funksiya tovar nomini oladi
async def get_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product = update.message.text.strip()
    if len(product) < 2:
        await update.message.reply_text("❌ Tovar nomi juda qisqa. Qaytadan kiriting:")
        return TOTAL_PRICE
    context.user_data["product"] = product

    await update.message.reply_text(
        f"✅ Tovar: {product}\n\n"
        "5️⃣ Tovarning jami narxini kiriting (so'mda):\n"
        "(Masalan: 3500000)"
    )
    return PAYMENT_TYPE


async def get_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Duplicate tasdiqlash callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data in ["dup_yes", "dup_no"]:
            if query.data == "dup_no":
                await query.edit_message_text("❌ Savdo bekor qilindi.")
                context.user_data.clear()
                return ConversationHandler.END
            else:
                context.user_data["awaiting_dup_confirm"] = False
                phone = context.user_data["phone"]
                await query.edit_message_text(
                    f"✅ Telefon: {phone}\n\n"
                    "3️⃣ Mijozning ish joyini kiriting:\n"
                    "(Masalan: Bozor, Maktab)\n"
                    "(Yo'q bo'lsa: - yozing)"
                )
                return PRODUCT

        if query.data in ["pay_monthly", "pay_weekly"]:
            if query.data == "pay_monthly":
                context.user_data["payment_type"] = "Oylik"
                period_word = "oyga"
            else:
                context.user_data["payment_type"] = "Haftalik"
                period_word = "haftaga"

            pay_type = context.user_data["payment_type"]
            await query.edit_message_text(
                f"✅ To'lov turi: {pay_type}\n\n"
                f"6️⃣ Necha {period_word}?\n"
                "(Masalan: 6)"
            )
            return INSTALLMENT_PERIOD

        return PAYMENT_TYPE

    # Jami narx kiritish (message)
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


async def get_installment_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        period = int(update.message.text.strip())
        if period <= 0 or period > 60:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri muddat. 1-60 oralig'ida kiriting:")
        return INSTALLMENT_PERIOD

    context.user_data["installment_period"] = period
    pay_type = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    await update.message.reply_text(
        f"✅ Muddat: {period} {period_word}\n\n"
        "7️⃣ Boshlang'ich to'lov (avans) summasini kiriting:\n"
        "(Avans yo'q bo'lsa 0 kiriting)"
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
        await update.message.reply_text(f"❌ Noto'g'ri summa. 0 dan {total_str} gacha kiriting:")
        return DOWN_PAYMENT

    context.user_data["down_payment"] = down
    remaining = context.user_data["total_price"] - down
    period = context.user_data["installment_period"]
    pay_per = round(remaining / period)
    pay_type = context.user_data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    await update.message.reply_text(
        f"✅ Avans: {format_money(down)} so'm\n"
        f"💰 Qoldiq: {format_money(remaining)} so'm\n"
        f"📅 Har {period_word}: {format_money(pay_per)} so'm\n\n"
        "8️⃣ Agent ismini kiriting:\n"
        "(Yo'q bo'lsa: - yozing)"
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
            "9️⃣ Har oy necha-sida to'lov qiladi?\n"
            "To'lov kunini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PAY_DAY
    else:
        # Haftalik uchun haftaning kunini tanlash
        keyboard = [[
            InlineKeyboardButton("Dushanba", callback_data="payday_1"),
            InlineKeyboardButton("Seshanba", callback_data="payday_2"),
            InlineKeyboardButton("Chorshanba", callback_data="payday_3"),
        ], [
            InlineKeyboardButton("Payshanba", callback_data="payday_4"),
            InlineKeyboardButton("Juma", callback_data="payday_5"),
            InlineKeyboardButton("Shanba", callback_data="payday_6"),
        ], [
            InlineKeyboardButton("Yakshanba", callback_data="payday_7"),
        ]]
        await update.message.reply_text(
            "9️⃣ Har hafta qaysi kuni to'lov qiladi?\n"
            "To'lov kunini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PAY_DAY


WEEK_DAYS = {
    1: "Dushanba", 2: "Seshanba", 3: "Chorshanba",
    4: "Payshanba", 5: "Juma", 6: "Shanba", 7: "Yakshanba"
}

async def get_pay_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    day = int(query.data.replace("payday_", ""))
    context.user_data["pay_day"] = day

    pay_type = context.user_data.get("payment_type", "Oylik")
    if pay_type == "Haftalik":
        day_name = WEEK_DAYS.get(day, str(day))
        await query.edit_message_text(f"✅ To'lov kuni: har hafta {day_name}")
    else:
        await query.edit_message_text(f"✅ To'lov kuni: har oyning {day}-si")
    return await show_confirm_callback(query, context)


async def show_confirm(update, context):
    data = context.user_data
    remaining = data["total_price"] - data.get("down_payment", 0)
    pay_per = round(remaining / data["installment_period"])
    pay_type = data["payment_type"]
    period_word = "oy" if pay_type == "Oylik" else "hafta"

    summary = (
        f"📋 SAVDO MA'LUMOTLARI\n"
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
    )
    if data.get("pay_day"):
        pay_type_c = data.get("payment_type", "Oylik")
        if pay_type_c == "Haftalik":
            _day_name = WEEK_DAYS.get(int(data["pay_day"]), str(data["pay_day"]))
            summary += f"🔔 To'lov kuni: har hafta {_day_name}\n"
        else:
            summary += f"🔔 To'lov kuni: har oyning {data['pay_day']}-si\n" 
    if data.get("agent"):
        summary += f"👨‍💼 Agent: {data['agent']}\n"
    summary += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")
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
        f"📋 SAVDO MA'LUMOTLARI\n"
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
    )
    if data.get("pay_day"):
        pay_type_c = data.get("payment_type", "Oylik")
        if pay_type_c == "Haftalik":
            _day_name = WEEK_DAYS.get(int(data["pay_day"]), str(data["pay_day"]))
            summary += f"🔔 To'lov kuni: har hafta {_day_name}\n"
        else:
            summary += f"🔔 To'lov kuni: har oyning {data['pay_day']}-si\n" 
    if data.get("agent"):
        summary += f"👨‍💼 Agent: {data['agent']}\n"
    summary += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")
    ]]
    await query.message.reply_text(
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def confirm_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # payday_ callback bu yerga kelmasligi kerak, lekin xavfsizlik uchun
    if query.data.startswith("payday_"):
        return await get_pay_day(update, context)

    if query.data == "confirm_no":
        await query.edit_message_text("❌ Savdo bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    if query.data != "confirm_yes":
        return CONFIRM

    await query.edit_message_text("⏳ Ma'lumotlar saqlanmoqda...")

    try:
        result = add_sale(context.user_data)
        schedule_text = "📅 TO'LOV JADVALI:\n"
        for item in result["schedule"][:6]:
            amount_str = format_money(item["amount"])
            remaining_str = format_money(item["remaining"])
            schedule_text += (
                f"{item['num']}. {item['date']} — "
                f"{amount_str} so'm "
                f"(qoldiq: {remaining_str})\n"
            )
        if len(result["schedule"]) > 6:
            schedule_text += f"... va yana {len(result['schedule'])-6} ta to'lov\n"

        success_msg = (
            f"✅ SAVDO SAQLANDI!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Savdo ID: {result['sale_id']}\n"
            f"💰 Qoldiq: {format_money(result['remaining'])} so'm\n"
            f"📆 Har to'lov: {format_money(result['payment_per_period'])} so'm\n"
            f"📅 Birinchi to'lov: {result['next_payment']}\n\n"
            f"{schedule_text}\n"
            f"✅ Google Sheets ga saqlandi"
        )
        await query.edit_message_text(success_msg)

        # Mijozga savdo haqida darhol xabar yuborish
        try:
            from sheets.google_sheets import get_client_chat_id
            phone = context.user_data.get("phone", "")
            client_chat_id = get_client_chat_id(phone)
            if client_chat_id and str(client_chat_id).strip():
                fio = context.user_data.get("fio", "")
                product = context.user_data.get("product", "")
                pay_type = context.user_data.get("payment_type", "Oylik")
                period = context.user_data.get("installment_period", 0)
                period_word = "oy" if pay_type == "Oylik" else "hafta"
                pay_day = context.user_data.get("pay_day", 0)

                if pay_type == "Oylik" and pay_day:
                    tolov_kuni = f"Har oyning {pay_day}-si"
                elif pay_type == "Haftalik" and pay_day:
                    kunlar = {1:"Dushanba",2:"Seshanba",3:"Chorshanba",
                              4:"Payshanba",5:"Juma",6:"Shanba",7:"Yakshanba"}
                    tolov_kuni = "Har hafta " + kunlar.get(int(pay_day), str(pay_day))
                else:
                    tolov_kuni = result["next_payment"]

                client_msg = (
                    f"🎉 *Yangi nasiya rasmiylashtirildi!*\n\n"
                    f"Hurmatli *{fio}!*\n\n"
                    f"🛍 Tovar: *{product}*\n"
                    f"💰 Jami qoldiq: *{format_money(result['remaining'])} so'm*\n"
                    f"📅 To'lov turi: *{pay_type}*\n"
                    f"🗓 Muddat: *{period} {period_word}*\n"
                    f"💳 Har to'lov: *{format_money(result['payment_per_period'])} so'm*\n"
                    f"🔔 To'lov kuni: *{tolov_kuni}*\n"
                    f"📆 Birinchi to'lov: *{result['next_payment']}*\n\n"
                    f"Xaridingiz uchun rahmat!\n"
                    f"🏪 TexnoVibe"
                )
                await query.get_bot().send_message(
                    chat_id=int(client_chat_id),
                    text=client_msg,
                    parse_mode="Markdown"
                )
        except Exception:
            pass  # Mijoz bot bilan suhbat boshlamamagan bo'lishi mumkin

    except Exception as e:
        await query.edit_message_text(f"❌ Xatolik: {str(e)}\n\nQaytadan: /savdo")

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

    await update.message.reply_text("🏠 Bosh menyuga qaytildi.", reply_markup=keyboard)
    context.user_data.clear()
    return ConversationHandler.END
