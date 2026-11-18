"""Check the syntax of common ASCII email addresses."""

import argparse
import re

LOCAL_PART = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*")
DOMAIN_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def is_valid_email(address: str) -> bool:
    """Return whether the address matches the supported syntax."""
    if not address.isascii() or len(address) > 254 or address.count("@") != 1:
        return False

    local, domain = address.split("@")
    if len(local) > 64 or not LOCAL_PART.fullmatch(local):
        return False

    labels = domain.split(".")
    return (
        len(labels) >= 2
        and any(character.isalpha() for character in labels[-1])
        and all(DOMAIN_LABEL.fullmatch(label) for label in labels)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email address to check")
    args = parser.parse_args()
    valid = is_valid_email(args.email)
    print("Valid email syntax" if valid else "Invalid email syntax")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
