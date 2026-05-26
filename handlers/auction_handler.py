"""
Auksion tizimi
/auksion — Yangi auksion boshlash
Mijozlar bot orqali narx oshiradi
"""

import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

AUCTION_SETUP, AUCTION_BID = range(20, 22)
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")  # Kanal ID (ixtiyoriy)

# Joriy auksion holati (xotira)
current_auction = {
    "active": False,
    "product": "",
    "start_price": 0,
    "current_price": 0,
    "current_winner": "",
    "winner_chat_id": None,
    "end_time": None,
    "bid_step": 10000,  # Har bir narx oshirish: 10,000 so'm
    "bids": []
}


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_auction_keyboard():
    """Auksion tugmalari"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🔺 Narx oshirish (+{format_money(current_auction['bid_step'])} so'm)",
                callback_data="auction_bid"
            )
        ],
        [
            InlineKeyboardButton("📊 Joriy holat", callback_data="auction_status")
        ]
    ])


async def start_auction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin uchun auksion boshlash"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Faqat admin auksion boshlay oladi.")
        return ConversationHandler.END

    if current_auction["active"]:
        await update.message.reply_text(
            f"⚠️ Hozir auksion davom etmoqda!\n"
            f"🛍 Tovar: *{current_auction['product']}*\n"
            f"💰 Joriy narx: *{format_money(current_auction['current_price'])} so'm*\n\n"
            f"Auksionni tugatish uchun: /auksion_tugat",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🎯 *YANGI AUKSION BOSHLASH*\n\n"
        "Tovar nomini kiriting:\n"
        "_(Masalan: iPhone 15 Pro 256GB)_",
        parse_mode="Markdown"
    )
    return AUCTION_SETUP


async def auction_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auksion sozlamalari va bid"""

    # Setup bosqichi (admin tovarni kiritadi)
    if update.message and not current_auction["active"]:
        if context.user_data.get("auction_step") is None:
            # Tovar nomi
            context.user_data["auction_product"] = update.message.text.strip()
            context.user_data["auction_step"] = "price"
            await update.message.reply_text(
                f"✅ Tovar: *{context.user_data['auction_product']}*\n\n"
                "Boshlang'ich narxni kiriting (so'mda):",
                parse_mode="Markdown"
            )
            return AUCTION_SETUP

        elif context.user_data.get("auction_step") == "price":
            try:
                price = float(update.message.text.strip().replace(" ", "").replace(",", ""))
                context.user_data["auction_price"] = price
                context.user_data["auction_step"] = "duration"
            except:
                await update.message.reply_text("❌ Narx noto'g'ri. Qaytadan kiriting:")
                return AUCTION_SETUP

            await update.message.reply_text(
                f"✅ Narx: *{format_money(price)} so'm*\n\n"
                "Auksion davomiyligi (daqiqalarda):\n_(Masalan: 60 — 1 soat)_",
                parse_mode="Markdown"
            )
            return AUCTION_SETUP

        elif context.user_data.get("auction_step") == "duration":
            try:
                duration = int(update.message.text.strip())
            except:
                await update.message.reply_text("❌ Noto'g'ri. Raqam kiriting:")
                return AUCTION_SETUP

            # Auksionni boshlash
            product = context.user_data["auction_product"]
            price = context.user_data["auction_price"]
            end_time = datetime.now() + timedelta(minutes=duration)

            current_auction.update({
                "active": True,
                "product": product,
                "start_price": price,
                "current_price": price,
                "current_winner": "Hali yo'q",
                "winner_chat_id": None,
                "end_time": end_time,
                "bids": []
            })

            announcement = (
                f"🎯 *AUKSION BOSHLANDI!*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🛍 *Tovar:* {product}\n"
                f"💰 *Boshlang'ich narx:* {format_money(price)} so'm\n"
                f"⏰ *Tugash vaqti:* {end_time.strftime('%H:%M:%S')}\n"
                f"📈 *Narx oshirish:* {format_money(current_auction['bid_step'])} so'm\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 Eng yuqori narx berganga tovar *nasiyaga* beriladi!\n"
                f"_(Boshlang'ich to'lovsiz)_"
            )

            await update.message.reply_text(
                announcement,
                parse_mode="Markdown",
                reply_markup=get_auction_keyboard()
            )

            # Kanalga ham yuborish
            if CHANNEL_ID:
                try:
                    await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=announcement,
                        parse_mode="Markdown",
                        reply_markup=get_auction_keyboard()
                    )
                except:
                    pass

            context.user_data.clear()

            # Avtomatik tugatish
            asyncio.create_task(
                auto_end_auction(context.bot, update.effective_chat.id, duration * 60)
            )

            return ConversationHandler.END

    # Callback — bid yoki status
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "auction_status":
            if not current_auction["active"]:
                await query.answer("Auksion tugagan!", show_alert=True)
                return ConversationHandler.END

            remaining = current_auction["end_time"] - datetime.now()
            mins = int(remaining.total_seconds() / 60)
            secs = int(remaining.total_seconds() % 60)

            await query.answer(
                f"🛍 {current_auction['product']}\n"
                f"💰 {format_money(current_auction['current_price'])} so'm\n"
                f"🏆 {current_auction['current_winner']}\n"
                f"⏰ {mins}:{secs:02d} qoldi",
                show_alert=True
            )

        elif query.data == "auction_bid":
            if not current_auction["active"]:
                await query.answer("❌ Auksion tugagan!", show_alert=True)
                return ConversationHandler.END

            if datetime.now() > current_auction["end_time"]:
                await query.answer("❌ Auksion vaqti tugadi!", show_alert=True)
                current_auction["active"] = False
                return ConversationHandler.END

            user = query.from_user
            new_price = current_auction["current_price"] + current_auction["bid_step"]

            current_auction["current_price"] = new_price
            current_auction["current_winner"] = user.full_name
            current_auction["winner_chat_id"] = user.id
            current_auction["bids"].append({
                "user": user.full_name,
                "price": new_price,
                "time": datetime.now().strftime("%H:%M:%S")
            })

            remaining = current_auction["end_time"] - datetime.now()
            mins = int(remaining.total_seconds() / 60)
            secs = int(remaining.total_seconds() % 60)

            updated_text = (
                f"🎯 *AUKSION DAVOM ETMOQDA*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🛍 *Tovar:* {current_auction['product']}\n"
                f"💰 *Joriy narx:* *{format_money(new_price)} so'm*\n"
                f"🏆 *Yetakchi:* {user.full_name}\n"
                f"⏰ *Qolgan vaqt:* {mins}:{secs:02d}\n"
                f"📊 *Jami bidlar:* {len(current_auction['bids'])}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

            try:
                await query.edit_message_text(
                    updated_text,
                    parse_mode="Markdown",
                    reply_markup=get_auction_keyboard()
                )
            except:
                pass

    return ConversationHandler.END


async def auction_end_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin tomonidan auksionni tugatish"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    await end_auction(context.bot, update.effective_chat.id)


async def auto_end_auction(bot, chat_id, delay_seconds):
    """Vaqt tugagach avtomatik tugatish"""
    await asyncio.sleep(delay_seconds)
    if current_auction["active"]:
        await end_auction(bot, chat_id)


async def end_auction(bot, chat_id):
    """Auksionni tugatadi va g'olibni e'lon qiladi"""
    if not current_auction["active"]:
        return

    current_auction["active"] = False
    winner = current_auction["current_winner"]
    price = current_auction["current_price"]
    product = current_auction["product"]

    if current_auction["winner_chat_id"]:
        result_text = (
            f"🏆 *AUKSION TUGADI!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍 *Tovar:* {product}\n"
            f"💰 *Yakuniy narx:* *{format_money(price)} so'm*\n"
            f"🥇 *G'olib:* {winner}\n"
            f"📊 *Jami bidlar:* {len(current_auction['bids'])}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*{winner}* — sizga tabriklar! 🎉\n"
            f"Do'konimizga kelib rasmiylashtiring.\n"
            f"_(Boshlang'ich to'lovsiz nasiya!)_"
        )

        # G'olibga xabar
        try:
            await bot.send_message(
                chat_id=current_auction["winner_chat_id"],
                text=(
                    f"🎉 *Tabriklaymiz!*\n\n"
                    f"Siz *{product}* auksionida g'olib bo'ldingiz!\n"
                    f"Yakuniy narx: *{format_money(price)} so'm*\n\n"
                    f"Do'konimizga kelib, hujjatlarni rasmiylashtirishingiz mumkin.\n"
                    f"🏪 TexnoVibe"
                ),
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        result_text = (
            f"⚠️ *AUKSION TUGADI — Hech kim qatnashmadi*\n"
            f"🛍 Tovar: {product}\n"
            f"💰 Boshlang'ich narx: {format_money(price)} so'm"
        )

    await bot.send_message(
        chat_id=chat_id,
        text=result_text,
        parse_mode="Markdown"
    )

    if CHANNEL_ID:
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=result_text,
                parse_mode="Markdown"
            )
        except:
            pass
