"""Generate activity QR images offline.

Dependencies: pip install "qrcode[pil]"
Import: generate_qrcode(flag=0, aid="19728") returns PNG Base64 without a data URI.
Run: python MicroHXActivityCode.py [aid]
"""

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
from pathlib import Path
import re
import secrets

import qrcode


__all__ = ["generate_qrcode"]

_KEYSTREAM = b"b7c0f55bb2a42a7845eedebc78d38c43"
_PREFIXES = {
    0: "https://m.hxxy.edu.cn/hdzx/stage3/ScanIn/hdbh/",
    1: "https://m.hxxy.edu.cn/hdzx/stage4/ScanOut/hdbh/",
    2: "https://m.hxxy.edu.cn/hdzx/stage3/xcbmScanIn/hdbh/",
}
_LABELS = {0: "入场码", 1: "出场码", 2: "预约码"}
_TIMEZONE = timezone(timedelta(hours=8))


def _normalize_aid(aid: int | str) -> str:
    if isinstance(aid, bool) or not isinstance(aid, (int, str)):
        raise ValueError("aid must be a nonnegative integer or decimal string")
    value = str(aid).strip()
    if re.fullmatch(r"[0-9]+", value) is None:
        raise ValueError("aid must contain only ASCII decimal digits")
    return value


def _validate_flag(flag: int) -> None:
    if isinstance(flag, bool) or not isinstance(flag, int) or flag not in _PREFIXES:
        raise ValueError("flag must be 0 (entry), 1 (exit), or 2 (reservation)")


def _encode_text(text: str) -> str:
    seed = secrets.randbelow(32001)
    random_key = hashlib.md5(str(seed).encode("ascii")).hexdigest().encode("ascii")
    encoded = bytearray()
    for index, value in enumerate(text.encode("ascii")):
        random_byte = random_key[index % 32]
        encoded.append(random_byte ^ _KEYSTREAM[(2 * index) % 32])
        encoded.append(random_byte ^ value ^ _KEYSTREAM[(2 * index + 1) % 32])
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def _build_payload(flag: int, aid: str, timestamp: str) -> str:
    return (
        _PREFIXES[flag] + _encode_text(aid)
        + "/p/" + _encode_text("hxxyhdzx" + timestamp)
    )


def _generate_png(flag: int, aid: str, timestamp: str) -> bytes:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4,
        border=4,
    )
    qr.add_data(_build_payload(flag, aid, timestamp), optimize=0)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    with BytesIO() as output:
        image.save(output, format="PNG")
        return output.getvalue()


def generate_qrcode(flag: int, aid: int | str) -> str:
    """Return a PNG image as plain Base64; flags: 0=entry, 1=exit, 2=reservation.

    Uses the current UTC+8 timestamp, preserves leading zeros in string IDs,
    and performs no network requests or filesystem writes.
    """
    _validate_flag(flag)
    aid_text = _normalize_aid(aid)
    timestamp = datetime.now(_TIMEZONE).strftime("%Y%m%d%H%M%S")
    return base64.b64encode(_generate_png(flag, aid_text, timestamp)).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aid", nargs="?", help="Activity ID; prompts when omitted")
    args = parser.parse_args()
    try:
        aid = _normalize_aid(args.aid if args.aid is not None else input("请输入活动ID: "))
    except (ValueError, EOFError) as error:
        parser.error(str(error))

    timestamp = datetime.now(_TIMEZONE).strftime("%Y%m%d%H%M%S")
    images = {flag: _generate_png(flag, aid, timestamp) for flag in _PREFIXES}
    destination = Path("result") / aid
    destination.mkdir(parents=True, exist_ok=True)
    for flag, image in images.items():
        path = destination / f"{_LABELS[flag]}{aid}.png"
        path.write_bytes(image)
        print(path.resolve())


if __name__ == "__main__":
    main()
