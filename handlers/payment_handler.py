"""
TexnoVibe — handlers/payment_handler.py
Yangilik: Telefon kiritilgandan keyin mijozning faol savdolari
          (tovarlar) inline tugmalar sifatida ko'rsatiladi.
          Admin qaysi tovar uchun to'lov ekanini tanlaydi.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import record_payment, get_client_chat_id, get_spreadsheet, ensure_worksheets

PAY_PHONE, PAY_SELECT, PAY_AMOUNT, PAY_CONFIRM = range(10, 14)
# PAY_SELECT — YANGI: tovar tanlash bosqichi


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_active_sales_by_phone(phone: str) -> list[dict]:
    """
    Telefon raqami bo'yicha barcha FAOL savdolarni qaytaradi.
    Har biri: {row_index, id, tovar, qoldiq, oylik, ...}
    """
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Savdolar"]
    records = ws.get_all_records()

    clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    natija = []

    for i, rec in enumerate(records, start=2):
        rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
        if rec_phone == clean and str(rec.get("Holat", "")).strip() == "Faol":
            natija.append({
                "row_index": i,
                "id":        rec.get("ID", f"qator-{i}"),
                "tovar":     rec.get("Tovar", "Noma'lum tovar"),
                "qoldiq":    rec.get("Qoldiq", 0),
                "oylik":     rec.get("To'lov Summasi", rec.get("Oylik To'lov", 0)),
                "fio":       rec.get("FIO", ""),
            })

    return natija


# ─────────────────────────────────────────────
# 1. BOSHLASH
# ─────────────────────────────────────────────
async def start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💰 *To'lov Qabul Qilish*\n\n"
        "📞 Mijozning telefon raqamini kiriting:\n"
        "_(Masalan: +998901234567)_",
        parse_mode="Markdown"
    )
    return PAY_PHONE


# ─────────────────────────────────────────────
# 2. TELEFON → savdolarni ko'rsat
# ─────────────────────────────────────────────
async def payment_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()

    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.isdigit() or len(clean_phone) < 9:
        await update.message.reply_text(
            "❌ Telefon raqami noto'g'ri.\n"
            "To'g'ri kiriting: +998901234567"
        )
        return PAY_PHONE

    context.user_data["pay_phone"] = phone

    await update.message.reply_text("⏳ Savdolar qidirilmoqda...")

    savdolar = get_active_sales_by_phone(phone)

    if not savdolar:
        await update.message.reply_text(
            f"❌ `{phone}` raqami bo'yicha faol savdo topilmadi.\n"
            "Telefon raqamini tekshiring.",
            parse_mode="Markdown"
        )
        return PAY_PHONE

    # Faqat bitta savdo bo'lsa — to'g'ridan tanlash
    if len(savdolar) == 1:
        s = savdolar[0]
        context.user_data["pay_sale"] = s
        qoldiq_fmt = format_money(s["qoldiq"])
        oylik_fmt  = format_money(s["oylik"])

        await update.message.reply_text(
            f"✅ *Savdo topildi:*\n\n"
            f"👤 Mijoz: *{s['fio']}*\n"
            f"🛍 Tovar: *{s['tovar']}*\n"
            f"💰 Qoldiq: *{qoldiq_fmt} so'm*\n"
            f"📅 Oylik: *{oylik_fmt} so'm*\n\n"
            f"💵 To'lov summasini kiriting (so'mda):",
            parse_mode="Markdown"
        )
        return PAY_AMOUNT

    # Bir nechta savdo — tanlash tugmalari
    context.user_data["pay_savdolar"] = savdolar

    keyboard = []
    for s in savdolar:
        qoldiq_fmt = format_money(s["qoldiq"])
        label = f"🛍 {s['tovar']} — qoldiq: {qoldiq_fmt} so'm"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"paysel_{s['id']}")])
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="paysel_cancel")])

    fio = savdolar[0]["fio"]
    await update.message.reply_text(
        f"👤 *{fio}* — {len(savdolar)} ta faol savdo topildi.\n\n"
        "Qaysi tovar uchun to'lov qabul qilasiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAY_SELECT


# ─────────────────────────────────────────────
# 3. TOVAR TANLASH (bir nechta savdo bo'lganda)
# ─────────────────────────────────────────────
async def payment_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "paysel_cancel":
        await query.edit_message_text("❌ To'lov bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    # Tanlangan savdo ID
    sale_id = query.data.replace("paysel_", "")
    savdolar = context.user_data.get("pay_savdolar", [])
    tanlangan = next((s for s in savdolar if str(s["id"]) == sale_id), None)

    if not tanlangan:
        await query.edit_message_text("❌ Savdo topilmadi. Qayta urinib ko'ring.")
        return ConversationHandler.END

    context.user_data["pay_sale"] = tanlangan

    qoldiq_fmt = format_money(tanlangan["qoldiq"])
    oylik_fmt  = format_money(tanlangan["oylik"])

    await query.edit_message_text(
        f"✅ *Tanlandi:*\n\n"
        f"👤 Mijoz: *{tanlangan['fio']}*\n"
        f"🛍 Tovar: *{tanlangan['tovar']}*\n"
        f"💰 Qoldiq: *{qoldiq_fmt} so'm*\n"
        f"📅 Oylik: *{oylik_fmt} so'm*\n\n"
        f"💵 To'lov summasini yozing (so'mda):",
        parse_mode="Markdown"
    )
    return PAY_AMOUNT


# ─────────────────────────────────────────────
# 4. SUMMA
# ─────────────────────────────────────────────
async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount_text = update.message.text.strip().replace(" ", "").replace(",", "")
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri summa. Faqat raqam kiriting (masalan: 500000):")
        return PAY_AMOUNT

    context.user_data["pay_amount"] = amount

    phone  = context.user_data["pay_phone"]
    sale   = context.user_data["pay_sale"]
    tovar  = sale["tovar"]

    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="pay_yes"),
        InlineKeyboardButton("❌ Bekor",      callback_data="pay_no")
    ]]

    await update.message.reply_text(
        f"💳 *TO'LOV TASDIQLASH*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: *{sale['fio']}*\n"
        f"📞 Telefon: `{phone}`\n"
        f"🛍 Tovar: *{tovar}*\n"
        f"💵 Summa: *{format_money(amount)} so'm*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tasdiqlaysizmi?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAY_CONFIRM


# ─────────────────────────────────────────────
# 5. TASDIQLASH
# ─────────────────────────────────────────────
async def payment_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pay_no":
        await query.edit_message_text("❌ To'lov bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("⏳ To'lov qayd etilmoqda...")

    phone  = context.user_data["pay_phone"]
    amount = context.user_data["pay_amount"]
    sale   = context.user_data["pay_sale"]

    try:
        # record_payment ga row_index ham beramiz — to'g'ri qatorni yangilash uchun
        result = record_payment(phone, amount, row_index=sale.get("row_index"))

        if not result["success"]:
            error_msg = result.get("error", "Noma'lum xato")
            await query.edit_message_text(
                f"❌ Xatolik: {error_msg}\n\nTelefon raqamini tekshiring."
            )
            context.user_data.clear()
            return ConversationHandler.END

        fio      = result["fio"]
        paid     = format_money(amount)
        old_rem  = format_money(result["old_remaining"])
        new_rem  = format_money(result["new_remaining"])
        next_pay = result["next_payment"]
        bonus    = format_money(result.get("bonus", 0))
        tovar    = sale["tovar"]

        if result["is_closed"]:
            admin_msg = (
                "🎉 *KREDIT TO'LIQ YOPILDI!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Mijoz: *{fio}*\n"
                f"📞 Telefon: `{phone}`\n"
                f"🛍 Tovar: *{tovar}*\n"
                f"💵 So'nggi to'lov: *{paid} so'm*\n"
                f"✅ Qoldiq: *0 so'm*\n"
                f"🏆 Bonus: *{bonus} so'm*\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
        else:
            admin_msg = (
                "✅ *TO'LOV QABUL QILINDI*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Mijoz: *{fio}*\n"
                f"📞 Telefon: `{phone}`\n"
                f"🛍 Tovar: *{tovar}*\n"
                f"💵 To'landi: *{paid} so'm*\n"
                f"📊 Eski qoldiq: *{old_rem} so'm*\n"
                f"💰 Yangi qoldiq: *{new_rem} so'm*\n"
                f"📅 Keyingi to'lov: *{next_pay}*\n"
                f"🎁 Bonus: *{bonus} so'm*\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

        await query.edit_message_text(admin_msg, parse_mode="Markdown")

        # Mijozga xabar
        client_chat_id = get_client_chat_id(phone)
        if client_chat_id and str(client_chat_id).strip():
            try:
                if result["is_closed"]:
                    client_msg = (
                        "🎉 *Tabriklaymiz!*\n\n"
                        f"🛍 Tovar: *{tovar}*\n"
                        "Siz nasiya qarzingizni to'liq yopdingiz!\n"
                        f"✅ So'nggi to'lov: *{paid} so'm*\n\n"
                        "🏆 Sizga *Ishonchli Mijoz* statusi berildi!\n"
                        "🎁 Keyingi xaridingizda *5% keshbek* taqdim etamiz!\n\n"
                        f"💰 Bonus hisobingizda: *{bonus} so'm*\n\n"
                        "Xaridingiz uchun rahmat! TexnoVibe 🏪"
                    )
                else:
                    client_msg = (
                        "✅ *To'lovingiz qabul qilindi!*\n\n"
                        f"🛍 Tovar: *{tovar}*\n"
                        f"💵 To'langan summa: *{paid} so'm*\n"
                        f"💰 Qoldig'ingiz: *{new_rem} so'm*\n"
                        f"📅 Keyingi to'lov: *{next_pay}*\n\n"
                        f"🎁 Bonus hisobingiz: *{bonus} so'm*\n\n"
                        "Rahmat! TexnoVibe 🏪"
                    )
                await query.get_bot().send_message(
                    chat_id=int(client_chat_id),
                    text=client_msg,
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    except Exception as e:
        await query.edit_message_text(
            f"❌ Xatolik:\n`{str(e)}`",
            parse_mode="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END
