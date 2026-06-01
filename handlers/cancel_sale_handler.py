"""
TexnoVibe — handlers/cancel_sale_handler.py
Savdoni bekor qilish va mijozga avtomatik eslatma/bildirishnoma yuborish moduli.
Dinamik ustunlar filtri bilan to'g'rilangan variant.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets

logger = logging.getLogger(__name__)

# Conversation holatlari
CANCEL_SEARCH, CANCEL_SELECT, CANCEL_CONFIRM = range(3)

def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


async def start_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin bekor qilish bo'limini boshlaganda"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ <b>Savdoni bekor qilish paneli</b>\n\n"
        "Bekor qilinishi kerak bo'lgan mijozning ismi yoki telefon raqamini kiriting:\n"
        "<i>(Masalan: +998901234567 yoki Xushvaqtov)</i>",
        parse_mode="HTML"
    )
    return CANCEL_SEARCH


async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijoz so'rovi bo'yicha qidirish va topilganlarni Inline tugma qilib ko'rsatish"""
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
            mijoz_ismi = str(r.get("Mijoz", r.get("Ismi", r.get("Mijoz Ismi", "")))).strip().lower()
            telefon = str(r.get("Telefon", r.get("Tel", ""))).strip().lower()

            if query_text in mijoz_ismi or query_text in telefon:
                r["_row_index"] = idx
                found_sales.append(r)

        await status_msg.delete()

        if not found_sales:
            await update.message.reply_text("📭 Bunday mijoz bilan bog'liq faol savdo topilmadi.")
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
            "🎯 <b>Bekor qilinadigan savdoni tanlang:</b>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return CANCEL_SELECT

    except Exception as e:
        logger.error(f"Bekor qilish qidiruvida xatolik: {e}")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
        return ConversationHandler.END


async def cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin biror savdoni tanlaganda tasdiqlash so'rovi (Dinamik xabarnoma)"""
    query = update.callback_query
    await query.answer()

    row_idx = int(query.data.split("_")[1])
    context.user_data["selected_sale_index"] = row_idx

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        row_data = ws.row_values(row_idx)
        headers = ws.row_values(1)

        # Bo'sh kataklarni to'ldiramiz, uzunliklar mos kelishi uchun
        while len(row_data) < len(headers):
            row_data.append("")

        sale_dict = dict(zip(headers, row_data))

        # Ma'lumotlarni chiroyli ko'rinishga keltiramiz
        details = "📝 <b>O'chirilayotgan savdo ma'lumotlari:</b>\n\n"
        
        savdo_id = sale_dict.get("ID", sale_dict.get("Savdo ID", "—"))
        mijoz_ismi = sale_dict.get("Mijoz", sale_dict.get("Ismi", "—"))
        tovar_nomi = sale_dict.get("Tovar", "—")
        jami = format_money(sale_dict.get("Jami", sale_dict.get("Narxi", "0")))
        qoldiq = format_money(sale_dict.get("Qoldiq", "0"))

        details += f"🆔 <b>ID:</b> {savdo_id}\n"
        details += f"👤 <b>Mijoz:</b> {mijoz_ismi}\n"
        details += f"📦 <b>Tovar:</b> {tovar_nomi}\n"
        details += f"💰 <b>Jami:</b> {jami} so'm\n"
        if qoldiq != "0":
            details += f"💵 <b>Qoldiq:</b> {qoldiq} so'm\n"

        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, bekor qilinsin", callback_data="cnl_yes"),
                InlineKeyboardButton("❌ Yo'q, qolsin", callback_data="cnl_no")
            ]
        ]
        
        await query.edit_message_text(
            text=f"{details}\n⚠️ <b>Ushbu savdoni bekor qilishni tasdiqlaysizmi?</b>\n"
                 "<i>(Ushbu amalni ortga qaytarib bo'lmaydi va mijozga ogohlantirish boradi!)</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return CANCEL_CONFIRM

    except Exception as e:
        logger.error(f"Savdoni tanlashda xatolik: {e}")
        await query.message.reply_text(f"❌ Ma'lumotni o'qishda xatolik: {str(e)}")
        return ConversationHandler.END


async def cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Savdoni Sheets'dan o'chirish va MIJOZGA ESLATMA yuborish mantiqi"""
    query = update.callback_query
    await query.answer()

    if query.data == "cnl_no":
        await query.edit_message_text("🔄 Savdoni bekor qilish jarayoni bekor qilindi.")
        return ConversationHandler.END

    sale_index = context.user_data.get("selected_sale_index")

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        
        row_data = ws.row_values(sale_index)
        headers = ws.row_values(1)
        
        while len(row_data) < len(headers):
            row_data.append("")
            
        sale_dict = dict(zip(headers, row_data))

        savdo_id = sale_dict.get("ID", sale_dict.get("Savdo ID", ""))
        mijoz_ismi = sale_dict.get("Mijoz", sale_dict.get("Ismi", "Mijoz"))
        tovar_nomi = sale_dict.get("Tovar", "Tovar")
        
        # Jadvalingizdan Telegram ID yoki Chat ID ustunini o'qiymiz
        mijoz_chat_id = sale_dict.get("Chat ID", sale_dict.get("chat_id", sale_dict.get("Telegram ID", sale_dict.get("Mijoz ID", None))))

        # Agar sarlavha orqali topilmasa, qatordagi elementlar ichidan katta raqamli ID ni avtomatik izlaymiz
        if not mijoz_chat_id:
            for val in row_data:
                if str(val).isdigit() and len(str(val)) >= 8 and not str(val).startswith("998"):
                    mijoz_chat_id = int(val)
                    break

        # 1. Google Sheets'dan qatorni butunlay o'chiramiz
        ws.delete_rows(sale_index)
        
        # 2. Adminga chiroyli yakuniy hisobot (Xuddi avvalgidek toza holatda!)
        id_text = f"<b>ID:</b> {savdo_id}\n" if savdo_id else ""
        await query.edit_message_text(
            f"✅ <b>SAVDO BEKOR QILINDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{id_text}"
            f"👤 <b>Mijoz:</b> {mijoz_ismi}\n"
            f"📦 <b>Tovar:</b> {tovar_nomi}\n\n"
            f"📊 Google Sheets muvaffaqiyatli yangilandi! ✅",
            parse_mode="HTML"
        )
        
        # 3. MIJOZGA AVTOMATIK ESLATMA YUBORISH 🚀
        if mijoz_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=int(mijoz_chat_id),
                    text=(
                        f"⚠️ <b>Hurmatli {mijoz_ismi}!</b>\n\n"
                        f"Sizning 📦 <b>{tovar_nomi}</b> uchun rasmiylashtirilgan "
                        f"nasiya savdoingiz shartnoma shartlariga ko'ra yoki "
                        f"kelishuv asosida tizimda <b>BEKOR QILINDI</b>.\n\n"
                        f"ℹ️ Savollar yoki tushunmovchiliklar bo'lsa, ma'muriyatga murojaat qiling."
                    ),
                    parse_mode="HTML"
                )
                logger.info(f"Mijozga ({mijoz_chat_id}) bekor qilish xabari yuborildi.")
            except Exception as bot_err:
                logger.error(f"Mijoz botni block qilgan yoki ID xato: {bot_err}")
                await query.message.reply_text("ℹ *Eslatma:* Mijoz botni block qilgani (yoki start bosmagani) sababli unga xabar yetib bormadi.", parse_mode="HTML")
        else:
            logger.warning("Ushbu savdo qatorida mijozning Telegram Chat ID si topilmadi.")
            await query.message.reply_text("ℹ *Eslatma:* Jadvalda mijozning Telegram Chat ID si topilmadi, shu sababli unga eslatma yuborilmadi.", parse_mode="HTML")

    except Exception as e:
        logger.error(f"Bekor qilishni tasdiqlashda xatolik: {e}")
        await query.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")
        
    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jarayonni to'xtatish"""
    await update.message.reply_text("🔄 Savdoni bekor qilish paneli yopildi.")
    return ConversationHandler.END