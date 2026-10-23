"""二元感測器平台：提供「今天」與「明天」兩個實體，當停止上班或停止上課時為 on。"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WorkClassConfigEntry, WorkClassCoordinator


@dataclass(frozen=True)
class DayDescription:
    """描述一個「某一天」的實體。"""

    translation_key: str
    days_from_today: int
    # 舊版只有一個實體且 unique_id 沒有後綴；「今天」沿用它，既有自動化才不會失效
    unique_id_suffix: str


DAYS = (
    DayDescription("today", 0, ""),
    DayDescription("tomorrow", 1, "_tomorrow"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WorkClassConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        WorkClassBinarySensor(entry.runtime_data, entry, day) for day in DAYS
    )


class WorkClassBinarySensor(CoordinatorEntity[WorkClassCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WorkClassCoordinator,
        entry: WorkClassConfigEntry,
        day: DayDescription,
    ) -> None:
        super().__init__(coordinator)
        self._day = day
        self._attr_translation_key = day.translation_key
        base_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_id}{day.unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="行政院人事行政總處 (DGPA)",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # 跨日時「今天／明天」所指的日期會改變，不等下次輪詢就立即重算
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._handle_midnight, hour=0, minute=0, second=5
            )
        )

    @callback
    def _handle_midnight(self, _now) -> None:
        self.async_write_ha_state()

    def _result(self) -> dict | None:
        if not self.coordinator.is_data_usable():
            return None
        return self.coordinator.get_day(self._day.days_from_today)

    @property
    def available(self) -> bool:
        return self.coordinator.is_data_usable()

    @property
    def is_on(self) -> bool | None:
        result = self._result()
        if result is None:
            return None
        return bool(result["work_stopped"] or result["class_stopped"])

    @property
    def icon(self) -> str:
        return "mdi:cloud-alert" if self.is_on else "mdi:cloud"

    @property
    def extra_state_attributes(self) -> dict:
        result = self._result() or {}
        fetched_at = (self.coordinator.data or {}).get("fetched_at")
        return {
            "status": result.get("status"),
            "work_stopped": result.get("work_stopped"),
            "class_stopped": result.get("class_stopped"),
            "partial": result.get("partial"),
            "raw": result.get("raw"),
            "date": result.get("date"),
            "city": self.coordinator.city,
            "district": self.coordinator.district,
            "last_updated": fetched_at.isoformat(timespec="seconds") if fetched_at else None,
            "stale": not self.coordinator.last_update_success,
        }
