"""Nutrislice School Menus Home Assistant Integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .api import NutrisliceApiClient
from .calendar_sync import async_sync_entry
from .const import DOMAIN, SERVICE_SYNC_CALENDAR
from .coordinator import NutrisliceCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's services."""

    async def _async_handle_sync_calendar(call: ServiceCall) -> None:
        """Sync every school with a sync calendar, using the data already fetched."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            if coordinator := hass.data.get(DOMAIN, {}).get(entry.entry_id):
                await async_sync_entry(hass, entry, coordinator)

    hass.services.async_register(
        DOMAIN, SERVICE_SYNC_CALENDAR, _async_handle_sync_calendar
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nutrislice from a config entry."""
    session = async_get_clientsession(hass)
    client = NutrisliceApiClient(session)
    coordinator = NutrisliceCoordinator(hass, client, entry)

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up sensor and calendar platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Push menus into the configured sync calendar now and after every refresh
    @callback
    def _async_schedule_sync() -> None:
        if coordinator.last_update_success:
            entry.async_create_background_task(
                hass,
                async_sync_entry(hass, entry, coordinator),
                f"{DOMAIN}_calendar_sync_{entry.entry_id}",
            )

    entry.async_on_unload(coordinator.async_add_listener(_async_schedule_sync))
    _async_schedule_sync()

    # Today and Tomorrow change at midnight; rewrite every entity's state then
    # rather than waiting for the next refresh (which can be hours away)
    @callback
    def _async_midnight(_now) -> None:
        coordinator.async_update_listeners()

    entry.async_on_unload(
        async_track_time_change(hass, _async_midnight, hour=0, minute=0, second=1)
    )

    # Reload on options update
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Nutrislice config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
