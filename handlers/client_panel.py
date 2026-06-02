"""
TexnoVibe — Mijoz paneli
Bekor qilingan savdolarning to'lovlarini hisobga olmaydigan, faqat faol savdo ID-lariga 
tegishli to'lovlarni sanasi bilan ko'rsatuvchi mukammal variant.
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    save_client_chat_id, ws_to_records
)
from datetime import date
import os

REGISTER_PHONE = 40

def safe_float(val):
    try:
        if not val:
            return 0.0
        clean_val = "".join(c for c in str(val) if c.isdigit() or c in [".", "-"])
        return float(clean_val)
    except:
        return 0.0


def format_money(amount) -> str:
    try:
        if not amount or str(amount).strip() in ["", "-", "0"]:
            return "0"
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def find_dynamic_key(record, keys):
    """Sarlavha kalit so'zlarga qarab record ichidan to'g'ri kalitni topadi"""
    if not record:
        return None
    for r_key in record.keys():
        r_key_lower = str(r_key).strip().lower()
        for key in keys:
            if key in r_key_lower:
                return r_key
    return None


def get_client_keyboard():
    keyboard = [
        [KeyboardButton("📊 Mening Nasiyam")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ro'yxatdan o'tish — telefon so'raydi"""
    await update.message.reply_text(
        "📝 *Royxatdan otish*\n\n"
        "Telefon raqamingizni yozing:\n"
        "_(Masalan: 998901234567 yoki +998901234567)_",
        parse_mode="Markdown"
    )
    return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telefon raqamini qabul qiladi va bazada tekshiradi"""
    phone_input = update.message.text.strip()
    user = update.effective_user
    chat_id = user.id
    username = user.username or ""

    phone_clean = phone_input.replace("+", "").replace(" ", "").replace("-", "")

    if not phone_clean.isdigit() or len(phone_clean) < 9:
        await update.message.reply_text(
            "❌ Telefon raqami noto'g'ri.\n"
            "Qaytadan kiriting:\n"
            "_(Masalan: 998901234567)_",
            parse_mode="Markdown"
        )
        return REGISTER_PHONE

    if not phone_input.startswith("+"):
        phone = "+" + phone_clean
    else:
        phone = phone_input

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_sales = sheets["Savdolar"]
        records = ws_to_records(ws_sales)

        found_rec = None
        for rec in records:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            if rec_phone == phone_clean and rec.get("Holat") == "Faol":
                found_rec = rec
                break

        if not found_rec:
            await update.message.reply_text(
                f"❌ `{phone}` raqami bazada topilmadi.\n\n"
                "Telefon raqamingiz to'g'riligini tekshiring\n"
                "yoki do'konimizga murojaat qiling.\n\n"
                "Qaytadan kiriting:",
                parse_mode="Markdown"
            )
            return REGISTER_PHONE

        save_client_chat_id(phone, chat_id, username)

        fio = found_rec.get("FIO", "")
        tovar = found_rec.get("Tovar", "")
        qoldiq = format_money(found_rec.get("Qoldiq", 0))
        keyingi = found_rec.get("Keyingi To'lov Sanasi", "")

        await update.message.reply_text(
            f"✅ *Muvaffaqiyatli royxatdan otdingiz!*\n\n"
            f"👤 Ism: *{fio}*\n"
            f"📞 Telefon: `{phone}`\n\n"
            f"📋 *Joriy kredit:*\n"
            f"🛍 {tovar}\n"
            f"💰 Qoldiq: *{qoldiq} so'm*\n"
            f"📅 Keyingi to'lov: *{keyingi}*\n\n"
            f"Endi to'lov eslatmalarini olasiz!\n"
            f"🏪 TexnoVibe",
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Bosh menyuga qaytildi.",
        reply_markup=get_client_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        context.args = args
        await register_phone(update, context)
    else:
        await start_register(update, context)


async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijoz 'Mening Nasiyam' tugmasini bosganda"""
    chat_id = update.effective_user.id
    status_msg = await update.message.reply_text("⏳ Ma'lumotlaringiz yangilanmoqda...")

    try:
        sh = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        ws_clients = sheets["Mijozlar"]
        ws_sales = sheets["Savdolar"]

        client_records = ws_to_records(ws_clients)
        phone = None
        fio = None

        for rec in client_records:
            if str(rec.get("Chat ID", "")).strip() == str(chat_id):
                phone = str(rec.get("Telefon", ""))
                fio = rec.get("FIO", "")
                break

        if not phone:
            await status_msg.edit_text(
                "❌ Siz hali royxatdan otmagansiz!\n\n"
                "Royxatdan otish tugmasini bosing.",
                reply_markup=get_client_keyboard()
            )
            return

        sale_records = ws_to_records(ws_sales)
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        active_sales = []
        allowed_sale_ids = set() # Faqat bekor qilinmagan savdolarning ID raqamlarini saqlash uchun to'plam

        # 1. Savdolarni tekshiramiz va bekor bo'lmaganlarning ID larini yig'amiz
        for rec in sale_records:
            rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "")
            if rec_phone == phone_clean:
                holat = str(rec.get("Holat", "")).strip().lower()
                if "bekor" in holat:
                    continue # Bekor bo'lgan shartnomani tashlab ketamiz
                
                active_sales.append(rec)
                
                # Savdo ID'sini aniqlaymiz va allowed_sale_ids ga qo'shamiz
                id_key = find_dynamic_key(rec, ["id", "savdo id", "txn"]) or "ID"
                s_id = str(rec.get(id_key, "")).strip()
                if s_id:
                    allowed_sale_ids.add(s_id)

        if not active_sales:
            await status_msg.edit_text(
                f"👤 *{fio}*\n\n"
                "📋 Hozirda faol kreditingiz yo'q.\n\n"
                "🏪 TexnoVibe",
                parse_mode="Markdown",
                reply_markup=get_client_keyboard()
            )
            return

        text = f"👤 *{fio}*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in active_sales:
            holat = rec.get("Holat", "")
            holat_emoji = "✅" if holat == "Yopildi" else "🔄"

            tovar = rec.get("Tovar", "")
            jami = format_money(rec.get("Jami Summa", 0))
            qoldiq = format_money(rec.get("Qoldiq", 0))
            tolov_turi = rec.get("To'lov Turi", "")
            tolov_summasi = format_money(rec.get("To'lov Summasi", 0))
            keyingi = rec.get("Keyingi To'lov Sanasi", "")
            reyting = rec.get("Reyting", "")
            bonus = format_money(rec.get("Kredit Bonusu", 0))

            text += (
                f"{holat_emoji} *{tovar}*\n"
                f"💵 Jami: *{jami} so'm*\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"📅 {tolov_turi} | 💳 {tolov_summasi} so'm\n"
                f"📆 Keyingi to'lov: *{keyingi}*\n"
                f"⭐ Reyting: {reyting}\n"
                f"🎁 Bonus: *{bonus} so'm*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
            )

        # 🚀 TO'LOVLAR TARIXINI TO'G'RI (SAVDO ID BILAN) FILTRLAB CHIQARISH QISMI
        text += f"📋 *SO'NGGI TO'LOVLAR:*\n"
        
        try:
            try:
                ws_kassa = sh.worksheet("Kassa")
            except:
                ws_kassa = sh.worksheet("To'lovlar")
                
            kassa_records = ws_to_records(ws_kassa)
            client_history = []
            
            if kassa_records:
                sample_k = kassa_records[0]
                k_phone_key = find_dynamic_key(sample_k, ["tel", "telefon", "nomer"]) or "Telefon"
                k_val_key = find_dynamic_key(sample_k, ["summa", "to'lov summasi", "tolov summasi", "miqdor", "berdi"]) or "To'lov Summasi"
                k_date_key = find_dynamic_key(sample_k, ["sana", "to'lov sanasi", "tolov sanasi", "vaqt"]) or "To'lov Sanasi"
                k_id_key = find_dynamic_key(sample_k, ["id", "savdo id", "shartnoma"]) or "Savdo ID"
                
                for r in kassa_records:
                    k_phone = str(r.get(k_phone_key, "")).replace("+", "").replace(" ", "").replace("-", "")
                    k_sale_id = str(r.get(k_id_key, "")).strip()
                    
                    # 🛑 CRITICAL CHECK: Telefon to'g'ri kelsa VA ushbu to'lov BEKOR BO'LMAGAN Savdo ID ga tegishli bo'lsagina ro'yxatga qo'shamiz!
                    if k_phone == phone_clean:
                        # Agar jadvalda Savdo ID yozilgan bo'lsa va u faol ID larning ichida bo'lmasa — o'tkazib yuboramiz!
                        if k_sale_id and allowed_sale_ids and (k_sale_id not in allowed_sale_ids):
                            continue
                            
                        client_history.append({
                            "sana": r.get(k_date_key, ""),
                            "summa": safe_float(r.get(k_val_key, 0))
                        })
            
            if client_history:
                total_paid = sum(item["summa"] for item in client_history)
                for item in client_history[-5:]:
                    text += f"• {item['sana']} — *{format_money(item['summa'])} so'm*\n"
                text += f"\n✅ Jami tolangan: *{format_money(total_paid)} so'm*\n"
            else:
                text += "• Hozircha amaldagi shartnomalar uchun to'lovlar mavjud emas.\n\n✅ Jami tolangan: *0 so'm*\n"
                
        except Exception as history_err:
            text += "• To'lovlar tarixi yuklanmoqda...\n"
            from sheets.google_sheets import get_payment_history
            history = get_payment_history(phone)
            if history:
                sample_rec = history[0]
                val_key = find_dynamic_key(sample_rec, ["summa", "to'lov summasi"]) or "To'lov Summasi"
                date_key = find_dynamic_key(sample_rec, ["sana", "to'lov sanasi"]) or "To'lov Sanasi"
                total_paid = sum(safe_float(r.get(val_key, 0)) for r in history)
                for r in history[-5:]:
                    text += f"• {r.get(date_key, "")} — *{format_money(r.get(val_key, 0))} so'm*\n"
                text += f"\n✅ Jami tolangan: *{format_money(total_paid)} so'm*\n"
            else:
                text += "\n✅ Jami tolangan: *0 so'm*\n"

        text += "\n🏪 TexnoVibe"

        await status_msg.delete()
        await update.message.reply_text(
            text,
            parse