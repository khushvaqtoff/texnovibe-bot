# helpers.py faylining ichi faqat mana shunday bo'lsin:

def normalize_phone(phone: str) -> str:
    return str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()