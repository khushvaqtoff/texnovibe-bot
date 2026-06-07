"""
Savdo kiritish handleri
Yangilik: Bitta savdoda bir nechta tovar — vergul bilan, narxlar qo'shiladi
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import add_sale, check_duplicate, get_sheet
import os
import calendar
from datetime import date, timedelta

PHONE, NAME, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE, \
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
    return str(phone).replace("+","").replace(" ","").replace("-","").strip()

def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)

def get_catalog_products() -> list:
    try:
        ws   = get_sheet("Katalog")
        rows = ws.get_all_records()
        return [r for r in rows if str(r.get("Holat","")).strip() == "Faol"]
    except:
        return []


# ─── YORDAMCHI: tanlangan tovarlar ro'yxatini ko'rsatish ────
def _selected_text(context) -> str:
    items = context.user_data.get("_selected_items", [])
    if not items:
        return ""
    text = "🛒 *Tanlangan tovarlar:*\n"
    total = 0
    for i, item in enumerate(items, 1):
        text += f"  {i}. {item['nom']} — {format_money(item['narx'])} so'm\n"
        total += item['narx']
    text += f"💵 *Jami: {format_money(total)} so'm*\n"
    return text


async def _ask_product(msg_or_query, context, edit=False):
    """Katalogdan tovar tanlash tugmalarini ko'rsatish"""
    products = get_catalog_products()
    context.user_data["_catalog"] = products

    selected_items = context.user_data.get("_selected_items", [])
    selected_names = {item["nom"] for item in selected_items}

    keyboard = []

    if products:
        for i, p in enumerate(products):
            nom  = p.get("Tovar Nomi", p.get("Nom", "Tovar"))
            narx = format_money(p.get("Narx", 0))
            # Allaqachon tanlangan tovarni belgilash
            prefix = "✅ " if nom in selected_names else "🛍 "
            keyboard.append([InlineKeyboardButton(
                f"{prefix}{nom} — {narx} so'm",
                callback_data=f"prod_{i}"
            )])

    keyboard.append([InlineKeyboardButton("✏️ Qo'lda kiritish", callback_data="prod_manual")])

    # Agar kamida 1 ta tanlangan bo'lsa — "Tayyor" tugmasi
    if selected_items:
        total = sum(item["narx"] for item in selected_items)
        keyboard.append([InlineKeyboardButton(
            f"✅ Tayyor ({len(selected_items)} ta | {format_money(total)} so'm)",
            callback_data="prod_done"
        )])

    sel_text = _selected_text(context)
    text = (sel_text + "\n" if sel_text else "") + "3️⃣ Tovar tanlang (bir nechta bo'lsa qayta bosing):"

    if edit:
        try:
            await msg_or_query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            await msg_or_query.message.reply_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await msg_or_query.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ─── 1. BOSHLASH ────────────────────────────────────────────
async def start_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "➕ *Yangi Nasiya Savdo*\n\n"
        "1️⃣ Mijozning telefon raqamini kiriting:\n"
        "_(Masalan: +998901234567)_",
        parse_mode="Markdown"
    )
    return PHONE


# ─── 2. TELEFON → tekshirish → ISM ──────────────────────────
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone       = update.message.text.strip()
    clean_phone = normalize_phone(phone)

    if not clean_phone.isdigit() or len(clean_phone) < 9:
        await update.message.reply_text("❌ Telefon raqami noto\u2019g\u2019ri. Qaytadan kiriting:")
        return PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text("⏳ Tekshirilmoqda...")

    try:
        dup = check_duplicate(clean_phone)
        if dup["exists"]:
            # Ism allaqachon ma'lum — saqlash va to'g'ridan tovar tanlashga o'tish
            context.user_data["fio"] = dup["fio"]
            context.user_data["_selected_items"] = []
            keyboard = [[
                InlineKeyboardButton("✅ Ha, qo'shaman", callback_data="dup_yes"),
                InlineKeyboardButton("❌ Yo'q, bekor",   callback_data="dup_no")
            ]]
            await update.message.reply_text(
                f"⚠️ Bu telefon bazada bor!\n\n"
                f"👤 Mijoz: *{dup['fio']}*\n"
                f"🛍 Mavjud tovar: {dup['product']}\n"
                f"💰 Qoldiq: {format_money(dup['remaining'])} so'm\n\n"
                f"Shunda ham yangi savdo qo'shaveraymi?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return NAME
    except Exception as e:
        await update.message.reply_text(f"⚠️ Baza tekshirishda xato: {str(e)}\nDavom etilmoqda...")

    # Yangi mijoz — ism so'rash
    await update.message.reply_text(
        f"✅ Telefon: `{phone}`\n\n"
        "2️⃣ Mijozning to'liq ismini kiriting:\n"
        "_(Masalan: Anvarov Ali Karimovich)_",
        parse_mode="Markdown"
    )
    return NAME


# ─── 3. ISM ─────────────────────────────────────────────────
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Duplicate callback dan kelishi mumkin
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "dup_no":
            await query.edit_message_text("❌ Savdo bekor qilindi.")
            context.user_data.clear()
            return ConversationHandler.END
        elif query.data == "dup_yes":
            # Ism allaqachon saqlangan — tovar tanlashga o'tish
            await query.edit_message_text(
                f"✅ Mijoz: *{context.user_data.get('fio', '')}*\n"
                f"📞 Telefon: `{context.user_data.get('phone', '')}`\n\n"
                "Tovar tanlanmoqda...",
                parse_mode="Markdown"
            )
            await _ask_product(query, context, edit=False)
            return PRODUCT

    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("❌ Ism juda qisqa. Qaytadan kiriting:")
        return NAME
    context.user_data["fio"] = name
    context.user_data["_selected_items"] = []
    await _ask_product(update.message, context)
    return PRODUCT



# ─── 4. TOVAR (bir nechta tanlash) ──────────────────────────
async def get_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        # Duplicate callback endi NAME state da ishlaydi
        if query.data in ("dup_no", "dup_yes"):
            return PRODUCT

        # Tovar tanlash tugaди
        if query.data == "prod_done":
            items = context.user_data.get("_selected_items", [])
            if not items:
                await query.answer("❌ Hech tovar tanlanmadi!", show_alert=True)
                return PRODUCT

            # Tovarlar nomini vergul bilan birlashtirish
            nom_list   = ", ".join(item["nom"] for item in items)
            total_narx = sum(item["narx"] for item in items)
            context.user_data["product"]        = nom_list
            context.user_data["_catalog_price"] = float(total_narx)

            await query.edit_message_text(
                f"✅ *Tovarlar:*\n{_selected_text(context)}\n"
                f"4️⃣ Ish joyini kiriting:\n_(Yo'q bo'lsa: - yozing)_",
                parse_mode="Markdown"
            )
            return TOTAL_PRICE

        # Qo'lda kiritish
        if query.data == "prod_manual":
            await query.edit_message_text(
                "✏️ Tovar nomini yozing:\n_(Masalan: Samsung Galaxy A55)_",
                parse_mode="Markdown"
            )
            context.user_data["_manual_product"] = True
            return PRODUCT

        # Katalogdan tanlash
        if query.data.startswith("prod_"):
            idx      = int(query.data.replace("prod_", ""))
            products = context.user_data.get("_catalog", [])
            if idx < len(products):
                p    = products[idx]
                nom  = p.get("Tovar Nomi", p.get("Nom", ""))
                narx = float(p.get("Narx", 0))

                items = context.user_data.setdefault("_selected_items", [])
                # Agar allaqachon bor bo'lsa — olib tashlash (toggle)
                existing = next((i for i, x in enumerate(items) if x["nom"] == nom), None)
                if existing is not None:
                    items.pop(existing)
                    await query.answer(f"❌ {nom} olib tashlandi")
                else:
                    items.append({"nom": nom, "narx": narx})
                    await query.answer(f"✅ {nom} qo'shildi!")

                # Yangilangan tugmalar bilan ko'rsatish
                await _ask_product(query, context, edit=True)
            return PRODUCT

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

        # Qo'lda kiritilgan tovarni ro'yxatga qo'shish (narxsiz)
        items = context.user_data.setdefault("_selected_items", [])
        items.append({"nom": product, "narx": 0})
        context.user_data["_manual_product"] = False

        await update.message.reply_text(
            f"✅ *{product}* qo'shildi!\n\n"
            f"{_selected_text(context)}\n"
            "Yana tovar qo'shishingiz yoki 'Tayyor' deb bosishingiz mumkin:",
            parse_mode="Markdown"
        )
        await _ask_product(update.message, context)
        return PRODUCT

    return PRODUCT


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
        work_place = text
        if work_place in ["-", "yoq", "yo'q"]:
            work_place = ""
        context.user_data["work_place"] = work_place

        catalog_price = context.user_data.get("_catalog_price", 0)
        if catalog_price:
            keyboard = [[
                InlineKeyboardButton(
                    f"✅ Ha, {format_money(catalog_price)} so'm",
                    callback_data="price_confirm"
                ),
                InlineKeyboardButton("✏️ Narxni o'zgartirish", callback_data="price_change")
            ]]
            await update.message.reply_text(
                f"✅ Ish joyi: {work_place or 'Korsatilmagan'}\n"
                f"💵 Jami narx: *{format_money(catalog_price)} so'm*\n\n"
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

    # Narx kiritish
    try:
        price_text = text.replace(" ","").replace(",","")
        price = float(price_text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Narx noto'g'ri. Faqat raqam kiriting (masalan: 3500000):")
        return TOTAL_PRICE

    context.user_data["total_price"] = price
    keyboard = [[
        InlineKeyboardButton("📅 Oylik",    callback_data="pay_monthly"),
        InlineKeyboardButton("📆 Haftalik", callback_data="pay_weekly")
    ]]
    await update.message.reply_text(
        f"✅ Jami narx: {format_money(price)} so'm\n\n6️⃣ To'lov turini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT_TYPE


# ─── 6. TO'LOV TURI ─────────────────────────────────────────
async def get_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "price_confirm":
            price = context.user_data.get("_catalog_price", 0)
            context.user_data["total_price"] = price
            await query.edit_message_text(
                f"✅ Narx tasdiqlandi: *{format_money(price)} so'm*\n\n6️⃣ To'lov turini tanlang:",
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

        if query.data in ["pay_monthly", "pay_weekly"]:
            pay_type    = "Oylik" if query.data == "pay_monthly" else "Haftalik"
            period_word = "oyga"  if query.data == "pay_monthly" else "haftaga"
            context.user_data["payment_type"] = pay_type
            await query.edit_message_text(
                f"✅ To'lov turi: {pay_type}\n\n7️⃣ Necha {period_word}?\n_(Masalan: 6)_",
                parse_mode="Markdown"
            )
            return INSTALLMENT_PERIOD

    if "total_price" not in context.user_data:
        try:
            price = float(update.message.text.strip().replace(" ","").replace(",",""))
            if price <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Narx noto'g'ri. Faqat raqam kiriting:")
            return PAYMENT_TYPE
        context.user_data["total_price"] = price
        keyboard = [[
            InlineKeyboardButton("📅 Oylik",    callback_data="pay_monthly"),
            InlineKeyboardButton("📆 Haftalik", callback_data="pay_weekly")
        ]]
        await update.message.reply_text(
            f"✅ Jami narx: {format_money(price)} so'm\n\n6️⃣ To'lov turini tanlang:",
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
        "8️⃣ Boshlang'ich to'lov (avans) summasini kiriting:\n_(Avans yo'q bo'lsa 0 kiriting)_",
        parse_mode="Markdown"
    )
    return DOWN_PAYMENT


# ─── 8. AVANS ───────────────────────────────────────────────
async def get_down_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        down  = float(update.message.text.strip().replace(" ","").replace(",",""))
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
        # Keyingi 7 kun — sana bilan ko'rsatish
        from datetime import date, timedelta
        bugun = date.today()
        keyboard = []
        for i in range(7):
            kun = bugun + timedelta(days=i+1)
            kun_nomi = WEEK_DAYS.get(kun.isoweekday(), "")
            label = f"{kun_nomi} ({kun.strftime('%d.%m')})"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"payday_{kun.isoweekday()}")])
        await update.message.reply_text(
            "🔟 Har hafta qaysi kuni to'lov qiladi?\nQuyidagi kunlardan tanlang:",
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
        else:
            await query.edit_message_text(f"✅ To'lov kuni: har oyning {day}-si")
        return await _ask_start_month(query, context)

    if query.data.startswith("startmonth_"):
        parts = query.data.replace("startmonth_", "").split("_")
        if len(parts) == 3:
            # Haftalik — aniq sana: month_day_year
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            context.user_data["start_month"] = month
            context.user_data["start_day"]   = day
            context.user_data["start_year"]  = year
            from datetime import date as _date
            sana = _date(year, month, day).strftime("%d.%m.%Y")
            await query.edit_message_text(f"✅ Birinchi to'lov: {sana} dan boshlanadi")
        else:
            # Oylik
            month = int(parts[0])
            context.user_data["start_month"] = month
            month_name = MONTHS.get(month, str(month))
            await query.edit_message_text(f"✅ Birinchi to'lov: {month_name} oyidan boshlanadi")
        return await _show_confirm(query, context)

    return PAY_DAY


async def _ask_start_month(query, context):
    from datetime import date, timedelta
    today    = date.today()
    pay_type = context.user_data.get("payment_type", "Oylik")

    if pay_type == "Haftalik":
        # Haftalik — keyingi 4 hafta sanasini ko'rsatish
        pay_day = context.user_data.get("pay_day", 1)  # haftaning kuni
        keyboard = []
        # Tanlangan hafta kuniga qarab keyingi 4 ta sanani topish
        bugun = today
        sanalar = []
        for i in range(1, 29):
            kun = bugun + timedelta(days=i)
            if kun.isoweekday() == pay_day:
                sanalar.append(kun)
            if len(sanalar) == 4:
                break
        row = []
        for s in sanalar:
            kun_nomi = WEEK_DAYS.get(s.isoweekday(), "")
            label    = f"{kun_nomi} {s.strftime('%d.%m.%Y')}"
            row.append(InlineKeyboardButton(label, callback_data=f"startmonth_{s.month}_{s.day}_{s.year}"))
        keyboard.append(row)
        text = "📅 Birinchi to'lov qaysi kuni boshlanadi?"
    else:
        # Oylik — keyingi 4 oy
        keyboard = []
        row = []
        for i in range(4):
            m = (today.month - 1 + i) % 12 + 1
            y = today.year + ((today.month - 1 + i) // 12)
            label = f"{MONTHS[m]} {y}"
            row.append(InlineKeyboardButton(label, callback_data=f"startmonth_{m}"))
        keyboard.append(row)
        text = "📅 Birinchi to'lov qaysi oydan boshlanadi?"

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
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
    month_name  = MONTHS.get(data.get("start_month", date.today().month), "")

    tolov_kuni = (
        f"Har hafta {WEEK_DAYS.get(pay_day, str(pay_day))}"
        if pay_type == "Haftalik"
        else f"Har oyning {pay_day}-si"
    )

    # Tovarlar ro'yxati
    items    = data.get("_selected_items", [])
    tovar_str = data.get("product", "")
    if items:
        tovar_lines = "\n".join(f"   • {item['nom']} — {format_money(item['narx'])} so'm" for item in items)
        tovar_block = f"🛍 Tovarlar:\n{tovar_lines}"
    else:
        tovar_block = f"🛍 Tovar: {tovar_str}"

    summary = (
        f"📋 *SAVDO MA'LUMOTLARI*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: {data['fio']}\n"
        f"📞 Telefon: {data['phone']}\n"
        f"🏢 Ish joyi: {data.get('work_place','') or 'Korsatilmagan'}\n"
        f"{tovar_block}\n"
        f"💵 Jami narx: {format_money(data['total_price'])} so'm\n"
        f"💳 Avans: {format_money(data.get('down_payment',0))} so'm\n"
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
        result = add_sale(context.user_data)

        try:
            from handlers.order_handler import auto_complete_order
            auto_complete_order(
                phone=context.user_data.get("phone",""),
                product_name=context.user_data.get("product","")
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
            f"{schedule_text}\n✅ Google Sheets ga saqlandi",
            parse_mode="Markdown"
        )

        # Mijozga xabar
        try:
            from sheets.google_sheets import get_client_chat_id
            phone          = context.user_data.get("phone","")
            client_chat_id = get_client_chat_id(phone)
            if client_chat_id and str(client_chat_id).strip():
                pay_type    = context.user_data.get("payment_type","Oylik")
                period      = context.user_data.get("installment_period",0)
                period_word = "oy" if pay_type == "Oylik" else "hafta"
                pay_day     = context.user_data.get("pay_day",0)

                if pay_type == "Oylik" and pay_day:
                    tolov_kuni = f"Har oyning {pay_day}-si"
                elif pay_type == "Haftalik" and pay_day:
                    tolov_kuni = "Har hafta " + WEEK_DAYS.get(int(pay_day), str(pay_day))
                else:
                    tolov_kuni = result["next_payment"]

                jadval      = result.get("schedule", [])
                jadval_text = "📅 *TO'LOV JADVALI:*\n"
                for item in jadval[:12]:
                    jadval_text += (
                        f"`{item['num']:2}.` {item['date']} — "
                        f"*{format_money(item['amount'])} so'm* "
                        f"(qoldiq: {format_money(item['remaining'])})\n"
                    )
                if len(jadval) > 12:
                    jadval_text += f"_... va yana {len(jadval)-12} ta to'lov_\n"

                # Tovarlar ro'yxati
                items = context.user_data.get("_selected_items", [])
                if items and len(items) > 1:
                    tovar_lines = "\n".join(f"   • {x['nom']} — {format_money(x['narx'])} so'm" for x in items)
                    tovar_block = f"🛍 *Tovarlar:*\n{tovar_lines}"
                else:
                    tovar_block = f"🛍 Tovar: *{context.user_data.get('product')}*"

                client_msg = (
                    f"🎉 *Yangi nasiya rasmiylashtirildi!*\n\n"
                    f"Hurmatli *{context.user_data.get('fio')}!*\n\n"
                    f"{tovar_block}\n"
                    f"💵 Jami narx: *{format_money(context.user_data.get('total_price',0))} so'm*\n"
                    f"💳 Avans: *{format_money(context.user_data.get('down_payment',0))} so'm*\n"
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
    admin_id = int(os.getenv("ADMIN_CHAT_ID","0"))
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
