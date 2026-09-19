"""Mock Home Assistant and dependency classes for self-contained testing."""
from datetime import datetime, time
import sys
import types
from typing import Any


class MockConfigEntry:
    """Mock ConfigEntry."""

    def __init__(self, entry_id="test_entry_id", data=None, options=None):
        self.entry_id = entry_id
        self.data = data or {}
        self.options = options or {}
        self.unique_id = None

    def async_on_unload(self, func):
        pass

    def add_update_listener(self, func):
        return lambda: None

    def async_create_background_task(self, hass, target, name):
        target.close()


class MockHomeAssistant:
    """Mock HomeAssistant instance."""

    def __init__(self):
        self.data = {}
        self.config_entries = types.SimpleNamespace(
            async_forward_entry_setups=lambda entry, platforms: None,
            async_reload=lambda entry_id: None,
            async_unload_platforms=lambda entry, platforms: True,
        )


class MockConfigFlow:
    """Mock ConfigFlow."""

    def __init_subclass__(cls, domain=None, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        self.hass = None
        self.unique_id = None

    def async_show_form(self, step_id, data_schema=None, errors=None, description_placeholders=None):
        return {
            "type": "form",
            "step_id": step_id,
            "errors": errors or {},
            "description_placeholders": description_placeholders or {},
        }

    def async_create_entry(self, title, data, options=None):
        return {"type": "create_entry", "title": title, "data": data, "options": options or {}}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass


class MockHomeAssistantError(Exception):
    """Mock HomeAssistantError."""


class MockOptionsFlow:
    """Mock OptionsFlow."""

    config_entry = None  # provided by Home Assistant's flow manager at runtime

    def __init__(self, *args, **kwargs):
        pass

    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {"type": "form", "step_id": step_id, "errors": errors or {}}

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}


def callback(func):
    return func


class MockPlatform:
    SENSOR = "sensor"
    CALENDAR = "calendar"


class MockUpdateFailed(Exception):
    pass


class MockDataUpdateCoordinator:
    """Mock DataUpdateCoordinator."""

    __class_getitem__ = classmethod(lambda cls, item: cls)

    def __init__(self, hass, logger, name, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}
        self.last_update_success = True

    def async_add_listener(self, update_callback, context=None):
        return lambda: None

    async def async_config_entry_first_refresh(self):
        self.data = await self._async_update_data()

    async def _async_update_data(self):
        return {}


class MockCoordinatorEntity:
    """Mock CoordinatorEntity."""

    __class_getitem__ = classmethod(lambda cls, item: cls)

    def __init__(self, coordinator):
        self.coordinator = coordinator


class MockSensorEntity:
    """Mock SensorEntity."""

    _attr_has_entity_name = False
    _attr_name = None
    _attr_unique_id = None
    _attr_icon = None


class MockCalendarEntity:
    """Mock CalendarEntity."""

    _attr_has_entity_name = False
    _attr_name = None
    _attr_unique_id = None
    _attr_icon = None


class MockCalendarEvent:
    """Mock CalendarEvent."""

    def __init__(self, start, end, summary, description=None, location=None):
        self.start = start
        self.end = end
        self.summary = summary
        self.description = description
        self.location = location


class MockDeviceInfo:
    """Mock DeviceInfo."""

    def __init__(self, identifiers, name, manufacturer=None, model=None, configuration_url=None):
        self.identifiers = identifiers
        self.name = name
        self.manufacturer = manufacturer
        self.model = model
        self.configuration_url = configuration_url


def setup_ha_mocks():
    """Setup mock Home Assistant and aiohttp modules if not present."""
    if "aiohttp" not in sys.modules:
        try:
            import aiohttp  # noqa: F401
        except ImportError:
            aio = types.ModuleType("aiohttp")

            class ClientError(Exception):
                pass

            class ClientConnectorError(ClientError):
                pass

            class ClientTimeout:
                def __init__(self, total=None):
                    self.total = total

            class ClientSession:
                def __init__(self, *args, **kwargs):
                    self.closed = False

                async def close(self):
                    self.closed = True

                def get(self, *args, **kwargs):
                    raise NotImplementedError

            aio.ClientError = ClientError
            aio.ClientConnectorError = ClientConnectorError
            aio.ClientTimeout = ClientTimeout
            aio.ClientSession = ClientSession
            sys.modules["aiohttp"] = aio

    if "homeassistant" in sys.modules and hasattr(sys.modules["homeassistant"], "__file__"):
        return

    # Modules
    ha = types.ModuleType("homeassistant")
    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MockHomeAssistant
    ha_core.callback = callback
    ha_core.ServiceCall = object

    ha_const = types.ModuleType("homeassistant.const")
    ha_const.Platform = MockPlatform

    ha_ce = types.ModuleType("homeassistant.config_entries")
    ha_ce.ConfigEntry = MockConfigEntry
    ha_ce.ConfigFlow = MockConfigFlow
    ha_ce.OptionsFlow = MockOptionsFlow

    ha_def = types.ModuleType("homeassistant.data_entry_flow")
    ha_def.FlowResult = dict

    ha_helpers = types.ModuleType("homeassistant.helpers")

    ha_coord = types.ModuleType("homeassistant.helpers.update_coordinator")
    ha_coord.DataUpdateCoordinator = MockDataUpdateCoordinator
    ha_coord.UpdateFailed = MockUpdateFailed
    ha_coord.CoordinatorEntity = MockCoordinatorEntity

    ha_entity = types.ModuleType("homeassistant.helpers.entity")
    ha_entity.DeviceInfo = MockDeviceInfo

    ha_ep = types.ModuleType("homeassistant.helpers.entity_platform")
    ha_ep.AddEntitiesCallback = Any

    ha_aio = types.ModuleType("homeassistant.helpers.aiohttp_client")
    ha_aio.async_get_clientsession = lambda hass: None

    ha_sel = types.ModuleType("homeassistant.helpers.selector")
    ha_sel.TextSelector = lambda *args, **kwargs: None
    ha_sel.TextSelectorConfig = lambda *args, **kwargs: None
    ha_sel.TextSelectorType = types.SimpleNamespace(TEXT="text", URL="url", SEARCH="search")
    ha_sel.SelectSelector = lambda *args, **kwargs: None
    ha_sel.SelectSelectorConfig = lambda *args, **kwargs: None
    ha_sel.SelectSelectorMode = types.SimpleNamespace(DROPDOWN="dropdown", LIST="list")
    ha_sel.SelectOptionDict = dict
    ha_sel.NumberSelector = lambda *args, **kwargs: None
    ha_sel.NumberSelectorConfig = lambda *args, **kwargs: None
    ha_sel.NumberSelectorMode = types.SimpleNamespace(BOX="box")
    ha_sel.BooleanSelector = lambda *args, **kwargs: None
    ha_sel.EntitySelector = lambda *args, **kwargs: None
    ha_sel.EntitySelectorConfig = lambda *args, **kwargs: None
    ha_sel.EntityFilterSelectorConfig = lambda *args, **kwargs: None

    ha_event = types.ModuleType("homeassistant.helpers.event")
    ha_event.async_track_time_change = lambda hass, action, **kwargs: (lambda: None)

    ha_er = types.ModuleType("homeassistant.helpers.entity_registry")
    ha_er.async_get = lambda hass: hass.entity_registry

    ha_exc = types.ModuleType("homeassistant.exceptions")
    ha_exc.HomeAssistantError = MockHomeAssistantError

    ha_cv = types.ModuleType("homeassistant.helpers.config_validation")
    ha_cv.config_entry_only_config_schema = lambda domain: None

    ha_typing = types.ModuleType("homeassistant.helpers.typing")
    ha_typing.ConfigType = dict

    ha_util = types.ModuleType("homeassistant.util")
    ha_dt = types.ModuleType("homeassistant.util.dt")
    ha_dt.now = datetime.now
    ha_dt.start_of_local_day = lambda day: datetime.combine(day, time.min)
    ha_util.dt = ha_dt

    ha_comp = types.ModuleType("homeassistant.components")
    ha_sensor = types.ModuleType("homeassistant.components.sensor")
    ha_sensor.SensorEntity = MockSensorEntity

    ha_calendar = types.ModuleType("homeassistant.components.calendar")
    ha_calendar.CalendarEntity = MockCalendarEntity
    ha_calendar.CalendarEvent = MockCalendarEvent
    ha_calendar.DOMAIN = "calendar"

    # Voluptuous
    vol = types.ModuleType("voluptuous")
    vol.Schema = lambda *args, **kwargs: None
    vol.Required = lambda *args, **kwargs: None
    vol.Optional = lambda *args, **kwargs: None

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.config_entries"] = ha_ce
    sys.modules["homeassistant.data_entry_flow"] = ha_def
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_coord
    ha_helpers.update_coordinator = ha_coord
    sys.modules["homeassistant.helpers.entity"] = ha_entity
    ha_helpers.entity = ha_entity
    sys.modules["homeassistant.helpers.entity_platform"] = ha_ep
    ha_helpers.entity_platform = ha_ep
    sys.modules["homeassistant.helpers.aiohttp_client"] = ha_aio
    ha_helpers.aiohttp_client = ha_aio
    sys.modules["homeassistant.helpers.selector"] = ha_sel
    ha_helpers.selector = ha_sel
    sys.modules["homeassistant.helpers.config_validation"] = ha_cv
    ha_helpers.config_validation = ha_cv
    sys.modules["homeassistant.helpers.typing"] = ha_typing
    ha_helpers.typing = ha_typing
    sys.modules["homeassistant.helpers.event"] = ha_event
    ha_helpers.event = ha_event
    sys.modules["homeassistant.helpers.entity_registry"] = ha_er
    ha_helpers.entity_registry = ha_er
    sys.modules["homeassistant.exceptions"] = ha_exc
    sys.modules["homeassistant.util"] = ha_util
    sys.modules["homeassistant.util.dt"] = ha_dt
    sys.modules["homeassistant.components"] = ha_comp
    sys.modules["homeassistant.components.sensor"] = ha_sensor
    ha_comp.sensor = ha_sensor
    sys.modules["homeassistant.components.calendar"] = ha_calendar
    ha_comp.calendar = ha_calendar
    sys.modules["voluptuous"] = vol


setup_ha_mocks()
