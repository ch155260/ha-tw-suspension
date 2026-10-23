"""Config flow: dropdowns come from NLSC open data, manual entry as fallback."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import NlscError, async_fetch_counties, async_fetch_towns
from .const import (
    ALL_DISTRICTS,
    CONF_CITY,
    CONF_DISTRICT,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .parser import normalize


def _select(options: list[SelectOptionDict]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


class WorkClassConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._counties: dict[str, str] = {}  # name -> code
        self._city = ""
        self._error = "-"

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return WorkClassOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._city = user_input[CONF_CITY]
            return await self.async_step_district()
        try:
            self._counties = {
                name: code for code, name in await async_fetch_counties(self.hass)
            }
        except NlscError as err:
            self._error = str(err)
            return await self.async_step_manual()
        options = [SelectOptionDict(value=n, label=n) for n in self._counties]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_CITY): _select(options)}),
        )

    async def async_step_district(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            district = user_input[CONF_DISTRICT]
            return await self._create(
                self._city, "" if district == ALL_DISTRICTS else district
            )
        try:
            towns = await async_fetch_towns(self.hass, self._counties[self._city])
        except NlscError as err:
            self._error = str(err)
            return await self.async_step_manual()
        options = [SelectOptionDict(value=ALL_DISTRICTS, label="整個縣市")]
        options += [SelectOptionDict(value=n, label=n) for _, n in towns]
        return self.async_show_form(
            step_id="district",
            data_schema=vol.Schema(
                {vol.Required(CONF_DISTRICT, default=ALL_DISTRICTS): _select(options)}
            ),
            description_placeholders={"city": self._city},
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return await self._create(
                user_input[CONF_CITY], user_input.get(CONF_DISTRICT, "")
            )
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CITY): str,
                    vol.Optional(CONF_DISTRICT, default=""): str,
                }
            ),
            description_placeholders={"error": self._error},
        )

    async def _create(self, city: str, district: str):
        city, district = normalize(city), normalize(district)
        await self.async_set_unique_id(f"{city}|{district}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{city}{district}",
            data={CONF_CITY: city, CONF_DISTRICT: district},
        )


class WorkClassOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=1440)),
                    vol.Required(
                        CONF_VERIFY_SSL, default=opts.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
                    ): bool,
                }
            ),
        )
