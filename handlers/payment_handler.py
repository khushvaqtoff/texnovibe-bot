"""
To'lov qabul qilish handleri
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import record_payment, get_client_chat_id

PAY_PHONE, PAY_AMOUNT, PAY_CONFIRM = range(10, 13)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💰 *To'lov Qabul Qilish*\n\n"
        "📞 Mijozning telefon raqamini kiriting:\n"
        "_(Masalan: +998901234567)_",
        parse_mode="Markdown"
    )
    return PAY_PHONE


async def payment_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["pay_phone"] = phone
    await update.message.reply_text(
        f"✅ Telefon: `{phone}`\n\n"
        "💵 To'lov summasini kiriting (so'mda):\n"
        "_(Masalan: 500000)_",
        parse_mode="Markdown"
    )
    return PAY_AMOUNT


async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount_text = update.message.text.strip().replace(" ", "").replace(",", "")
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri summa. Qaytadan kiriting:")
        return PAY_AMOUNT

    context.user_data["pay_amount"] = amount

    keyboard = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="pay_yes"),
            InlineKeyboardButton("❌ Bekor", callback_data="pay_no")
        ]
    ]

    phone = context.user_data["pay_phone"]
    await update.message.reply_text(
        f"💳 *TO'LOV TASDIQLASH*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📞 Telefon: `{phone}`\n"
        f"💵 Summa: *{format_money(amount)} so'm*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tasdiqlaysizmi?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAY_CONFIRM


async def payment_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pay_no":
        await query.edit_message_text("❌ To'lov bekor qilindi.")
        return ConversationHandler.END

    await query.edit_message_text("⏳ To'lov qayd etilmoqda...")

    phone = context.user_data["pay_phone"]
    amount = context.user_data["pay_amount"]

    try:
        result = record_payment(phone, amount)

        if not result["success"]:
            error_msg = result.get("error", "Noma'lum xato")
            await query.edit_message_text(
                f"❌ Xatolik: {error_msg}\n\n"
                "Telefon raqamini tekshiring va qaytadan urinib ko'ring."
            )
            return ConversationHandler.END

        fio = result["fio"]
        paid = format_money(amount)
        old_rem = format_money(result["old_remaining"])
        new_rem = format_money(result["new_remaining"])
        next_pay = result["next_payment"]
        bonus = format_money(result.get("bonus", 0))

        if result["is_closed"]:
            admin_msg = (
                "🎉 *KREDIT TO'LIQ YOPILDI!*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Mijoz: *{fio}*\n"
                f"📞 Telefon: `{phone}`\n"
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
        if client_chat_id and client_chat_id.strip():
            try:
                if result["is_closed"]:
                    client_msg = (
                        "🎉 *Tabriklaymiz!*\n\n"
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
                        f"💵 To'langan summa: *{paid} so'm*\n"
                        f"💰 Qoldigingiz: *{new_rem} so'm*\n"
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
