"""
Google Sheets — OAuth2 autentifikatsiya
Railway uchun TOKEN_PICKLE_BASE64 environment variable dan o'qiydi
"""
import os
import pickle
import base64
import gspread
import calendar
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from sheets.google_sheets import normalize_phone
from helpers import normalize_phone
load_dotenv()

def normalize_phone(phone: str) -> str:
    """
    Telefon raqamidan ortiqcha belgilarni (plyus, probel, tire) olib tashlaydi.
    Masalan: "+998 90 123-45-67" -> "998901234567"
    """
    cleaned = str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()
    return cleaned

# Logger sozlamasi
logger = logging.getLogger(__name__)

import gspread

# qolgan kodlar...

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
    # credentials.json fayli asosiy papkada bo'lishi shart
    return gspread.service_account(filename='credentials.json')
	clean = token_b64.replace("-----BEGIN CERTIFICATE-----", "").replace("-----END 	CERTIFICATE-----","").replace("\r\n", "").replace("\n", "").replace(" ", "")
	token_bytes = base64.b64decode(clean)
	creds = pickle.loads(token_bytes)
except Exception as e:
	logger.error(f"Token o'qishda xato: {e}")

    if creds is None and os.path.exists(TOKEN_FILE):
    	with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        elif os.path.exists(CREDENTIALS_FILE):
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        else:
            raise Exception("Token topilmadi! TOKEN_PICKLE_BASE64 yoki credentials.json kerak.")

    return gspread.authorize(creds)

def get_spreadsheet():
    client = get_sheets_client()
    sheet_id = os.getenv("SPREADSHEET_ID")
    if sheet_id:
        return client.open_by_key(sheet_id)
    sh = client.create("TexnoVibe Nasiya Baza")
    return sh

def ensure_worksheets(sh):
    needed = ["Savdolar", "Tolovlar", "Mijozlar"]
    existing = [ws.title for ws in sh.worksheets()]
    for name in needed:
        if name not in existing:
            ws = sh.add_worksheet(title=name, rows=1000, cols=20)
            if name == "Savdolar":
                ws.append_row(SALE_HEADERS)
            elif name == "Tolovlar":
                ws.append_row(PAYMENT_HEADERS)
            elif name == "Mijozlar":
                ws.append_row(CLIENT_HEADERS)
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

def add_sale(data):
    try:
        gc = get_sheets_client()
        sheet = gc.open("Jadvalingiz_Nomi").sheet1
        sheet.append_row(data)
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")    
    if sale_data["payment_type"] == "Haftalik":
        pay_day = int(sale_data.get("pay_day", 0) or 0)
        if pay_day > 0:
            days_ahead = pay_day - today.isoweekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_payment = today + timedelta(days=days_ahead)
        else:
            next_payment = today + timedelta(weeks=1)
    else:
        pay_day = int(sale_data.get("pay_day", 0) or 0)
        if pay_day > 0:
            next_month = today.month + 1 if today.month < 12 else 1
            next_year = today.year if today.month < 12 else today.year + 1
            max_day = calendar.monthrange(next_year, next_month)[1]
            actual_day = min(pay_day, max_day)
            next_payment = date(next_year, next_month, actual_day)
        else:
            next_payment = today + timedelta(days=30)
            
    row = [sale_id, today.strftime("%d.%m.%Y"), sale_data["fio"], sale_data["phone"],
           sale_data["product"], float(sale_data["total_price"]), float(sale_data.get("down_payment", 0)),
           remaining, sale_data["payment_type"], period, payment_per_period,
           next_payment.strftime("%d.%m.%Y"), sale_data.get("agent", ""), "Faol", "🟡 Yangi",
           sale_data.get("birthday", ""), "", 0, sale_data.get("work_place", ""),
           sale_data.get("pay_day", ""), float(sale_data.get("down_payment", 0))]
    
    ws_sales.append_row(row)
    update_client_db(ws_clients, sale_data)
    
    return {"sale_id": sale_id}

def update_client_db(ws_clients, sale_data):
    all_values = ws_clients.get_all_values()
    phone = str(sale_data["phone"]).replace("+", "").replace(" ", "")
    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > 1 and str(row[1]).replace("+", "").replace(" ", "") == phone:
            return
    ws_clients.append_row([sale_data["fio"], sale_data["phone"], "", "", 1, 0, 0, "Bronze", sale_data.get("birthday", ""), date.today().strftime("%d.%m.%Y"), sale_data.get("work_place", ""), date.today().strftime("%d.%m.%Y"), "Yoq"])

def ws_to_records(ws):
    values = ws.get_all_values()
    if len(values) < 2: return []
    headers = values[0]
    return [dict(zip(headers, row)) for row in values[1:]]

def safe_float(val, default=0):
    try: return float(str(val).replace(" ", "").replace(",", "").strip())
    except: return default
# ─────────────────────────────────────────────────────────────
# record_payment — row_index parametri YANGI qo'shildi
# Agar row_index berilsa, o'sha qatorni yangilaydi (tovar aniq).
# Berilmasa, eskicha telefon bo'yicha birinchi faol savdoni topadi.
# ─────────────────────────────────────────────────────────────
def record_payment(phone: str, amount: float, row_index: int = None) -> dict:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws_sales    = sheets["Savdolar"]
    ws_payments = sheets["Tolovlar"]

    all_values  = ws_sales.get_all_values()
    if len(all_values) < 2:
        return {"success": False, "error": "Baza bo'sh"}

    headers = all_values[0]

    def col(name):
        try:
            return headers.index(name)
        except ValueError:
            return -1

    phone_clean = normalize_phone(phone)
    target_row  = None

    # ── row_index berilgan — to'g'ridan o'sha qatorni ol ──
    if row_index is not None:
        row = all_values[row_index - 1]   # all_values 0-indexed, row_index 1-indexed
        target_row = {h: (row[j] if j < len(row) else "") for j, h in enumerate(headers)}

        # Xavfsizlik tekshiruvi
        if normalize_phone(target_row.get("Telefon", "")) != phone_clean:
            return {"success": False, "error": "Telefon va qator mos kelmadi"}
        if target_row.get("Holat") != "Faol":
            return {"success": False, "error": "Bu savdo faol emas"}

    # ── row_index yo'q — eskicha birinchi faol savdoni top ──
    else:
        for i, row in enumerate(all_values[1:], start=2):
            def get(name, default=""):
                idx = col(name)
                if idx < 0 or idx >= len(row):
                    return default
                return row[idx] if row[idx] != "" else default

            if normalize_phone(get("Telefon")) == phone_clean and get("Holat") == "Faol":
                target_row = {h: (row[j] if j < len(row) else "") for j, h in enumerate(headers)}
                row_index  = i
                break

    if not target_row:
        return {"success": False, "error": "Mijoz topilmadi yoki qarzi yo'q"}

    # ── Hisob-kitob ──────────────────────────────────────────
    old_remaining = safe_float(target_row.get("Qoldiq", 0))
    new_remaining = max(0, old_remaining - amount)
    today         = date.today()
    pay_type      = target_row.get("To'lov Turi", "Oylik")
    next_date     = today + (timedelta(weeks=1) if pay_type == "Haftalik" else timedelta(days=30))

    # Sheets yangilash
    ws_sales.update_cell(row_index, col("Qoldiq") + 1,                  new_remaining)
    ws_sales.update_cell(row_index, col("Keyingi To'lov Sanasi") + 1,   next_date.strftime("%d.%m.%Y"))

    old_paid = safe_float(target_row.get("To'langan Summa", 0))
    new_paid = old_paid + amount
    ws_sales.update_cell(row_index, col("To'langan Summa") + 1, new_paid)

    if new_remaining == 0:
        ws_sales.update_cell(row_index, col("Holat") + 1,   "Yopildi")
        ws_sales.update_cell(row_index, col("Reyting") + 1, "🟢 Alo")

    # Bonus
    current_bonus      = safe_float(target_row.get("Kredit Bonusu", 0))
    payment_per_period = safe_float(target_row.get("To'lov Summasi", 0))
    bonus_earned       = round((payment_per_period if amount >= payment_per_period else amount) * 0.02)
    new_bonus          = current_bonus + bonus_earned
    ws_sales.update_cell(row_index, col("Kredit Bonusu") + 1, new_bonus)

    # To'lovlar varag'iga yozish
    payment_records = ws_payments.get_all_values()
    pay_id = f"PAY-{max(0, len(payment_records) - 1):04d}"
    ws_payments.append_row([
        pay_id,
        target_row.get("ID"),
        target_row.get("FIO"),
        phone,
        amount,
        today.strftime("%d.%m.%Y"),
        new_remaining
    ])

    update_rating(ws_sales, row_index, today, target_row)

    return {
        "success":       True,
        "fio":           target_row.get("FIO"),
        "tovar":         target_row.get("Tovar", ""),
        "paid":          amount,
        "old_remaining": old_remaining,
        "new_remaining": new_remaining,
        "next_payment":  next_date.strftime("%d.%m.%Y"),
        "is_closed":     new_remaining == 0,
        "bonus":         new_bonus,
        "chat_id":       target_row.get("Chat ID", "")
    }


def update_rating(ws, row_index, today, record):
    try:
        next_pay  = datetime.strptime(record.get("Keyingi To'lov Sanasi", ""), "%d.%m.%Y").date()
        days_diff = (today - next_pay).days
        rating    = "🟢 Alo" if days_diff <= 0 else ("🟡 Ortacha" if days_diff <= 2 else "🔴 Xavfli")
        ws.update_cell(row_index, 15, rating)
    except:
        pass


def update_client_db(ws_clients, sale_data):
    all_values = ws_clients.get_all_values()
    phone      = normalize_phone(sale_data["phone"])
    today_str  = date.today().strftime("%d.%m.%Y")

    if len(all_values) > 1:
        headers = all_values[0]
        try:
            tel_idx = headers.index("Telefon")
        except ValueError:
            tel_idx = 1

        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > tel_idx:
                if normalize_phone(row[tel_idx]) == phone:
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
        sale_data["fio"], sale_data["phone"], "", "",
        1, 0, 0, "Bronze",
        sale_data.get("birthday", ""), today_str,
        sale_data.get("work_place", ""), today_str, "Yoq"
    ])


def check_duplicate(phone: str) -> dict:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Savdolar"]
    all_values  = ws.get_all_values()
    if len(all_values) < 2:
        return {"exists": False}
    headers     = all_values[0]
    phone_clean = normalize_phone(phone)
    try:
        tel_idx   = headers.index("Telefon")
        holat_idx = headers.index("Holat")
        fio_idx   = headers.index("FIO")
        tovar_idx = headers.index("Tovar")
        qoldiq_idx= headers.index("Qoldiq")
    except ValueError:
        return {"exists": False}
    for row in all_values[1:]:
        if len(row) <= max(tel_idx, holat_idx, fio_idx, tovar_idx, qoldiq_idx):
            continue
        if normalize_phone(row[tel_idx]) == phone_clean and row[holat_idx] == "Faol":
            return {
                "exists":    True,
                "fio":       row[fio_idx],
                "product":   row[tovar_idx],
                "remaining": row[qoldiq_idx]
            }
    return {"exists": False}


def get_today_payments() -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    today_str = date.today().strftime("%d.%m.%Y")
    return [
        r for r in ws_to_records(sheets["Savdolar"])
        if r.get("Holat") == "Faol" and r.get("Keyingi To'lov Sanasi") == today_str
    ]


def get_overdue_payments(days: int = 3) -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    today  = date.today()
    result = []
    for rec in ws_to_records(sheets["Savdolar"]):
        if rec.get("Holat") != "Faol":
            continue
        try:
            next_pay     = datetime.strptime(rec.get("Keyingi To'lov Sanasi", ""), "%d.%m.%Y").date()
            overdue_days = (today - next_pay).days
            if overdue_days >= days:
                rec["Kechikish Kunlari"] = overdue_days
                result.append(rec)
        except:
            pass
    return result


def get_payment_history(phone: str) -> list:
    from handlers.client_panel import ws_to_records 
    
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    phone_clean = str(phone).replace(" ", "").replace("+", "")
    return [
        r for r in ws_to_records(sheets["Tolovlar"])
        if str(r.get("Telefon", "")).replace(" ", "").replace("+", "") == phone_clean
    ]

def get_all_clients_with_status() -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    active = [r for r in ws_to_records(sheets["Savdolar"]) if r.get("Holat") == "Faol"]
    return sorted(active, key=lambda x: x.get("Reyting", ""))


def get_statistics() -> dict:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    records = ws_to_records(sheets["Savdolar"])
    active  = [r for r in records if r.get("Holat") == "Faol"]
    closed  = [r for r in records if r.get("Holat") == "Yopildi"]
    return {
        "total_sales":    len(records),
        "active":         len(active),
        "closed":         len(closed),
        "total_debt":     sum(safe_float(r.get("Qoldiq", 0)) for r in active),
        "total_revenue":  sum(safe_float(r.get("Jami Summa", 0)) for r in records),
        "overdue_count":  len(get_overdue_payments(1)),
        "blacklist_count":len(get_overdue_payments(3))
    }


def save_client_chat_id(phone: str, chat_id: int, username: str = ""):
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    ws = sheets["Mijozlar"]
    phone_clean = str(phone).replace(" ", "")
    today_str   = date.today().strftime("%d.%m.%Y")

    for i, rec in enumerate(ws_to_records(ws), start=2):
        if str(rec.get("Telefon", "")).replace(" ", "") == phone_clean:
            ws.update_cell(i, 3,  chat_id)
            ws.update_cell(i, 4,  username)
            ws.update_cell(i, 12, today_str)
            ws.update_cell(i, 13, "Ha")
            return True

    ws.append_row([
        "", phone, chat_id, username,
        0, 0, 0, "Bronze", "", today_str, "", today_str, "Ha"
    ])
    return False


def get_todays_birthdays() -> list:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    today    = date.today()
    today_md = f"{today.day:02d}.{today.month:02d}"
    return [
        r for r in ws_to_records(sheets["Savdolar"])
        if str(r.get("Tug'ilgan Kun", ""))[:5] == today_md
    ]


def get_client_chat_id(phone: str) -> str:
    sh = get_spreadsheet()
    sheets = ensure_worksheets(sh)
    phone_digits = str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()

    for rec in ws_to_records(sheets["Mijozlar"]):
        rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "").strip()
        if rec_phone == phone_digits and str(rec.get("Chat ID", "")).strip():
            return str(rec.get("Chat ID", "")).strip()

    for rec in ws_to_records(sheets["Savdolar"]):
        rec_phone = str(rec.get("Telefon", "")).replace("+", "").replace(" ", "").replace("-", "").strip()
        if rec_phone == phone_digits:
            chat_id = str(rec.get("Chat ID", "")).strip()
            if chat_id:
                return chat_id

    return ""


# katalog uchun — catalog_handler.py ishlatadi
def get_sheet(sheet_name: str):
    sh = get_spreadsheet()
    try:
        return sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=500, cols=10)
        if sheet_name == "Katalog":
            ws.append_row(["Nom", "Narx", "Tavsif", "PhotoID", "Sana"])
            ws.format("A1:E1", {"textFormat": {"bold": True}})
        return ws
