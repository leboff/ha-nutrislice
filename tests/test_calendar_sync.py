"""Unit tests for syncing Nutrislice menus into another calendar."""
import asyncio
from datetime import date, datetime, timedelta
from types import SimpleNamespace
import unittest

from tests.ha_mock import MockConfigEntry, setup_ha_mocks

setup_ha_mocks()

from homeassistant.exceptions import HomeAssistantError

from custom_components.nutrislice.calendar_sync import async_sync_entry
from custom_components.nutrislice.coordinator import (
    NutrisliceCoordinator,
    NutrisliceMenuData,
    ParsedDayMenu,
)

TARGET = "calendar.family"


class FakeServices:
    """Records service calls and serves canned get_events responses."""

    def __init__(self, existing=None, fail_on=None):
        self.existing = existing or []
        self.fail_on = fail_on
        self.calls = []

    async def async_call(self, domain, service, data, blocking=False, return_response=False):
        self.calls.append((domain, service, data))
        if service == self.fail_on:
            raise HomeAssistantError("boom")
        if service == "get_events":
            return {data["entity_id"]: {"events": self.existing}}
        return None

    @property
    def created(self):
        return [data for _, service, data in self.calls if service == "create_event"]


def make_day(day: date, entrees):
    return ParsedDayMenu(
        date_str=day.isoformat(),
        target_date=day,
        is_holiday=False,
        has_menu=bool(entrees),
        entrees=entrees,
        sides=["Apple"],
        raw_day={"date": day.isoformat()},
    )


def make_menu(slug, name, days):
    return NutrisliceMenuData(
        district="sample-district",
        school_slug="lincoln-elementary",
        school_name="Lincoln Elementary",
        menu_type_slug=slug,
        menu_type_name=name,
        days_by_date={d.date_str: d for d in days},
        last_updated=datetime(2026, 9, 18, 12, 0, 0),
    )


class TestCalendarSync(unittest.IsolatedAsyncioTestCase):
    """Test syncing menus to a target calendar."""

    def setUp(self):
        self.today = date.today()
        self.tomorrow = self.today + timedelta(days=1)
        self.lunch = make_menu(
            "lunch",
            "Lunch",
            [
                make_day(self.today - timedelta(days=1), ["Yesterday Pasta"]),
                make_day(self.today, ["Cheeseburger", "Pizza"]),
                make_day(self.tomorrow, []),
                make_day(self.today + timedelta(days=2), ["Chicken Wings"]),
            ],
        )
        self.coordinator = NutrisliceCoordinator.__new__(NutrisliceCoordinator)
        self.coordinator.data = {"lunch": self.lunch}
        # Real lock, as created by the coordinator's __init__
        self.coordinator.sync_lock = asyncio.Lock()

    def hass(self, **kwargs):
        return SimpleNamespace(services=FakeServices(**kwargs))

    async def test_creates_upcoming_meals_as_all_day_events(self):
        hass = self.hass()
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        created = await async_sync_entry(hass, entry, self.coordinator)

        self.assertEqual(created, 2)
        self.assertEqual(
            hass.services.created,
            [
                {
                    "entity_id": TARGET,
                    "summary": "🍽️ Lunch: Cheeseburger, Pizza",
                    "description": self.lunch.days_by_date[self.today.isoformat()].formatted_description,
                    "location": "Lincoln Elementary",
                    "start_date": self.today.isoformat(),
                    "end_date": self.tomorrow.isoformat(),
                },
                {
                    "entity_id": TARGET,
                    "summary": "🍽️ Lunch: Chicken Wings",
                    "description": self.lunch.days_by_date[(self.today + timedelta(days=2)).isoformat()].formatted_description,
                    "location": "Lincoln Elementary",
                    "start_date": (self.today + timedelta(days=2)).isoformat(),
                    "end_date": (self.today + timedelta(days=3)).isoformat(),
                },
            ],
        )

    async def test_looks_up_existing_events_over_the_synced_range(self):
        hass = self.hass()
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        await async_sync_entry(hass, entry, self.coordinator)

        domain, service, data = hass.services.calls[0]
        self.assertEqual((domain, service), ("calendar", "get_events"))
        self.assertEqual(data["entity_id"], TARGET)
        self.assertEqual(data["start_date_time"].date(), self.today)
        self.assertEqual(data["end_date_time"].date(), self.today + timedelta(days=3))

    async def test_skips_meals_already_on_calendar(self):
        existing = [
            {
                "start": self.today.isoformat(),
                "end": self.tomorrow.isoformat(),
                # Entrees changed since it was synced: still counts as synced
                "summary": "Lunch: Old Entree",
                "location": "Lincoln Elementary",
            }
        ]
        hass = self.hass(existing=existing)
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        created = await async_sync_entry(hass, entry, self.coordinator)

        self.assertEqual(created, 1)
        self.assertEqual(hass.services.created[0]["summary"], "🍽️ Lunch: Chicken Wings")

    async def test_meals_synced_by_older_versions_are_not_duplicated(self):
        """Pre-1.4.0 titles had no emoji; the new titles must not re-create them."""
        existing = [
            {"start": self.today.isoformat(), "summary": "Lunch: Cheeseburger, Pizza", "location": "Lincoln Elementary"},
            {"start": (self.today + timedelta(days=2)).isoformat(), "summary": "🍽️ Lunch: Chicken Wings", "location": "Lincoln Elementary"},
        ]
        hass = self.hass(existing=existing)
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        self.assertEqual(await async_sync_entry(hass, entry, self.coordinator), 0)

    async def test_uses_the_configured_title_sections(self):
        hass = self.hass()
        entry = MockConfigEntry(options={"sync_calendar": TARGET, "title_sections": ["entrees", "sides"]})

        await async_sync_entry(hass, entry, self.coordinator)

        self.assertEqual(hass.services.created[0]["summary"], "Lunch: 🍽️ Cheeseburger, Pizza 🥖 Apple")

    async def test_changing_title_sections_does_not_duplicate(self):
        """Every title style ever produced counts as the same meal."""
        for title in ("🍽️ Lunch", "Lunch: 🍽️ Old 🥖 Stuff", "🍽️ Lunch: Old", "Lunch: Old"):
            with self.subTest(title=title):
                existing = [
                    {"start": self.today.isoformat(), "summary": title, "location": "Lincoln Elementary"},
                    {"start": (self.today + timedelta(days=2)).isoformat(), "summary": title, "location": "Lincoln Elementary"},
                ]
                hass = self.hass(existing=existing)
                entry = MockConfigEntry(options={"sync_calendar": TARGET, "title_sections": []})
                self.assertEqual(await async_sync_entry(hass, entry, self.coordinator), 0)

    async def test_similar_menu_name_is_not_a_match(self):
        """A "Preschool Lunch" event doesn't count as the "Lunch" meal."""
        existing = [
            {"start": self.today.isoformat(), "summary": "🍽️ Preschool Lunch: Pasta", "location": "Lincoln Elementary"},
            {"start": self.today.isoformat(), "summary": "Preschool Lunch: Pasta", "location": "Lincoln Elementary"},
            {"start": self.today.isoformat(), "summary": "🍽️ Preschool Lunch", "location": "Lincoln Elementary"},
        ]
        hass = self.hass(existing=existing)
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        self.assertEqual(await async_sync_entry(hass, entry, self.coordinator), 2)

    async def test_unrelated_events_do_not_block_sync(self):
        existing = [
            # Same day, different menu / different school / different day
            {"start": self.today.isoformat(), "summary": "Breakfast: Waffles", "location": "Lincoln Elementary"},
            {"start": self.today.isoformat(), "summary": "Lunch: Tacos", "location": "Other School"},
            {"start": self.tomorrow.isoformat(), "summary": "Lunch: Cheeseburger, Pizza", "location": "Lincoln Elementary"},
        ]
        hass = self.hass(existing=existing)
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        created = await async_sync_entry(hass, entry, self.coordinator)

        self.assertEqual(created, 2)

    async def test_second_sync_after_first_creates_nothing(self):
        entry = MockConfigEntry(options={"sync_calendar": TARGET})
        hass = self.hass()
        await async_sync_entry(hass, entry, self.coordinator)

        # Feed what was created back as the calendar's contents
        hass2 = self.hass(
            existing=[
                {"start": c["start_date"], "summary": c["summary"], "location": c["location"]}
                for c in hass.services.created
            ]
        )
        created = await async_sync_entry(hass2, entry, self.coordinator)

        self.assertEqual(created, 0)
        self.assertEqual(hass2.services.created, [])

    async def test_no_sync_calendar_configured_does_nothing(self):
        hass = self.hass()
        entry = MockConfigEntry(options={})

        self.assertEqual(await async_sync_entry(hass, entry, self.coordinator), 0)
        self.assertEqual(hass.services.calls, [])

    async def test_nothing_upcoming_makes_no_calls(self):
        self.coordinator.data = {
            "lunch": make_menu("lunch", "Lunch", [make_day(self.today - timedelta(days=3), ["Old"])])
        }
        hass = self.hass()
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        self.assertEqual(await async_sync_entry(hass, entry, self.coordinator), 0)
        self.assertEqual(hass.services.calls, [])

    async def test_multiple_menu_types_sync_separately(self):
        breakfast = make_menu("breakfast", "Breakfast", [make_day(self.today, ["Waffles"])])
        self.coordinator.data["breakfast"] = breakfast
        hass = self.hass()
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        await async_sync_entry(hass, entry, self.coordinator)

        self.assertEqual(
            [c["summary"] for c in hass.services.created],
            ["🥞 Breakfast: Waffles", "🍽️ Lunch: Cheeseburger, Pizza", "🍽️ Lunch: Chicken Wings"],
        )

    async def test_lookup_failure_is_logged_not_raised(self):
        hass = self.hass(fail_on="get_events")
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        self.assertEqual(await async_sync_entry(hass, entry, self.coordinator), 0)
        self.assertEqual(hass.services.created, [])

    async def test_create_failure_stops_without_raising(self):
        hass = self.hass(fail_on="create_event")
        entry = MockConfigEntry(options={"sync_calendar": TARGET})

        self.assertEqual(await async_sync_entry(hass, entry, self.coordinator), 0)
        # Gave up after the first failure instead of retrying every meal
        self.assertEqual(sum(1 for _, s, _ in hass.services.calls if s == "create_event"), 1)


if __name__ == "__main__":
    unittest.main()
