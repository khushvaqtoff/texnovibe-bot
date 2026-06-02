# helpers.py
from helpers import normalize_phone

def normalize_phone(phone: str) -> str:
    return str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()