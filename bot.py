"""
TexnoVibe Nasiya Bot — Asosiy fayl
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
    start_sale, get_name, get_phone, get_product,
    get_total_price, get_payment_type, get_installment_period,
    get_down_payment, get_agent, get_pay_day, confirm_sale, cancel,
    NAME, PHONE, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE,
    INSTALLMENT_PERIOD, DOWN_PAYMENT, AGENT, PAY_DAY, START_MONTH, CONFIRM
)
from handlers.payment_handler import (
    start_payment, payment_phone, payment_select, payment_amount, payment_confirm,
    PAY_PHONE, PAY_SELECT, PAY_AMOUNT, PAY_CONFIRM
)
from handlers.query_handler import (
    cmd_history, cmd_search, cmd_debtors, cmd_blacklist,
    cmd_rating, cmd_clients, cmd_today, cmd_stats,
    start_search, search_query, SEARCH_QUERY
)
from handlers.auction_handler import (
    start_auction, auction_bid, auction_end_cmd,
    AUCTION_SETUP, AUCTION_BID
)
from handlers.admin_handler import cmd_export, cmd_backup, cmd_clients_db
from handlers.report_handler import cmd_daily_report, cmd_warehouse, cmd_excel_export
from handlers.cancel_sale_handler import (
    start_cancel, cancel_search, cancel_select, cancel_confirm, cancel_cmd,
    CANCEL_SEARCH, CANCEL_SELECT, CANCEL_CONFIRM
)
from handlers.client_panel import (
    cmd_mening_malumotlarim, cmd_register, cmd_tolovlarim,
    start_register, register_phone, cancel_register,
    REGISTER_PHONE
)
from handlers.catalog_handler import (
    start_add_product, cat_get_name, cat_get_price,
    cat_get_desc, cat_get_photo, cat_skip_photo, cat_confirm,
    cmd_catalog, cmd_remove_product,
    CAT_NAME, CAT_PRICE, CAT_DESC, CAT_PHOTO, CAT_CONFIRM
)
from handlers.order_handler import (
    start_order, order_select, order_workplace, order_confirm, cancel_order,
    cmd_orders, order_done_callback, ORDER_SELECT, ORDER_WORKPLACE, ORDER_CONFIRM
)
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
    keyboard = [
        [KeyboardButton("➕ Yangi Savdo"),      KeyboardButton("💰 To'lov Qabul")],
        [KeyboardButton("❌ Bekor Qilish"),      KeyboardButton("📅 Bugungi To'lovlar")],
        [KeyboardButton("👥 Mijozlar"),           KeyboardButton("📊 Statistika")],
        [KeyboardButton("⚠️ Qarzdorlar"),        KeyboardButton("🚫 Qora Ro'yxat")],
        [KeyboardButton("⭐ Reyting"),            KeyboardButton("🔍 Qidirish")],
        [KeyboardButton("🎯 Auksion"),            KeyboardButton("📥 Excel Eksport")],
        [KeyboardButton("📦 Tovar Qoshish"),      KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtmalar"),        KeyboardButton("👥 Mijozlar Bazasi")],
        [KeyboardButton("📈 Bugungi Hisobot"),    KeyboardButton("🏭 Ombor Nazorati")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_client_keyboard():
    keyboard = [
        [KeyboardButton("📊 Mening Nasiyam")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def cmd_start(update: Update, context):
    user_id = update.effective_user.id
    if is_admin(user_id):
        await update.message.reply_text(
            "🏪 *TexnoVibe Nasiya Bot — Admin Panel*\n\nQuyidagi tugmalardan foydalaning 👇",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.message.reply_text(
            "🏪 *TexnoVibe Nasiya Bot*\n\nAssalomu alaykum! 👋\nQuyidagi tugmalardan foydalaning 👇",
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    bekor_filter = filters.Regex("^🚫 Bekor Qilish$") | filters.Regex("^/bekor$")
    home_filter  = filters.Regex("^🏠 Bosh Menyu$")

    sale_conv = ConversationHandler(
        entry_points=[
            CommandHandler("savdo", start_sale),
            MessageHandler(filters.Regex("^➕ Yangi Savdo$"), start_sale),
        ],
        states={
            PHONE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
            NAME: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(get_name, pattern="^dup_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
            ],
            PRODUCT: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(get_product),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_product),
            ],
            TOTAL_PRICE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(get_payment_type, pattern="^price_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_total_price),
            ],
            PAYMENT_TYPE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(get_payment_type),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_payment_type),
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
            PAY_DAY: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                CallbackQueryHandler(get_pay_day),
            ],
            START_MONTH: [
                CallbackQueryHandler(get_pay_day),
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
            PAY_SELECT: [
                CallbackQueryHandler(payment_select, pattern="^paysel_"),
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
            CANCEL_SELECT: [
                CallbackQueryHandler(cancel_select, pattern="^cnlsel_"),
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

    register_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📝 Ro'yxatdan O'tish$"), start_register),
            CommandHandler("royhattan_otish", start_register),
        ],
        states={
            REGISTER_PHONE: [
                MessageHandler(home_filter, cancel_register),
                MessageHandler(filters.CONTACT, register_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_phone),
            ],
        },
        fallbacks=[
            CommandHandler("bekor", cancel_register),
            CommandHandler("start", cancel_register),
            MessageHandler(home_filter, cancel_register),
        ],
        conversation_timeout=300,
    )

    catalog_add_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📦 Tovar Qoshish$"), start_add_product),
            CommandHandler("tovarqosh", start_add_product),
        ],
        states={
            CAT_NAME: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cat_get_name),
            ],
            CAT_PRICE: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cat_get_price),
            ],
            CAT_DESC: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cat_get_desc),
            ],
            CAT_PHOTO: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.PHOTO, cat_get_photo),
                CallbackQueryHandler(cat_skip_photo, pattern="^cat_skip_photo$"),
            ],
            CAT_CONFIRM: [
                CallbackQueryHandler(cat_confirm),
                MessageHandler(home_filter, cancel),
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

    order_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🛒 Buyurtma Berish$"), start_order),
            CommandHandler("buyurtma", start_order),
        ],
        states={
            ORDER_SELECT: [
                CallbackQueryHandler(order_select),
                MessageHandler(home_filter, cancel_order),
            ],
            ORDER_WORKPLACE: [
                MessageHandler(home_filter, cancel_order),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_workplace),
            ],
            ORDER_CONFIRM: [
                CallbackQueryHandler(order_confirm),
                MessageHandler(home_filter, cancel_order),
            ],
        },
        fallbacks=[
            CommandHandler("bekor", cancel_order),
            CommandHandler("start", cancel_order),
            MessageHandler(home_filter, cancel_order),
        ],
        conversation_timeout=300,
    )

    search_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔍 Qidirish$"), start_search),
            CommandHandler("qidir", start_search),
        ],
        states={
            SEARCH_QUERY: [
                MessageHandler(home_filter, cancel),
                MessageHandler(bekor_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_query),
            ],
        },
        fallbacks=[
            CommandHandler("bekor", cancel),
            CommandHandler("start", cancel),
            MessageHandler(home_filter, cancel),
        ],
        conversation_timeout=120,
    )

    app.add_handler(register_conv)
    app.add_handler(catalog_add_conv)
    app.add_handler(order_conv)
    app.add_handler(search_conv)
    app.add_handler(sale_conv)
    app.add_handler(payment_conv)
    app.add_handler(cancel_sale_conv)
    app.add_handler(auction_conv)

    app.add_handler(CommandHandler("start", cmd_start))

    app.add_handler(MessageHandler(filters.Regex("^📅 Bugungi To'lovlar$"),  cmd_today))
    app.add_handler(MessageHandler(filters.Regex("^👥 Mijozlar$"),           cmd_clients))
    app.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"),         cmd_stats))
    app.add_handler(MessageHandler(filters.Regex("^⚠️ Qarzdorlar$"),        cmd_debtors))
    app.add_handler(MessageHandler(filters.Regex("^🚫 Qora Ro'yxat$"),      cmd_blacklist))
    app.add_handler(MessageHandler(filters.Regex("^⭐ Reyting$"),            cmd_rating))
    app.add_handler(MessageHandler(filters.Regex("^📥 Excel Eksport$"),      cmd_excel_export))
    app.add_handler(MessageHandler(filters.Regex("^👥 Mijozlar Bazasi$"),    cmd_clients_db))
    app.add_handler(MessageHandler(filters.Regex("^📈 Bugungi Hisobot$"),    cmd_daily_report))
    app.add_handler(MessageHandler(filters.Regex("^🏭 Ombor Nazorati$"),     cmd_warehouse))
    app.add_handler(MessageHandler(filters.Regex("^🛍 Katalog$"),            cmd_catalog))
    app.add_handler(MessageHandler(filters.Regex("^🛒 Buyurtmalar$"),        cmd_orders))
    app.add_handler(MessageHandler(filters.Regex("^🏠 Bosh Menyu$"),         cmd_start))
    app.add_handler(MessageHandler(filters.Regex("^📊 Mening Nasiyam$"),     cmd_mening_malumotlarim))
    app.add_handler(MessageHandler(filters.Regex("^💳 To'lovlarim$"),          cmd_tolovlarim))

    app.add_handler(CommandHandler("register",            cmd_register))
    app.add_handler(CommandHandler("tarix",               cmd_history))
    app.add_handler(CommandHandler("qidir",               cmd_search))
    app.add_handler(CommandHandler("qarzdorlar",          cmd_debtors))
    app.add_handler(CommandHandler("qoralist",            cmd_blacklist))
    app.add_handler(CommandHandler("reyting",             cmd_rating))
    app.add_handler(CommandHandler("mijozlar",            cmd_clients))
    app.add_handler(CommandHandler("bugun",               cmd_today))
    app.add_handler(CommandHandler("statistika",          cmd_stats))
    app.add_handler(CommandHandler("eksport",             cmd_excel_export))
    app.add_handler(CommandHandler("backup",              cmd_backup))
    app.add_handler(CommandHandler("auksion_tugat",       auction_end_cmd))
    app.add_handler(CommandHandler("mening_malumotlarim", cmd_mening_malumotlarim))
    app.add_handler(CommandHandler("mijozlarbazasi",      cmd_clients_db))
    app.add_handler(CommandHandler("hisobot",             cmd_daily_report))
    app.add_handler(CommandHandler("ombor",               cmd_warehouse))
    app.add_handler(CommandHandler("katalog",             cmd_catalog))
    app.add_handler(CommandHandler("tovarchiqar",         cmd_remove_product))
    app.add_handler(CommandHandler("buyurtmalar",         cmd_orders))

    # Buyurtma yetkazildi callback
    app.add_handler(CallbackQueryHandler(order_done_callback, pattern="^ord_done_"))

    setup_scheduler(app)

    logger.info("✅ TexnoVibe Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
