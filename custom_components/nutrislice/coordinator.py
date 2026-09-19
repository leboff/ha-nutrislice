"""DataUpdateCoordinator for Nutrislice."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NutrisliceApiClient, NutrisliceError
from .const import (
    CONF_DISTRICT,
    CONF_MENU_TYPES,
    CONF_SCAN_INTERVAL_HOURS,
    CONF_SCHOOL_NAME,
    CONF_SCHOOL_SLUG,
    DEFAULT_SCAN_INTERVAL_HOURS,
    BEVERAGE_FOOD_CATEGORIES,
    COURSE_EMOJI,
    COURSE_HEADINGS,
    DEFAULT_TITLE_SECTIONS,
    CONDIMENT_FOOD_CATEGORIES,
    CONDIMENT_FOOD_CATEGORY_PREFIXES,
    DEFAULT_UPCOMING_WEEKS,
    ENTREE_FOOD_CATEGORIES,
    ENTREE_SECTION_KEYWORDS,
    IGNORE_SECTION_KEYWORDS,
    LOGGER,
    SIDE_FOOD_CATEGORIES,
)


@dataclass
class ParsedFoodItem:
    """Represents an individual food item."""

    name: str
    category: str
    section: str
    is_entree: bool
    is_side: bool
    calories: float | None = None
    allergens: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDayMenu:
    """Represents a day's menu."""

    date_str: str
    target_date: date
    is_holiday: bool
    has_menu: bool
    entrees: list[str] = field(default_factory=list)
    # Everything that isn't an entree, beverage, or condiment (fruit and vegetables included)
    sides: list[str] = field(default_factory=list)
    beverages: list[str] = field(default_factory=list)
    condiments: list[str] = field(default_factory=list)
    # Subsets of sides, split out for display
    fruits: list[str] = field(default_factory=list)
    vegetables: list[str] = field(default_factory=list)
    items: list[ParsedFoodItem] = field(default_factory=list)
    categories: dict[str, list[str]] = field(default_factory=dict)
    raw_day: dict[str, Any] = field(default_factory=dict)

    @property
    def has_entrees(self) -> bool:
        """Return True if the day has a published menu with at least one entree."""
        return self.has_menu and bool(self.entrees)

    @property
    def summary(self) -> str:
        """Return clean summary of entrees for state display (capped at 255 chars)."""
        if not self.has_entrees:
            return "No Menu Scheduled"
        return truncate_state(", ".join(self.entrees))

    @property
    def courses(self) -> dict[str, list[str]]:
        """Return the menu split into courses, in display order.

        Fruit and vegetables are pulled out of ``sides`` so each appears once.
        """
        split_out = set(self.fruits) | set(self.vegetables)
        return {
            "entrees": self.entrees,
            "sides": [name for name in self.sides if name not in split_out],
            "fruits": self.fruits,
            "vegetables": self.vegetables,
            "beverages": self.beverages,
        }

    @property
    def formatted_description(self) -> str:
        """Menu grouped by course with emoji headings, for calendar events and notifications."""
        blocks = [
            f"{COURSE_EMOJI[course]} {COURSE_HEADINGS[course]}:\n"
            + "\n".join(f"• {name}" for name in names)
            for course, names in self.courses.items()
            if names
        ]
        return "\n\n".join(blocks) if blocks else "No menu items published."

    @property
    def formatted_markdown(self) -> str:
        """Menu grouped by course as Markdown, ready for a dashboard Markdown card.

        Each course is a bold emoji heading over a bullet list. Condiments are
        left out, as in the calendar description.
        """
        blocks = [
            f"**{COURSE_EMOJI[course]} {COURSE_HEADINGS[course]}**\n"
            + "\n".join(f"- {escape_markdown(name)}" for name in names)
            for course, names in self.courses.items()
            if names
        ]
        return "\n\n".join(blocks) if blocks else NO_MENU_MARKDOWN

    def courses_text(self, sections: list[str]) -> str:
        """Return the chosen courses on one line, each led by its emoji.

        For example "🍽️ Cheeseburger, Pizza 🍎 Apple". Courses with nothing on
        the menu that day, and unknown section names, are skipped.
        """
        return " ".join(
            f"{COURSE_EMOJI[course]} {', '.join(names)}"
            for course, names in self.courses.items()
            if course in sections and names
        )

    def calendar_summary(
        self, menu_name: str, sections: list[str] | None = None
    ) -> str:
        """Return the calendar event title.

        ``sections`` picks which courses appear. Entrees alone (the default)
        gives "🍽️ Lunch: Cheeseburger, Pizza"; several courses are each led
        by their emoji, "Lunch: 🍽️ Cheeseburger 🍎 Apple"; none gives "🍽️ Lunch".
        """
        if sections is None:
            sections = DEFAULT_TITLE_SECTIONS
        if list(sections) == ["entrees"] or not self.has_entrees:
            return f"{calendar_title_prefix(menu_name)}{self.summary}"

        text = self.courses_text(sections)
        if not text:
            return f"{menu_emoji(menu_name)} {menu_name}"
        return f"{menu_name}: {text}"

    def state_summary(
        self, menu_name: str, sections: list[str] | None = None
    ) -> str:
        """Return the sensor state: the event title without its menu name.

        The same courses as :meth:`calendar_summary`, so the sensors and the
        calendar always agree, cut down to fit Home Assistant's state limit.
        A day with no menu is always "No Menu Scheduled", which automations
        can rely on.
        """
        if sections is None:
            sections = DEFAULT_TITLE_SECTIONS
        if list(sections) == ["entrees"] or not self.has_entrees:
            return self.summary
        return truncate_state(
            self.courses_text(sections) or f"{menu_emoji(menu_name)} {menu_name}"
        )

@dataclass
class NutrisliceMenuData:
    """Menu data for a single menu type."""

    district: str
    school_slug: str
    school_name: str
    menu_type_slug: str
    menu_type_name: str
    days_by_date: dict[str, ParsedDayMenu]
    last_updated: datetime

    # today / tomorrow / next_school_day are worked out when read, not when the
    # menu was fetched, so they roll over at midnight instead of staying on the
    # previous day until the next refresh (up to the whole update interval).

    def _day_at(self, offset_days: int) -> ParsedDayMenu | None:
        """Return the menu offset_days from today, if one was published."""
        day = dt_util.now().date() + timedelta(days=offset_days)
        return self.days_by_date.get(day.isoformat())

    @property
    def today(self) -> ParsedDayMenu | None:
        """Today's menu, if one was published."""
        return self._day_at(0)

    @property
    def tomorrow(self) -> ParsedDayMenu | None:
        """Tomorrow's menu, if one was published."""
        return self._day_at(1)

    @property
    def next_school_day(self) -> ParsedDayMenu | None:
        """The first day after today with entrees.

        Nutrislice marks weekends, holidays, breaks, and summer alike, as days
        with no menu, so "school day" here simply means a day with a menu.
        """
        today = dt_util.now().date().isoformat()
        return next(
            (
                self.days_by_date[date_str]
                for date_str in sorted(self.days_by_date)
                if date_str > today and self.days_by_date[date_str].has_entrees
            ),
            None,
        )


NO_MENU_MARKDOWN = "No menu scheduled"


def escape_markdown(text: str) -> str:
    """Escape characters that would be read as Markdown formatting in a menu item."""
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", text)


# Home Assistant rejects sensor states longer than 255 characters; leave headroom
STATE_TEXT_LIMIT = 250


def truncate_state(text: str) -> str:
    """Shorten text to fit in a sensor state, marking the cut with "..."."""
    if len(text) > STATE_TEXT_LIMIT:
        return text[: STATE_TEXT_LIMIT - 3] + "..."
    return text


def menu_emoji(menu_name: str) -> str:
    """Return an emoji for a meal type, matching the description's style."""
    name = menu_name.casefold()
    if "breakfast" in name:
        return "🥞"
    if "snack" in name:
        return "🍪"
    return "🍽️"


def calendar_title_prefix(menu_name: str) -> str:
    """Return the start of a meal's calendar event title, e.g. "🍽️ Lunch: "."""
    return f"{menu_emoji(menu_name)} {menu_name}: "


def menu_entity_name(school_name: str, menu_name: str, suffix: str = "") -> str | None:
    """Return an entity name that doesn't repeat what the device already says.

    Home Assistant renders "<device name> <entity name>", and the device is the
    school. A school whose name already ends with the menu type (for example
    "Surf City Elementary Lunch") would otherwise read "... Lunch Lunch".
    Returning None makes the entity simply take the device's name.
    """
    menu_name = menu_name.strip()
    school_name = school_name.strip()
    # Compare whole words, so "Deerlunch Academy Lunch" dedupes but "Brunch" doesn't
    ends_with_menu_name = school_name.casefold() == menu_name.casefold() or (
        school_name.casefold().endswith(f" {menu_name.casefold()}")
    )
    parts = [suffix] if ends_with_menu_name else [menu_name, suffix]
    return " ".join(part for part in parts if part) or None


def classify_item(food_category: str, section: str) -> str:
    """Return "entree", "side", "beverage", or "condiment" for a menu item.

    The item's own food_category is trusted first, because schools often list
    breads, gravies, and rolls under an "Entree" or "Express" heading. The
    section heading only decides when the category says nothing useful.
    """
    if food_category in CONDIMENT_FOOD_CATEGORIES or food_category.startswith(
        CONDIMENT_FOOD_CATEGORY_PREFIXES
    ):
        return "condiment"
    if food_category in BEVERAGE_FOOD_CATEGORIES:
        return "beverage"
    if food_category in ENTREE_FOOD_CATEGORIES:
        return "entree"
    if food_category in SIDE_FOOD_CATEGORIES:
        return "side"

    is_entree_section = any(kw in section for kw in ENTREE_SECTION_KEYWORDS)
    if food_category == "salad":
        # A chef salad under "Express" is a meal; a side salad isn't
        return "entree" if is_entree_section else "side"
    if any(kw in section for kw in IGNORE_SECTION_KEYWORDS):
        return "beverage" if ("milk" in section or "beverage" in section) else "condiment"
    if is_entree_section:
        return "entree"
    return "side"


def parse_day(raw_day: dict[str, Any]) -> ParsedDayMenu:
    """Parse a day dictionary from Nutrislice into ParsedDayMenu."""
    date_str = raw_day.get("date", "")
    try:
        t_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        t_date = dt_util.now().date()

    is_holiday = bool(raw_day.get("is_holiday", False))
    raw_menu_items = raw_day.get("menu_items", []) or []

    entrees: list[str] = []
    sides: list[str] = []
    beverages: list[str] = []
    condiments: list[str] = []
    fruits: list[str] = []
    vegetables: list[str] = []
    categories: dict[str, list[str]] = {}
    parsed_items: list[ParsedFoodItem] = []

    current_section = "General"

    for item in raw_menu_items:
        if not isinstance(item, dict):
            continue

        if item.get("is_section_title"):
            current_section = item.get("text") or "General"
            continue

        food = item.get("food")
        if not food or not isinstance(food, dict):
            continue

        name = food.get("name")
        if not name:
            continue
        name = name.strip()

        food_category = (food.get("food_category") or "").lower()
        section_lower = current_section.lower()

        # Nutrition & allergens
        calories = None
        rounded_nutr = food.get("rounded_nutrition_info")
        if isinstance(rounded_nutr, dict):
            calories = rounded_nutr.get("calories")

        allergens: list[str] = []
        icons = food.get("icons")
        if isinstance(icons, dict):
            food_icons = icons.get("food_icons")
            if isinstance(food_icons, list):
                for icon in food_icons:
                    if isinstance(icon, dict) and icon.get("name"):
                        allergens.append(icon["name"])

        kind = classify_item(food_category, section_lower)
        is_entree = kind == "entree"
        is_side = kind == "side"
        bucket = {
            "entree": entrees,
            "side": sides,
            "beverage": beverages,
            "condiment": condiments,
        }[kind]
        if name not in bucket:
            bucket.append(name)
        if is_side:
            is_fruit = food_category == "fruit" or "fruit" in section_lower
            is_vegetable = food_category == "vegetable" or any(
                kw in section_lower for kw in ("vegetable", "veggie")
            )
            group = fruits if is_fruit else vegetables if is_vegetable else None
            if group is not None and name not in group:
                group.append(name)

        categories.setdefault(current_section, []).append(name)
        parsed_items.append(
            ParsedFoodItem(
                name=name,
                category=food_category,
                section=current_section,
                is_entree=is_entree,
                is_side=is_side,
                calories=calories,
                allergens=allergens,
                raw_data=item,
            )
        )

    has_menu = len(parsed_items) > 0

    return ParsedDayMenu(
        date_str=date_str,
        target_date=t_date,
        is_holiday=is_holiday,
        has_menu=has_menu,
        entrees=entrees,
        sides=sides,
        beverages=beverages,
        condiments=condiments,
        fruits=fruits,
        vegetables=vegetables,
        items=parsed_items,
        categories=categories,
        raw_day=raw_day,
    )


class NutrisliceCoordinator(DataUpdateCoordinator[dict[str, NutrisliceMenuData]]):
    """Coordinator to fetch Nutrislice menu data for configured menu types."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: NutrisliceApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        self.client = client
        self.district: str = entry.data[CONF_DISTRICT]
        self.school_slug: str = entry.data[CONF_SCHOOL_SLUG]
        self.school_name: str = entry.data.get(CONF_SCHOOL_NAME, self.school_slug)
        self.menu_types: list[dict[str, Any]] = entry.data.get(CONF_MENU_TYPES, [])
        # Serializes pushes into the sync target calendar (see calendar_sync.py)
        self.sync_lock = asyncio.Lock()

        scan_interval_hours = entry.options.get(
            CONF_SCAN_INTERVAL_HOURS,
            entry.data.get(CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS),
        )

        super().__init__(
            hass,
            LOGGER,
            name=f"Nutrislice ({self.school_name})",
            update_interval=timedelta(hours=scan_interval_hours),
        )

    async def _async_update_data(self) -> dict[str, NutrisliceMenuData]:
        """Fetch all menu types data from Nutrislice."""
        result: dict[str, NutrisliceMenuData] = {}
        now = dt_util.now()
        today_date = now.date()

        for menu_info in self.menu_types:
            menu_type_slug = menu_info.get("slug")
            menu_type_name = menu_info.get("name", menu_type_slug)
            if not menu_type_slug:
                continue

            try:
                raw_days = await self.client.async_get_upcoming_menu(
                    district=self.district,
                    school_slug=self.school_slug,
                    menu_type_slug=menu_type_slug,
                    start_date=today_date,
                    weeks=DEFAULT_UPCOMING_WEEKS,
                )
            except NutrisliceError as err:
                raise UpdateFailed(
                    f"Error updating Nutrislice menu for {self.school_slug}/{menu_type_slug}: {err}"
                ) from err

            days_by_date: dict[str, ParsedDayMenu] = {}
            for d in raw_days:
                parsed = parse_day(d)
                days_by_date[parsed.date_str] = parsed

            result[menu_type_slug] = NutrisliceMenuData(
                district=self.district,
                school_slug=self.school_slug,
                school_name=self.school_name,
                menu_type_slug=menu_type_slug,
                menu_type_name=menu_type_name,
                days_by_date=days_by_date,
                last_updated=now,
            )

        return result
