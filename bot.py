"""
TexnoVibe Nasiya Bot — Asosiy fayl
Admin va Mijoz uchun alohida keyboard menyu
Tuzatilgan variant: Barcha eskilari va yangi qidiruv tizimi uyg'unlashtirildi.
"""

import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from dotenv import load_dotenv

# === SAVDO HANDLERLARI ===
from handlers.sale_handler import (
    start_sale, get_name, get_phone, get_product,
    get_total_price, get_payment_type, get_installment_period,
    get_down_payment, get_agent, get_pay_day, confirm_sale, cancel,
    NAME, PHONE, PRODUCT, TOTAL_PRICE, PAYMENT_TYPE,
    INSTALLMENT_PERIOD, DOWN_PAYMENT, AGENT, PAY_DAY, CONFIRM
)

# === TO'LOV HANDLERLARI ===
from handlers.payment_handler import (
    start_payment, payment_phone, payment_select, payment_amount, payment_confirm,
    PAY_PHONE, PAY_SELECT, PAY_AMOUNT, PAY_CONFIRM
)

# === AUKSION HANDLERLARI ===
from handlers.auction_handler import (
    start_auction, auction_bid, auction_end_cmd,
    AUCTION_SETUP, AUCTION_BID
)

# === ADMIN VA REPORT HANDLERLARI ===
from handlers.admin_handler import cmd_export, cmd_backup, cmd_clients_db
from handlers.report_handler import cmd_daily_report, cmd_warehouse, cmd_excel_export

# === SAVDONI BEKOR QILISH HANDLERLARI ===
from handlers.cancel_sale_handler import (
    start_cancel, cancel_search, cancel_select, cancel_confirm, cancel_cmd,
    CANCEL_SEARCH, CANCEL_SELECT, CANCEL_CONFIRM
)

# === MIJOZ PANEL HANDLERLARI ===
from handlers.client_panel import (
    cmd_mening_malumotlarim, cmd_register,
    start_register, register_phone, cancel_register,
    REGISTER_PHONE
)

# === KATALOG HANDLERLARI ===
from handlers.catalog_handler import (
    start_add_product, cat_get_name, cat_get_price,
    cat_get_desc, cat_confirm, cmd_catalog, cmd_remove_product,
    CAT_NAME, CAT_PRICE, CAT_DESC, CAT_CONFIRM
)

# === BUYURTMA HANDLERLARI ===
from handlers.order_handler import (
    start_order, order_select, order_workplace, order_confirm, cancel_order,
    cmd_orders, ORDER_SELECT, ORDER_WORKPLACE, ORDER_CONFIRM
)

# === YANGI: QIDIRUV PANELI HANDLERLARI ===
from handlers.search_handler import start_search, search_query, SEARCH_QUERY

# === SCHEDULER ===
from scheduler.reminder import setup_scheduler

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))


# === ETISHMAYOTGAN BOSHQA SARIQLAR (DUMMY STUBS) ===
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Bugungi to'lovlar ro'yxati tayyorlanmoqda...")

async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Mijozlar ro'yxati yuklanmoqda...")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Statistika ma'lumotlari hisoblanmoqda...")

async def cmd_debtors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Qarzdorlar ro'yxati shakllantirilmoqda...")

async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Qora ro'yxat yuklanmoqda...")

async def cmd_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⭐ Agentlar va mijozlar reytingi...")

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ To'lovlar tarixi yuklanmoqda...")

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Qidiruv bo'limi. /qidir [ism/tel] ko'rinishida yozing.")


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
        [KeyboardButton("📦 Tovar Qoshish"), KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtmalar"), KeyboardButton("👥 Mijozlar Bazasi")],
        [KeyboardButton("📈 Bugungi Hisobot"), KeyboardButton("🏭 Ombor Nazorati")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_client_keyboard():
    """Mijoz uchun pastki menyu"""
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


def main():
    app = Application.builder().token(BOT_TOKEN).build()

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
                CallbackQueryHandler(get_product),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_product),
            ],
            TOTAL_PRICE: