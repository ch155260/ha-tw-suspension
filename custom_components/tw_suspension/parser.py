"""純解析輔助工具（不依賴 Home Assistant 套件，便於進行單元測試）。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

from bs4 import BeautifulSoup

OTHER_AREAS = "其他地區"
NO_ANNOUNCEMENT_TEXT = "無停班停課訊息"

# 判斷結果（對應 binary_sensor 的 status attribute）
STATUS_STOPPED = "stopped"
STATUS_NORMAL = "normal"
STATUS_NOT_LISTED = "not_listed"
STATUS_NOT_ANNOUNCED = "not_announced"
STATUS_NO_ANNOUNCEMENT = "no_announcement"

COUNTIES = [
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "雲林縣", "南投縣", "嘉義市", "嘉義縣", "臺南市",
    "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "連江縣", "金門縣",
]
_CITY_NAMES = COUNTIES + [c.replace("臺", "台") for c in COUNTIES if "臺" in c]
_REGIONS = r"(?:北部地區|中部地區|南部地區|東部地區|外島地區)"
_REGION_ONLY_RE = re.compile(rf"^{_REGIONS}$")
_CITY_LINE_RE = re.compile(
    rf"^{_REGIONS}?\s*("
    + "|".join(_CITY_NAMES)
    + r")\s*(.*)$"
)
_END_RE = re.compile(
    r"(^備註|^[0-9]+\.\s*若欲進入|語音查詢電話|偽造、變造|刑法第|通報權責機關)"
)
_BAD_KEY_RE = re.compile(
    r"(縣市名稱|是否停止上班上課情形|語音查詢電話|總處網站|民間事業單位及勞工|勞動部"
    r"|免付費電話|0800-|刑法|災害防救法|停止上班及上課時|通報權責機關|公文書)"
)
_PAIR_RE = re.compile(r"\s*([^:\n；。]+?)\s*:\s*([^；。\n]+)(?=[；。]|$)")
_PARTIAL_RE = re.compile(r"(上午|下午|晚上|夜間|中午|\d+\s*時|\d+:\d+)")
# 頁首日期，例如「115年 10月 23日 天然災害停止上班及上課情形」（民國年）
_PAGE_DATE_RE = re.compile(r"(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_MONTH_DAY_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_TODAY_WORDS = ("今天", "今日")
_TOMORROW_WORDS = ("明天", "明日")
# 「明天未達停止上班及上課標準」也含有「停止上班」，必須先排除否定句
_NEGATION_RE = re.compile(r"(未達|不停止|無須停止|毋須停止)")
_WORK_STOP_RE = re.compile(r"停止上班")
# 「停止上班及上課」「停止上班、上課」裡沒有連續的「停止上課」，所以另外比對
_CLASS_STOP_RE = re.compile(r"停止(?:上班)?(?:及|、|與)?上課")
_ROC_YEAR_OFFSET = 1911


def normalize(name: str | None) -> str:
    """統一「台／臺」字元並移除前後空白。"""
    return (name or "").strip().replace("台", "臺")


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def _is_scope_key(k: str) -> bool:
    k = _clean(k)
    return bool(k) and len(k) <= 15 and not _BAD_KEY_RE.search(k)


def _parse_pairs(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in _PAIR_RE.findall(text.replace("：", ":")):
        if _is_scope_key(k):
            out[_clean(k)] = _clean(v).replace("。", "")
    return out


def _split_sentences(text: str) -> list[str]:
    """一行裡可能同時有今天與明天兩句，以句號／分號切開。"""
    parts = re.split(r"[。；]", text)
    return [_clean(p) for p in parts if _clean(p)]


class _CityCollector:
    """把每個縣市的公告整理成 {縣市: {範圍: [句子, ...]}}。

    範圍 (scope) 等於縣市名稱時代表全縣市公告；否則是行政區或「其他地區」。
    沒有冒號的句子會接在同縣市最後一個範圍後面，這樣「北投區:今天…」下一行的
    「明天…」才不會被丟掉。
    """

    def __init__(self) -> None:
        self.cities: dict[str, dict[str, list[str]]] = {}
        self._last_scope: dict[str, str] = {}

    def add(self, city: str, text: str) -> None:
        text = _clean(text)
        if not text:
            return
        scopes = self.cities.setdefault(city, {})
        pairs = _parse_pairs(text)
        if pairs:
            for scope, sentence in pairs.items():
                scopes.setdefault(scope, []).append(sentence)
                self._last_scope[city] = scope
            return
        scope = self._last_scope.get(city, city)
        scopes.setdefault(scope, []).extend(_split_sentences(text))


def _parse_page_date(text: str) -> str | None:
    """從頁首的民國日期取出西元日期（ISO 字串），找不到就回傳 None。"""
    match = _PAGE_DATE_RE.search(text)
    if not match:
        return None
    roc_year, month, day = (int(x) for x in match.groups())
    try:
        return date(roc_year + _ROC_YEAR_OFFSET, month, day).isoformat()
    except ValueError:
        return None


def parse_page(html: str) -> dict:
    """解析 DGPA 網頁。

    回傳：
        {
            "page_date": "2026-10-23" 或 None,
            "no_announcement": 是否顯示「無停班停課訊息」,
            "cities": {縣市: {範圍: [句子, ...]}},
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    lines = [
        _clean(x) for x in soup.get_text("\n", strip=True).splitlines() if _clean(x)
    ]
    collector = _CityCollector()
    current = None
    for line in lines:
        # 區域名稱獨立成一格時，會緊接在上一個縣市後面，必須略過
        if "縣市名稱" in line or _REGION_ONLY_RE.match(line):
            continue
        if _END_RE.search(line):
            break
        m = _CITY_LINE_RE.match(line)
        if m:
            current = normalize(m.group(1))
            collector.add(current, m.group(2))
        elif current:
            collector.add(current, line)

    full_text = " ".join(lines)
    return {
        "page_date": _parse_page_date(full_text),
        "no_announcement": NO_ANNOUNCEMENT_TEXT in full_text,
        "cities": collector.cities,
    }


def sentence_day_offset(sentence: str, page_date: date | None) -> int:
    """判斷一句公告是指頁面日期的哪一天：0 = 當天、1 = 隔天、-1 = 其他日期。

    沒有寫日期的句子（舊格式）視為當天。
    """
    if sentence.startswith(_TODAY_WORDS):
        return 0
    if sentence.startswith(_TOMORROW_WORDS):
        return 1
    match = _MONTH_DAY_RE.match(sentence)
    if match and page_date is not None:
        month, day = (int(x) for x in match.groups())
        for offset in (0, 1):
            target = date.fromordinal(page_date.toordinal() + offset)
            if (target.month, target.day) == (month, day):
                return offset
        return -1
    return 0


def parse_status(text: str) -> dict:
    """把（同一天的）公告文字轉成旗標。"""
    negated = bool(_NEGATION_RE.search(text))
    work = not negated and bool(_WORK_STOP_RE.search(text))
    cls = not negated and bool(_CLASS_STOP_RE.search(text))
    return {
        "status": STATUS_STOPPED if (work or cls) else STATUS_NORMAL,
        "work_stopped": work,
        "class_stopped": cls,
        "partial": bool((work or cls) and _PARTIAL_RE.search(text)),
        "raw": text,
    }


def _empty_status(status: str, raw: str = "") -> dict:
    return {
        "status": status,
        "work_stopped": False,
        "class_stopped": False,
        "partial": False,
        "raw": raw,
    }


def _sentences_for_day(
    sentences: list[str], offset: int, page_date: date | None
) -> list[str]:
    return [s for s in sentences if sentence_day_offset(s, page_date) == offset]


def _evaluate_scope_chain(
    scoped: dict[str, list[str]], keys: tuple[str, ...], offset: int,
    page_date: date | None,
) -> dict:
    """依序找第一個有這一天公告的範圍（行政區 → 縣市 → 其他地區）。"""
    found_any_key = False
    for key in keys:
        if key not in scoped:
            continue
        found_any_key = True
        day_sentences = _sentences_for_day(scoped[key], offset, page_date)
        if day_sentences:
            return parse_status("；".join(day_sentences))
    if found_any_key:
        return _empty_status(STATUS_NOT_ANNOUNCED)
    return _empty_status(STATUS_NOT_LISTED)


def _evaluate_all_districts(
    scoped: dict[str, list[str]], offset: int, page_date: date | None
) -> dict:
    """沒有選行政區、也沒有全縣市公告：任一區停班停課就算。"""
    parts: list[str] = []
    statuses: list[dict] = []
    for scope, sentences in scoped.items():
        if scope == OTHER_AREAS:
            continue
        day_sentences = _sentences_for_day(sentences, offset, page_date)
        if not day_sentences:
            continue
        text = "；".join(day_sentences)
        statuses.append(parse_status(text))
        parts.append(f"{scope}:{text}")
    if not statuses:
        return _empty_status(STATUS_NOT_ANNOUNCED)
    work = any(s["work_stopped"] for s in statuses)
    cls = any(s["class_stopped"] for s in statuses)
    return {
        "status": STATUS_STOPPED if (work or cls) else STATUS_NORMAL,
        "work_stopped": work,
        "class_stopped": cls,
        "partial": work or cls,
        "raw": "；".join(parts),
    }


def evaluate(
    data: dict, city: str, district: str, offset: int,
    page_date: date | None = None,
) -> dict:
    """找出某縣市／行政區在「頁面日期 + offset 天」的停班停課狀態。

    offset 只支援 0（頁面當天）與 1（隔天），其他日期一律視為尚未公告。
    """
    if data.get("no_announcement") and not data.get("cities"):
        return _empty_status(STATUS_NO_ANNOUNCEMENT, NO_ANNOUNCEMENT_TEXT)

    city, district = normalize(city), normalize(district)
    cities = {normalize(k): v for k, v in data.get("cities", {}).items()}
    scoped_raw = cities.get(city)
    if scoped_raw is None:
        return _empty_status(STATUS_NOT_LISTED)
    if offset not in (0, 1):
        return _empty_status(STATUS_NOT_ANNOUNCED)

    scoped = {normalize(k): v for k, v in scoped_raw.items()}
    if district:
        return _evaluate_scope_chain(
            scoped, (district, city, OTHER_AREAS), offset, page_date
        )
    if city in scoped:  # 全縣市公告
        return _evaluate_scope_chain(scoped, (city,), offset, page_date)
    return _evaluate_all_districts(scoped, offset, page_date)


def parse_xml_items(
    xml_data: bytes | str, code_tag: str, name_tag: str
) -> list[tuple[str, str]]:
    """從國土測繪中心 XML 解析 (代碼, 名稱) 列表，具備標籤容錯性。"""
    root = ET.fromstring(xml_data)
    seen: set[str] = set()
    items: list[tuple[str, str]] = []
    for node in root.iter():
        kids = {
            c.tag.split("}")[-1].lower(): (c.text or "").strip() for c in node
        }
        code, name = kids.get(code_tag), kids.get(name_tag)
        if code and name and name not in seen:
            seen.add(name)
            items.append((code, name))
    return items
