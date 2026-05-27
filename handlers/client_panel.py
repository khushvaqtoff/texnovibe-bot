"""
Mijoz paneli
/mening_malumotlarim — Mijozning o'z ma'lumotlari
/royhattan_otish — Telefon raqamini bog'lash
"""

from telegram import Update
from telegram.ext import ContextTypes
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    get_payment_history, save_client_chat_id
)
from datetime import date


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/royhattan_otish — Mijoz o'z telefon raqamini kiritadi"""
    args = context.args

    if not args:
        await update.message.reply_text(
            "📝 *Royxatdan otish*\n\n"
            "Telefon raqamingizni kiriting:\n"
            "`/royhattan_otish +998901234567`\n\n"
            "Shundan so'ng to'lov eslatmalari va\n"
            "ma'lumotlaringizni ko'ra olasiz!",
            parse_mode="Markdown"
        )
        return

    phone = args[0].strip()
    user = update.effective_user
    chat_id = user.id
    username = user.username or ""

    try:
        # Sheets da mijozni topish
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_sales = sheets["Savdolar"]
        records = ws_sales.get_all_records()

        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        found = False

        for rec in records:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            if rec_phone == phone_clean and rec.get("Holat") == "Faol":
                found = True
                break

        if not found:
            await update.message.reply_text(
                f"❌ `{phone}` raqami bazada topilmadi.\n\n"
                "Telefon raqamingiz to'g'riligini tekshiring\n"
                "yoki do'konimizga murojaat qiling.",
                parse_mode="Markdown"
            )
            return

        # Chat ID ni saqlash
        save_client_chat_id(phone, chat_id, username)

        fio = rec.get("FIO", "")
        await update.message.reply_text(
            f"✅ *Muvaffaqiyatli royxatdan otdingiz!*\n\n"
            f"👤 Ism: *{fio}*\n"
            f"📞 Telefon: `{phone}`\n\n"
            f"Endi siz:\n"
            f"• To'lov eslatmalarini olasiz\n"
            f"• /mening\\_malumotlarim — kreditingizni ko'rasiz\n\n"
            f"🏪 TexnoVibe ga xush kelibsiz!",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )


async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/mening_malumotlarim — Mijoz o'z kredit ma'lumotlarini ko'radi"""
    chat_id = update.effective_user.id

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_clients = sheets["Mijozlar"]
        ws_sales = sheets["Savdolar"]

        # Chat ID bo'yicha telefon topish
        client_records = ws_clients.get_all_records()
        phone = None
        fio = None

        for rec in client_records:
            if str(rec.get("Chat ID", "")).strip() == str(chat_id):
                phone = str(rec.get("Telefon", ""))
                fio = rec.get("FIO", "")
                break

        if not phone:
            await update.message.reply_text(
                "❌ Siz hali royxatdan otmagansiz!\n\n"
                "Royxatdan otish uchun:\n"
                "`/royhattan_otish +998901234567`\n\n"
                "_(O'z telefon raqamingizni kiriting)_",
                parse_mode="Markdown"
            )
            return

        # Faol kreditlarni topish
        sale_records = ws_sales.get_all_records()
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        active_sales = []

        for rec in sale_records:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            if rec_phone == phone_clean:
                active_sales.append(rec)

        if not active_sales:
            await update.message.reply_text(
                f"👤 *{fio}*\n\n"
                "📋 Hozirda faol kreditingiz yoq.\n\n"
                "🏪 TexnoVibe",
                parse_mode="Markdown"
            )
            return

        # Har bir kredit ma'lumotlarini ko'rsatish
        text = f"👤 *{fio}*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in active_sales:
            holat = rec.get("Holat", "")
            holat_emoji = "✅" if holat == "Yopildi" else ("❌" if holat == "Bekor qilindi" else "🔄")

            tovar = rec.get("Tovar", "")
            jami = format_money(rec.get("Jami Summa", 0))
            qoldiq = format_money(rec.get("Qoldiq", 0))
            tolov_turi = rec.get("To'lov Turi", "")
            tolov_summasi = format_money(rec.get("To'lov Summasi", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "")
            bonus = format_money(rec.get("Kredit Bonusu", 0))
            sale_id = rec.get("ID", "")

            text += (
                f"{holat_emoji} *{tovar}*\n"
                f"🆔 {sale_id} | 📅 {rec.get('Sana', '')}\n"
                f"💵 Jami: *{jami} so'm*\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"📅 To'lov turi: {tolov_turi}\n"
                f"💳 Keyingi to'lov: *{tolov_summasi} so'm*\n"
                f"📆 To'lov sanasi: *{keyingi}*\n"
                f"⭐ Reyting: {reyting}\n"
                f"🎁 Bonus: *{bonus} so'm*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
            )

        # To'lov tarixini ham qo'shish
        history = get_payment_history(phone)
        if history:
            total_paid = sum(float(r.get("To'lov Summasi", 0)) for r in history)
            text += (
                f"📋 *TO'LOV TARIXI* ({len(history)} ta)\n"
            )
            for rec in history[-5:]:  # Oxirgi 5 ta
                sana = rec.get("To'lov Sanasi", "")
                summa = format_money(rec.get("To'lov Summasi", 0))
                text += f"• {sana} — *{summa} so'm*\n"

            if len(history) > 5:
                text += f"_(va yana {len(history)-5} ta to'lov)_\n"

            text += f"\n✅ Jami tolangan: *{format_money(total_paid)} so'm*\n"

        text += "\n🏪 TexnoVibe"

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )
