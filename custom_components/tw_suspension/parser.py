"""Pure parsing helpers (no Home Assistant imports, easy to unit-test)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

OTHER_AREAS = "其他地區"

COUNTIES = [
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "雲林縣", "南投縣", "嘉義市", "嘉義縣", "臺南市",
    "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "連江縣", "金門縣",
]
_CITY_NAMES = COUNTIES + [c.replace("臺", "台") for c in COUNTIES if "臺" in c]
_CITY_LINE_RE = re.compile(
    r"^(?:北部地區|中部地區|南部地區|東部地區|外島地區)?\s*("
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


def normalize(name: str | None) -> str:
    """Unify 台/臺 and strip whitespace."""
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


def _add_entry(result: dict, city: str, rest: str) -> None:
    rest = _clean(rest)
    if not rest:
        return
    kv = _parse_pairs(rest)
    if kv:
        existing = result.get(city)
        if isinstance(existing, dict):
            existing.update(kv)
        elif isinstance(existing, str) and existing:
            result[city] = {city: existing, **kv}
        else:
            result[city] = kv
    elif city not in result:
        result[city] = rest.replace("。", "")


def parse_page(html: str) -> dict:
    """Parse the DGPA page into {city: str | {scope: str}}."""
    soup = BeautifulSoup(html, "html.parser")
    lines = [
        _clean(x) for x in soup.get_text("\n", strip=True).splitlines() if _clean(x)
    ]
    result: dict = {}
    current = None
    for line in lines:
        if "縣市名稱" in line:
            continue
        if _END_RE.search(line):
            break
        m = _CITY_LINE_RE.match(line)
        if m:
            current = normalize(m.group(1))
            _add_entry(result, current, m.group(2))
        elif current:
            _add_entry(result, current, line)
    return result


def parse_status(text: str) -> dict:
    """Turn a status sentence into flags."""
    work = "停止上班" in text
    cls = "停止上課" in text
    return {
        "work_stopped": work,
        "class_stopped": cls,
        "partial": bool((work or cls) and _PARTIAL_RE.search(text)),
        "raw": text,
    }


def evaluate(data: dict, city: str, district: str) -> dict:
    """Find the status for city/district, with sensible fallbacks."""
    city, district = normalize(city), normalize(district)
    entry = {normalize(k): v for k, v in data.items()}.get(city)
    if entry is None:
        return parse_status("")
    if isinstance(entry, str):
        return parse_status(entry)

    scoped = {normalize(k): v for k, v in entry.items()}
    if district:
        for key in (district, city, OTHER_AREAS):
            if key in scoped:
                return parse_status(scoped[key])
        return parse_status("")

    if city in scoped:  # whole-city statement
        return parse_status(scoped[city])
    # No district chosen and no overall statement: any district counts.
    items = [(k, v) for k, v in scoped.items() if k != OTHER_AREAS]
    statuses = [parse_status(v) for _, v in items]
    work = any(s["work_stopped"] for s in statuses)
    cls = any(s["class_stopped"] for s in statuses)
    return {
        "work_stopped": work,
        "class_stopped": cls,
        "partial": work or cls,
        "raw": "；".join(f"{k}:{v}" for k, v in items),
    }


def parse_xml_items(
    xml_data: bytes | str, code_tag: str, name_tag: str
) -> list[tuple[str, str]]:
    """Extract (code, name) pairs from NLSC XML, tolerant of tag nesting."""
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
