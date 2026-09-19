"""Unit tests for Nutrislice calendar entity."""
from datetime import date, datetime, timedelta
import unittest

from tests.ha_mock import MockConfigEntry, setup_ha_mocks

setup_ha_mocks()

from custom_components.nutrislice.calendar import NutrisliceCalendarEntity
from custom_components.nutrislice.coordinator import (
    NutrisliceMenuData,
    ParsedDayMenu,
)


class MockCoordinator:
    """Mock coordinator for calendar tests."""

    def __init__(self, data=None):
        self.district = "sample-district"
        self.school_slug = "lincoln-elementary"
        self.school_name = "Lincoln Elementary"
        self.data = data or {}


class TestNutrisliceCalendar(unittest.IsolatedAsyncioTestCase):
    """Test calendar entity methods and properties."""

    def setUp(self):
        self.today_date = date.today()
        self.today_str = self.today_date.isoformat()

        today_menu = ParsedDayMenu(
            date_str=self.today_str,
            target_date=self.today_date,
            is_holiday=False,
            has_menu=True,
            entrees=["Cheeseburger", "Cheese Pizza"],
            sides=["Apple", "Cucumbers"],
            beverages=["1% Milk"],
            raw_day={"date": self.today_str},
        )

        future_date = self.today_date + timedelta(days=2)
        future_menu = ParsedDayMenu(
            date_str=future_date.isoformat(),
            target_date=future_date,
            is_holiday=False,
            has_menu=True,
            entrees=["Chicken Wings"],
            sides=["Corn"],
            raw_day={"date": future_date.isoformat()},
        )

        self.menu_data = NutrisliceMenuData(
            district="sample-district",
            school_slug="lincoln-elementary",
            school_name="Lincoln Elementary",
            menu_type_slug="lunch",
            menu_type_name="Lunch",
            days_by_date={self.today_str: today_menu, future_date.isoformat(): future_menu},
            last_updated=datetime(2026, 9, 18, 12, 0, 0),
        )

        self.mock_coord = MockCoordinator(data={"lunch": self.menu_data})
        self.mock_entry = MockConfigEntry()
        self.calendar = NutrisliceCalendarEntity(self.mock_coord, self.mock_entry, "lunch")

    def test_current_event_property(self):
        """Test event property returns today's meal event."""
        event = self.calendar.event
        self.assertIsNotNone(event)
        self.assertEqual(event.summary, "🍽️ Lunch: Cheeseburger, Cheese Pizza")
        self.assertEqual(event.start, self.today_date)
        self.assertEqual(event.end, self.today_date + timedelta(days=1))
        self.assertIn("Apple", event.description)
        self.assertEqual(event.location, "Lincoln Elementary")

    async def test_async_get_events_in_range(self):
        """Test async_get_events returns events within queried window."""
        start_dt = datetime.combine(self.today_date, datetime.min.time())
        end_dt = datetime.combine(self.today_date + timedelta(days=7), datetime.max.time())

        events = await self.calendar.async_get_events(None, start_dt, end_dt)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].summary, "🍽️ Lunch: Cheeseburger, Cheese Pizza")
        self.assertEqual(events[1].summary, "🍽️ Lunch: Chicken Wings")

    async def test_async_get_events_end_is_exclusive(self):
        """A day starting exactly at the (exclusive) range end is not returned."""
        start_dt = datetime.combine(self.today_date, datetime.min.time())
        end_dt = datetime.combine(self.today_date + timedelta(days=2), datetime.min.time())

        events = await self.calendar.async_get_events(None, start_dt, end_dt)
        self.assertEqual([e.summary for e in events], ["🍽️ Lunch: Cheeseburger, Cheese Pizza"])

    async def test_async_get_events_excludes_days_before_range(self):
        """Days that end before the range starts are not returned."""
        start_dt = datetime.combine(self.today_date + timedelta(days=1), datetime.min.time())
        end_dt = datetime.combine(self.today_date + timedelta(days=7), datetime.min.time())

        events = await self.calendar.async_get_events(None, start_dt, end_dt)
        self.assertEqual([e.summary for e in events], ["🍽️ Lunch: Chicken Wings"])


if __name__ == "__main__":
    unittest.main()
