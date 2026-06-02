import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Google Sheets uchun ruxsat doirasi
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def generate_token():
    creds = None
    # Agar token.pickle mavjud bo'lsa, uni yuklab olish
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # Agar token bo'lmasa yoki yaroqsiz bo'lsa, yangisini so'rash
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Tokenni saqlash
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    print("token.pickle muvaffaqiyatli yaratildi!")

if __name__ == '__main__':
    generate_token()