"""
TexnoVibe — handlers/cancel_sale_handler.py
Savdoni bekor qilish paneli.
Faqat FAOL savdolarni qidiradi va mijozga (C-ustundagi Chat ID orqali) eslatma yuboradi.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date
import html

logger = logging.getLogger(__name__)

# Konstantalar (Sizning jadvalingiz parametrlari)
STATUS_COLUMN = 14       # N ustuni - Holat
CANCEL_DATE_COLUMN = 17  # Q ustuni - Bekor qilingan sana

# States (bot.py faylingizdagi qiymatga mos kelishi kerak)
CANCEL_SEARCH, CANCEL_SELECT, CANCEL_CONFIRM = range(3)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


def escape_html(text) -> str:
    return html.escape(str(text)) if text else ""


async def start_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin bekor qilish bo'limini boshlaganda"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ <b>Savdoni bekor qilish paneli</b>\n\n"
        "Mijozning ismi yoki telefon raqamini kiriting:\n"
        "<i>(Faqat hozirgi faol savdolar qidiriladi)</i>",
        parse_mode="HTML"
    )
    return CANCEL_SEARCH


async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijoz so'rovi bo'yicha qidirish (FAQAT FAOL SAVDOLARNI)"""
    query_text = update.message.text.strip().lower()
    status_msg = await update.message.reply_text("⏳ Savdolar ro'yxati tekshirilmoqda...")

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws = sheets["Savdolar"]
        records = ws.get_all_records()

        found_sales = []
        # get_all_records sarlavhani hisobga olib, 1-ma'lumot qatorini jadvalda 2-qator deb hisoblaydi.
        for idx, r in enumerate(records, start=2):
            # 1. Avvalo savdoning holatini tekshiramiz
            holat = str(r.get("Holat", r.get("Status", ""))).strip().lower()
            if "bekor" in holat or holat == "yakunlangan":
                continue  # Oldin bekor qilingan bo'lsa, ro'yxatga qo'shmaymiz!

            # 2. Ism yoki telefon bo'yicha qidiramiz
            mijoz_ismi = str(r.get("Mijoz", r.get("Ismi", r.get("Mijoz Ismi", "")))).strip().lower()
            telefon = str(r.get("Telefon", r.get("Tel", ""))).strip().lower()

            if query_text in mijoz_ismi or query_text in telefon:
                r["_row_index"] = idx
                found_sales.append(r)

        await status_msg.delete()

        if not found_sales:
            await update.message.reply_text("📭 Bunday ma'lumotga ega faol nasiya savdosi topilmadi.")
            return ConversationHandler.END

        # Inline tugmalarni shakllantiramiz
        keyboard = []
        for s in found_sales[:10]:
            nomi = s.get("Mijoz", s.get("Ismi", "Noma'lum"))
            tovar = s.get("Tovar", "Tovar")
            savdo_id = s.get("ID", s.get("Savdo ID", ""))
            row_idx = s["_row_index"]
            
            id_str = f" [{savdo_id}]" if savdo_id else ""
            btn_text = f"👤 {nomi} | 📦 {tovar}{id_str}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"cnlsel_{row_idx}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🎯 <b>Bekor qilinadigan faol savdoni tanlang:</b>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return CANCEL_SELECT

    except Exception as e:
        logger.error(f"Bekor qilish qidiruvida xatolik: {e}")
        await status_msg.edit_text(f"❌ Xatolik: {escape_html(str(e))}", parse_mode="HTML")
        return ConversationHandler.END


async def cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin savdoni tanlaganda tasdiqlash oynasi"""
    query = update.callback_query
    await query.answer()

    row_idx = int(query.data.split("_")[1])
    context.user_data["selected_sale_index"] = row_idx

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        row_data = ws.row_values(row_idx)
        headers = ws.row_values(1)

        while len(row_data) < len(headers):
            row_data.append("")

        sale_dict = dict(zip(headers, row_data))
        context.user_data["sale_data_dict"] = sale_dict  # Ma'lumotlarni keyingi bosqich uchun saqlaymiz

        # Ma'lumotlar kartasini tuzamiz
        savdo_id = sale_dict.get("ID", sale_dict.get("Savdo ID", "—"))
        mijoz_ismi = sale_dict.get("Mijoz", sale_dict.get("Ismi", "—"))
        tovar_nomi = sale_dict.get("Tovar", "—")
        jami = format_money(sale_dict.get("Jami", sale_dict.get("Narxi", "0")))

        details = (
            f"🆔 <b>ID:</b> {escape_html(savdo_id)}\n"
            f"👤 <b>Mijoz:</b> {escape_html(mijoz_ismi)}\n"
            f"📦 <b>Tovar:</b> {escape_html(tovar_nomi)}\n"
            f"💰 <b>Narxi:</b> {jami} so'm\n"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, bekor qilinsin", callback_data="cnl_yes"),
                InlineKeyboardButton("❌ Yo'q, qolsin", callback_data="cnl_no")
            ]
        ]
        
        await query.edit_message_text(
            text=f"📝 <b>O'chirilayotgan savdo ma'lumotlari:</b>\n\n{details}\n"
                 f"⚠️ <b>Ushbu savdoni bekor qilishni tasdiqlaysizmi?</b>\n"
                 f"<i>(Holat 'Bekor qilindi'ga o'tadi va mijozga bildirishnoma ketadi)</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return CANCEL_CONFIRM

    except Exception as e:
        logger.error(f"Savdoni tanlashda xatolik: {e}")
        await query.message.reply_text(f"❌ Ma'lumot o'qishda xatolik yuz berdi.")
        return ConversationHandler.END


async def cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tasdiqlash bosqichi: Holatni yangilash + Mijozga xabar yuborish"""
    query = update.callback_query
    await query.answer()

    if query.data == "cnl_no":
        await query.edit_message_text("🔄 Savdoni bekor qilish jarayoni to'xtatildi.")
        return ConversationHandler.END

    sale_index = context.user_data.get("selected_sale_index")
    sale_dict = context.user_data.get("sale_data_dict", {})

    await query.edit_message_text("⏳ Google Sheets yangilanmoqda va mijozga xabar yuborilmoqda...")

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        
        today = date.today().strftime("%d.%m.%Y")
        
        # 1. Google Sheets ustunlarini yangilaymiz (O'chirmaymiz, faqat holatni o'zgartiramiz)
        ws.update_cell(sale_index, STATUS_COLUMN, "Bekor qilindi")
        ws.update_cell(sale_index, CANCEL_DATE_COLUMN, f"Bekor qilindi: {today}")

        # Dizaynni qizil qilish (Sizning original kodingiz mantiqi)
        try:
            row_range = f"A{sale_index}:U{sale_index}"
            ws.format(row_range, {
                "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8},
                "textFormat": {"strikethrough": True}
            })
        except Exception:
            pass

        savdo_id = sale_dict.get("ID", sale_dict.get("Savdo ID", ""))
        mijoz_ismi = sale_dict.get("Mijoz", sale_dict.get("Ismi", "Mijoz"))
        tovar_nomi = sale_dict.get("Tovar", "Tovar")
        
        # 2. MIJOZ TELEGRAM CHAT ID SINI ANIQLASH (C-ustun yoki lug'atdan)
        mijoz_chat_id = sale_dict.get("Chat ID", sale_dict.get("chat_id", sale_dict.get("Telegram ID", None)))
        
        # Agar lug'at kalitidan topilmasa, C ustunidan (3-qiymat) aniq olamiz
        if not mijoz_chat_id:
            row_values = ws.row_values(sale_index)
            if len(row_values) >= 3:
                potential_id = str(row_values[2]).strip()  # C ustuni - indeks bo'yicha 2
                if potential_id.isdigit() and len(potential_id) >= 7:
                    mijoz_chat_id = int(potential_id)

        # Adminga chiroyli yakuniy hisobot
        id_text = f"<b>ID:</b> {escape_html(savdo_id)}\n" if savdo_id else ""
        await query.edit_message_text(
            f"✅ <b>SAVDO BEKOR QILINDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{id_text}"
            f"👤 <b>Mijoz:</b> {escape_html(mijoz_ismi)}\n"
            f"📦 <b>Tovar:</b> {escape_html(tovar_nomi)}\n\n"
            f"📊 Google Sheets statusi yangilandi va qizil rangga o'tkazildi! ✅",
            parse_mode="HTML"
        )
        
        # 3. MIJOZNING SHAXSIY TELEGRAMIGA ESLATMA YUBORISH 🚀
        if mijoz_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=int(mijoz_chat_id),
                    text=(
                        f"⚠️ <b>Hurmatli {escape_html(mijoz_ismi)}!</b>\n\n"
                        f"Sizning 📦 <b>{escape_html(tovar_nomi)}</b> uchun rasmiylashtirilgan "
                        f"nasiya savdoingiz tomonlar kelishuvi yoki shartnoma shartlariga ko'ra "
                        f"tizimda <b>BEKOR QILINDI</b>.\n\n"
                        f"ℹ️ Savollar bo'lsa, ma'muriyatga murojaat qilishingiz mumkin."
                    ),
                    parse_mode="HTML"
                )
                logger.info(f"Mijozga ({mijoz_chat_id}) bekor qilish eslatmasi yuborildi.")
            except Exception as bot_err:
                logger.error(f"Mijozga yuborishda xatolik: {bot_err}")
                await query.message.reply_text("ℹ️ <i>Mijoz botni block qilgan bo'lishi mumkin, eslatma yetib bormadi.</i>", parse_mode="HTML")
        else:
            await query.message.reply_text("ℹ️ <i>Jadvalning 'Chat ID' ustunida mijozning Telegram ID raqami topilmadi, eslatma yuborilmadi.</i>", parse_mode="HTML")

    except Exception as e:
        logger.error(f"Tasdiqlashda xatolik: {e}")
        await query.message.reply_text(f"❌ Xatolik yuz berdi: {escape_html(str(e))}", parse_mode="HTML")
        
    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Savdoni bekor qilish paneli yopildi.")
    return ConversationHandler.END