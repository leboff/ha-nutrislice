"""Unit tests for the Nutrislice coordinator and data parser."""
from datetime import date, datetime
import unittest
from unittest.mock import patch

from tests.ha_mock import setup_ha_mocks

setup_ha_mocks()

from custom_components.nutrislice import coordinator as coordinator_module
from custom_components.nutrislice.coordinator import (
    NutrisliceMenuData,
    ParsedDayMenu,
    calendar_title_prefix,
    classify_item,
    escape_markdown,
    parse_day,
)


def item(name, category):
    return {"food": {"name": name, "food_category": category}}


def section(text):
    return {"is_section_title": True, "text": text}


# A real Pender County Schools (greatschools) lunch, 2026-09-21
REAL_LUNCH = {
    "date": "2026-09-21",
    "menu_items": [
        section("Daily Serve Entree"),
        item("Peanut Butter & Jelly Sandwich", "sandwich"),
        section("Entree"),
        item("Fresh Baked Breadstick", "side"),
        item("Salisbury Steak", "entree"),
        item("Beef Gravy", "sauce_grvy"),
        item("Pepperoni Pizza", "pizza"),
        section("Express"),
        item("Egg Chef Salad", "salad"),
        item("Dinner Roll", "side"),
        section("Fruit"),
        item("Red Delicious Apple", "side"),
        item("Fruit Juice", "beverage"),
        section("Vegetable"),
        item("Mashed Potatoes", "side"),
        section("Milk"),
        item("1% Milk", "beverage"),
        section("Condiments"),
        item("Ketchup", "condiment"),
    ],
}


class TestNutrisliceCoordinatorParser(unittest.TestCase):
    """Test menu parsing and classification logic."""

    def test_parse_day_with_real_menu_items(self):
        """Test parsing day payload with entrees, sides, milk, and condiments."""
        raw_day = {
            "date": "2026-09-18",
            "is_holiday": False,
            "menu_items": [
                # Entree section
                {"is_section_title": True, "text": "Entree"},
                {
                    "food": {
                        "name": "Cheeseburger",
                        "food_category": "sandwich",
                        "rounded_nutrition_info": {"calories": 360.0},
                        "icons": {"food_icons": [{"name": "Milk"}, {"name": "Wheat"}]},
                    }
                },
                {
                    "food": {
                        "name": "Cheese Pizza",
                        "food_category": "pizza",
                        "rounded_nutrition_info": {"calories": 320.0},
                    }
                },
                # Fruit / Side section
                {"is_section_title": True, "text": "Fruit"},
                {
                    "food": {
                        "name": "Red Delicious Apple",
                        "food_category": "side",
                    }
                },
                # Vegetable section
                {"is_section_title": True, "text": "Vegetable"},
                {
                    "food": {
                        "name": "Fresh Cucumber Slices",
                        "food_category": "side",
                    }
                },
                # Milk section
                {"is_section_title": True, "text": "Milk"},
                {
                    "food": {
                        "name": "Chocolate Skim Milk",
                        "food_category": "beverage",
                    }
                },
                # Condiments
                {"is_section_title": True, "text": "Condiments"},
                {
                    "food": {
                        "name": "Ketchup",
                        "food_category": "condiment",
                    }
                },
            ],
        }

        parsed: ParsedDayMenu = parse_day(raw_day)

        self.assertEqual(parsed.date_str, "2026-09-18")
        self.assertEqual(parsed.target_date, date(2026, 9, 18))
        self.assertFalse(parsed.is_holiday)
        self.assertTrue(parsed.has_menu)

        # Verify entrees
        self.assertIn("Cheeseburger", parsed.entrees)
        self.assertIn("Cheese Pizza", parsed.entrees)
        self.assertEqual(len(parsed.entrees), 2)

        # Verify sides
        self.assertIn("Red Delicious Apple", parsed.sides)
        self.assertIn("Fresh Cucumber Slices", parsed.sides)

        # Verify beverages and condiments
        self.assertIn("Chocolate Skim Milk", parsed.beverages)
        self.assertIn("Ketchup", parsed.condiments)

        # Verify summary
        self.assertEqual(parsed.summary, "Cheeseburger, Cheese Pizza")

        # Verify formatted description
        desc = parsed.formatted_description
        self.assertIn("Cheeseburger", desc)
        self.assertIn("Red Delicious Apple", desc)
        self.assertIn("Chocolate Skim Milk", desc)

        # Verify individual parsed item details
        cheeseburger_item = next(i for i in parsed.items if i.name == "Cheeseburger")
        self.assertTrue(cheeseburger_item.is_entree)
        self.assertEqual(cheeseburger_item.calories, 360.0)
        self.assertEqual(cheeseburger_item.allergens, ["Milk", "Wheat"])

    def test_parse_day_empty_menu(self):
        """Test parsing weekend or holiday with no menu items."""
        raw_day = {
            "date": "2026-09-19",
            "is_holiday": False,
            "menu_items": [],
        }

        parsed = parse_day(raw_day)
        self.assertFalse(parsed.has_menu)
        self.assertEqual(parsed.entrees, [])
        self.assertEqual(parsed.summary, "No Menu Scheduled")

    def test_parse_day_long_summary_truncation(self):
        """Test summary truncates properly to prevent Home Assistant 255-char state limit."""
        raw_day = {
            "date": "2026-09-20",
            "menu_items": [
                {"is_section_title": True, "text": "Entree"},
            ]
            + [
                {"food": {"name": f"Super Long Entree Item Option Number {i} With Extra Description", "food_category": "entree"}}
                for i in range(15)
            ],
        }

        parsed = parse_day(raw_day)
        self.assertLessEqual(len(parsed.summary), 250)
        self.assertTrue(parsed.summary.endswith("..."))


class TestEventTitleSections(unittest.TestCase):
    """The courses chosen in the options decide what an event title shows."""

    def setUp(self):
        self.day = parse_day(REAL_LUNCH)

    def test_default_is_entrees_with_meal_emoji(self):
        self.assertEqual(
            self.day.calendar_summary("Lunch"),
            "🍽️ Lunch: Peanut Butter & Jelly Sandwich, Salisbury Steak, Pepperoni Pizza, Egg Chef Salad",
        )
        self.assertEqual(self.day.calendar_summary("Lunch", ["entrees"]), self.day.calendar_summary("Lunch"))

    def test_several_courses_each_led_by_their_emoji(self):
        self.assertEqual(
            self.day.calendar_summary("Lunch", ["entrees", "sides", "fruits"]),
            "Lunch: 🍽️ Peanut Butter & Jelly Sandwich, Salisbury Steak, Pepperoni Pizza, Egg Chef Salad"
            " 🥖 Fresh Baked Breadstick, Dinner Roll 🍎 Red Delicious Apple",
        )

    def test_courses_follow_menu_order_not_selection_order(self):
        self.assertEqual(
            self.day.calendar_summary("Lunch", ["beverages", "vegetables"]),
            "Lunch: 🥦 Mashed Potatoes 🥛 Fruit Juice, 1% Milk",
        )

    def test_empty_course_is_skipped(self):
        no_veg = parse_day({**REAL_LUNCH, "menu_items": [i for i in REAL_LUNCH["menu_items"] if i.get("text") != "Vegetable" and (i.get("food") or {}).get("name") != "Mashed Potatoes"]})
        self.assertEqual(no_veg.calendar_summary("Lunch", ["vegetables", "fruits"]), "Lunch: 🍎 Red Delicious Apple")

    def test_nothing_selected_shows_just_the_meal(self):
        self.assertEqual(self.day.calendar_summary("Lunch", []), "🍽️ Lunch")
        self.assertEqual(self.day.calendar_summary("Breakfast", []), "🥞 Breakfast")


def menu_data(school_days):
    """Menu data with a one-entree menu on each of the given dates."""
    days = {}
    for d in school_days:
        days[d.isoformat()] = parse_day(
            {"date": d.isoformat(), "menu_items": [section("Entree"), item(f"Meal {d.day}", "entree")]}
        )
    return NutrisliceMenuData(
        district="d", school_slug="s", school_name="School", menu_type_slug="lunch",
        menu_type_name="Lunch", days_by_date=days, last_updated=datetime(2026, 9, 17, 12, 0),
    )


def at(data, when):
    """Return (today, tomorrow, next school day) as meal names, as of `when`."""
    with patch.object(coordinator_module.dt_util, "now", return_value=when):
        name = lambda day: day.entrees[0] if day else None
        return name(data.today), name(data.tomorrow), name(data.next_school_day)


class TestDayPointers(unittest.TestCase):
    """Today, tomorrow, and next school day follow the clock, not the last refresh."""

    # Mon-Fri Sep 14-18, Mon Sep 21 is a holiday, Tue-Fri Sep 22-25, then a two-week break
    DATA = menu_data(
        [date(2026, 9, d) for d in (14, 15, 16, 17, 18, 22, 23, 24, 25)] + [date(2026, 10, 12)]
    )

    def test_school_day_evening(self):
        self.assertEqual(at(self.DATA, datetime(2026, 9, 16, 18)), ("Meal 16", "Meal 17", "Meal 17"))

    def test_rolls_over_at_midnight_without_a_refresh(self):
        """The same data read either side of midnight gives a different day."""
        before = at(self.DATA, datetime(2026, 9, 17, 23, 59))
        after = at(self.DATA, datetime(2026, 9, 18, 0, 1))
        self.assertEqual(before, ("Meal 17", "Meal 18", "Meal 18"))
        self.assertEqual(after, ("Meal 18", None, "Meal 22"))

    def test_weekend_points_to_the_next_school_day(self):
        self.assertEqual(at(self.DATA, datetime(2026, 9, 19, 18)), (None, None, "Meal 22"))

    def test_holiday_weekday_has_no_menu_but_tomorrow_does(self):
        self.assertEqual(at(self.DATA, datetime(2026, 9, 21, 12)), (None, "Meal 22", "Meal 22"))

    def test_break_points_to_the_first_day_back(self):
        self.assertEqual(at(self.DATA, datetime(2026, 10, 3, 18)), (None, None, "Meal 12"))

    def test_summer_has_nothing(self):
        self.assertEqual(at(menu_data([]), datetime(2026, 7, 6, 12)), (None, None, None))

    def test_past_days_are_never_the_next_school_day(self):
        self.assertEqual(at(self.DATA, datetime(2026, 10, 13, 12))[2], None)


class TestFormattedMarkdown(unittest.TestCase):
    """The pre-formatted menu for dashboard Markdown cards."""

    def test_real_menu_is_grouped_with_bold_emoji_headings_and_bullets(self):
        self.assertEqual(
            parse_day(REAL_LUNCH).formatted_markdown,
            "**🍽️ Entrees**\n- Peanut Butter & Jelly Sandwich\n- Salisbury Steak\n- Pepperoni Pizza\n- Egg Chef Salad"
            "\n\n**🥖 Sides**\n- Fresh Baked Breadstick\n- Dinner Roll"
            "\n\n**🍎 Fruit**\n- Red Delicious Apple"
            "\n\n**🥦 Vegetables**\n- Mashed Potatoes"
            "\n\n**🥛 Beverages**\n- Fruit Juice\n- 1% Milk",
        )

    def test_matches_the_calendar_description_courses(self):
        """Same groups in the same order; only the markup differs."""
        day = parse_day(REAL_LUNCH)
        strip = lambda text: [line.strip("*• -:") for line in text.splitlines() if line.strip()]
        self.assertEqual(strip(day.formatted_markdown), strip(day.formatted_description))

    def test_empty_day(self):
        self.assertEqual(parse_day({"date": "2026-09-19", "menu_items": []}).formatted_markdown, "No menu scheduled")

    def test_markdown_characters_in_names_are_escaped(self):
        day = parse_day({"date": "2026-09-19", "menu_items": [
            section("Entree"), item("Mac_n_Cheese *Special* [new] <b>", "entree")]})
        self.assertEqual(day.formatted_markdown, "**🍽️ Entrees**\n- Mac\\_n\\_Cheese \\*Special\\* \\[new\\] \\<b\\>")

    def test_escape_leaves_ordinary_punctuation_alone(self):
        for text in ("PBJ Sandwich, Animal Crackers & Cheese Stick Pack", "1% Milk", "Chef's Salad (fresh)", "Mac-n-Cheese"):
            self.assertEqual(escape_markdown(text), text)


class TestClassification(unittest.TestCase):
    """Items are grouped by their own category before the section they're listed under."""

    def test_real_menu_entrees_are_only_the_mains(self):
        parsed = parse_day(REAL_LUNCH)
        self.assertEqual(
            parsed.entrees,
            ["Peanut Butter & Jelly Sandwich", "Salisbury Steak", "Pepperoni Pizza", "Egg Chef Salad"],
        )

    def test_breads_under_entree_headings_are_sides(self):
        parsed = parse_day(REAL_LUNCH)
        self.assertIn("Fresh Baked Breadstick", parsed.sides)
        self.assertIn("Dinner Roll", parsed.sides)

    def test_gravy_is_a_condiment(self):
        self.assertEqual(parse_day(REAL_LUNCH).condiments, ["Beef Gravy", "Ketchup"])

    def test_juice_listed_under_fruit_is_a_beverage(self):
        self.assertEqual(parse_day(REAL_LUNCH).beverages, ["Fruit Juice", "1% Milk"])

    def test_fruit_and_vegetables_split_out_of_sides(self):
        parsed = parse_day(REAL_LUNCH)
        self.assertEqual(parsed.fruits, ["Red Delicious Apple"])
        self.assertEqual(parsed.vegetables, ["Mashed Potatoes"])
        # sides still holds everything, so existing templates keep working
        self.assertEqual(
            parsed.sides,
            ["Fresh Baked Breadstick", "Dinner Roll", "Red Delicious Apple", "Mashed Potatoes"],
        )

    def test_description_groups_with_emoji_headings(self):
        self.assertEqual(
            parse_day(REAL_LUNCH).formatted_description,
            "🍽️ Entrees:\n• Peanut Butter & Jelly Sandwich\n• Salisbury Steak\n• Pepperoni Pizza\n• Egg Chef Salad"
            "\n\n🥖 Sides:\n• Fresh Baked Breadstick\n• Dinner Roll"
            "\n\n🍎 Fruit:\n• Red Delicious Apple"
            "\n\n🥦 Vegetables:\n• Mashed Potatoes"
            "\n\n🥛 Beverages:\n• Fruit Juice\n• 1% Milk",
        )

    def test_event_title_lists_only_entrees_with_emoji(self):
        self.assertEqual(
            parse_day(REAL_LUNCH).calendar_summary("Lunch"),
            "🍽️ Lunch: Peanut Butter & Jelly Sandwich, Salisbury Steak, Pepperoni Pizza, Egg Chef Salad",
        )

    def test_salad_depends_on_section(self):
        self.assertEqual(classify_item("salad", "express"), "entree")
        self.assertEqual(classify_item("salad", "vegetable"), "side")

    def test_section_decides_when_category_is_missing(self):
        self.assertEqual(classify_item("", "entree"), "entree")
        self.assertEqual(classify_item("", "milk"), "beverage")
        self.assertEqual(classify_item("", "condiments"), "condiment")
        self.assertEqual(classify_item("", "fruit"), "side")

    def test_menu_emoji(self):
        self.assertEqual(calendar_title_prefix("Lunch"), "🍽️ Lunch: ")
        self.assertEqual(calendar_title_prefix("Preschool Breakfast"), "🥞 Preschool Breakfast: ")
        self.assertEqual(calendar_title_prefix("After School Snack Menu"), "🍪 After School Snack Menu: ")


if __name__ == "__main__":
    unittest.main()
