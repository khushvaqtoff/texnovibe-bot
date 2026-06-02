from helpers import normalize_phone
from sheets.google_sheets import add_sale, check_duplicate

def handle_sale_process(user_data):
    raw_phone = user_data.get('phone')
    clean_phone = normalize_phone(raw_phone)
    
    # Endi baza bilan ishlash
    if not check_duplicate(clean_phone):
        add_sale([user_data['name'], clean_phone, user_data['job']])