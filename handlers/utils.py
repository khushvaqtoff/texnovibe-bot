def normalize_phone(phone: str) -> str:
    """Telefon raqamini tozalash uchun yordamchi funksiya"""
    return str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()