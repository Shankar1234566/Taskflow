def parse_optional_id(value, label):
    """Parse an optional positive integer ID without leaking conversion errors."""
    if value is None or value == "":
        return None, None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None, f"{label} must be a positive integer."
    if isinstance(value, str):
        value = value.strip()
        if not value.isdecimal():
            return None, f"{label} must be a positive integer."
    try:
        parsed_id = int(value)
    except ValueError:
        return None, f"{label} must be a positive integer."
    if parsed_id <= 0:
        return None, f"{label} must be a positive integer."
    return parsed_id, None
