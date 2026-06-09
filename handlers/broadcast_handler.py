"""
Barcha mijozlarga xabar yuborish (broadcast)
Admin panelida: 📢 Xabar Yuborish tugmasi
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from sheets.google_sheets import get_spreadsheet, ensure_worksheets, ws_to_records

logger = logging.getLogger(__name__)

ADMIN_CHAT_ID  = int(os.getenv("ADMIN_CHAT_ID", "0"))
BROADCAST_TEXT = 10_000  # state


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_all_client_chat_ids() -> list[dict]:
    """Barcha ro'yxatdan o'tgan mijozlarning chat_id larini qaytaradi"""
    try:
        sh      = get_spreadsheet()
        sheets  = ensure_worksheets(sh)
        all_val = sheets["Mijozlar"].get_all_values()
        if len(all_val) < 2:
            return []

        headers = [h.strip() for h in all_val[0]]

        # Chat ID ustun indeksini topish
        chat_id_idx = None
        fio_idx     = 0
        phone_idx   = 1
        for i, h in enumerate(headers):
            h_lower = h.lower().replace(" ", "").replace("_", "")
            if "chatid" in h_lower or "chat" in h_lower:
                chat_id_idx = i
            if "fio" in h_lower or "ism" in h_lower:
                fio_idx = i
            if "telefon" in h_lower or "phone" in h_lower:
                phone_idx = i

        # Topilmasa 3-ustun (C) — standart joylashuv
        if chat_id_idx is None:
            chat_id_idx = 2

        result = []
        for row in all_val[1:]:
            if len(row) <= chat_id_idx:
                continue
            chat_id = str(row[chat_id_idx]).strip()
            fio     = str(row[fio_idx]).strip()   if len(row) > fio_idx   else ""
            phone   = str(row[phone_idx]).strip() if len(row) > phone_idx else ""
            if chat_id and chat_id.isdigit() and int(chat_id) > 0:
                result.append({"chat_id": int(chat_id), "fio": fio, "phone": phone})
        return result
    except Exception as e:
        logger.error(f"Chat ID larni olishda xato: {e}")
        return []


# ─── BOSHLASH ───────────────────────────────────────────────
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return ConversationHandler.END

    clients = get_all_client_chat_ids()
    await update.message.reply_text(
        f"📢 *Barcha Mijozlarga Xabar Yuborish*\n\n"
        f"👥 Telegram ulangan mijozlar: *{len(clients)} ta*\n\n"
        f"Yuboriladigan xabarni yozing:\n"
        f"_(Bekor qilish uchun: 🏠 Bosh Menyu)_",
        parse_mode="Markdown"
    )
    return BROADCAST_TEXT


# ─── XABAR MATNINI QABUL QILISH ─────────────────────────────
async def broadcast_get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return ConversationHandler.END

    text = update.message.text.strip()
    context.user_data["broadcast_text"] = text

    clients = get_all_client_chat_ids()

    keyboard = [[
        InlineKeyboardButton(
            f"✅ Ha, {len(clients)} ta mijozga yuborish",
            callback_data="broadcast_yes"
        ),
        InlineKeyboardButton("❌ Bekor", callback_data="broadcast_no")
    ]]

    preview = text[:200] + ("..." if len(text) > 200 else "")
    await update.message.reply_text(
        f"📋 *Xabar ko'rinishi:*\n\n"
        f"{preview}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Yuboriladi: *{len(clients)} ta* mijozga\n\n"
        f"Tasdiqlaysizmi?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BROADCAST_TEXT


# ─── TASDIQLASH VA YUBORISH ──────────────────────────────────
async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "broadcast_no":
        await query.edit_message_text("❌ Xabar yuborish bekor qilindi.")
        context.user_data.clear()
        return ConversationHandler.END

    text    = context.user_data.get("broadcast_text", "")
    clients = get_all_client_chat_ids()

    if not clients:
        await query.edit_message_text("❌ Telegram ulangan mijoz yo'q.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"⏳ Yuborilmoqda... (0/{len(clients)})"
    )

    yuborildi = 0
    xato      = 0

    full_msg = (
        f"📢 *TexnoVibe xabari:*\n\n"
        f"{text}\n\n"
        f"🏪 TexnoVibe"
    )

    for i, client in enumerate(clients):
        try:
            await context.bot.send_message(
                chat_id=client["chat_id"],
                text=full_msg,
                parse_mode="Markdown"
            )
            yuborildi += 1
        except Exception as e:
            logger.warning(f"Yuborishda xato ({client['chat_id']}): {e}")
            xato += 1

        # Har 10 mijozda progress yangilash
        if (i + 1) % 10 == 0:
            try:
                await query.edit_message_text(
                    f"⏳ Yuborilmoqda... ({i+1}/{len(clients)})"
                )
            except Exception:
                pass

    await query.edit_message_text(
        f"✅ *Xabar yuborildi!*\n\n"
        f"👥 Jami mijozlar: {len(clients)} ta\n"
        f"✅ Muvaffaqiyatli: {yuborildi} ta\n"
        f"❌ Xato (bot bloklangan): {xato} ta",
        parse_mode="Markdown"
    )

    context.user_data.clear()
    return ConversationHandler.END


# ─── BEKOR QILISH ───────────────────────────────────────────
async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Xabar yuborish bekor qilindi.")
    return ConversationHandler.END
