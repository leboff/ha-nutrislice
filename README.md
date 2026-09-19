# Nutrislice School Menus for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/default)
[![Validate](https://img.shields.io/github/actions/workflow/status/The-Croz/ha-nutrislice/validate.yml?branch=main&label=Hassfest%20%26%20HACS&style=for-the-badge)](https://github.com/The-Croz/ha-nutrislice/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration for tracking school menus (Lunch, Breakfast, Snacks, etc.) published on **Nutrislice**, for any school or district on the platform.

View upcoming meals on a Home Assistant calendar, show today's and tomorrow's menu on your dashboard, and automate notifications for the next school meal.

---

## ✨ Features

- 🔍 **Easy Setup:** Paste a link to your school's Nutrislice menu, or search by district name. The integration then finds your school and all of its available meal menus.
- 📅 **Native Calendar Platform:** Generates all-day calendar events for each school day with entrees, sides, and beverages, directly on your Home Assistant calendar.
- 🔄 **Calendar Sync:** Optionally copy upcoming meals into any writable calendar (Local Calendar, Google Calendar, CalDAV, ...) so they appear alongside your other events on every device.
- 🍽️ **Smart Sensors:**
  - **Today's Menu:** Displays today's main entrees as state, with sides, allergens, and full menu items in attributes.
  - **Tomorrow's Menu:** Displays tomorrow's main entrees (with an option to preview Monday's lunch over the weekend!).
  - **Dashboard-Ready Menu:** Both sensors have a `menu_markdown` attribute with the whole menu grouped by course, ready to drop into a Markdown card.
- 🛡️ **Rate-Limit Friendly:** Fetches 2 weeks in advance with configurable update polling (default: every 4 hours).
- 🏷️ **Clean Item Categorization:** Separates entrees from sides, fruits, vegetables, milk, and condiments.

---

## 📦 Installation

### Option 1: HACS (Recommended)

1. Ensure [HACS (Home Assistant Community Store)](https://hacs.xyz/) is installed.
2. In Home Assistant, open **HACS** > **Integrations**.
3. Click the **three dots** in the top right corner and select **Custom repositories**.
4. Paste the repository URL: `https://github.com/The-Croz/ha-nutrislice`
5. Select **Integration** as the Category and click **Add**.
6. Find **Nutrislice School Menus** in HACS, click **Download**, and restart Home Assistant.

### Option 2: Manual Installation

1. Download the `custom_components/nutrislice` folder from the latest release.
2. Copy the `nutrislice` folder into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant.

---

## ⚙️ Configuration & School Discovery

The integration includes an interactive UI setup flow to find your school:

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **+ Add Integration** and search for **Nutrislice**.
3. On **Step 1 (Find Your School)**, fill in *either* box:
   - **Link to your school's Nutrislice menu** — the reliable option. Paste any address from your school's menu site, e.g. `https://my-district.nutrislice.com/menu/my-school/lunch`. A link that includes your school skips straight to Step 3.
   - **Or search by district name** — e.g. `Souderton` or `Fairfax County Public Schools`. See the caveat below.
4. **Step 2 (School Selection):** Pick your school from the list. If the search matched more than one district, each school is labelled with its district.
5. **Step 3 (Menu Types):** Select which meal menus to track (e.g. `Lunch`, `Breakfast`, `Snack`), and which courses to show in calendar event titles.
6. Click **Submit**. Your school device, sensors, and calendar entities are created automatically.

### Finding your link

Don't know your school's Nutrislice address? Open **[Nutrislice Lookup](https://lookup.nutrislice.com)**, search for your school, open its menu page, then copy the address out of your browser's address bar and paste it into Step 1.

### Why search by name doesn't always work

Nutrislice has no public directory of districts, and its own lookup service is protected by a CAPTCHA that an integration can't use. Searching by name therefore works by *guessing* the web address from the name — trying forms like `souderton`, `soudertonsd`, `soudertonschools`, and initials such as `fcps`.

That finds many districts, but **it cannot find a district whose web address is unrelated to its name.** For example, Pender County Schools in North Carolina publishes at `greatschools.nutrislice.com`, which no amount of guessing will produce from "Pender" or "Surf City". If your district is one of these, use the link instead — it always works.

---

## 📱 Entities Created

For each configured school and meal type:

| Entity Pattern | Platform | Description |
| :--- | :--- | :--- |
| `calendar.<school>_<menu>` | Calendar | Upcoming school meals with entree summaries and formatted descriptions. |
| `sensor.<school>_<menu>_today` | Sensor | State is today's entrees (e.g. `Cheeseburger, Pizza`), or `No Menu Scheduled`. |
| `sensor.<school>_<menu>_tomorrow` | Sensor | State is tomorrow's entrees (or the next school day's meal on weekends). |

**Weekends, holidays, breaks, and summer:** Nutrislice doesn't mark these any differently, they're simply days with no menu. On those days Today reads `No Menu Scheduled`, the calendar has no event, and nothing is synced. When *tomorrow* has no menu, the Tomorrow sensor shows the next day that does have one and sets its `is_next_school_day` attribute to `true` (turn this off under Options to always read `No Menu Scheduled` instead). During a break that can mean a menu several days away.

The Today and Tomorrow states show the same courses as your calendar event titles (see **Show in Calendar Titles and Sensors** under Options), so with the default they are the entree list shown above. The full menu is always in the attributes.

`<school>` is the school's name and `<menu>` is the meal type, both lowercased with underscores. *(For example, a school named "Maple Grove" with a Lunch menu gets `sensor.maple_grove_lunch_today`, `sensor.maple_grove_lunch_tomorrow`, and `calendar.maple_grove_lunch`.)*

> **Upgrading from 1.2.0 or earlier?** Entity IDs you already have are kept as-is by Home Assistant, so your automations keep working. Only the display names change (the redundant trailing "Calendar" is dropped).

The **Today** and **Tomorrow** sensors carry `date`, `entrees`, `sides`, `fruits`, `vegetables`, `beverages`, and `menu_items` (with calories and allergens) attributes, plus `menu_markdown`: the whole menu pre-formatted as Markdown (a bold heading and bullet list for each course, or `No menu scheduled`). The **Tomorrow** sensor also has `is_next_school_day`, which is `true` when it's showing a later school day because tomorrow has no menu. `sides` includes fruit and vegetables; `fruits` and `vegetables` list those separately.

The examples below use `my_school_lunch` as a placeholder. Replace it with your own entity IDs, which you can find under **Settings** > **Devices & Services** > **Nutrislice**.

---

## 🔄 Syncing Menus to Another Calendar

The calendar entities this integration creates are read-only. To get school meals onto a calendar you already use, such as a shared family calendar, sync them into a writable one:

1. Make sure you have a calendar that supports creating events, e.g. [Local Calendar](https://www.home-assistant.io/integrations/local_calendar/), [Google Calendar](https://www.home-assistant.io/integrations/google/) (with write access), or CalDAV.
2. Go to **Settings** > **Devices & Services** > **Nutrislice** and click **Configure**.
3. Pick the calendar under **Sync menus to calendar** and submit.

Upcoming meals are then copied as all-day events (titled like `🍽️ Lunch: Cheeseburger, Pizza`, with the menu grouped into 🍽️ Entrees, 🥖 Sides, 🍎 Fruit, 🥦 Vegetables, and 🥛 Beverages in the description, and the school as the location) right away, after every menu update, and whenever you call the `nutrislice.sync_calendar` action. All menu types for a school go to the same calendar. Clear the field to turn syncing off.

**Good to know:**
- Sync only adds events. Home Assistant has no way for an integration to edit or delete calendar events, so a meal is created once and never rewritten. If the school changes a menu after it was synced, edit or delete that event on the target calendar yourself.
- Meals already on the target calendar (same day, menu type, and school) are skipped, so nothing is duplicated. To re-create a meal, delete its event and run `nutrislice.sync_calendar`.
- Only today and upcoming days are synced; past meals are left alone.
- If the target calendar is missing or can't create events, a warning is logged and the next update tries again.

---

## 🔔 Automations & Notifications

### School Lunch Reminder
Trigger from the **calendar**, not the sensors. The calendar only has an event on days that have a menu, so this stays quiet on weekends, holidays, no-school weekdays, school breaks, and all summer, with no conditions to maintain.

```yaml
alias: School lunch reminder
triggers:
  - trigger: calendar
    event: start
    entity_id: calendar.my_school_lunch
    offset: "-06:00:00" # 6:00 PM the evening before. Use "07:00:00" for 7:00 AM that morning.
actions:
  - action: notify.notify
    data:
      title: "{{ trigger.calendar_event.summary }}"
      message: "{{ trigger.calendar_event.description }}"
```

The evening reminder for a Monday menu arrives on Sunday evening, and nothing is sent on Friday or Saturday. It only fires for days whose menu Nutrislice has published.

> **Don't use the Tomorrow sensor's state on its own to decide whether there's school tomorrow.** When tomorrow has no menu it shows the *next* school day's, so on a Friday it's a real menu and looks like there's school. If you must use it, also require its `is_next_school_day` attribute to be `false`.

---

## 📊 Dashboard Card Examples

### Markdown Card: Today & Tomorrow
The `menu_markdown` attribute is the whole menu, already grouped by course, so the card needs no formatting of its own. The second heading changes to "Next School Day" whenever tomorrow has no menu:

```yaml
type: markdown
title: School Lunch
content: |
  ## Today
  {{ state_attr('sensor.my_school_lunch_today', 'menu_markdown') or 'Not available' }}

  ## {{ 'Next School Day' if state_attr('sensor.my_school_lunch_tomorrow', 'is_next_school_day') else 'Tomorrow' }}
  {{ state_attr('sensor.my_school_lunch_tomorrow', 'menu_markdown') or 'Not available' }}
```

### Calendar Card
```yaml
type: calendar
entities:
  - calendar.my_school_lunch
initial_view: listWeek
```

---

## 🛠️ Options & Customization

Click **Configure** on the Nutrislice integration entry in **Settings** > **Devices & Services**:
- **Update Interval (hours):** Adjust how frequently Home Assistant checks for menu updates (1 to 24 hours, default `4`).
- **Show Next School Day When Tomorrow Has No Menu:** On by default. When tomorrow has no menu (weekends, holidays, breaks), the Tomorrow sensor shows the next day that does instead of `No Menu Scheduled`, and sets its `is_next_school_day` attribute to `true`.
- **Show in Calendar Titles and Sensors:** Tick which courses appear in calendar event titles and in the Today and Tomorrow sensor states: 🍽️ Entrees, 🥖 Sides, 🍎 Fruit, 🥦 Vegetables, 🥛 Beverages. The default, Entrees only, gives `🍽️ Lunch: Cheeseburger, Pizza`. Tick more and each course is led by its emoji, e.g. `Lunch: 🍽️ Cheeseburger, Pizza 🍎 Apple, Orange`. Tick none for just `🍽️ Lunch`. The full grouped menu is always in the event description, and every item is in the sensor attributes. Also offered during setup.
- **Sync Menus to Calendar:** Optional. Copy upcoming meals into another calendar. See [Syncing Menus to Another Calendar](#-syncing-menus-to-another-calendar).

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
