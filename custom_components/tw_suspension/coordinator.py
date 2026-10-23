"""DataUpdateCoordinator for tw_suspension."""
from __future__ import annotations

import logging
from datetime import timedelta

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
    """Polls DGPA and evaluates one location."""

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
        result = evaluate(page, self.city, self.district)
        result["fetched_at"] = dt_util.now().isoformat(timespec="seconds")
        return result
