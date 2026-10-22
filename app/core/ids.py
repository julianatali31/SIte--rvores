import secrets

# No 0/o, 1/l/i: easy to read aloud or type from a plaque if the QR fails.
PUBLIC_ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
PUBLIC_ID_LENGTH = 8


def new_public_id() -> str:
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))


def tree_code(number: int) -> str:
    return f"ARV-{number:03d}"
