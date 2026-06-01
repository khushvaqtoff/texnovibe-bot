"""
TexnoVibe — handlers/cancel_sale_handler.py
Savdoni bekor qilish paneli.
Ustun nomlariga bog'lanmasdan, indekslar orqali aniq ishlaydigan variant.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date
import html

logger = logging.getLogger(__name__)

# Boshqaruv ustunlari indekslari (Google Sheets'da 1 dan boshlanadi)
STATUS_COLUMN = 14       # N ustuni - Holat
CANCEL_DATE_COLUMN = 17  # Q ustuni - Bekor qilingan sana

# States
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
        "<i>(Faqat faol savdolar qidiriladi)</i>",
        parse_mode="HTML"
    )
    return CANCEL_SEARCH


async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijoz so'rovi bo'yicha qidirish"""
    query_text = update.message.text.strip().lower()
    status_msg = await update.message.reply_text("⏳ Savdolar ro'yxati tekshirilmoqda...")

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        
        # Barcha qatorlarni massiv (list) ko'rinishida olamiz
        all_rows = ws.get_all_values()
        if not all_rows:
            await status_msg.edit_text("📭 Jadval bo'sh.")
            return ConversationHandler.END

        found_sales = []
        
        # 1-qator sarlavhalar bo'lgani uchun 2-qatordan (indeks 1) boshlaymiz
        for idx, row in enumerate(all_rows[1:], start=2):
            # Agar qator bo'sh bo'lsa yoki kerakli ustunlar yetishmasa o'tkazib yuboramiz
            if len(row) < 5:
                continue

            # N-ustun (index 13) - Holat
            holat = str(row[13]).strip().lower() if len(row) >= 14 else ""
            if "bekor" in holat or holat == "yakunlangan":
                continue

            # Qidirilayotgan matnni butun qator ichidan qidiramiz (Ism yoki Tel)
            row_dump = " ".join([str(cell).lower() for cell in row])
            if query_text in row_dump:
                found_sales.append({
                    "row_index": idx,
                    "savdo_id": row[0],    # A ustuni
                    "mijoz_ismi": row[1],  # B ustuni
                    "chat_id": row[2],     # C ustuni
                    "tovar": row[4]        # E ustuni
                })

        await status_msg.delete()

        if not found_sales:
            await update.message.reply_text("📭 Bunday ma'lumotga ega faol nasiya savdosi topilmadi.")
            return ConversationHandler.END

        # Inline tugmalarni shakllantiramiz
        keyboard = []
        for s in found_sales[:10]:
            nomi = s["mijoz_ismi"] if s["mijoz_ismi"] else "Noma'lum"
            tovar = s["tovar"] if s["tovar"] else "Tovar"
            savdo_id = s["savdo_id"]
            
            id_str = f" [{savdo_id}]" if savdo_id else ""
            btn_text = f"👤 {nomi} | 📦 {tovar}{id_str}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"cnlsel_{s['row_index']}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🎯 <b>Bekor qilinadigan faol savdoni tanlang:</b>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return CANCEL_SELECT

    except Exception as e:
        logger.error(f"Bekor qilish qidiruvida xatolik: {e}")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {escape_html(str(e))}", parse_mode="HTML")
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

        # Ma'lumotlarni indeks bo'yicha aniq yuklaymiz
        savdo_id = row_data[0] if len(row_data) >= 1 else "—"
        mijoz_ismi = row_data[1] if len(row_data) >= 2 else "—"
        chat_id = row_data[2] if len(row_data) >= 3 else ""
        tovar_nomi = row_data[4] if len(row_data) >= 5 else "—"
        jami = format_money(row_data[5]) if len(row_data) >= 6 else "0"

        # Keyingi bosqich uchun ma'lumotlarni user_data'ga saqlaymiz
        context.user_data["sale_info"] = {
            "savdo_id": savdo_id,
            "mijoz_ismi": mijoz_ismi,
            "chat_id": chat_id,
            "tovar_nomi": tovar_nomi
        }

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
    sale_info = context.user_data.get("sale_info", {})

    await query.edit_message_text("⏳ Google Sheets yangilanmoqda va mijozga xabar yuborilmoqda...")

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        
        today = date.today().strftime("%d.%m.%Y")
        
        # 1. Google Sheets hujayralarini yangilaymiz
        ws.update_cell(sale_index, STATUS_COLUMN, "Bekor qilindi")
        ws.update_cell(sale_index, CANCEL_DATE_COLUMN, f"Bekor qilindi: {today}")

        # Qatorni vizual qizil rangga o'tkazish
        try:
            row_range = f"A{sale_index}:U{sale_index}"
            ws.format(row_range, {
                "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8},
                "textFormat": {"strikethrough": True}
            })
        except Exception:
            pass

        savdo_id = sale_info.get("savdo_id", "")
        mijoz_ismi = sale_info.get("mijoz_ismi", "Mijoz")
        tovar_nomi = sale_info.get("tovar_nomi", "Tovar")
        mijoz_chat_id = sale_info.get("chat_id", "")

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
        if mijoz_chat_id and str(mijoz_chat_id).isdigit() and len(str(mijoz_chat_id)) >= 7:
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