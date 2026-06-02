# helpers.py
def normalize_phone(phone: str) -> str:
    return str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()