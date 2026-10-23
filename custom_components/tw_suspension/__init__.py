"""停班停課 (DGPA) integration."""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import get_client
from .const import CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
from .coordinator import WorkClassConfigEntry, WorkClassCoordinator

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WorkClassConfigEntry) -> bool:
    client = get_client(hass, entry.options.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
    coordinator = WorkClassCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _reload(hass: HomeAssistant, entry: WorkClassConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WorkClassConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
