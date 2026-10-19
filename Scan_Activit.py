"""Scan reservation QR URLs and save their page headings.

Run: python Scan_Activit.py [COOKIES START END]
Without arguments, all three values are prompted interactively.
"""

import argparse
from getpass import getpass
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from MicroHXActivityCode import generate_url


USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 17; SM-S9180 Build/UP1A.231005.007; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/146.0.7680.178 Mobile Safari/537.36 XWEB/1460263 "
    "MMWEBSDK/20250205 MMWEBID/4827 wxwork/5.0.9 "
    "MicroMessenger/7.0.1 NetType/WIFI Language/zh_CN Lang/zh "
    "ColorScheme/Light wwmver/3.26.509.642"
)
TIMEOUT_SECONDS = 15


class BodyHeadingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.path = []
        self.heading = None
        self._parts = []
        self._heading_depth = None

    def handle_starttag(self, tag, attrs):
        if self.heading is not None:
            return
        if self._heading_depth is not None and tag == "br":
            self._parts.append(" ")
        if tag == "h1" and self.path == ["html", "body"]:
            self._heading_depth = len(self.path) + 1
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.path.append(tag)

    def handle_startendtag(self, tag, attrs):
        if self._heading_depth is not None and tag == "br":
            self._parts.append(" ")

    def handle_endtag(self, tag):
        if self.heading is not None:
            return
        if tag == "h1" and self._heading_depth == len(self.path):
            self.heading = " ".join("".join(self._parts).split())
            self._heading_depth = None
        if tag in self.path:
            del self.path[len(self.path) - 1 - self.path[::-1].index(tag):]

    def handle_data(self, data):
        if self._heading_depth is not None and self.heading is None:
            self._parts.append(data)


def decode_html(body, headers):
    charset = headers.get_content_charset()
    if charset is None:
        match = re.search(rb"<meta\b[^>]*charset\s*=\s*['\"]?([\w-]+)", body[:4096], re.I)
        charset = match.group(1).decode("ascii") if match else "utf-8"
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def fetch_heading(url, cookies):
    request = Request(url, headers={
        "Cookie": cookies,
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        html = decode_html(response.read(), response.headers)
    parser = BodyHeadingParser()
    parser.feed(html)
    parser.close()
    return parser.heading


def parse_inputs():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cookies", nargs="?", help="Raw Cookie header value")
    parser.add_argument("start", nargs="?", help="First activity ID, inclusive")
    parser.add_argument("end", nargs="?", help="Last activity ID, inclusive")
    args = parser.parse_args()
    supplied = [args.cookies, args.start, args.end]
    if any(value is not None for value in supplied) and not all(
        value is not None for value in supplied
    ):
        parser.error("provide all three arguments or omit all three to be prompted")
    try:
        cookies = args.cookies if args.cookies is not None else getpass("Cookies: ")
        start_text = args.start if args.start is not None else input("起始编号: ")
        end_text = args.end if args.end is not None else input("终止编号: ")
    except EOFError:
        parser.error("input ended before all three values were provided")
    if not cookies.strip():
        parser.error("Cookies cannot be empty")
    if not re.fullmatch(r"[0-9]+", start_text) or not re.fullmatch(r"[0-9]+", end_text):
        parser.error("start and end must be nonnegative decimal integers")
    start, end = int(start_text), int(end_text)
    if start > end:
        parser.error("start must be less than or equal to end")
    return cookies, start, end


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cookies, start, end = parse_inputs()
    destination = Path(__file__).resolve().parent / "result" / f"Scan_Activit_{start}_{end}.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = end - start + 1
    print(f"开始扫描: {start} 至 {end}，共 {total} 个编号", flush=True)
    print(f"结果文件: {destination}", flush=True)
    success = 0
    with destination.open("w", encoding="utf-8") as output:
        for index, aid in enumerate(range(start, end + 1), 1):
            url = generate_url(2, aid)
            print(f"[{index}/{total}] [{aid}] 请求: {url}", flush=True)
            try:
                heading = fetch_heading(url, cookies)
                if heading is None:
                    result = "未找到 /html/body/h1"
                else:
                    result = heading
                    success += 1
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                result = f"请求失败: {error}"
            result = " ".join(result.split())
            output.write(f"[{aid}] --> {result}\n")
            output.flush()
            print(f"[{index}/{total}] [{aid}] 结果: {result}", flush=True)
    print(f"扫描完成: 成功提取 {success}/{total}，结果已保存至 {destination}", flush=True)


if __name__ == "__main__":
    main()
