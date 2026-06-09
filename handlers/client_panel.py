"""
Mijoz paneli
Yangilik:
  - Ro'yxatdan o'tgan foydalanuvchi qayta bosса — tasdiq xabari
  - Kontakt tugmasi bilan avtomatik telefon yuborish
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets.google_sheets import (
    get_spreadsheet, ensure_worksheets,
    get_payment_history, save_client_chat_id, ws_to_records
)
from datetime import datetime, timedelta, date
import os


def generate_schedule(remaining, per_payment, pay_type, periods,
                      next_payment_str, pay_day=None,
                      first_payment=None, base_payment=None) -> str:
    """
    remaining     — hozirgi qoldiq
    per_payment   — joriy keyingi to'lov (ortiqcha/kamdan keyin yangilangan)
    base_payment  — ASAL oylik miqdor (har oy shu miqdor, o'zgarmaydi)
    first_payment — 1-to'lov miqdori (= per_payment)
    """
    import calendar
    try:
        current = datetime.strptime(next_payment_str, "%d.%m.%Y").date()
    except Exception:
        return ""

    tolov_kun = int(pay_day) if pay_day else current.day

    # Asl oylik — 2-oydan boshlab shu miqdor ishlatiladi
    asl = float(base_payment) if base_payment and float(base_payment) > 0 \
          else float(per_payment) if float(per_payment) > 0 else float(remaining)
    # 1-to'lov (joriy, ortiqcha/kamdan keyin)
    birinchi = float(per_payment) if float(per_payment) > 0 else asl

    lines = ["\n📅 *To'lov jadvali:*"]
    current_remaining = float(remaining)
    i = 0

    while current_remaining > 0:
        i += 1
        payment = min(birinchi if i == 1 else asl, current_remaining)
        current_remaining = max(0, current_remaining - payment)

        lines.append(
            f"`{i:2}.` {current.strftime('%d.%m.%Y')} — "
            f"*{int(payment):,}* so'm "
            f"(qoldiq: {int(current_remaining):,})".replace(",", " ")
        )

        if pay_type == "Haftalik":
            current += timedelta(weeks=1)
        else:
            month = current.month + 1 if current.month < 12 else 1
            year  = current.year if current.month < 12 else current.year + 1
            max_day = calendar.monthrange(year, month)[1]
            current = date(year, month, min(tolov_kun, max_day))

        if i >= 60:  # xavfsizlik limiti
            break

    return "\n".join(lines)

REGISTER_PHONE = 40


def safe_float(val):
    try:
        return float(str(val).replace(" ", "").replace(",", "").strip() or 0)
    except:
        return 0


def format_money(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)


def get_client_keyboard():
    keyboard = [
        [KeyboardButton("📊 Mening Nasiyam")],
        [KeyboardButton("📝 Ro'yxatdan O'tish")],
        [KeyboardButton("🛍 Katalog")],
        [KeyboardButton("🛒 Buyurtma Berish")],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_contact_keyboard():
    """Kontakt yuborish tugmasi"""
    keyboard = [
        [KeyboardButton("📱 Raqamimni yuborish", request_contact=True)],
        [KeyboardButton("🏠 Bosh Menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def is_registered(chat_id: int) -> dict | None:
    """Foydalanuvchi ro'yxatdan o'tganmi — chat_id bo'yicha"""
    try:
        sh     = get_spreadsheet()
        sheets = ensure_worksheets(sh)
        cid    = str(chat_id).strip()

        for sheet_name in ["Mijozlar", "Savdolar"]:
            try:
                all_val = sheets[sheet_name].get_all_values()
                if len(all_val) < 2:
                    continue
                headers = [h.strip() for h in all_val[0]]
                for row in all_val[1:]:
                    row_vals = [str(v).strip() for v in row]
                    if cid in row_vals:
                        rec   = dict(zip(headers, row_vals))
                        phone = rec.get("Telefon", "").replace(" ", "")
                        fio   = rec.get("FIO", "")
                        if phone:
                            return {"Chat ID": cid, "Telefon": phone, "FIO": fio}
            except Exception:
                continue
    except Exception:
        pass
    return None


async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_user.id
    registered = is_registered(chat_id)

    if registered:
        # Allaqachon ro'yxatdan o'tgan
        phone = registered.get("Telefon", "")
        fio   = registered.get("FIO", "")

        # Barcha nasiyalarni ko'rsatish
        try:
            sh          = get_spreadsheet()
            sheets      = ensure_worksheets(sh)
            records     = ws_to_records(sheets["Savdolar"])
            phone_clean = phone.replace("+","").replace(" ","").replace("-","")

            korsatish = [
                r for r in records
                if str(r.get("Telefon","")).replace("+","").replace(" ","").replace("-","") == phone_clean
                and str(r.get("Holat","")).strip() != "Bekor qilindi"
            ]

            text = (
                f"✅ *Siz allaqachon ro'yxatdan o'tgansiz!*\n\n"
                f"👤 Ism: *{fio}*\n"
                f"📞 Telefon: `{phone}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
            )

            if korsatish:
                for rec in korsatish:
                    holat       = str(rec.get("Holat","")).strip()
                    holat_emoji = "✅" if holat == "Yopildi" else "🔄"
                    tovar       = rec.get("Tovar", "")
                    jami        = format_money(rec.get("Jami Summa", 0))
                    qoldiq      = format_money(rec.get("Qoldiq", 0))
                    tolangan    = format_money(rec.get("To'langan Summa", 0))
                    oylik       = format_money(rec.get("To'lov Summasi", rec.get("Oylik To'lov", 0)))
                    tolov_turi  = rec.get("To'lov Turi", "")
                    keyingi     = rec.get("Keyingi To'lov Sanasi", "")
                    bonus       = format_money(rec.get("Kredit Bonusu", 0))
                    reyting     = rec.get("Reyting", "")

                    # To'lov grafigi
                    if holat == "Faol":
                        # Asl oylik = (Jami - Avans) / Muddat
                        try:
                            _jami   = safe_float(rec.get("Jami Summa", 0))
                            _avans  = safe_float(rec.get("Boshlang'ich To'lov", 0))
                            _muddat = int(str(rec.get("Muddat", 1)).replace(" ", "") or 1)
                            asl_oylik = round((_jami - _avans) / _muddat) if _muddat > 0 else 0
                        except Exception:
                            asl_oylik = None
                        jadval = generate_schedule(
                            remaining=rec.get("Qoldiq", 0),
                            per_payment=rec.get("To'lov Summasi", rec.get("Oylik To'lov", 0)),
                            pay_type=tolov_turi,
                            periods=rec.get("Muddat", 0),
                            next_payment_str=keyingi,
                            pay_day=rec.get("To'lov Kuni", None),
                            first_payment=rec.get("To'lov Summasi", None),
                            base_payment=asl_oylik
                        )
                    else:
                        jadval = ""

                    text += (
                        f"{holat_emoji} *{tovar}*\n"
                        f"💵 Jami: *{jami} so'm*\n"
                        f"✅ To'langan: *{tolangan} so'm*\n"
                        f"💰 Qoldiq: *{qoldiq} so'm*\n"
                        f"📅 {tolov_turi} | 💳 Oylik: *{oylik} so'm*\n"
                        f"📆 Keyingi to'lov: *{keyingi}*\n"
                        f"⭐ Reyting: {reyting}\n"
                        f"🎁 Bonus: *{bonus} so'm*\n"
                    )
                    if jadval:
                        text += jadval + "\n"
                    text += "━━━━━━━━━━━━━━━━━━━━\n"
                    
            else:
                text += "📋 Hozirda faol kreditingiz yo'q.\n━━━━━━━━━━━━━━━━━━━━\n"

            text += "\n🏪 TexnoVibe"
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_client_keyboard())

        except Exception as e:
            await update.message.reply_text(
                f"✅ *Siz allaqachon ro'yxatdan o'tgansiz!*\n\n👤 {fio} | 📞 {phone}",
                parse_mode="Markdown",
                reply_markup=get_client_keyboard()
            )
        return ConversationHandler.END

    # Yangi foydalanuvchi — kontakt tugmasi bilan
    await update.message.reply_text(
        "📝 *Ro'yxatdan o'tish*\n\n"
        "Pastdagi tugmani bosib telefon raqamingizni yuboring 👇\n\n"
        "_(Yoki qo'lda ham yozishingiz mumkin)_",
        parse_mode="Markdown",
        reply_markup=get_contact_keyboard()
    )
    return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    chat_id  = user.id
    username = user.username or ""

    # Kontakt yuborilgan bo'lsa
    if update.message.contact:
        phone_input = update.message.contact.phone_number or ""
        phone_clean = phone_input.replace("+", "").replace(" ", "").replace("-", "")
    else:
        # Qo'lda yozilgan
        phone_input = update.message.text.strip()
        phone_clean = phone_input.replace("+", "").replace(" ", "").replace("-", "")

    if not phone_clean.isdigit() or len(phone_clean) < 9:
        await update.message.reply_text(
            "❌ Telefon raqami noto'g'ri.\nQaytadan kiriting:",
            reply_markup=get_contact_keyboard()
        )
        return REGISTER_PHONE

    phone = ("+" + phone_clean) if not phone_input.startswith("+") else phone_input

    try:
        sh      = get_spreadsheet()
        sheets  = ensure_worksheets(sh)
        records = ws_to_records(sheets["Savdolar"])

        found_rec = None
        for rec in records:
            rec_phone = str(rec.get("Telefon", "")).replace("+","").replace(" ","").replace("-","")
            if rec_phone == phone_clean and str(rec.get("Holat","")).strip() == "Faol":
                found_rec = rec
                break

        if not found_rec:
            await update.message.reply_text(
                f"❌ `{phone}` raqami bazada topilmadi.\n\n"
                "Telefon raqamingiz to'g'riligini tekshiring\n"
                "yoki do'konimizga murojaat qiling.\n\nQaytadan kiriting:",
                parse_mode="Markdown",
                reply_markup=get_contact_keyboard()
            )
            return REGISTER_PHONE

        # To'g'ridan Mijozlar varag'iga yozish
        try:
            from datetime import date as _date
            ws_mij     = sheets["Mijozlar"]
            all_rows   = ws_mij.get_all_values()
            today_str  = _date.today().strftime("%d.%m.%Y")
            found_row  = None

            for i, row in enumerate(all_rows[1:], start=2):
                r_phone = str(row[1] if len(row) > 1 else "").replace("+","").replace(" ","").replace("-","")
                if r_phone == phone_clean:
                    found_row = i
                    break

            if found_row:
                ws_mij.update_cell(found_row, 3, str(chat_id))
                ws_mij.update_cell(found_row, 4, username or "")
            else:
                # Yangi qator — faqat asosiy ustunlar
                fio_val = found_rec.get("FIO", "")
                ws_mij.append_row([
                    fio_val, phone, str(chat_id), username or "",
                    1, 0, 0, "Bronze", "", today_str, "", today_str, "Ha"
                ])
                # Agar append_row ustun soni tufayli xato bersa — cell update bilan yozish
        except Exception as e:
            # append_row ishlamasa — yangi qator cell bilan yozamiz
            try:
                from datetime import date as _date
                ws_mij    = sheets["Mijozlar"]
                next_row  = len(ws_mij.get_all_values()) + 1
                ws_mij.update_cell(next_row, 1, found_rec.get("FIO", ""))
                ws_mij.update_cell(next_row, 2, phone)
                ws_mij.update_cell(next_row, 3, str(chat_id))
                ws_mij.update_cell(next_row, 4, username or "")
            except Exception as e2:
                import logging
                logging.getLogger(__name__).error(f"Yozishda xato: {e} | {e2}")
                await update.message.reply_text(f"⚠️ Saqlashda xato: {str(e2)}")

        fio     = found_rec.get("FIO", "")
        tovar   = found_rec.get("Tovar", "")
        qoldiq  = format_money(found_rec.get("Qoldiq", 0))
        keyingi = found_rec.get("Keyingi To'lov Sanasi", "")

        await update.message.reply_text(
            f"✅ *Muvaffaqiyatli ro'yxatdan o'tdingiz!*\n\n"
            f"👤 Ism: *{fio}*\n"
            f"📞 Telefon: `{phone}`\n\n"
            f"📋 *Joriy kredit:*\n"
            f"🛍 {tovar}\n"
            f"💰 Qoldiq: *{qoldiq} so'm*\n"
            f"📅 Keyingi to'lov: *{keyingi}*\n\n"
            f"Endi to'lov eslatmalarini olasiz! 🔔\n"
            f"🏪 TexnoVibe",
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: `{str(e)}`",
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 Bosh menyuga qaytildi.", reply_markup=get_client_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_register(update, context)


async def cmd_mening_malumotlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id

    try:
        sh      = get_spreadsheet()
        sheets  = ensure_worksheets(sh)

        phone = None
        fio   = None

        # Mijozlar varag'idan chat_id bo'yicha qidirish
        try:
            ws_mij  = sheets["Mijozlar"]
            all_mij = ws_mij.get_all_values()
            if len(all_mij) > 1:
                headers = [h.strip() for h in all_mij[0]]
                for row in all_mij[1:]:
                    row_vals = [str(v).strip() for v in row]
                    if str(chat_id) in row_vals:
                        rec = dict(zip(headers, row_vals))
                        phone = rec.get("Telefon", "").replace(" ", "")
                        fio   = rec.get("FIO", "")
                        if phone:
                            break
        except Exception:
            pass

        # Topilmasa — Savdolar varag'idan qidirish
        if not phone:
            try:
                ws_sav  = sheets["Savdolar"]
                all_sav = ws_sav.get_all_values()
                if len(all_sav) > 1:
                    headers = [h.strip() for h in all_sav[0]]
                    for row in all_sav[1:]:
                        row_vals = [str(v).strip() for v in row]
                        if str(chat_id) in row_vals:
                            rec   = dict(zip(headers, row_vals))
                            phone = rec.get("Telefon", "").replace(" ", "")
                            fio   = rec.get("FIO", "")
                            if phone:
                                break
            except Exception:
                pass

        if not phone:
            await update.message.reply_text(
                "❌ Siz hali ro'yxatdan o'tmagansiz!\n\nRo'yxatdan o'tish tugmasini bosing.",
                reply_markup=get_client_keyboard()
            )
            return

        phone_clean = phone.replace("+","").replace(" ","").replace("-","")
        all_sales   = ws_to_records(sheets["Savdolar"])

        # Bekor qilinganlar chiqmaydi
        korsatish = [
            r for r in all_sales
            if str(r.get("Telefon","")).replace("+","").replace(" ","").replace("-","") == phone_clean
            and str(r.get("Holat","")).strip() != "Bekor qilindi"
        ]

        if not korsatish:
            await update.message.reply_text(
                f"👤 *{fio}*\n\n📋 Hozirda faol kreditingiz yo'q.\n\n🏪 TexnoVibe",
                parse_mode="Markdown",
                reply_markup=get_client_keyboard()
            )
            return

        text = f"👤 *{fio}*\n📞 `{phone}`\n━━━━━━━━━━━━━━━━━━━━\n"

        for rec in korsatish:
            holat        = str(rec.get("Holat","")).strip()
            holat_emoji  = "✅" if holat == "Yopildi" else "🔄"
            tovar        = rec.get("Tovar", "")
            jami         = format_money(rec.get("Jami Summa", 0))
            qoldiq       = format_money(rec.get("Qoldiq", 0))
            tolov_turi   = rec.get("To'lov Turi", "")
            oylik        = format_money(rec.get("To'lov Summasi", rec.get("Oylik To'lov", 0)))
            keyingi      = rec.get("Keyingi To'lov Sanasi", "")
            reyting      = rec.get("Reyting", "")
            bonus        = format_money(rec.get("Kredit Bonusu", 0))
            tolangan     = format_money(rec.get("To'langan Summa", 0))

            # To'lov grafigi
            if holat == "Faol":
                try:
                    _jami   = safe_float(rec.get("Jami Summa", 0))
                    _avans  = safe_float(rec.get("Boshlang'ich To'lov", 0))
                    _muddat = int(str(rec.get("Muddat", 1)).replace(" ", "") or 1)
                    asl_oylik = round((_jami - _avans) / _muddat) if _muddat > 0 else 0
                except Exception:
                    asl_oylik = None
                jadval = generate_schedule(
                    remaining=rec.get("Qoldiq", 0),
                    per_payment=rec.get("To'lov Summasi", rec.get("Oylik To'lov", 0)),
                    pay_type=tolov_turi,
                    periods=rec.get("Muddat", 0),
                    next_payment_str=keyingi,
                    pay_day=rec.get("To'lov Kuni", None),
                    first_payment=rec.get("To'lov Summasi", None),
                    base_payment=asl_oylik
                )
            else:
                jadval = ""

            text += (
                f"{holat_emoji} *{tovar}*\n"
                f"💵 Jami: *{jami} so'm*\n"
                f"✅ To'langan: *{tolangan} so'm*\n"
                f"💰 Qoldiq: *{qoldiq} so'm*\n"
                f"📅 {tolov_turi} | 💳 Oylik: *{oylik} so'm*\n"
                f"📆 Keyingi to'lov: *{keyingi}*\n"
                f"⭐ Reyting: {reyting}\n"
                f"🎁 Bonus: *{bonus} so'm*\n"
            )
            if jadval:
                text += jadval + "\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            

        # To'lovlar tarixi — faqat aktiv (Faol) savdolar uchun
        try:
            tolovlar    = ws_to_records(sheets["Tolovlar"])
            # Aktiv savdolarning ID larini olish
            faol_ids    = {
                str(r.get("ID","")).strip()
                for r in korsatish
                if str(r.get("Holat","")).strip() == "Faol"
            }
            mijoz_tolovlar = [
                r for r in tolovlar
                if str(r.get("Telefon","")).replace("+","").replace(" ","").replace("-","") == phone_clean
                and str(r.get("Savdo ID","")).strip() in faol_ids
            ]
            if mijoz_tolovlar:
                total_paid = sum(safe_float(r.get("To'lov Summasi", 0)) for r in mijoz_tolovlar)
                text += f"📋 *SO'NGGI TO'LOVLAR:*\n"
                for r in mijoz_tolovlar[-5:]:
                    sana  = r.get("To'lov Sanasi", "")
                    summa = format_money(r.get("To'lov Summasi", 0))
                    text += f"• {sana} — *{summa} so'm*\n"
                text += f"\n✅ Jami to'langan: *{format_money(total_paid)} so'm*\n"
        except Exception:
            pass

        text += "\n🏪 TexnoVibe"

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_client_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: `{str(e)}`", parse_mode="Markdown")
