"""One-off VAPID keypair generator for web push (T1.9).

    python scripts/generate_vapid_keys.py

Prints VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY for you to paste into .env.
Never writes to .env directly - these are secrets, and .env is yours to
edit. Run once; re-running invalidates every subscription signed with the
old key (browsers would need to re-subscribe).
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02


def main() -> None:
    vapid = Vapid02()
    vapid.generate_keys()

    public_bytes = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode()

    private_value = vapid.private_key.private_numbers().private_value
    private_bytes = private_value.to_bytes(32, "big")
    private_b64 = base64.urlsafe_b64encode(private_bytes).rstrip(b"=").decode()

    print("Paste these into .env (never commit them):\n")
    print(f"VAPID_PUBLIC_KEY={public_b64}")
    print(f"VAPID_PRIVATE_KEY={private_b64}")
    print("VAPID_SUBJECT=mailto:you@example.com  # change to a real contact")


if __name__ == "__main__":
    main()
