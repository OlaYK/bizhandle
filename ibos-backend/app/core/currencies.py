COMMON_CURRENCY_CATALOG: list[tuple[str, str]] = [
    ("USD", "US Dollar"),
    ("NGN", "Nigerian Naira"),
    ("EUR", "Euro"),
    ("GBP", "British Pound Sterling"),
    ("JPY", "Japanese Yen"),
    ("CAD", "Canadian Dollar"),
    ("AUD", "Australian Dollar"),
    ("CHF", "Swiss Franc"),
    ("CNY", "Chinese Yuan"),
    ("INR", "Indian Rupee"),
    ("AED", "UAE Dirham"),
    ("KES", "Kenyan Shilling"),
    ("GHS", "Ghanaian Cedi"),
    ("ZAR", "South African Rand"),
    ("XOF", "West African CFA Franc"),
    ("XAF", "Central African CFA Franc"),
]

COMMON_CURRENCY_CODES = {code for code, _name in COMMON_CURRENCY_CATALOG}


def normalize_currency_code(value: str) -> str:
    return (value or "").strip().upper()
