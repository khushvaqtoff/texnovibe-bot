async def get_total_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bu aslida tovar nomi qadamidan keyin jami narxni qabul qilish qadami
    try:
        price_text = update.message.text.strip().replace(" ", "").replace(",", "")
        price = float(price_text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Narx notogri. Faqat raqam kiriting:")
        return TOTAL_PRICE  # Xato bo'lsa shu qadamda qoladi

    context.user_data["total_price"] = price

    # Tugmalarni shu yerning o'zida chiqaramiz
    keyboard = [[
        InlineKeyboardButton("Oylik", callback_data="pay_monthly"),
        InlineKeyboardButton("Haftalik", callback_data="pay_weekly")
    ]]
    await update.message.reply_text(
        f"Jami narx: {format_money(price)} som\n\n"
        "6. Tolov turini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT_TYPE  # Tugma bosilishini kutish uchun o'tadi


async def get_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bu yerda faqat tugma (callback_query) qayta ishlanadi
    query = update.callback_query
    await query.answer()

    if query.data in ["dup_yes", "dup_no"]:
        if query.data == "dup_no":
            await query.edit_message_text("Savdo bekor qilindi.")
            context.user_data.clear()
            return ConversationHandler.END
        else:
            context.user_data["awaiting_dup_confirm"] = False
            phone = context.user_data["phone"]
            await query.edit_message_text(
                f"Telefon: {phone}\n\n"
                "3. Mijozning ish joyini kiriting:\n"
                "(Masalan: Bozor, Maktab)\n"
                "(Yoq bolsa: - yozing)"
            )
            return PRODUCT

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