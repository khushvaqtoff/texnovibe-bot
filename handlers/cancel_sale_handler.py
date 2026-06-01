"""
TexnoVibe — handlers/cancel_sale_handler.py
Savdoni bekor qilish paneli.
Sarlavha nomlarini aqlli qidirish orqali ustunlar chalkashligini to'liq hal qiluvchi variant.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import get_spreadsheet, ensure_worksheets
from datetime import date
import html

logger = logging.getLogger(__name__)

# States
CANCEL_SEARCH, CANCEL_SELECT, CANCEL_CONFIRM = range(3)


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(amount)


def escape_html(text) -> str:
    return html.escape(str(text)) if text else ""


def find_column_index(headers, keys):
    """Sarlavhalar ichidan kalit so'zlarga mos keladigan ustun indeksini qaytaradi (1-boshlanadi)"""
    for idx, h in enumerate(headers, start=1):
        header_lower = str(h).strip().lower()
        for key in keys:
            if key in header_lower:
                return idx
    return None


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
        
        all_rows = ws.get_all_values()
        if not all_rows:
            await status_msg.edit_text("📭 Jadval bo'sh.")
            return ConversationHandler.END

        headers = all_rows[0]
        
        # Ustunlar indekslarini sarlavha matniga qarab dinamik aniqlaymiz
        id_col = find_column_index(headers, ["id", "savdo id"]) or 1
        name_col = find_column_index(headers, ["mijoz", "ism", "fio", "f.i.o"]) or 2
        chat_col = find_column_index(headers, ["chat", "telegram id", "mijoz id"]) or 3
        tovar_col = find_column_index(headers, ["tovar", "mahsulot", "buyum"]) or 5
        status_col = find_column_index(headers, ["holat", "status"]) or 14

        # Indekslarni context'da saqlab turamiz, keyingi funksiyalarda ham ishlatish uchun
        context.user_data["cols"] = {
            "id": id_col, "name": name_col, "chat": chat_col, 
            "tovar": tovar_col, "status": status_col
        }

        found_sales = []
        for idx, row in enumerate(all_rows[1:], start=2):
            # 1. Holatni tekshirish
            holat = str(row[status_col - 1]).strip().lower() if len(row) >= status_col else ""
            if "bekor" in holat or holat == "yakunlangan":
                continue

            # 2. Qidiruv matnini tekshirish
            row_dump = " ".join([str(cell).lower() for cell in row])
            if query_text in row_dump:
                found_sales.append({
                    "row_index": idx,
                    "savdo_id": row[id_col - 1] if len(row) >= id_col else "",
                    "mijoz_ismi": row[name_col - 1] if len(row) >= name_col else "Noma'lum",
                    "tovar": row[tovar_col - 1] if len(row) >= tovar_col else "Tovar"
                })

        await status_msg.delete()

        if not found_sales:
            await update.message.reply_text("📭 Bunday ma'lumotga ega faol nasiya savdosi topilmadi.")
            return ConversationHandler.END

        keyboard = []
        for s in found_sales[:10]:
            nomi = s["mijoz_ismi"]
            tovar = s["tovar"]
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
    cols = context.user_data.get("cols", {})

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        row_data = ws.row_values(row_idx)

        # Saqlab olingan aniq indekslar bo'yicha ma'lumotlarni o'qiymiz
        savdo_id = row_data[cols["id"] - 1] if len(row_data) >= cols["id"] else "—"
        mijoz_ismi = row_data[cols["name"] - 1] if len(row_data) >= cols["name"] else "—"
        chat_id = row_data[cols["chat"] - 1] if len(row_data) >= cols["chat"] else ""
        tovar_nomi = row_data[cols["tovar"] - 1] if len(row_data) >= cols["tovar"] else "—"
        
        # Narx ustunini ham qidirib ko'ramiz
        headers = ws.row_values(1)
        price_col = find_column_index(headers, ["jami", "narxi", "summa"]) or 6
        jami = format_money(row_data[price_col - 1]) if len(row_data) >= price_col else "0"

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
    cols = context.user_data.get("cols", {})

    await query.edit_message_text("⏳ Google Sheets yangilanmoqda va mijozga xabar yuborilmoqda...")

    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("Savdolar")
        headers = ws.row_values(1)
        
        today = date.today().strftime("%d.%m.%Y")
        
        # Dinamik ravishda aynan kerakli ustun katakchalarini yangilaymiz
        status_column_idx = cols.get("status") or find_column_index(headers, ["holat", "status"]) or 14
        cancel_date_idx = find_column_index(headers, ["bekor qilingan sana", "bekor", "sana"]) or 17
        
        ws.update_cell(sale_index, status_column_idx, "Bekor qilindi")
        ws.update_cell(sale_index, cancel_date_idx, f"Bekor qilindi: {today}")

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