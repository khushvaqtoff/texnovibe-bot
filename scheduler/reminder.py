"""
Avtomatik eslatmalar tizimi (Scheduler)
"""

import os
import logging
from datetime import datetime, date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from sheets.google_sheets import (
    get_today_payments, get_overdue_payments,
    get_todays_birthdays, get_statistics, get_client_chat_id
)

logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", "0"))


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


async def send_today_reminders(app: Application):
    logger.info("📅 Bugungi eslatmalar yuborilmoqda...")
    try:
        today_list = get_today_payments()
        today_str = date.today().strftime("%d.%m.%Y")

        if not today_list:
            await app.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"📅 {today_str} — Bugun tolov qilishi kerak bolgan mijoz yoq.",
                parse_mode="Markdown"
            )
            return

        total = sum(safe_float(r.get("To'lov Summasi", 0)) for r in today_list)
        total_str = format_money(total)
        count = len(today_list)

        admin_text = (
            f"☀️ *BUGUNGI TOLOVLAR ESLATMASI*\n"
            f"📅 {today_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Mijozlar soni: *{count} ta*\n"
            f"💵 Kutilayotgan: *{total_str} so'm*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        for rec in today_list:
            pay_type = rec.get("To'lov Turi", "Oylik")
            pay_emoji = "📆" if pay_type == "Haftalik" else "📅"
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            tolov = format_money(rec.get("To'lov Summasi", 0))
            qoldiq = format_money(rec.get("Qoldiq", 0))
            admin_text += (
                f"{pay_emoji} *{fio}*\n"
                f"   📞 `{phone}`\n"
                f"   💳 *{tolov} so'm*\n"
                f"   💰 Qoldiq: {qoldiq} so'm\n\n"
            )

        await app.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            parse_mode="Markdown"
        )

        for rec in today_list:
            phone = str(rec.get("Telefon", ""))
            chat_id = get_client_chat_id(phone)
            if not chat_id or not chat_id.strip():
                continue
            try:
                pay_type = rec.get("To'lov Turi", "Oylik")
                period_word = "haftalik" if pay_type == "Haftalik" else "oylik"
                fio = rec.get("FIO", "")
                tolov = format_money(rec.get("To'lov Summasi", 0))
                qoldiq = format_money(rec.get("Qoldiq", 0))

                client_msg = (
                    f"🔔 *TexnoVibe — Tolov Eslatmasi*\n\n"
                    f"Assalomu alaykum, *{fio}!*\n\n"
                    f"Bugun ({today_str}) sizning {period_word} tolov kuningiz.\n\n"
                    f"💳 Tolov summasi: *{tolov} so'm*\n"
                    f"💰 Umumiy qoldigingiz: *{qoldiq} so'm*\n\n"
                    f"🏪 TexnoVibe — Ishonchli dokoningiz!"
                )
                await app.bot.send_message(
                    chat_id=int(chat_id),
                    text=client_msg,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Mijozga eslatma yuborib bolmadi {phone}: {e}")

        logger.info(f"✅ {count} ta mijozga eslatma yuborildi")

    except Exception as e:
        logger.error(f"Eslatma xatosi: {e}")
        await app.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"❌ Eslatma yuborishda xato: `{str(e)}`",
            parse_mode="Markdown"
        )


async def send_overdue_warning(app: Application):
    try:
        overdue = get_overdue_payments(1)
        if not overdue:
            return

        text = "⚠️ *KECHIKAYOTGANLAR OGOHLANTIRISHII*\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in overdue:
            days = rec.get("Kechikish Kunlari", 0)
            fio = rec.get("FIO", "")
            phone = rec.get("Telefon", "")
            qoldiq = format_money(rec.get("Qoldiq", 0))
            text += (
                f"🔴 *{fio}*\n"
                f"📞 `{phone}`\n"
                f"⏰ {days} kun kechikmoqda\n"
                f"💰 Qoldiq: {qoldiq} so'm\n\n"
            )

        await app.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )

        for rec in overdue:
            phone = str(rec.get("Telefon", ""))
            chat_id = get_client_chat_id(phone)
            days = rec.get("Kechikish Kunlari", 0)
            if not chat_id or not chat_id.strip():
                continue
            try:
                fio = rec.get("FIO", "")
                qoldiq = format_money(rec.get("Qoldiq", 0))
                late_msg = (
                    f"⚠️ *TexnoVibe — Muhim Eslatma*\n\n"
                    f"Hurmatli *{fio}!*\n\n"
                    f"Sizning tolov muddatingiz *{days} kun* oldin otgan.\n\n"
                    f"💰 Tolanmagan qoldiq: *{qoldiq} so'm*\n\n"
                    f"Iltimos, imkon qadar tezroq tolovni amalga oshiring.\n"
                    f"🏪 TexnoVibe"
                )
                await app.bot.send_message(
                    chat_id=int(chat_id),
                    text=late_msg,
                    parse_mode="Markdown"
                )
            except:
                pass

    except Exception as e:
        logger.error(f"Overdue warning xatosi: {e}")


async def send_blacklist_report(app: Application):
    try:
        blacklist = get_overdue_payments(3)
        if not blacklist:
            return

        today_str = date.today().strftime("%d.%m.%Y")
        count = len(blacklist)
        text = (
            f"🚫 *QORA ROYXAT HISOBOTI*\n"
            f"_{today_str}_\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Quyidagi mijozlar 3+ kun kechiktirmoqda:\n\n"
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
                f"⏰ *{days} kun* kechikmoqda\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"─────────────────\n"
            )

        await app.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Blacklist report xatosi: {e}")


async def send_birthday_greetings(app: Application):
    try:
        birthdays = get_todays_birthdays()
        for rec in birthdays:
            phone = str(rec.get("Telefon", ""))
            fio = rec.get("FIO", "")
            chat_id = get_client_chat_id(phone)

            await app.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"🎂 *TUGILGAN KUN!*\n"
                    f"Bugun {fio} ning tugilgan kuni!\n"
                    f"📞 `{phone}`"
                ),
                parse_mode="Markdown"
            )

            if chat_id and chat_id.strip():
                try:
                    bday_msg = (
                        f"🎉 *Tugilgan kuningiz bilan!*\n\n"
                        f"Hurmatli *{fio}!*\n\n"
                        f"TexnoVibe jamoasi sizni tugilgan kuningiz bilan "
                        f"samimiy tabriklab, umr yolingizga omad tilaymiz! 🎊\n\n"
                        f"🎁 *Maxsus sovga:* Keyingi xaridingizda *5% chegirma!*\n\n"
                        f"🏪 TexnoVibe"
                    )
                    await app.bot.send_message(
                        chat_id=int(chat_id),
                        text=bday_msg,
                        parse_mode="Markdown"
                    )
                except:
                    pass

    except Exception as e:
        logger.error(f"Birthday greeting xatosi: {e}")


async def send_weekly_report(app: Application):
    try:
        if date.today().weekday() != 5:
            return

        stats = get_statistics()
        today_str = date.today().strftime("%d.%m.%Y")
        total_debt = format_money(stats["total_debt"])

        text = (
            f"📊 *HAFTALIK HISOBOT*\n"
            f"_{today_str}_\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Jami savdolar: *{stats['total_sales']} ta*\n"
            f"🔄 Faol kreditlar: *{stats['active']} ta*\n"
            f"✅ Yopilgan: *{stats['closed']} ta*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Jami qoldiq: *{total_debt} so'm*\n"
            f"⚠️ Kechikayotganlar: *{stats['overdue_count']} ta*\n"
            f"🚫 Qora royxat: *{stats['blacklist_count']} ta*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Keyingi hafta uchun muvaffaqiyat! 💪"
        )

        await app.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Haftalik hisobot xatosi: {e}")


def setup_scheduler(app: Application):
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

    scheduler.add_job(send_today_reminders, "cron", hour=REMINDER_HOUR, minute=REMINDER_MINUTE, args=[app], id="daily_reminder")
    scheduler.add_job(send_birthday_greetings, "cron", hour=9, minute=30, args=[app], id="birthday_greetings")
    scheduler.add_job(send_overdue_warning, "cron", hour=10, minute=0, args=[app], id="overdue_warning")
    scheduler.add_job(send_blacklist_report, "cron", hour=18, minute=0, args=[app], id="blacklist_report")
    scheduler.add_job(send_weekly_report, "cron", hour=20, minute=0, args=[app], id="weekly_report")

    scheduler.start()
    logger.info("✅ Scheduler ishga tushdi!")
