"""tw_suspension 整合的資料更新協調器 (DataUpdateCoordinator)。"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DgpaClient, DgpaError
from .const import CONF_CITY, CONF_DISTRICT, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .parser import evaluate

_LOGGER = logging.getLogger(__name__)

type WorkClassConfigEntry = ConfigEntry[WorkClassCoordinator]


class WorkClassCoordinator(DataUpdateCoordinator[dict]):
    """定期抓取 DGPA 網頁；各實體再依自己的日期向它查詢結果。"""

    config_entry: WorkClassConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: WorkClassConfigEntry, client: DgpaClient
    ) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"tw_suspension {entry.title}",
            config_entry=entry,
            update_interval=timedelta(minutes=minutes),
        )
        self._client = client
        self.city = entry.data[CONF_CITY]
        self.district = entry.data.get(CONF_DISTRICT, "")

    async def _async_update_data(self) -> dict:
        try:
            page = await self._client.async_get_data()
        except DgpaError as err:
            raise UpdateFailed(str(err)) from err
        return {"page": page, "fetched_at": dt_util.now()}

    def _page_date(self) -> date:
        """網頁標示的日期；抓不到時退回成功抓取當下的日期。"""
        page_date = self.data["page"].get("page_date")
        if page_date:
            return date.fromisoformat(page_date)
        fetched_at: datetime = self.data["fetched_at"]
        return fetched_at.date()

    def is_data_usable(self) -> bool:
        """資料能不能用：最近一次成功，或雖然失敗但資料仍是今天抓的。

        跨日後昨天的「今天停班」已不正確，此時寧可顯示不可用，也不要誤導自動化。
        """
        if self.data is None:
            return False
        if self.last_update_success:
            return True
        fetched_at: datetime = self.data["fetched_at"]
        return fetched_at.date() == dt_util.now().date()

    def get_day(self, days_from_today: int) -> dict:
        """取得「今天 + days_from_today 天」的判斷結果（呼叫前請先確認資料可用）。"""
        target = dt_util.now().date() + timedelta(days=days_from_today)
        page_date = self._page_date()
        offset = (target - page_date).days
        result = evaluate(self.data["page"], self.city, self.district, offset, page_date)
        result["date"] = target.isoformat()
        return result
