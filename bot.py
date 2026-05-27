"""
TexnoVibe Nasiya Bot — Asosiy fayl
"""

import logging
import os
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
from scheduler.reminder import setup_scheduler

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # === SAVDO KIRITISH ===
    sale_conv = ConversationHandler(
        entry_points=[CommandHandler("savdo", start_sale)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product)],
            TOTAL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_total_price)],
            PAYMENT_TYPE: [CallbackQueryHandler(get_payment_type)],
            INSTALLMENT_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_installment_period)],
            DOWN_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_down_payment)],
            AGENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_agent)],
            CONFIRM: [CallbackQueryHandler(confirm_sale)],
        },
        fallbacks=[CommandHandler("bekor", cancel)],
    )

    # === TO'LOV QABUL QILISH ===
    payment_conv = ConversationHandler(
        entry_points=[CommandHandler("tolov", start_payment)],
        states={
            PAY_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_phone)],
            PAY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)],
            PAY_CONFIRM: [CallbackQueryHandler(payment_confirm)],
        },
        fallbacks=[CommandHandler("bekor", cancel)],
    )

    # === SAVDONI BEKOR QILISH ===
    cancel_sale_conv = ConversationHandler(
        entry_points=[CommandHandler("bekorqilish", start_cancel)],
        states={
            CANCEL_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_search)],
            CANCEL_CONFIRM: [CallbackQueryHandler(cancel_confirm)],
        },
        fallbacks=[CommandHandler("bekor", cancel_cmd)],
    )

    # === AUKSION ===
    auction_conv = ConversationHandler(
        entry_points=[CommandHandler("auksion", start_auction)],
        states={
            AUCTION_SETUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, auction_bid)],
            AUCTION_BID: [CallbackQueryHandler(auction_bid)],
        },
        fallbacks=[CommandHandler("bekor", cancel)],
    )

    app.add_handler(sale_conv)
    app.add_handler(payment_conv)
    app.add_handler(cancel_sale_conv)
    app.add_handler(auction_conv)

    app.add_handler(CommandHandler("start", cmd_start))
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

    setup_scheduler(app)

    logger.info("✅ TexnoVibe Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


async def cmd_start(update, context):
    text = (
        "🏪 *TexnoVibe Nasiya Bot*\n\n"
        "📋 *Asosiy buyruqlar:*\n"
        "➕ /savdo — Yangi savdo kiritish\n"
        "💰 /tolov — To'lov qabul qilish\n"
        "❌ /bekorqilish — Savdoni bekor qilish\n"
        "📅 /bugun — Bugungi to'lovlar\n"
        "👥 /mijozlar — Mijozlar ro'yxati\n"
        "📊 /statistika — Umumiy statistika\n\n"
        "🔍 *Qidirish:*\n"
        "/tarix [telefon] — To'lov tarixi\n"
        "/qidir [ism yoki telefon] — Mijoz qidirish\n\n"
        "⚠️ *Hisobot:*\n"
        "/qarzdorlar — Kechikayotganlar\n"
        "/qoralist — Qora ro'yxat (3+ kun)\n"
        "/reyting — Mijozlar reytingi\n\n"
        "🎯 *Boshqa:*\n"
        "/auksion — Auksion boshlash\n"
        "/eksport — Excel eksport\n"
        "/backup — Zaxira nusxa\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


if __name__ == "__main__":
    main()
