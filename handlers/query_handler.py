"""
So'rov handlerlari
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_payment_history, get_all_clients_with_status,
    get_overdue_payments, get_today_payments, get_statistics
)

SEARCH_QUERY = 50


def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", "").strip() or 0)
    except:
        return 0


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        context.user_data["search_text"] = " ".join(context.args)
        return await search_query(update, context)
    await update.message.reply_text(
        "Qidirish\n\nIsm yoki telefon raqamini yozing:"
    )
    return SEARCH_QUERY


async def search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("search_text"):
        query_text = context.user_data.pop("search_text").lower().strip()
    else:
        query_text = update.message.text.strip().lower()

    try:
        all_clients = get_all_clients_with_status()
        results = []
        for client in all_clients:
            fio = str(client.get("FIO", "")).lower()
            phone = str(client.get("Telefon", "")).replace("+", "").replace(" ", "")
            search_clean = query_text.replace("+", "").replace(" ", "")
            if query_text in fio or search_clean in phone:
                results.append(client)

        if not results:
            await update.message.reply_text(
                f"'{query_text}' boyicha hech narsa topilmadi.\n\nQaytadan yozing:"
            )
            return SEARCH_QUERY

        text = f"QIDIRUV NATIJALARI ({len(results)} ta)\n\n"
        for rec in results[:10]:
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "")
            text += (
                f"👤 {fio}\n"
                f"📞 {phone}\n"
                f"🛍 {tovar}\n"
                f"💰 Qoldiq: {qoldiq} som\n"
                f"📅 Keyingi: {keyingi}\n"
                f"⭐ {reyting}\n"
                f"---\n"
            )
        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")

    context.user_data.clear()
    return ConversationHandler.END


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Foydalanish:\n/tarix +998901234567"
        )
        return

    phone = args[0]
    await update.message.reply_text("Malumotlar yuklanmoqda...")

    try:
        history = get_payment_history(phone)
        if not history:
            await update.message.reply_text(f"'{phone}' uchun tolov tarixi topilmadi.")
            return

        total_paid = sum(safe_float(r.get("To'lov Summasi", 0)) for r in history)
        last_remaining = history[-1].get("Qoldiq", 0) if history else 0

        text = f"TOLOV TARIXI\nTelefon: {phone}\n\n"
        for i, rec in enumerate(history, 1):
            sana = rec.get("To'lov Sanasi", "")
            summa = format_money(rec.get("To'lov Summasi", 0))
            text += f"{i}. {sana} - {summa} som\n"

        text += f"\nJami tolangan: {format_money(total_paid)} som\n"
        text += f"Hozirgi qoldiq: {format_money(last_remaining)} som"
        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Foydalanish:\n/qidir Anvarov\n/qidir +998901234567")
        return
    context.user_data["search_text"] = " ".join(args)
    await search_query(update, context)


async def cmd_debtors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Malumotlar yuklanmoqda...")
    try:
        overdue = get_overdue_payments(1)
        if not overdue:
            await update.message.reply_text("Hozircha hech kim kechiktirayotgani yoq!")
            return

        text = f"KECHIKAYOTGANLAR ({len(overdue)} ta)\n\n"
        for rec in overdue:
            days      = rec.get("Kechikish Kunlari", 0)
            emoji     = "🔴" if days >= 3 else "🟡"
            fio       = rec.get("FIO", "")
            phone     = rec.get("Telefon", "")
            qoldiq    = format_money(rec.get("Qoldiq", 0))
            keyingi   = rec.get("Keyingi To'lov Sanasi", "")
            pay_type  = rec.get("To'lov Turi", "Oylik")
            oylik     = format_money(rec.get("To'lov Summasi", 0))
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            text += (
                f"{emoji} {fio}\n"
                f"📞 {phone}\n"
                f"💰 Qoldiq: {qoldiq} som\n"
                f"{pay_emoji} {pay_type} | 💳 {oylik} som\n"
                f"⏰ Kechikish: {days} kun\n"
                f"📅 Tolashi kerak edi: {keyingi}\n\n"
            )
        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Qora royxat yuklanmoqda...")
    try:
        blacklist = get_overdue_payments(3)
        if not blacklist:
            await update.message.reply_text("Qora royxat bosh!")
            return

        text = f"QORA ROYXAT ({len(blacklist)} ta)\n\n"
        for rec in blacklist:
            days = rec.get("Kechikish Kunlari", 0)
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tovar = rec.get("Tovar", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += (
                f"🔴 {fio}\n"
                f"📞 {phone}\n"
                f"🛍 {tovar}\n"
                f"💰 Qoldiq: {qoldiq} som\n"
                f"⏰ Kechikish: {days} kun\n\n"
            )
        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Reyting hisoblanmoqda...")
    try:
        clients = get_all_clients_with_status()
        green = [c for c in clients if "🟢" in str(c.get("Reyting", ""))]
        yellow = [c for c in clients if "🟡" in str(c.get("Reyting", ""))]
        red = [c for c in clients if "🔴" in str(c.get("Reyting", ""))]

        text = (
            f"MIJOZLAR REYTINGI\n\n"
            f"🟢 Alo: {len(green)} ta\n"
            f"🟡 Ortacha: {len(yellow)} ta\n"
            f"🔴 Xavfli: {len(red)} ta\n\n"
        )
        if red:
            text += "🔴 XAVFLI:\n"
            for c in red[:5]:
                text += f"• {c.get('FIO')} - {c.get('Telefon')}\n"
            text += "\n"
        if green:
            text += "🟢 ENG YAXSHI:\n"
            for c in green[:5]:
                text += f"• {c.get('FIO')} - {c.get('Telefon')}\n"

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mijozlar yuklanmoqda...")
    try:
        clients = get_all_clients_with_status()
        if not clients:
            await update.message.reply_text("Hozircha faol mijozlar yoq.")
            return

        text = f"FAOL MIJOZLAR ({len(clients)} ta)\n\n"
        for i, rec in enumerate(clients, 1):
            pay_type = rec.get("To'lov Turi", "Oylik")
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            reyting = rec.get("Reyting", "🟡")
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += f"{i}. {reyting} {fio}\n   📞 {phone}\n   {pay_emoji} {pay_type} | 💰 {qoldiq} som\n"

            if i % 20 == 0 and i < len(clients):
                await update.message.reply_text(text)
                text = ""

        if text:
            await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bugungi tolovlar yuklanmoqda...")
    try:
        today_payments = get_today_payments()
        if not today_payments:
            await update.message.reply_text("Bugun tolov qilishi kerak bolgan mijoz yoq.")
            return

        total_expected = sum(safe_float(r.get("To'lov Summasi", 0)) for r in today_payments)
        text = (
            f"BUGUNGI TOLOVLAR ({len(today_payments)} ta)\n"
            f"Kutilayotgan: {format_money(total_expected)} som\n\n"
        )
        for i, rec in enumerate(today_payments, 1):
            pay_type = rec.get("To'lov Turi", "Oylik")
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tolov = format_money(rec.get("To'lov Summasi", 0))
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += (
                f"{i}. {pay_emoji} {fio}\n"
                f"   📞 {phone}\n"
                f"   💳 {tolov} som | Qoldiq: {qoldiq} som\n\n"
            )
        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Statistika hisoblanmoqda...")
    try:
        stats = get_statistics()
        text = (
            f"UMUMIY STATISTIKA\n\n"
            f"📦 Jami savdolar: {stats['total_sales']} ta\n"
            f"🔄 Faol kreditlar: {stats['active']} ta\n"
            f"✅ Yopilgan: {stats['closed']} ta\n\n"
            f"💰 Jami qoldiq: {format_money(stats['total_debt'])} som\n"
            f"💵 Jami sotuv: {format_money(stats['total_revenue'])} som\n\n"
            f"⚠️ Kechikayotganlar: {stats['overdue_count']} ta\n"
            f"🚫 Qora royxat: {stats['blacklist_count']} ta\n"
        )
        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")
