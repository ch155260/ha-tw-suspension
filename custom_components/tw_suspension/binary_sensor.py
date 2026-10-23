"""Binary sensor: on when work OR class is suspended."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WorkClassConfigEntry, WorkClassCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WorkClassConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WorkClassBinarySensor(entry.runtime_data, entry)])


class WorkClassBinarySensor(CoordinatorEntity[WorkClassCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "suspension"

    def __init__(self, coordinator: WorkClassCoordinator, entry: WorkClassConfigEntry):
        super().__init__(coordinator)
        self._attr_unique_id = entry.unique_id or entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="行政院人事行政總處 (DGPA)",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        # Keep the last known state when a refresh fails.
        return self.coordinator.data is not None

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None:
            return None
        return bool(data["work_stopped"] or data["class_stopped"])

    @property
    def icon(self) -> str:
        return "mdi:cloud-alert" if self.is_on else "mdi:cloud"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "work_stopped": data.get("work_stopped"),
            "class_stopped": data.get("class_stopped"),
            "partial": data.get("partial"),
            "raw": data.get("raw"),
            "city": self.coordinator.city,
            "district": self.coordinator.district,
            "last_updated": data.get("fetched_at"),
        }
