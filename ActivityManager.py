import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
from lxml import etree


class ActivityManager:
    BASE_URL = "https://m.hxxy.edu.cn"
    AVAILABLE_URL = BASE_URL + "/hdzx/stage2/activelist1"
    PERSONAL_URL = BASE_URL + "/hdzx/stage2/activelist2"
    DETAIL_FIELDS = (
        "start_time", "end_time", "registration_status", "location",
        "category", "credits", "visibility", "reserved_count",
        "reserved_limit", "onsite_count", "onsite_limit",
        "cancelled_count", "content", "detail_error",
    )

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 17; SM-S9180 Build/UP1A.231005.007; wv) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                "Chrome/146.0.7680.178 Mobile Safari/537.36 XWEB/1460263 "
                "MMWEBSDK/20250205 MMWEBID/4827 wxwork/5.0.9 MicroMessenger/7.0.1 "
                "NetType/WIFI Language/zh_CN Lang/zh ColorScheme/Light wwmver/3.26.509.642"
            ),
        }
        self.domain = "m.hxxy.edu.cn"

    def set_login(self, cookie):
        self.headers["Cookie"] = cookie

    @staticmethod
    def _validate_options(max_page, max_workers):
        if max_page is not None and (type(max_page) is not int or max_page < 1):
            raise ValueError("max_page 必须是正整数或 None")
        if type(max_workers) is not int or max_workers < 1:
            raise ValueError("max_workers 必须是正整数")

    def _get_html(self, url):
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        html = etree.HTML(response.text)
        if html is None:
            raise ValueError(f"无法解析活动页面: {url}")
        return html, response.url

    @staticmethod
    def _activity_from_link(link, name, activity_type):
        href = link.get("href", "")
        match = re.search(r"/getactiveinfo/hdbh/(\d+)(?:[/?#]|$)", href)
        if not match or not name:
            return None
        return {
            "id": int(match.group(1)),
            "name": name,
            "url": href,
            "activity_type": activity_type,
        }

    @staticmethod
    def _next_page_url(html, current_url, section=None):
        root = section if section is not None else html
        links = root.xpath(
            './/li[contains(concat(" ", normalize-space(@class), " "), " next ") '
            'and not(contains(concat(" ", normalize-space(@class), " "), " disabled "))]/a[@href]'
        )
        for link in links:
            href = link.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:")):
                continue
            next_url = urljoin(current_url, href)
            parsed = urlparse(next_url)
            if parsed.netloc == urlparse(current_url).netloc and next_url != current_url:
                return next_url
        return None

    @staticmethod
    def _append_rows(section, activity_type, activities, seen):
        if section is None:
            return
        for row in section.xpath('.//table//tr[td[1]/a[@href]]'):
            link = row.xpath('./td[1]/a[@href]')[0]
            name = " ".join("".join(link.itertext()).split())
            activity = ActivityManager._activity_from_link(link, name, activity_type)
            if activity and activity["id"] not in seen:
                seen.add(activity["id"])
                activities.append(activity)

    def _get_detail(self, activity):
        result = {**activity, **dict.fromkeys(self.DETAIL_FIELDS)}
        detail_url = urljoin(self.BASE_URL, activity["url"])
        try:
            html, _ = self._get_html(detail_url)
            lists = html.xpath(
                '//ul[contains(concat(" ", normalize-space(@class), " "), " am-list ") '
                'and li[.//img]]'
            )
            if not lists:
                result["detail_error"] = "未找到活动详情列表"
                return result

            details = lists[0]
            for li in details.xpath("./li"):
                text = " ".join("".join(li.itertext()).split())
                if li.xpath('.//span[@id="timer"]'):
                    result["registration_status"] = text or None
                icons = li.xpath(".//img/@src")
                if not icons:
                    continue
                icon = icons[0].rsplit("/", 1)[-1].lower()
                if icon == "sj.png":
                    times = re.search(
                        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*至\s*"
                        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", text
                    )
                    if times:
                        result["start_time"], result["end_time"] = times.groups()
                elif icon == "dd.png":
                    result["location"] = text or None
                elif icon == "xf.png":
                    result["category"] = text or None
                elif icon == "hd.png":
                    credits = re.search(r"(\d+(?:\.\d+)?)\s*学分", text)
                    if credits:
                        result["credits"] = float(credits.group(1))
                elif icon == "gly.png":
                    result["visibility"] = text or None
                elif icon == "bm.png":
                    for label, prefix in (("预约报名", "reserved"), ("现场报名", "onsite")):
                        count = re.search(
                            rf"(\d+)\s*/\s*(\d+)\s*人\s*[（(]{label}人数/上限人数[）)]",
                            text,
                        )
                        if count:
                            result[f"{prefix}_count"] = int(count.group(1))
                            result[f"{prefix}_limit"] = int(count.group(2))
                elif icon == "quxiaobaoming1.png":
                    cancelled = re.search(r"(\d+)\s*人取消报名", text)
                    if cancelled:
                        result["cancelled_count"] = int(cancelled.group(1))

            content = details.xpath(
                './li[.//span[normalize-space(.)="活动内容"]]/following-sibling::li[1]'
            )
            if content:
                result["content"] = " ".join("".join(content[0].itertext()).split()) or None
        except (requests.RequestException, ValueError) as exc:
            result["detail_error"] = str(exc)
        return result

    def _with_details(self, activities, deep, max_workers):
        if not deep or not activities:
            return activities
        detailed = [None] * len(activities)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._get_detail, activity): index
                for index, activity in enumerate(activities)
            }
            for future in as_completed(futures):
                detailed[futures[future]] = future.result()
        return detailed

    def get_personal_activity_list(self, max_page=None, deep=False, max_workers=8):
        """获取已报名的专题和打卡活动；max_page 分别限制每种活动的页数。"""
        self._validate_options(max_page, max_workers)
        base_html, base_url = self._get_html(self.PERSONAL_URL)
        activities, seen = [], set()
        for section_id, activity_type in (("ybmhdDiv", "special"), ("dkhdDiv", "checkin")):
            html, current_url = base_html, base_url
            visited = {current_url}
            page = 1
            while True:
                sections = html.xpath(f'//*[@id="{section_id}"]')
                section = sections[0] if sections else None
                self._append_rows(section, activity_type, activities, seen)
                if section is None or (max_page is not None and page >= max_page):
                    break
                next_url = self._next_page_url(html, current_url, section)
                if not next_url or next_url in visited:
                    break
                visited.add(next_url)
                html, current_url = self._get_html(next_url)
                page += 1
        return self._with_details(activities, deep, max_workers)

    def get_activity_list(self, max_page=None, deep=False, max_workers=8):
        """获取可报名活动；仅在页面提供下一页链接时继续翻页。"""
        self._validate_options(max_page, max_workers)
        html, current_url = self._get_html(self.AVAILABLE_URL)
        activities, seen = [], set()
        visited = {current_url}
        page = 1
        while True:
            # The page currently renders the same activities as cards and table rows.
            self._append_rows(html, "special", activities, seen)
            for card in html.xpath(
                '//div[contains(concat(" ", normalize-space(@class), " "), " swiper-slide ")]'
                '[.//span[contains(concat(" ", normalize-space(@class), " "), " hdmc ")]]'
            ):
                links = card.xpath('.//a[contains(@href, "/getactiveinfo/hdbh/")]')
                if not links:
                    continue
                names = card.xpath('.//span[contains(concat(" ", normalize-space(@class), " "), " hdmc ")]')
                name = " ".join("".join(names[0].itertext()).split())
                activity = self._activity_from_link(links[0], name, "special")
                if activity and activity["id"] not in seen:
                    seen.add(activity["id"])
                    activities.append(activity)
            if max_page is not None and page >= max_page:
                break
            next_url = self._next_page_url(html, current_url)
            if not next_url or next_url in visited:
                break
            visited.add(next_url)
            html, current_url = self._get_html(next_url)
            page += 1
        return self._with_details(activities, deep, max_workers)
