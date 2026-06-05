"""
TexnoVibe — scheduler/reminder.py
Avtomatik eslatmalar:
  1. Har kuni ertalab 09:00 — bugungi to'lov kuniga ega BARCHA mijozlarga xabar
  2. Har kuni kechqurun 18:00 — to'lamagan mijozlarga qayta eslatma
  3. Har kuni 10:00 — adminga bugungi to'lovlar xulosasi
"""

import logging
from datetime import datetime, date
import pytz

from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Sizning mavjud sheets funksiyangiz — moslashtiring
from sheets.google_sheets import get_spreadsheet, ensure_worksheets, ws_to_records

logger = logging.getLogger(__name__)

TASHKENT_TZ = pytz.timezone("Asia/Tashkent")

# Google Sheets varaqlari nomlari — o'zingiznikiga moslang
SALES_SHEET   = "Savdolar"    # nasiya yozuvlari
CLIENTS_SHEET = "Mijozlar"    # ro'yxatdan o'tgan mijozlar (telegram_id bilan)


# ─────────────────────────────────────────────────────────
# YORDAMCHI: Bugungi to'lov kuniga ega mijozlarni olish
# ─────────────────────────────────────────────────────────
def get_todays_debtors() -> list[dict]:
    """
    Savdolar varag'idan bugungi to'lov kuniga ega,
    hali to'liq to'lanmagan mijozlarni qaytaradi.

    Kutilayotgan ustunlar (Google Sheets):
      A=Ism | B=Telefon | C=Tovar | D=Jami | E=Oylik | F=To'lov_Kuni
      G=To'langan | H=Holat | I=TelegramID

    To'lov_Kuni — oyning kuni (1-31), masalan: 15
    Holat — "Faol" yoki "Yopilgan"
    """
    try:
        sh     = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        rows   = ws_to_records(sheets[SALES_SHEET])
    except Exception as e:
        logger.error(f"Sheets dan ma'lumot olishda xato: {e}")
        return []

    bugun_kun = date.today().day
    natija = []

    for r in rows:
        holat = str(r.get("Holat", "")).strip()
        if holat.lower() != "faol":
            continue

        try:
            tolov_kuni = int(r.get("To'lov Kuni", r.get("To'lov_Kuni", 0)))
        except (ValueError, TypeError):
            continue

        if tolov_kuni != bugun_kun:
            continue

        natija.append({
            "ism":         r.get("FIO", r.get("Ism", "Mijoz")),
            "telefon":     r.get("Telefon", ""),
            "tovar":       r.get("Tovar", ""),
            "oylik":       r.get("To'lov Summasi", r.get("Oylik To'lov", r.get("Oylik", 0))),
            "qoldiq":      r.get("Qoldiq", 0),
            "tolangan":    r.get("To'langan Summa", r.get("To'langan", 0)),
            "jami":        r.get("Jami Summa", r.get("Jami", 0)),
            "telegram_id": r.get("Chat ID", r.get("TelegramID", "")),
        })

    return natija


def get_admin_chat_id() -> int:
    """Admin chat ID ni environment dan oladi"""
    import os
    return int(os.getenv("ADMIN_CHAT_ID", "0"))


# ─────────────────────────────────────────────────────────
# JOB 1 — Ertalab 09:00: Mijozlarga eslatma
# ─────────────────────────────────────────────────────────
async def job_morning_reminders(context):
    """
    Bugungi to'lov kuniga ega va Telegram ID si bor
    mijozlarga ertalab xabar yuboradi.
    """
    mijozlar = get_todays_debtors()
    if not mijozlar:
        logger.info("Bugun to'lov kuni bo'lgan mijoz yo'q.")
        return

    yuborildi = 0
    for m in mijozlar:
        tg_id = str(m.get("telegram_id", "")).strip()
        if not tg_id or not tg_id.isdigit():
            continue  # Telegram ID yo'q — o'tkazib yuborish

        try:
            oylik = int(m["oylik"])
            oylik_fmt = f"{oylik:,}".replace(",", " ")

            qoldiq_fmt = f"{int(float(m.get('qoldiq', 0))):,}".replace(",", " ")
            matn = (
                f"⏰ *Assalomu alaykum, {m['ism']}!*\n\n"
                f"Bugun sizning nasiya to'lov kuningiz.\n\n"
                f"📦 Tovar: `{m['tovar']}`\n"
                f"💳 Oylik to'lov: `{oylik_fmt} so'm`\n"
                f"💰 Umumiy qoldiq: `{qoldiq_fmt} so'm`\n\n"
                f"Iltimos, bugun to'lovni amalga oshiring. 🙏\n"
                f"📞 Savollar uchun: +998 XX XXX XX XX"
            )

            await context.bot.send_message(
                chat_id=int(tg_id),
                text=matn,
                parse_mode="Markdown",
            )
            yuborildi += 1
            logger.info(f"Eslatma yuborildi: {m['ism']} ({tg_id})")

        except Exception as e:
            logger.warning(f"Eslatma yuborishda xato ({tg_id}): {e}")

    logger.info(f"Ertalabki eslatma: {yuborildi} ta mijozga yuborildi.")


# ─────────────────────────────────────────────────────────
# JOB 2 — Kechqurun 18:00: To'lamagan mijozlarga qayta eslatma
# ─────────────────────────────────────────────────────────
async def job_evening_reminders(context):
    """
    Bugun to'lov kuni bo'lib, lekin hali to'lamagan
    mijozlarga kechqurun qayta eslatma yuboradi.
    """
    mijozlar = get_todays_debtors()
    if not mijozlar:
        return

    for m in mijozlar:
        tg_id = str(m.get("telegram_id", "")).strip()
        if not tg_id or not tg_id.isdigit():
            continue

        try:
            oylik = int(m["oylik"])
            oylik_fmt = f"{oylik:,}".replace(",", " ")

            matn = (
                f"🔔 *{m['ism']}, eslatma!*\n\n"
                f"Bugun to'lov kuni edi, lekin to'lov qayd etilmagan.\n\n"
                f"💰 To'lov miqdori: `{oylik_fmt} so'm`\n\n"
                f"Agar to'lov qilgan bo'lsangiz, savdogarimizga xabar bering. ✅"
            )

            await context.bot.send_message(
                chat_id=int(tg_id),
                text=matn,
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.warning(f"Kechki eslatmada xato ({tg_id}): {e}")


# ─────────────────────────────────────────────────────────
# JOB 3 — 10:00: Adminga kunlik xulosa
# ─────────────────────────────────────────────────────────
async def job_admin_summary(context):
    """
    Har kuni 10:00 da adminga bugungi to'lovlar
    haqida xulosa yuboradi.
    """
    admin_id = get_admin_chat_id()
    if not admin_id:
        return

    mijozlar = get_todays_debtors()

    if not mijozlar:
        await context.bot.send_message(
            chat_id=admin_id,
            text="📊 *Bugungi to'lovlar*\n\nBugun to'lov kuni bo'lgan mijoz yo'q.",
            parse_mode="Markdown",
        )
        return

    jami_summa = sum(int(m.get("oylik", 0)) for m in mijozlar)
    jami_fmt = f"{jami_summa:,}".replace(",", " ")

    qatorlar = []
    for i, m in enumerate(mijozlar, 1):
        oylik_fmt  = f"{int(m['oylik']):,}".replace(",", " ")
        qoldiq_fmt = f"{int(float(m.get('qoldiq', 0))):,}".replace(",", " ")
        tg         = "✅" if str(m.get("telegram_id", "")).strip().isdigit() else "❌"
        qatorlar.append(f"{i}. {m['ism']} — 💳 {oylik_fmt} so'm | 💰 {qoldiq_fmt} so'm {tg}")

    mijoz_list = "\n".join(qatorlar)

    bugun = date.today().strftime("%d.%m.%Y")
    matn = (
        f"📊 *Bugungi to'lovlar — {bugun}*\n\n"
        f"👥 Jami: {len(mijozlar)} ta mijoz\n"
        f"💰 Kutilayotgan: `{jami_fmt} so'm`\n\n"
        f"{mijoz_list}\n\n"
        f"✅ = Telegram bor (eslatma yuborildi)\n"
        f"❌ = Telegram yo'q (qo'l bilan xabar berish kerak)"
    )

    await context.bot.send_message(
        chat_id=admin_id,
        text=matn,
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────
# SETUP — bot.py dan chaqiriladi
# ─────────────────────────────────────────────────────────
def setup_scheduler(app: Application):
    """
    Schedulerni ishga tushiradi.
    bot.py da: setup_scheduler(app)  — o'zgarishsiz qoladi.
    """
    scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)

    # Ertalab 09:00 — mijozlarga eslatma
    scheduler.add_job(
        job_morning_reminders,
        trigger="cron",
        hour=9,
        minute=0,
        kwargs={"context": _make_context(app)},
        id="morning_reminders",
        replace_existing=True,
    )

    # Kechqurun 18:00 — qayta eslatma
    scheduler.add_job(
        job_evening_reminders,
        trigger="cron",
        hour=18,
        minute=0,
        kwargs={"context": _make_context(app)},
        id="evening_reminders",
        replace_existing=True,
    )

    # 10:00 — adminga xulosa
    scheduler.add_job(
        job_admin_summary,
        trigger="cron",
        hour=10,
        minute=0,
        kwargs={"context": _make_context(app)},
        id="admin_summary",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("✅ Scheduler ishga tushdi (09:00 eslatma | 10:00 admin | 18:00 qayta eslatma)")


class _BotContext:
    """Oddiy context o'rniga faqat bot ni o'z ichiga oladi"""
    def __init__(self, bot):
        self.bot = bot


def _make_context(app: Application) -> _BotContext:
    return _BotContext(app.bot)
