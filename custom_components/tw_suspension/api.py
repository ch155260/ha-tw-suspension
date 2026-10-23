"""DGPA 與國土測繪中心 (NLSC) 的 HTTP 客戶端模組。"""
from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CACHE_SECONDS,
    DGPA_URL,
    DOMAIN,
    NLSC_COUNTY_URL,
    NLSC_TOWN_URL,
    REQUEST_TIMEOUT,
)
from .parser import parse_page, parse_xml_items

_LOGGER = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (HomeAssistant tw_suspension)"}


class DgpaError(Exception):
    """DGPA 網頁無法連線或解析失敗時拋出的例外。"""


class NlscError(Exception):
    """國土測繪中心代碼服務無法連線或解析失敗時拋出的例外。"""


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("big5", errors="replace")


class DgpaClient:
    """抓取 DGPA 網頁客戶端，提供跨條目共用的短期快取機制。"""

    def __init__(self, hass: HomeAssistant, verify_ssl: bool) -> None:
        self._hass = hass
        self._verify_ssl = verify_ssl
        self._lock = asyncio.Lock()
        self._cache: dict | None = None
        self._ts = 0.0

    async def async_get_data(self) -> dict:
        async with self._lock:
            if self._cache is not None and time.monotonic() - self._ts < CACHE_SECONDS:
                return self._cache
            session = async_get_clientsession(self._hass, verify_ssl=self._verify_ssl)
            try:
                async with session.get(
                    DGPA_URL,
                    headers=HEADERS,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                ) as resp:
                    resp.raise_for_status()
                    html = _decode(await resp.read())
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.warning("無法連線 DGPA 網頁: %r", err)
                raise DgpaError(f"無法連線 DGPA 網頁: {err!r}") from err
            data = await self._hass.async_add_executor_job(parse_page, html)
            # 平常日只有「無停班停課訊息」，屬於正常狀態；兩者都沒有才是格式變更
            if not data["cities"] and not data["no_announcement"]:
                raise DgpaError("解析不到任何縣市資料，網頁格式可能已變更")
            self._cache, self._ts = data, time.monotonic()
            return data


def get_client(hass: HomeAssistant, verify_ssl: bool) -> DgpaClient:
    store = hass.data.setdefault(DOMAIN, {})
    key = f"client_{verify_ssl}"
    if key not in store:
        store[key] = DgpaClient(hass, verify_ssl)
    return store[key]


async def _nlsc_request(hass: HomeAssistant, url: str, verify_ssl: bool) -> bytes:
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    async with session.get(
        url,
        headers=HEADERS,
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
    ) as resp:
        resp.raise_for_status()
        return await resp.read()


async def _nlsc_get(hass: HomeAssistant, url: str, code_tag: str, name_tag: str):
    try:
        try:
            raw = await _nlsc_request(hass, url, True)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            # 政府網站常缺中繼憑證；此處只讀取公開清單，改用不驗證重試
            _LOGGER.warning("NLSC 連線失敗 (%r)，改用不驗證重試", err)
            raw = await _nlsc_request(hass, url, False)
        items = parse_xml_items(raw, code_tag, name_tag)
    except (aiohttp.ClientError, asyncio.TimeoutError, ET.ParseError) as err:
        _LOGGER.warning("無法取得 NLSC 清單 %s: %r", url, err)
        raise NlscError(repr(err)) from err
    if not items:
        _LOGGER.warning("NLSC 清單解析不到資料: %s", url)
        raise NlscError("empty result")
    return items


async def async_fetch_counties(hass: HomeAssistant) -> list[tuple[str, str]]:
    return await _nlsc_get(hass, NLSC_COUNTY_URL, "countycode", "countyname")


async def async_fetch_towns(hass: HomeAssistant, county_code: str):
    return await _nlsc_get(
        hass, f"{NLSC_TOWN_URL}/{county_code}", "towncode", "townname"
    )
