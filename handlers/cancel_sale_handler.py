"""
TexnoVibe — handlers/cancel_sale_handler.py
Savdoni bekor qilish paneli.
Agar Savdolar jadvalida Chat ID bo'lmasa, uni Mijozlar varag'idan avtomatik qidiruvchi mukammal variant.
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


def clean_telegram_id(raw_val):
    """Telegram ID raqamini har xil formatlardan (float, string) tozalab qaytaradi"""
    if not raw_val:
        return None
    try:
        raw_str = str(raw_val).split('.')[0].strip()
        if raw_str.isdigit() or (raw_str.startswith('-') and raw_str[1:].isdigit()):
            if len(raw_str) >= 6:
                return int(raw_str)
    except Exception:
        pass
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
        
        id_col = find_column_index(headers, ["id", "savdo id", "txn"]) or 1
        name_col = find_column_index(headers, ["mijoz", "ism", "fio", "f.i.o"]) or 2
        chat_col = find_column_index(headers, ["chat", "telegram id", "mijoz id", "tg id", "user id", "chatid", "tg_id"]) or 3
        tovar_col = find_column_index(headers, ["tovar", "mahsulot", "buyum"]) or 5
        status_col = find_column_index(headers, ["holat", "status"]) or 14
        phone_col = find_column_index(headers, ["tel", "telefon", "nomer"]) or 4

        context.user_data["cols"] = {
            "id": id_col, "name": name_col, "chat": chat_col, 
            "tovar": tovar_col, "status": status_col, "phone": phone_col
        }

        found_sales = []
        for idx, row in enumerate(all_rows[1:], start=2):
            holat = str(row[status_col - 1]).strip().lower() if len(row) >= status_col else ""
            if "bekor" in holat or holat == "yakunlangan":
                continue

            row_dump = " ".join([str(cell).lower() for cell in row])
            if query_text in row_dump:
                found_sales.append({
                    "row_index": idx,
                    "savdo_id": row[id_col - 1] if len(row) >= id_col else "",
                    "mijoz_ismi": row[name_col - 1] if len(row) >= name_col else "Noma'lum",
                    "tovar": row[tovar_col - 1] if len(row) >= tovar_col else "Tovar",
                    "telefon": row[phone_col - 1] if len(row) >= phone_col else ""
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

        savdo_id = row_data[cols["id"] - 1] if len(row_data) >= cols["id"] else "—"
        mijoz_ismi = row_data[cols["name"] - 1] if len(row_data) >= cols["name"] else "—"
        chat_id = row_data[cols["chat"] - 1] if len(row_data) >= cols["chat"] else ""
        tovar_nomi = row_data[cols["tovar"] - 1] if len(row_data) >= cols["tovar"] else "—"
        telefon = row_data[cols["phone"] - 1] if len(row_data) >= cols["phone"] else ""
        
        headers = ws.row_values(1)
        price_col = find_column_index(headers, ["jami", "narxi", "summa"]) or 6
        jami = format_money(row_data[price_col - 1]) if len(row_data) >= price_col else "0"

        context.user_data["sale_info"] = {
            "savdo_id": savdo_id,
            "mijoz_ismi": mijoz_ismi,
            "chat_id": chat_id,
            "tovar_nomi": tovar_nomi,
            "telefon": telefon
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
        row_values = ws.row_values(sale_index)
        
        today = date.today().strftime("%d.%m.%Y")
        
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
        telefon_raqam = str(sale_info.get("telefon", "")).strip()
        
        # 1-Bosqich: Savdolar varag'idan Chat ID ni tekshiramiz
        mijoz_chat_id = sale_info.get("chat_id", "")
        if not mijoz_chat_id and len(row_values) >= cols.get("chat", 3):
            mijoz_chat_id = row_values[cols.get("chat") - 1]
            
        clean_chat_id = clean_telegram_id(mijoz_chat_id)

        # 2-Bosqich: AGAR SAVDOLARDA TOPILMASA, MIJOZLAR VARAG'IDAN QIDIRAMIZ 🚀
        if not clean_chat_id:
            try:
                m_ws = sh.worksheet("Mijozlar")
                m_rows = m_ws.get_all_values()
                if m_rows:
                    m_headers = m_rows[0]
                    m_chat_idx = find_column_index(m_headers, ["chat", "telegram id", "tg id", "user id", "chatid"]) or 2
                    m_phone_idx = find_column_index(m_headers, ["tel", "telefon", "nomer"]) or 3
                    m_name_idx = find_column_index(m_headers, ["mijoz", "ism", "fio"]) or 1
                    
                    # Telefon yoki Ism bo'yicha mijozlar bazasidan Chat ID qidiramiz
                    for m_row in m_rows[1:]:
                        m_phone = str(m_row[m_phone_idx - 1]).strip() if len(m_row) >= m_phone_idx else ""
                        m_name = str(m_row[m_name_idx - 1]).strip().lower() if len(m_row) >= m_name_idx else ""
                        
                        # Telefon mos kelsa yoki Ism 100% bir xil bo'lsa
                        if (telefon_raqam and telefon_raqam in m_phone) or (mijoz_ismi.lower() in m_name and len(mijoz_ismi) > 3):
                            found_id = m_row[m_chat_idx - 1] if len(m_row) >= m_chat_idx else None
                            clean_chat_id = clean_telegram_id(found_id)
                            if clean_chat_id:
                                logger.info(f"Chat ID 'Mijozlar' varag'idan topildi: {clean_chat_id}")
                                break
            except Exception as sheet_err:
                logger.error(f"Mijozlar varag'idan qidirishda xatolik: {sheet_err}")

        # Adminga natija xabari
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
        
        # Mijozga shaxsiy xabar yuborish
        if clean_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=clean_chat_id,
                    text=(
                        f"⚠️ <b>Hurmatli {escape_html(mijoz_ismi)}!</b>\n\n"
                        f"Sizning 📦 <b>{escape_html(tovar_nomi)}</b> uchun rasmiylashtirilgan "
                        f"nasiya savdoingiz tomonlar kelishuvi yoki shartnoma shartlariga ko'ra "
                        f"tizimda <b>BEKOR QILINDI</b>.\n\n"
                        f"ℹ️ Savollar bo'lsa, ma'muriyatga murojaat qilishingiz mumkin."
                    ),
                    parse_mode="HTML"
                )
                logger.info(f"Mijozga ({clean_chat_id}) bekor qilish eslatmasi muvaffaqiyatli ketdi.")
            except Exception as bot_err:
                logger.error(f"Mijozga yuborishda xatolik: {bot_err}")
                await query.message.reply_text(
                    f"ℹ️ <i>Eslatma yuborishda xatolik:</i> <code>{escape_html(str(bot_err))}</code>", 
                    parse_mode="HTML"
                )
        else:
            await query.message.reply_text("ℹ️ <i>Chat ID bazalardan (Savdolar va Mijozlar varag'idan) topilmadi, eslatma yuborilmadi.</i>", parse_mode="HTML")

    except Exception as e:
        logger.error(f"Tasdiqlashda xatolik: {e}")
        await query.message.reply_text(f"❌ Xatolik yuz berdi: {escape_html(str(e))}", parse_mode="HTML")
        
    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Savdoni bekor qilish paneli yopildi.")
    return ConversationHandler.END