"""
Bu skriptni BIRINCHI MARTA ishga tushiring.
Brauzer ochiladi -> Google akkauntingizga kiring -> Ruxsat bering.
Keyin token.pickle saqlanadi va botni ishga tushirishingiz mumkin.

Ishlatish:
    python setup_oauth.py
"""

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import gspread
from dotenv import load_dotenv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def setup():
    print("=" * 50)
    print("  TexnoVibe Bot -- Google Autentifikatsiya")
    print("=" * 50)

    if not os.path.exists("credentials.json"):
        print("\n❌ credentials.json topilmadi!")
        print("\nQuyidagi qadamlarni bajaring:")
        print("1. https://console.cloud.google.com ga kiring")
        print("2. APIs & Services -> Credentials")
        print("3. + Create Credentials -> OAuth client ID")
        print("4. Application type: Desktop app")
        print("5. JSON yuklab, credentials.json deb saqlang")
        return

    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("✅ Token yangilandi!")
        else:
            print("\n🌐 Brauzer ochilmoqda...")
            print("   Google akkauntingizga kiring va ruxsat bering.\n")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            print("✅ Ruxsat berildi!")

        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)
        print("✅ Token saqlandi: token.pickle")
    else:
        print("✅ Token allaqachon mavjud va haqiqiy.")

    # Ulanishni tekshirish
    try:
        client = gspread.authorize(creds)
        sheets = client.list_spreadsheet_files()
        print(f"\n✅ Google Sheets ga muvaffaqiyatli ulandi!")
        print(f"   Sizning jadvallaringiz soni: {len(sheets)}")

        load_dotenv()
        sheet_id = os.getenv("SPREADSHEET_ID")
        if sheet_id and sheet_id.strip():
            sh = client.open_by_key(sheet_id)
            print(f"   📊 Jadval topildi: '{sh.title}'")
        else:
            print("\n⚠️  SPREADSHEET_ID hali .env ga qoshilmagan.")
            print("   Bot ishga tushganda avtomatik yaratiladi.")

    except Exception as e:
        print(f"\n❌ Ulanish xatosi: {e}")
        return

    print("\n" + "=" * 50)
    print("  Hammasi tayyor! Botni ishga tushiring:")
    print("  python bot.py")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    setup()
