"""
Google Sheets — OAuth2 autentifikatsiya
Railway uchun TOKEN_PICKLE_BASE64 environment variable dan o'qiydi
"""

import os
import pickle
import base64
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

TOKEN_FILE = "token.pickle"
CREDENTIALS_FILE = "credentials.json"

SALE_HEADERS = [
    "ID", "Sana", "FIO", "Telefon", "Tovar",
    "Jami Summa", "Boshlang'ich To'lov", "Qoldiq",
    "To'lov Turi", "Muddat", "To'lov Summasi",
    "Keyingi To'lov Sanasi", "Agent", "Holat",
    "Reyting", "Tug'ilgan Kun", "Izoh", "Kredit Bonusu",
    "Ish Joyi", "To'lov Kuni", "To'langan Summa"
]
PAYMENT_HEADERS = [
    "ID", "Savdo ID", "FIO", "Telefon",
    "To'lov Summasi", "To'lov Sanasi", "Qoldiq"
]
CLIENT_HEADERS = [
    "FIO", "Telefon", "Chat ID", "Telegram Username",
    "Jami Savdolar", "Muvaffaqiyatli Yopilgan", "Kredit Bali",
    "Status", "Tug'ilgan Kun", "Ro'yxatga Olingan Sana",
    "Ish Joyi", "Oxirgi Faollik", "Eslatma Oladi"
]


def get_sheets_client():
    """OAuth2 orqali Google Sheets clientini qaytaradi"""
    creds = None

    # 1. Environment variable dan token o'qish (Railway uchun)
    token_b64 = os.getenv("TOKEN_PICKLE_BASE64")
    if token_b64:
        try:
            # BEGIN/END CERTIFICATE qatorlarini tozalash
            clean = token_b64.replace("-----BEGIN CERTIFICATE-----", "")
            clean = clean.replace("-----END CERTIFICATE-----", "")
            clean = clean.replace("\r\n", "").replace("\n", "").replace(" ", "")
            token_bytes = base64.b64decode(clean)
            creds = pickle.loads(token_bytes)
        except Exception as e:
            print(f"Token o'qishda xato: {e}")

    # 2. Lokal token.pickle dan o'qish
    if creds is None and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    # 3. Token yangilash yoki yangi login
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, "wb") as f:
                    pickle.dump(creds, f)
        except Exception as e:
            print(f"Token yangilashda xato: {e}")
            creds = None

    if creds is None:
        raise Exception(
            "Google token eskirgan. TOKEN_PICKLE_BASE64 ni qayta yarating."
        )

    return gspread.authorize(creds)


def get_spreadsheet():
    client = get_sheets_client()
    sheet_id = os.getenv("SPREADSHEET_ID")
    if sheet_id:
        return client.open_by_key(sheet_id)
    sh = client.create("TexnoVibe Nasiya Baza")
    print(f"\n✅ Yangi spreadsheet: SPREADSHEET_ID={sh.id}\n")
    return sh


def ensure_worksheets(sh):
    needed = ["Savdolar", "Tolovlar", "Mijozlar"]
    existing = [ws.title for ws in sh.worksheets()]
    for name in needed:
        if name not in existing:
            ws = sh.add_worksheet(title=name, rows=1000, cols=20)
            if name == "Savdolar":
                ws.append_row(SALE_HEADERS)
                ws.format("A1:R1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}})
            elif name == "Tolovlar":
                ws.append_row(PAYMENT_HEADERS)
                ws.format("A1:G1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.3, "green": 0.8, "blue": 0.5}})
            elif name == "Mijozlar":
                ws.append_row(CLIENT_HEADERS)
                ws.format("A1:J1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.2}})
    return {name: sh.worksheet(name) for name in needed}


def generate_sale_id(ws_sales):
    records = ws_sales.get_all_values()
    if len(records) <= 1:
        return "TXN-001"
    last_row = records[-1]
    if last_row[0].startswith("TXN-"):
        num = int(last_row[0].split("-")[1]) + 1
        return f"TXN-{num:03d}"
    return f"TXN-{len(records):03d}"


def add_sale(sale_data: dict) -> dict:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws_sales = sheets["Savdolar"]
    ws_clients = sheets["Mijozlar"]
    today = date.today()
    sale_id = generate_sale_id(ws_sales)
    remaining = float(sale_data["total_price"]) - float(sale_data.get("down_payment", 0))
    period = int(sale_data["installment_period"])
    payment_per_period = round(remaining / period)
    import calendar
    if sale_data["payment_type"] == "Haftalik":
        pay_day = int(sale_data.get("pay_day", 0) or 0)
        if pay_day > 0:
            # Keyingi to'lov kuniga (haftaning kuni 1=Dushanba) o'tamiz
            days_ahead = pay_day - today.isoweekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_payment = today + timedelta(days=days_ahead)
        else:
            next_payment = today + timedelta(weeks=1)
            sale_data["pay_day"] = next_payment.isoweekday()
    else:
        pay_day = int(sale_data.get("pay_day", 0) or 0)
        if pay_day > 0:
            next_month = today.month + 1 if today.month < 12 else 1
            next_year = today.year if today.month < 12 else today.year + 1
            max_day = calendar.monthrange(next_year, next_month)[1]
            actual_day = min(pay_day, max_day)
            from datetime import date as date_cls
            next_payment = date_cls(next_year, next_month, actual_day)
        else:
            next_payment = today + timedelta(days=30)
    row = [
        sale_id, today.strftime("%d.%m.%Y"), sale_data["fio"], sale_data["phone"],
        sale_data["product"], float(sale_data["total_price"]), float(sale_data.get("down_payment", 0)),
        remaining, sale_data["payment_type"], period, payment_per_period,
        next_payment.strftime("%d.%m.%Y"), sale_data.get("agent", ""), "Faol", "🟡 Yangi",
        sale_data.get("birthday", ""), "", 0,
        sale_data.get("work_place", ""),
        sale_data.get("pay_day", ""),
        float(sale_data.get("down_payment", 0))  # Tolangan summa (avansdan boshlanadi)
    ]
    ws_sales.append_row(row)
    update_client_db(ws_clients, sale_data)
    schedule = generate_payment_schedule(remaining, payment_per_period, sale_data["payment_type"], period, next_payment)
    return {"sale_id": sale_id, "remaining": remaining, "payment_per_period": payment_per_period,
            "next_payment": next_payment.strftime("%d.%m.%Y"), "schedule": schedule}


def generate_payment_schedule(remaining, per_payment, pay_type, periods, start_date):
    """start_date = birinchi to'lov sanasi"""
    schedule = []
    current_date = start_date
    current_remaining = remaining
    for i in range(1, periods + 1):
        payment = min(per_payment, current_remaining)
        current_remaining -= payment
        schedule.append({"num": i, "date": current_date.strftime("%d.%m.%Y"), "amount": payment, "remaining": max(0, current_remaining)})
        current_date = current_date + (timedelta(weeks=1) if pay_type == "Haftalik" else timedelta(days=30))
    return schedule



def ws_to_records(ws):
    """get_all_records() muqobili — sarlavha muammosisiz"""
    values = ws.get_all_values()
    if len(values) < 2:
        return []
    headers = values[0]
    result = []
    for row in values[1:]:
        rec = {}
        for j, h in enumerate(headers):
            rec[h] = row[j] if j < len(row) else ""
        result.append(rec)
    return result

def safe_float(val, default=0):
    """Xavfsiz float konversiya"""
    try:
        v = str(val).replace(" ", "").replace(",", "").strip()
        return float(v) if v else default
    except:
        return default


def normalize_phone(phone: str) -> str:
    """Telefon raqamini standart formatga keltiradi: faqat raqamlar, 998XXXXXXXXX"""
    p = str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()
    # 998 bilan boshlanmasa, qo'shamiz
    if p.startswith("998") and len(p) == 12:
        return p
    if len(p) == 9:  # 901234567
        return "998" + p
    return p


def record_payment(phone: str, amount: float, row_index: int = None) -> dict:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws_sales = sheets["Savdolar"]
    ws_payments = sheets["Tolovlar"]
    all_values = ws_sales.get_all_values()
    target_row = None
    phone_clean = normalize_phone(phone)

    if len(all_values) < 2:
        return {"success": False, "error": "Baza bo'sh"}

    headers = all_values[0]

    def col(name):
        try:
            return headers.index(name)
        except ValueError:
            return -1

    # row_index berilgan bo'lsa — to'g'ridan o'sha qatorni ol
    if row_index is not None:
        row = all_values[row_index - 1]
        target_row = {h: (row[j] if j < len(row) else "") for j, h in enumerate(headers)}
        if normalize_phone(target_row.get("Telefon", "")) != phone_clean:
            return {"success": False, "error": "Telefon va qator mos kelmadi"}
        if target_row.get("Holat") != "Faol":
            return {"success": False, "error": "Bu savdo faol emas"}
    else:
        for i, row in enumerate(all_values[1:], start=2):
            def get(name, default=""):
                idx = col(name)
                if idx < 0 or idx >= len(row):
                    return default
                return row[idx] if row[idx] != "" else default
            if normalize_phone(get("Telefon")) == phone_clean:
                if get("Holat") == "Faol":
                    target_row = {h: (row[j] if j < len(row) else "") for j, h in enumerate(headers)}
                    row_index = i
                    break

    if not target_row:
        return {"success": False, "error": "Mijoz topilmadi yoki qarzi yoq"}
    old_remaining = safe_float(target_row.get("Qoldiq", 0))
    new_remaining = max(0, old_remaining - amount)
    today = date.today()
    pay_type = target_row.get("To'lov Turi", "Oylik")
    next_date = today + (timedelta(weeks=1) if pay_type == "Haftalik" else timedelta(days=30))
    ws_sales.update_cell(row_index, 8, new_remaining)
    ws_sales.update_cell(row_index, 12, next_date.strftime("%d.%m.%Y"))
    # Tolangan summani yangilash (21-ustun)
    old_paid = safe_float(target_row.get("To'langan Summa", 0))
    new_paid = old_paid + amount
    ws_sales.update_cell(row_index, 21, new_paid)
    if new_remaining == 0:
        ws_sales.update_cell(row_index, 14, "Yopildi")
        ws_sales.update_cell(row_index, 15, "🟢 Alo")
    # Bonus hisoblash:
    # - Oylik to'lovni to'liq to'lasa: oylik summaning 2%
    # - Oylikdan kam to'lasa: to'langan summaning 2%
    current_bonus = safe_float(target_row.get("Kredit Bonusu", 0))
    payment_per_period = safe_float(target_row.get("To'lov Summasi", 0))
    if amount >= payment_per_period:
        bonus_earned = round(payment_per_period * 0.02)
    else:
        bonus_earned = round(amount * 0.02)
    new_bonus = current_bonus + bonus_earned
    ws_sales.update_cell(row_index, 18, new_bonus)
    payment_records = ws_payments.get_all_values()
    pay_id = f"PAY-{max(0, len(payment_records)-1):04d}"
    ws_payments.append_row([pay_id, target_row.get("ID"), target_row.get("FIO"), phone, amount, today.strftime("%d.%m.%Y"), new_remaining])
    update_rating(ws_sales, row_index, today, target_row)
    return {"success": True, "fio": target_row.get("FIO"), "tovar": target_row.get("Tovar", ""), "paid": amount, "old_remaining": old_remaining,
            "new_remaining": new_remaining, "next_payment": next_date.strftime("%d.%m.%Y"),
            "is_closed": new_remaining == 0, "bonus": new_bonus, "chat_id": target_row.get("Chat ID", "")}


def update_rating(ws, row_index, today, record):
    try:
        next_pay = datetime.strptime(record.get("Keyingi To'lov Sanasi", ""), "%d.%m.%Y").date()
        days_diff = (today - next_pay).days
        rating = "🟢 Alo" if days_diff <= 0 else ("🟡 Ortacha" if days_diff <= 2 else "🔴 Xavfli")
        ws.update_cell(row_index, 15, rating)
    except:
        pass


def update_client_db(ws_clients, sale_data):
    all_values = ws_clients.get_all_values()
    phone = normalize_phone(sale_data["phone"])
    today_str = date.today().strftime("%d.%m.%Y")

    if len(all_values) > 1:
        headers = all_values[0]
        try:
            tel_idx = headers.index("Telefon")
        except ValueError:
            tel_idx = 1  # 2-ustun default

        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > tel_idx:
                row_phone = normalize_phone(row[tel_idx])
                if row_phone == phone:
                    try:
                        jami_idx = headers.index("Jami Savdolar")
                        total = safe_float(row[jami_idx]) + 1
                        ws_clients.update_cell(i, jami_idx + 1, int(total))
                    except (ValueError, IndexError):
                        pass
                    ws_clients.update_cell(i, 11, sale_data.get("work_place", ""))
                    ws_clients.update_cell(i, 12, today_str)
                    return

    ws_clients.append_row([
        sale_data["fio"],
        sale_data["phone"],
        "",   # Chat ID
        "",   # Username
        1,    # Jami savdolar
        0,    # Muvaffaqiyatli yopilgan
        0,    # Kredit bali
        "Bronze",
        sale_data.get("birthday", ""),
        today_str,
        sale_data.get("work_place", ""),
        today_str,
        "Yoq"  # Eslatma oladi
    ])


def check_duplicate(phone: str) -> dict:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Savdolar"]
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        return {"exists": False}
    headers = all_values[0]
    phone_clean = normalize_phone(phone)
    try:
        tel_idx = headers.index("Telefon")
        holat_idx = headers.index("Holat")
        fio_idx = headers.index("FIO")
        tovar_idx = headers.index("Tovar")
        qoldiq_idx = headers.index("Qoldiq")
    except ValueError:
        return {"exists": False}
    for row in all_values[1:]:
        if len(row) <= max(tel_idx, holat_idx, fio_idx, tovar_idx, qoldiq_idx):
            continue
        row_phone = normalize_phone(row[tel_idx])
        if row_phone == phone_clean and row[holat_idx] == "Faol":
            return {
                "exists": True,
                "fio": row[fio_idx],
                "product": row[tovar_idx],
                "remaining": row[qoldiq_idx]
            }
    return {"exists": False}


def get_today_payments() -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    today_str = date.today().strftime("%d.%m.%Y")
    return [r for r in ws_to_records(sheets["Savdolar"]) if r.get("Holat") == "Faol" and r.get("Keyingi To'lov Sanasi") == today_str]


def get_overdue_payments(days: int = 3) -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    today = date.today()
    result = []
    for rec in ws_to_records(sheets["Savdolar"]):
        if rec.get("Holat") != "Faol":
            continue
        try:
            next_pay = datetime.strptime(rec.get("Keyingi To'lov Sanasi", ""), "%d.%m.%Y").date()
            overdue_days = (today - next_pay).days
            if overdue_days >= days:
                rec["Kechikish Kunlari"] = overdue_days
                result.append(rec)
        except:
            pass
    return result


def get_payment_history(phone: str) -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    phone_clean = str(phone).replace(" ", "")
    return [r for r in ws_to_records(sheets["Tolovlar"]) if str(r.get("Telefon", "")).replace(" ", "") == phone_clean]


def get_all_clients_with_status() -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    active = [r for r in ws_to_records(sheets["Savdolar"]) if r.get("Holat") == "Faol"]
    return sorted(active, key=lambda x: x.get("Reyting", ""))


def get_statistics() -> dict:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    records = ws_to_records(sheets["Savdolar"])
    active = [r for r in records if r.get("Holat") == "Faol"]
    closed = [r for r in records if r.get("Holat") == "Yopildi"]
    return {
        "total_sales": len(records), "active": len(active), "closed": len(closed),
        "total_debt": sum(safe_float(r.get("Qoldiq", 0)) for r in active),
        "total_revenue": sum(safe_float(r.get("Jami Summa", 0)) for r in records),
        "overdue_count": len(get_overdue_payments(1)), "blacklist_count": len(get_overdue_payments(3))
    }


def save_client_chat_id(phone: str, chat_id: int, username: str = ""):
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Mijozlar"]
    phone_clean = str(phone).replace(" ", "")
    today_str = date.today().strftime("%d.%m.%Y")

    for i, rec in enumerate(ws_to_records(ws), start=2):
        if str(rec.get("Telefon", "")).replace(" ", "") == phone_clean:
            ws.update_cell(i, 3, chat_id)
            ws.update_cell(i, 4, username)
            ws.update_cell(i, 12, today_str)
            ws.update_cell(i, 13, "Ha")  # Eslatma oladi
            return True

    # Agar bazada yoq bolsa - yangi qator
    ws.append_row([
        "", phone, chat_id, username,
        0, 0, 0, "Bronze", "", today_str, "", today_str, "Ha"
    ])
    return False


def get_todays_birthdays() -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    today = date.today()
    today_md = f"{today.day:02d}.{today.month:02d}"
    return [r for r in ws_to_records(sheets["Savdolar"]) if str(r.get("Tug'ilgan Kun", ""))[:5] == today_md]


def get_client_chat_id(phone: str) -> str:
    """Telefon raqami orqali mijozning Chat ID sini topadi"""
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)

    # Telefon raqamini tozalash — faqat raqamlar
    phone_digits = str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()

    # Avval Mijozlar listidan qidirish
    for rec in ws_to_records(sheets["Mijozlar"]):
        rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "").strip()
        if rec_phone == phone_digits and str(rec.get("Chat ID", "")).strip():
            return str(rec.get("Chat ID", "")).strip()

    # Topilmasa Savdolar listidan qidirish (Chat ID ustuni bor bolsa)
    for rec in ws_to_records(sheets["Savdolar"]):
        rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "").strip()
        if rec_phone == phone_digits:
            chat_id = str(rec.get("Chat ID", "")).strip()
            if chat_id:
                return chat_id

    return ""


def get_sheet(sheet_name: str):
    """Katalog kabi qo'shimcha varaqlarni oladi yoki yaratadi"""
    import gspread
    sh = get_spreadsheet()
    try:
        return sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=500, cols=10)
        if sheet_name == "Katalog":
            ws.append_row(["ID", "Tovar Nomi", "Narx", "Tavsif", "PhotoID", "Holat", "Qoshilgan Sana"])
            ws.format("A1:G1", {"textFormat": {"bold": True}})
        return ws
