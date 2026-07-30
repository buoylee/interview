def normalize_email(value):
    normalized = value.strip().lower()
    if normalized.count("@") != 1:
        raise ValueError("email must contain exactly one @")

    local_part, domain = normalized.split("@", 1)
    if not local_part or not domain:
        raise ValueError("email local part and domain are required")
    if any(character.isspace() for character in normalized):
        raise ValueError("email must not contain whitespace")
    return normalized
