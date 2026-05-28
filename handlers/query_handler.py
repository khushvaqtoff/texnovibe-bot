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
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qidirish conversation boshlaydi"""
    # Agar argument bilan kelsa (/qidir Anvarov) — bevosita qidirish
    if context.args:
        context.user_data["search_text"] = " ".join(context.args)
        return await search_query(update, context)

    await update.message.reply_text(
        "🔍 Qidirish "

"Ism yoki telefon raqamini yozing:",
        parse_mode="Markdown"
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

        for client in all_clients:
            fio = str(client.get("FIO", "")).lower()
            phone = str(client.get("Telefon", "")).lower().replace("+", "").replace(" ", "")
            search_clean = query_text.replace("+", "").replace(" ", "")
            if query_text in fio or search_clean in phone:
                results.append(client)

        if not results:
            await update.message.reply_text(
                f"❌ *'{query_text}'* bo'yicha hech narsa topilmadi."

"
                "Qaytadan qidirish uchun ism yoki telefon yozing:",
                parse_mode="Markdown"
            )
            return SEARCH_QUERY

        text = f"🔍 *QIDIRUV NATIJALARI* ({len(results)} ta)
━━━━━━━━━━━━━━━━━━━━
"

        for rec in results[:10]:
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "🟡 Yangi")
            text += (
                f"👤 *{fio}*
"
                f"📞 `{phone}`
"
                f"🛍 {tovar}
"
                f"💰 Qoldiq: *{qoldiq} so'm*
"
                f"📅 Keyingi: {keyingi}
"
                f"⭐ {reyting}
"
                f"─────────────────
"
            )

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "📋 *Foydalanish:*\n`/tarix +998901234567`",
            parse_mode="Markdown"
        )
        return

    phone = args[0]
    await update.message.reply_text("⏳ Malumotlar yuklanmoqda...")

    try:
        history = get_payment_history(phone)
        if not history:
            await update.message.reply_text(
                f"❌ `{phone}` raqami uchun tolov tarixi topilmadi.",
                parse_mode="Markdown"
            )
            return

        total_paid = sum(float(r.get("To'lov Summasi", 0)) for r in history)
        last_remaining = history[-1].get("Qoldiq", 0) if history else 0

        text = (
            f"📋 *TOLOV TARIXI*\n"
            f"📞 Telefon: `{phone}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        for i, rec in enumerate(history, 1):
            sana = rec.get("To'lov Sanasi", "")
            summa = format_money(rec.get("To'lov Summasi", 0))
            text += f"{i}. 📅 {sana} — *{summa} so'm*\n"

        total_str = format_money(total_paid)
        rem_str = format_money(last_remaining)
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Jami tolangan: *{total_str} so'm*\n"
            f"💰 Hozirgi qoldiq: *{rem_str} so'm*"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "🔍 *Foydalanish:*\n`/qidir Anvarov`\n`/qidir +998901234567`",
            parse_mode="Markdown"
        )
        return

    query_text = " ".join(args).lower().strip()
    await update.message.reply_text("⏳ Qidirilmoqda...")

    try:
        all_clients = get_all_clients_with_status()
        results = []

        for client in all_clients:
            fio = str(client.get("FIO", "")).lower()
            phone = str(client.get("Telefon", "")).lower()
            if query_text in fio or query_text in phone:
                results.append(client)

        if not results:
            await update.message.reply_text(f"❌ '{query_text}' boyicha hech narsa topilmadi.")
            return

        text = f"🔍 *QIDIRUV NATIJALARI* ({len(results)} ta)\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in results[:10]:
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "🟡 Yangi")
            text += (
                f"👤 *{fio}*\n"
                f"📞 `{phone}`\n"
                f"🛍 {tovar}\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"📅 Keyingi: {keyingi}\n"
                f"⭐ {reyting}\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")


async def cmd_debtors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Malumotlar yuklanmoqda...")

    try:
        overdue = get_overdue_payments(1)
        if not overdue:
            await update.message.reply_text("✅ Hozircha hech kim kechiktirayotgani yoq!")
            return

        text = f"⚠️ *KECHIKAYOTGANLAR* ({len(overdue)} ta)\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in overdue:
            days = rec.get("Kechikish Kunlari", 0)
            emoji = "🔴" if days >= 3 else "🟡"
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            text += (
                f"{emoji} *{fio}*\n"
                f"📞 `{phone}`\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"⏰ Kechikish: *{days} kun*\n"
                f"📅 Tolashi kerak edi: {keyingi}\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Qora royxat yuklanmoqda...")

    try:
        blacklist = get_overdue_payments(3)
        if not blacklist:
            await update.message.reply_text("✅ Qora royxat bosh — hammasi vaqtida tolayapti!")
            return

        text = (
            f"🚫 *QORA ROYXAT* ({len(blacklist)} ta)\n"
            f"_(3 va undan kop kun kechiktirayotganlar)_\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        for rec in blacklist:
            days = rec.get("Kechikish Kunlari", 0)
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += (
                f"🔴 *{fio}*\n"
                f"📞 `{phone}`\n"
                f"🛍 {tovar}\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"⏰ Kechikish: *{days} kun* ❌\n"
                f"⚠️ Boshqa nasiya bermaslik tavsiya etiladi!\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")


async def cmd_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Reyting hisoblanmoqda...")

    try:
        clients = get_all_clients_with_status()
        green = [c for c in clients if "🟢" in str(c.get("Reyting", ""))]
        yellow = [c for c in clients if "🟡" in str(c.get("Reyting", ""))]
        red = [c for c in clients if "🔴" in str(c.get("Reyting", ""))]

        text = (
            f"⭐ *MIJOZLAR REYTINGI*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 Alo (vaqtida tolaydi): *{len(green)} ta*\n"
            f"🟡 Ortacha (1-2 kun kechikish): *{len(yellow)} ta*\n"
            f"🔴 Xavfli (doimiy kechikish): *{len(red)} ta*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if red:
            text += "🔴 *XAVFLI MIJOZLAR:*\n"
            for c in red[:5]:
                fio = c.get("FIO", "")
                phone = c.get("Telefon", "")
                text += f"• {fio} — `{phone}`\n"
            text += "\n"

        if green:
            text += "🟢 *ENG YAXSHI MIJOZLAR:*\n"
            for c in green[:5]:
                fio = c.get("FIO", "")
                phone = c.get("Telefon", "")
                text += f"• {fio} — `{phone}`\n"

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")


async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mijozlar yuklanmoqda...")

    try:
        clients = get_all_clients_with_status()
        if not clients:
            await update.message.reply_text("📋 Hozircha faol mijozlar yoq.")
            return

        text = f"👥 *FAOL MIJOZLAR* ({len(clients)} ta)\n━━━━━━━━━━━━━━━━━━━━\n"

        for i, rec in enumerate(clients, 1):
            pay_type = rec.get("To'lov Turi", "Oylik")
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            reyting = rec.get("Reyting", "🟡")
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += (
                f"{i}. {reyting} *{fio}*\n"
                f"   📞 `{phone}`\n"
                f"   {pay_emoji} {pay_type} | 💰 {qoldiq} so'm\n"
            )

            if i % 20 == 0 and i < len(clients):
                await update.message.reply_text(text, parse_mode="Markdown")
                text = ""

        if text:
            await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Bugungi tolovlar yuklanmoqda...")

    try:
        today_payments = get_today_payments()
        if not today_payments:
            await update.message.reply_text("📅 Bugun tolov qilishi kerak bolgan mijoz yoq.")
            return

        total_expected = sum(float(r.get("To'lov Summasi", 0)) for r in today_payments)
        total_str = format_money(total_expected)

        text = (
            f"📅 *BUGUNGI TOLOVLAR* ({len(today_payments)} ta)\n"
            f"💵 Kutilayotgan jami: *{total_str} so'm*\n"
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
                f"{i}. {pay_emoji} *{fio}*\n"
                f"   📞 `{phone}`\n"
                f"   💳 Tolashi kerak: *{tolov} so'm*\n"
                f"   💰 Jami qoldiq: {qoldiq} so'm\n"
                f"─────────────────\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Statistika hisoblanmoqda...")

    try:
        stats = get_statistics()
        total_debt = format_money(stats["total_debt"])
        total_rev = format_money(stats["total_revenue"])

        text = (
            "📊 *UMUMIY STATISTIKA*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Jami savdolar: *{stats['total_sales']} ta*\n"
            f"🔄 Faol kreditlar: *{stats['active']} ta*\n"
            f"✅ Yopilgan kreditlar: *{stats['closed']} ta*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Jami qoldiq: *{total_debt} so'm*\n"
            f"💵 Jami sotuv: *{total_rev} so'm*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Kechikayotganlar: *{stats['overdue_count']} ta*\n"
            f"🚫 Qora royxat: *{stats['blacklist_count']} ta*\n"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")
