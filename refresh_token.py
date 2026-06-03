import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

print("Brauzer ochiladi, Google akkauntingizga kiring...")
flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

with open('token.pickle', 'wb') as f:
    pickle.dump(creds, f)

with open('token.pickle', 'rb') as f:
    data = f.read()

b64 = base64.b64encode(data).decode()

print("\n" + "="*60)
print("TOKEN_PICKLE_BASE64 qiymati (barchasini nusxalang):")
print("="*60)
print(b64)
print("="*60)
print("\nBu qiymatni Railway -> Variables -> TOKEN_PICKLE_BASE64 ga kiriting.")
