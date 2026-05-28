"""
TexnoVibe Nasiya Bot — Asosiy fayl
Admin va Mijoz uchun alohida keyboard menyu
"""

import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
from dotenv import load_dotenv

from handlers.sale_handler import (
    start_sale, get_name, get_phone, get_product, get_total_price,
    get_payment_type, get_installment_period, get_down_payment,
    get_agent, confirm_sale, cancel,
    NAME, PHONE, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE,
    INSTALLMENT_PERIOD, DOWN_PAYMENT, AGENT, CONFIRM
)
from handlers.payment_handler import (
    start_payment, payment_phone, payment_amount, payment_confirm,
    PAY_PHONE, PAY_AMOUNT, PAY_CONFIRM
)
from handlers.query_handler import (
    cmd_history, cmd_search, cmd_debtors, cmd_blacklist,
    cmd_rating, cmd_clients, cmd_today, cmd_stats
)
from handlers.auction_handler import (
    start_auction, auction_bid, auction_end_cmd,
    AUCTION_SETUP, AUCTION_BID
)
from handlers.admin_handler import cmd_export, cmd_backup
from handlers.cancel_sale_handler import (
    start_cancel, cancel_search, cancel_confirm, cancel_cmd,
    CANCEL_SEARCH, CANCEL_CONFIRM
)
from handlers.client_panel import cmd_mening_malumotlarim, cmd_register
from scheduler.reminder import setup_scheduler

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_CHAT_ID


def get_admin_keyboard():
    """Admin uchun pastki menyu"""
    keyboard = [
        [KeyboardButton("➕ Yangi Savdo"), KeyboardButton("💰 To'lov Qabul")],
        [KeyboardButton("❌ Bekor Qilish"), KeyboardButton("📅 Bugungi To'lovlar")],
        [KeyboardButton("👥 Mijozlar"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("⚠️ Qarzdorlar"), KeyboardButton("🚫 Qora Ro'yxat")],
        [KeyboardButton("⭐ Reyting"), KeyboardButton("🔍 Qidirish")],
        [KeyboardButton("🎯 Auksion"), KeyboardButton("📥 Excel Eksport")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_client_keyboard():
    """Mijoz uchun pastki menyu"""
    keyboard = [
        [KeyboardButton("📊 Mening Kreditim")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Bekor qilish handleri (barcha conversationlar uchun)
    bekor_filter = filters.Regex("^🚫 Bekor Qilish$") | filters.Regex("^/bekor$")
    home_filter = filters.Regex("^🏠 Bosh Menyu$")

    # === SAVDO KIRITISH ===
    sale_conv = ConversationHandler(
        entry_points=[
            CommandHandler("savdo", start_sale),
            MessageHandler(filters.Regex("^➕ Yangi Savdo$"), start_sale),
        ],
        states={
            NAME: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
            ],
            PHONE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(get_payment_type),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
            PRODUCT: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_product),
            ],
            TOTAL_PRICE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_total_price),
            ],
            PAYMENT_TYPE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(get_payment_type),
            ],
            INSTALLMENT_PERIOD: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_installment_period),
            ],
            DOWN_PAYMENT: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_down_payment),
            ],
            AGENT: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_agent),
            ],
            CONFIRM: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(confirm_sale),
            ],
        },
        fallbacks=[
            CommandHandler("bekor", cancel),
            CommandHandler("start", cancel),
            MessageHandler(bekor_filter, cancel),
            MessageHandler(home_filter, cancel),
        ],
        conversation_timeout=300,
    )

    # === TO'LOV QABUL QILISH ===
    payment_conv = ConversationHandler(
        entry_points=[
            CommandHandler("tolov", start_payment),
            MessageHandler(filters.Regex("^💰 To'lov Qabul$"), start_payment),
        ],
        states={
            PAY_PHONE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_phone),
            ],
            PAY_AMOUNT: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount),
            ],
            PAY_CONFIRM: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(payment_confirm),
            ],
        },
        fallbacks=[
            CommandHandler("bekor", cancel),
            CommandHandler("start", cancel),
            MessageHandler(bekor_filter, cancel),
            MessageHandler(home_filter, cancel),
        ],
        conversation_timeout=300,
    )

    # === SAVDONI BEKOR QILISH ===
    cancel_sale_conv = ConversationHandler(
        entry_points=[
            CommandHandler("bekorqilish", start_cancel),
            MessageHandler(filters.Regex("^❌ Bekor Qilish$"), start_cancel),
        ],
        states={
            CANCEL_SEARCH: [
                MessageHandler(home_filter, cancel_cmd),
                MessageHandler(bekor_filter, cancel_cmd),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_search),
            ],
            CANCEL_CONFIRM: [
                MessageHandler(home_filter, cancel_cmd),
                MessageHandler(bekor_filter, cancel_cmd),
                CallbackQueryHandler(cancel_confirm),
            ],
        },
        fallbacks=[
            CommandHandler("bekor", cancel_cmd),
            CommandHandler("start", cancel_cmd),
            MessageHandler(bekor_filter, cancel_cmd),
            MessageHandler(home_filter, cancel_cmd),
        ],
        conversation_timeout=300,
    )

    # === AUKSION ===
    auction_conv = ConversationHandler(
        entry_points=[
            CommandHandler("auksion", start_auction),
            MessageHandler(filters.Regex("^🎯 Auksion$"), start_auction),
        ],
        states={
            AUCTION_SETUP: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, auction_bid),
            ],
            AUCTION_BID: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(auction_bid),
            ],
        },
        fallbacks=[
            CommandHandler("bekor", cancel),
            CommandHandler("start", cancel),
            MessageHandler(bekor_filter, cancel),
            MessageHandler(home_filter, cancel),
        ],
        conversation_timeout=300,
    )

    app.add_handler(sale_conv)
    app.add_handler(payment_conv)
    app.add_handler(cancel_sale_conv)
    app.add_handler(auction_conv)

    # Start
    app.add_handler(CommandHandler("start", cmd_start))

    # === ADMIN TUGMA HANDLERLARI ===
    app.add_handler(MessageHandler(filters.Regex("^📅 Bugungi To'lovlar$"), cmd_today))
    app.add_handler(MessageHandler(filters.Regex("^👥 Mijozlar$"), cmd_clients))
    app.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"), cmd_stats))
    app.add_handler(MessageHandler(filters.Regex("^⚠️ Qarzdorlar$"), cmd_debtors))
    app.add_handler(MessageHandler(filters.Regex("^🚫 Qora Ro'yxat$"), cmd_blacklist))
    app.add_handler(MessageHandler(filters.Regex("^⭐ Reyting$"), cmd_rating))
    app.add_handler(MessageHandler(filters.Regex("^📥 Excel Eksport$"), cmd_export))
    app.add_handler(MessageHandler(filters.Regex("^🔍 Qidirish$"), cmd_search_prompt))

    # === BOX MENYU HANDLERI ===
    app.add_handler(MessageHandler(filters.Regex("^🏠 Bosh Menyu$"), cmd_start))

    # === MIJOZ TUGMA HANDLERLARI ===
    app.add_handler(MessageHandler(filters.Regex("^📊 Mening Kreditim$"), cmd_mening_malumotlarim))
    app.add_handler(MessageHandler(filters.Regex("^📝 Ro'yxatdan O'tish$"), cmd_register_prompt))

    # === BUYRUQLAR ===
    app.add_handler(CommandHandler("tarix", cmd_history))
    app.add_handler(CommandHandler("qidir", cmd_search))
    app.add_handler(CommandHandler("qarzdorlar", cmd_debtors))
    app.add_handler(CommandHandler("qoralist", cmd_blacklist))
    app.add_handler(CommandHandler("reyting", cmd_rating))
    app.add_handler(CommandHandler("mijozlar", cmd_clients))
    app.add_handler(CommandHandler("bugun", cmd_today))
    app.add_handler(CommandHandler("statistika", cmd_stats))
    app.add_handler(CommandHandler("eksport", cmd_export))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("auksion_tugat", auction_end_cmd))
    app.add_handler(CommandHandler("mening_malumotlarim", cmd_mening_malumotlarim))
    app.add_handler(CommandHandler("royhattan_otish", cmd_register))

    setup_scheduler(app)

    logger.info("✅ TexnoVibe Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


async def cmd_start(update: Update, context):
    user_id = update.effective_user.id

    if is_admin(user_id):
        text = (
            "🏪 *TexnoVibe Nasiya Bot — Admin Panel*\n\n"
            "Quyidagi tugmalardan foydalaning 👇"
        )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
    else:
        text = (
            "🏪 *TexnoVibe Nasiya Bot*\n\n"
            "Assalomu alaykum! 👋\n"
            "Quyidagi tugmalardan foydalaning 👇"
        )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )


async def cmd_search_prompt(update: Update, context):
    """Qidirish tugmasi bosilganda"""
    await update.message.reply_text(
        "🔍 *Qidirish*\n\n"
        "Ism yoki telefon bo'yicha:\n"
        "`/qidir Anvarov`\n"
        "`/qidir +998901234567`\n\n"
        "To'lov tarixi:\n"
        "`/tarix +998901234567`",
        parse_mode="Markdown"
    )


async def cmd_register_prompt(update: Update, context):
    """Ro'yxatdan o'tish tugmasi bosilganda"""
    await update.message.reply_text(
        "📝 *Royxatdan otish*\n\n"
        "Telefon raqamingizni yozing:\n"
        "`/royhattan_otish +998901234567`",
        parse_mode="Markdown"
    )


if __name__ == "__main__":
    main()
