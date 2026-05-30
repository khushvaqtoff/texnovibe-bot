"""
Hisobot va Ombor nazorati handleri
"""

from telegram import Update
from telegram.ext import ContextTypes
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date, datetime


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def cmd_daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bugungi hisobot — savdo va tushgan tolovlar"""
    await update.message.reply_text("Bugungi hisobot yuklanmoqda...")

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_sales = sheets["Savdolar"]
        ws_payments = sheets["Tolovlar"]

        today_str = date.today().strftime("%d.%m.%Y")

        all_sales = ws_sales.get_all_records()
        all_payments = ws_payments.get_all_records()

        # Bugungi yangi savdolar
        today_sales = [r for r in all_sales if r.get("Sana") == today_str]

        # Bugungi tushgan tolovlar
        today_payments = [r for r in all_payments if r.get("To'lov Sanasi") == today_str]

        # Hisoblash
        today_sales_sum = sum(float(r.get("Jami Summa", 0)) for r in today_sales)
        today_sales_avans = sum(float(r.get("Boshlang'ich To'lov", 0)) for r in today_sales)
        today_payments_sum = sum(float(r.get("To'lov Summasi", 0)) for r in today_payments)
        total_income = today_sales_avans + today_payments_sum

        text = (
            f"BUGUNGI HISOBOT\n"
            f"Sana: {today_str}\n"
            f"{'='*30}\n\n"
            f"YANGI SAVDOLAR ({len(today_sales)} ta)\n"
            f"{'─'*25}\n"
        )

        if today_sales:
            for rec in today_sales:
                fio = rec.get("FIO", "")
                tovar = rec.get("Tovar", "")
                jami = format_money(rec.get("Jami Summa", 0))
                avans = format_money(rec.get("Boshlang'ich To'lov", 0))
                pay_type = rec.get("To'lov Turi", "")
                text += (
                    f"+ {fio}\n"
                    f"  {tovar}\n"
                    f"  Jami: {jami} som | Avans: {avans} som\n"
                    f"  {pay_type}\n\n"
                )
        else:
            text += "Bugun yangi savdo yoq\n\n"

        text += (
            f"TUSHGAN TOLOVLAR ({len(today_payments)} ta)\n"
            f"{'─'*25}\n"
        )

        if today_payments:
            for rec in today_payments:
                fio = rec.get("FIO", "")
                summa = format_money(rec.get("To'lov Summasi", 0))
                qoldiq = format_money(rec.get("Qoldiq", 0))
                text += (
                    f"+ {fio}\n"
                    f"  Tolandi: {summa} som\n"
                    f"  Qoldiq: {qoldiq} som\n\n"
                )
        else:
            text += "Bugun tolov tushgani yoq\n\n"

        text += (
            f"{'='*30}\n"
            f"BUGUNGI NATIJA\n"
            f"Yangi savdolar: {format_money(today_sales_sum)} som\n"
            f"Avans tushdi: {format_money(today_sales_avans)} som\n"
            f"Tolovlar tushdi: {format_money(today_payments_sum)} som\n"
            f"Jami kassa: {format_money(total_income)} som\n"
        )

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")


async def cmd_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ombor nazorati — qoldiq, sotilganlar, bugungi tolovlar"""
    await update.message.reply_text("Ombor ma'lumotlari yuklanmoqda...")

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_sales = sheets["Savdolar"]
        ws_payments = sheets["Tolovlar"]

        today_str = date.today().strftime("%d.%m.%Y")
        all_sales = ws_sales.get_all_records()
        all_payments = ws_payments.get_all_records()

        # Holat bo'yicha guruhlash
        faol = [r for r in all_sales if r.get("Holat") == "Faol"]
        yopilgan = [r for r in all_sales if r.get("Holat") == "Yopildi"]
        bekor = [r for r in all_sales if r.get("Holat") == "Bekor qilindi"]

        # Faol va yopilgan savdolar (bekor qilinganlar HISOBGA OLINMAYDI)
        hisob_savdolar = [r for r in all_sales if r.get("Holat") in ("Faol", "Yopildi")]

        # Moliyaviy hisob — bekor qilinganlar chiqariladi
        jami_nasiya = sum(float(r.get("Jami Summa", 0)) for r in hisob_savdolar if r.get("Jami Summa"))
        jami_qoldiq = sum(float(r.get("Qoldiq", 0)) for r in faol)
        jami_tolangan = sum(float(r.get("To'langan Summa", 0)) for r in hisob_savdolar if r.get("To'langan Summa"))
        jami_avans = sum(float(r.get("Boshlang'ich To'lov", 0)) for r in hisob_savdolar if r.get("Boshlang'ich To'lov"))

        # Bugungi tolovlar
        bugungi_tolovlar = [r for r in all_payments if r.get("To'lov Sanasi") == today_str]
        bugungi_sum = sum(float(r.get("To'lov Summasi", 0)) for r in bugungi_tolovlar)

        # Tovar bo'yicha statistika (bekor qilinganlar chiqariladi)
        tovar_stats = {}
        for rec in all_sales:
            tovar = rec.get("Tovar", "Nomalum")
            holat = rec.get("Holat", "")
            if holat == "Bekor qilindi":
                continue  # Bekor qilinganlarni o'tkazib yuborish
            if tovar not in tovar_stats:
                tovar_stats[tovar] = {"faol": 0, "yopilgan": 0, "jami": 0}
            tovar_stats[tovar]["jami"] += 1
            if holat == "Faol":
                tovar_stats[tovar]["faol"] += 1
            elif holat == "Yopildi":
                tovar_stats[tovar]["yopilgan"] += 1

        text = (
            f"OMBOR NAZORATI\n"
            f"Sana: {today_str}\n"
            f"{'='*30}\n\n"
            f"UMUMIY HOLAT\n"
            f"{'─'*25}\n"
            f"Jami sotilgan: {len(all_sales)} ta\n"
            f"Faol nasiya: {len(faol)} ta\n"
            f"Yopilgan: {len(yopilgan)} ta\n"
            f"Bekor qilingan: {len(bekor)} ta\n\n"
            f"MOLIYAVIY HOLAT\n"
            f"{'─'*25}\n"
            f"Jami nasiya: {format_money(jami_nasiya)} som\n"
            f"Jami avans: {format_money(jami_avans)} som\n"
            f"Jami tolangan: {format_money(jami_tolangan)} som\n"
            f"Qolgan qarz: {format_money(jami_qoldiq)} som\n\n"
            f"BUGUNGI TOLOVLAR ({len(bugungi_tolovlar)} ta)\n"
            f"{'─'*25}\n"
            f"Bugun tushdi: {format_money(bugungi_sum)} som\n"
        )

        if bugungi_tolovlar:
            for rec in bugungi_tolovlar:
                fio = rec.get("FIO", "")
                summa = format_money(rec.get("To'lov Summasi", 0))
                text += f"  + {fio}: {summa} som\n"

        text += f"\nTOVAR BO'YICHA\n{'─'*25}\n"
        for tovar, stats in sorted(tovar_stats.items(), key=lambda x: x[1]["jami"], reverse=True)[:10]:
            text += (
                f"{tovar}\n"
                f"  Jami: {stats['jami']} | Faol: {stats['faol']} | Yopilgan: {stats['yopilgan']}\n"
            )

        # Uzun bolsa bòlib yuborish
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")
