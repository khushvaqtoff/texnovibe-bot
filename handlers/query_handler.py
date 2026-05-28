"""
So'rov handlerlari
/tarix, /qidir, /qarzdorlar, /qoralist,
/reyting, /mijozlar, /bugun, /statistika
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_payment_history, get_all_clients_with_status,
    get_overdue_payments, get_today_payments, get_statistics
)

SEARCH_QUERY = 50


def format_money(amount) -> str:
    try:
        if not amount:
            return "0"
        # Probirlarni olib tashlab, raqamga o'giramiz
        clean_amount = str(amount).replace(" ", "").replace(",", "")
        return f"{int(float(clean_amount)):,}".replace(",", " ")
    except:
        return str(amount)


def safe_float(value) -> float:
    try:
        if not value:
            return 0.0
        return float(str(value).replace(" ", "").replace(",", ""))
    except:
        return 0.0


def safe_int(value) -> int:
    try:
        if not value:
            return 0
        return int(float(str(value).replace(" ", "").replace(",", "")))
    except:
        return 0


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qidirish conversation boshlaydi"""
    if context.args:
        context.user_data["search_text"] = " ".join(context.args)
        # To'g'ridan-to'g'ri qidiruvni yakunlaymiz, Conversation emas oddiy funksiya kabi
        await search_query(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "🔍 <b>Qidirish</b>\n\nIsm yoki telefon raqamini yozing:",
        parse_mode="HTML"
    )
    return SEARCH_QUERY


async def search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qidiruv so'rovini bajaradi"""
    if context.user_data.get("search_text"):
        query_text = context.user_data.pop("search_text").lower().strip()
    else:
        query_text = update.message.text.strip().lower()

    try:
        all_clients = get_all_clients_with_status()
        results = []

        search_clean = query_text.replace("+", "").replace(" ", "")

        for client in all_clients:
            fio = str(client.get("FIO", "")).lower()
            phone = str(client.get("Telefon", "")).lower().replace("+", "").replace(" ", "")
            if query_text in fio or search_clean in phone:
                results.append(client)

        if not results:
            await update.message.reply_text(
                f"❌ <b>'{query_text}'</b> bo'yicha hech narsa topilmadi.\n\n"
                "Qaytadan qidirish uchun ism yoki telefon yozing:",
                parse_mode="HTML"
            )
            return SEARCH_QUERY

        text = f"🔍 <b>QIDIRUV NATIJALARI</b> ({len(results)} ta)\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in results[:10]:
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "🟡 Yangi")
            text += (
                f"👤 <b>{fio}</b>\n"
                f"📞 <code>{phone}</code>\n"
                f"🛍 {tovar}\n"
                f"💰 Qoldiq: <b>{qoldiq} so'm</b>\n"
                f"📅 Keyingi: {keyingi}\n"
                f"⭐ {reyting}\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")

    context.user_data.clear()
    return ConversationHandler.END


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "📋 <b>Foydalanish:</b>\n<code>/tarix +998901234567</code>",
            parse_mode="HTML"
        )
        return

    phone = args[0]
    await update.message.reply_text("⏳ Ma'lumotlar yuklanmoqda...")

    try:
        history = get_payment_history(phone)
        if not history:
            await update.message.reply_text(
                f"❌ <code>{phone}</code> raqami uchun to'lov tarixi topilmadi.",
                parse_mode="HTML"
            )
            return

        total_paid = sum(safe_float(r.get("To'lov Summasi", 0)) for r in history)
        last_remaining = history[-1].get("Qoldiq", 0) if history else 0

        text = (
            f"📋 <b>TO'LOV TARIXI</b>\n"
            f"📞 Telefon: <code>{phone}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        for i, rec in enumerate(history, 1):
            sana = rec.get("To'lov Sanasi", "")
            summa = format_money(rec.get("To'lov Summasi", 0))
            text += f"{i}. 📅 {sana} — <b>{summa} so'm</b>\n"

        total_str = format_money(total_paid)
        rem_str = format_money(last_remaining)
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Jami to'langan: <b>{total_str} so'm</b>\n"
            f"💰 Hozirgi qoldiq: <b>{rem_str} so'm</b>"
        )

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "🔍 <b>Foydalanish:</b>\n<code>/qidir Anvarov</code>\n<code>/qidir +998901234567</code>",
            parse_mode="HTML"
        )
        return

    query_text = " ".join(args).lower().strip()
    await update.message.reply_text("⏳ Qidirilmoqda...")

    try:
        all_clients = get_all_clients_with_status()
        results = []
        search_clean = query_text.replace("+", "").replace(" ", "")

        for client in all_clients:
            fio = str(client.get("FIO", "")).lower()
            phone = str(client.get("Telefon", "")).lower().replace("+", "").replace(" ", "")
            if query_text in fio or search_clean in phone:
                results.append(client)

        if not results:
            await update.message.reply_text(f"❌ '{query_text}' bo'yicha hech narsa topilmadi.")
            return

        text = f"🔍 <b>QIDIRUV NATIJALARI</b> ({len(results)} ta)\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in results[:10]:
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "🟡 Yangi")
            text += (
                f"👤 <b>{fio}</b>\n"
                f"📞 <code>{phone}</code>\n"
                f"🛍 {tovar}\n"
                f"💰 Qoldiq: <b>{qoldiq} so'm</b>\n"
                f"📅 Keyingi: {keyingi}\n"
                f"⭐ {reyting}\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")


async def cmd_debtors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ma'lumotlar yuklanmoqda...")

    try:
        overdue = get_overdue_payments(1)
        if not overdue:
            await update.message.reply_text("✅ Hozircha hech kim kechiktirmayapti!")
            return

        text = f"⚠️ <b>KECHIKAYOTGANLAR</b> ({len(overdue)} ta)\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in overdue:
            days = safe_int(rec.get("Kechikish Kunlari", 0))
            emoji = "🔴" if days >= 3 else "🟡"
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            text += (
                f"{emoji} <b>{fio}</b>\n"
                f"📞 <code>{phone}</code>\n"
                f"💰 Qoldiq: <b>{qoldiq} so'm</b>\n"
                f"⏰ Kechikish: <b>{days} kun</b>\n"
                f"📅 To'lashi kerak edi: {keyingi}\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Qora ro'yxat yuklanmoqda...")

    try:
        blacklist = get_overdue_payments(3)
        if not blacklist:
            await update.message.reply_text("✅ Qora ro'yxat bo'sh — hammasi vaqtida to'layapti!")
            return

        text = (
            f"🚫 <b>QORA RO'YXAT</b> ({len(blacklist)} ta)\n"
            f"<i>(3 va undan ko'p kun kechiktirayotganlar)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        for rec in blacklist:
            days = safe_int(rec.get("Kechikish Kunlari", 0))
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += (
                f"🔴 <b>{fio}</b>\n"
                f"📞 <code>{phone}</code>\n"
                f"🛍 {tovar}\n"
                f"💰 Qoldiq: <b>{qoldiq} so'm</b>\n"
                f"⏰ Kechikish: <b>{days} kun</b> ❌\n"
                f"⚠️ Boshqa nasiya bermaslik tavsiya etiladi!\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")


async def cmd_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Reyting hisoblanmoqda...")

    try:
        clients = get_all_clients_with_status()
        green = [c for c in clients if "🟢" in str(c.get("Reyting", ""))]
        yellow = [c for c in clients if "🟡" in str(c.get("Reyting", ""))]
        red = [c for c in clients if "🔴" in str(c.get("Reyting", ""))]

        text = (
            f"⭐ <b>MIJOZLAR REYTINGI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 A'lo (vaqtida to'laydi): <b>{len(green)} ta</b>\n"
            f"🟡 O'rtacha (1-2 kun kechikish): <b>{len(yellow)} ta</b>\n"
            f"🔴 Xavfli (doimiy kechikish): <b>{len(red)} ta</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if red:
            text += "🔴 <b>XAVFLI MIJOZLAR:</b>\n"
            for c in red[:5]:
                fio = c.get("FIO", "")
                phone = c.get("Telefon", "")
                text += f"• {fio} — <code>{phone}</code>\n"
            text += "\n"

        if green:
            text += "🟢 <b>ENG YAXSHI MIJOZLAR:</b>\n"
            for c in green[:5]:
                fio = c.get("FIO", "")
                phone = c.get("Telefon", "")
                text += f"• {fio} — <code>{phone}</code>\n"

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")


async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mijozlar yuklanmoqda...")

    try:
        clients = get_all_clients_with_status()
        if not clients:
            await update.message.reply_text("📋 Hozircha faol mijozlar yo'q.")
            return

        text = f"👥 <b>FAOL MIJOZLAR</b> ({len(clients)} ta)\n━━━━━━━━━━━━━━━━━━━━\n"

        for i, rec in enumerate(clients, 1):
            pay_type = rec.get("To'lov Turi", "Oylik")
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            reyting = rec.get("Reyting", "🟡")
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            
            chunk = (
                f"{i}. {reyting} <b>{fio}</b>\n"
                f"   📞 <code>{phone}</code>\n"
                f"   {pay_emoji} {pay_type} | 💰 {qoldiq} so'm\n"
            )
            
            # Telegram xabar limiti (4096) oshib ketmasligi uchun xavfsiz limit (3500 belgi)
            if len(text) + len(chunk) > 3500:
                await update.message.reply_text(text, parse_mode="HTML")
                text = ""
                
            text += chunk

        if text:
            await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Bugungi to'lovlar yuklanmoqda...")

    try:
        today_payments = get_today_payments()
        if not today_payments:
            await update.message.reply_text("📅 Bugun to'lov qilishi kerak bo'lgan mijoz yo'q.")
            return

        total_expected = sum(safe_float(r.get("To'lov Summasi", 0)) for r in today_payments)
        total_str = format_money(total_expected)

        text = (
            f"📅 <b>BUGUNGI TO'LOVLAR</b> ({len(today_payments)} ta)\n"
            f"💵 Kutilayotgan jami: <b>{total_str} so'm</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        for i, rec in enumerate(today_payments, 1):
            pay_type = rec.get("To'lov Turi", "Oylik")
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tolov = format_money(rec.get("To'lov Summasi", 0))
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += (
                f"{i}. {pay_emoji} <b>{fio}</b>\n"
                f"   📞 <code>{phone}</code>\n"
                f"   💳 To'lashi kerak: <b>{tolov} so'm</b>\n"
                f"   💰 Jami qoldiq: {qoldiq} so'm\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Statistika hisoblanmoqda...")

    try:
        stats = get_statistics()
        total_debt = format_money(stats.get("total_debt", 0))
        total_rev = format_money(stats.get("total_revenue", 0))

        text = (
            "📊 <b>UMUMIY STATISTIKA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Jami savdolar: <b>{stats.get('total_sales', 0)} ta</b>\n"
            f"🔄 Faol kreditlar: <b>{stats.get('active', 0)} ta</b>\n"
            f"✅ Yopilgan kreditlar: <b>{stats.get('closed', 0)} ta</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Jami qoldiq: <b>{total_debt} so'm</b>\n"
            f"💵 Jami sotuv: <b>{total_rev} so'm</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Kechikayotganlar: <b>{stats.get('overdue_count', 0)} ta</b>\n"
            f"🚫 Qora ro'yxat: <b>{stats.get('blacklist_count', 0)} ta</b>\n"
        )

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: <code>{str(e)}</code>", parse_mode="HTML")