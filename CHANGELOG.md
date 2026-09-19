# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- **Today and Tomorrow showed the wrong day after midnight.** They were worked out when the menu was fetched, so until the next refresh (every 4 hours by default, up to 24) Today still showed yesterday's menu and Tomorrow showed today's. They're now worked out when read, and every entity is rewritten at midnight, so they roll over on time without fetching anything.
- **The README's "school lunch reminder" fired on weekends and on every evening of a school break.** It relied on the Tomorrow sensor's state, but when tomorrow has no menu that sensor shows the *next school day's* menu, which looked like a valid menu. In a four-week simulation with a holiday Monday and a two-week break it fired 19 times when it shouldn't have. It's replaced with a calendar trigger, which only fires for days that have a menu, so weekends, holidays, no-school weekdays, breaks, and summer are all skipped with no conditions to maintain (no misfires in the same simulation).

### Changed
- README: documents how weekends, holidays, breaks, and summer appear (Nutrislice doesn't distinguish them; they're all days with no menu), warns against using the Tomorrow sensor's state alone to decide whether there's school, and the dashboard card's second heading now reads "Next School Day" only when tomorrow has no menu, and "Tomorrow" otherwise.
- The "show next school day on weekends" option is now labelled "Show the next school day when tomorrow has no menu", which is what it has always done.

## [1.6.0] - 2026-09-19

### Added
- **`menu_markdown` attribute on the Today and Tomorrow sensors:** the whole menu pre-formatted as Markdown, with a bold emoji heading and bullet list for each course (🍽️ Entrees, 🥖 Sides, 🍎 Fruit, 🥦 Vegetables, 🥛 Beverages). Drop it straight into a Markdown card; a day with no menu reads `No menu scheduled`, so a card never shows `None`. It is always the full menu, whatever courses are ticked for titles and states. The README's dashboard card now uses it.

### Changed
- **The course checkboxes now also set the Today and Tomorrow sensor states**, so they match the calendar event titles. With the default (Entrees only) nothing changes. A day with no menu is always `No Menu Scheduled`, whatever is ticked, and long states are shortened to fit Home Assistant's 255-character limit. Attributes always contain the full menu. The setting is now labelled "Show in calendar titles and sensors".

### Removed
- **The raw "Menu" sensor (`sensor.<school>_<menu>_menu`).** Nothing in the integration used it. It held every menu item Nutrislice returns for two weeks, over 1 MB, about 100 times what Home Assistant's database accepts, so it caused recorder size warnings on every update and was sent to every open browser. Existing copies are removed automatically on upgrade. If a template or dashboard read its `days` attribute, switch it to the Today and Tomorrow sensors, whose attributes hold the same menu items, or to `menu_markdown`.

## [1.5.0] - 2026-09-19

### Added
- **Choose what calendar event titles show.** A new "Show in calendar event titles" setting, offered during setup and under **Configure**, has a checkbox for each course: 🍽️ Entrees, 🥖 Sides, 🍎 Fruit, 🥦 Vegetables, and 🥛 Beverages. Entrees only is the default and keeps titles as before. With more ticked, each course is led by its emoji (`Lunch: 🍽️ Cheeseburger, Pizza 🍎 Apple`). With none ticked, the title is just `🍽️ Lunch`.

### Changed
- Calendar sync recognizes a meal it already synced whatever the title style, so changing the title setting doesn't duplicate synced meals. Existing synced events keep their old title.

## [1.4.0] - 2026-09-18

### Changed
- **Calendar events are grouped by course with emoji headings.** The description now lists 🍽️ Entrees, 🥖 Sides, 🍎 Fruit, 🥦 Vegetables, and 🥛 Beverages, and the title starts with a meal emoji (🍽️ lunch, 🥞 breakfast, 🍪 snack), e.g. `🍽️ Lunch: Salisbury Steak, Pepperoni Pizza`.
- Calendar sync recognizes meals it synced before this release (titles without the emoji), so they aren't created again.

### Added
- `fruits` and `vegetables` attributes on the Today and Tomorrow sensors. `sides` still includes them, so existing templates keep working.

### Fixed
- **Menu items are categorized by their own food category first**, not just the heading they're listed under. Breadsticks and rolls listed under "Entree" are now sides, gravy is a condiment, and juice under "Fruit" is a beverage, so event titles and the entree sensors list only actual entrees.

## [1.3.2] - 2026-09-18

### Changed
- Restored the fuller README layout (emoji section headings, installation options, setup details, calendar sync notes), keeping the corrected examples from 1.3.1.

## [1.3.1] - 2026-09-18

### Fixed
- README examples, checked against a running Home Assistant:
  - Removed the raw `days` notification template, which always failed with `UndefinedError`.
  - The evening-before notification now names the day ("Lunch for Monday") instead of saying "Tomorrow" over weekends, and uses a native state condition.
  - The markdown card no longer errors when the sensors are unavailable.

### Changed
- Simplified the README and documented the sensor attributes the examples use.

## [1.3.0] - 2026-09-18

### Added
- Setup now has **two separate boxes**: one for a link to your school's Nutrislice menu, and one for searching by district name. The link is presented first because it always works, and the step links directly to [Nutrislice Lookup](https://lookup.nutrislice.com) for finding it.

### Changed
- Setup wording now talks about finding your *school*, and is explicit that name search guesses the district's web address and can't find districts whose address is unrelated to their name (for example Pender County Schools, which publishes at `greatschools.nutrislice.com`).
- A link that isn't a Nutrislice address is now rejected immediately, without a network request.

### Fixed
- **Entity names no longer repeat the meal type.** A school whose name already ends with the menu type produced names like "Surf City Elementary Lunch Lunch Calendar". Entity names now omit a meal type the device name already carries, and the redundant trailing "Calendar" is dropped, giving "Surf City Elementary Lunch".
  - Existing entity IDs are preserved by Home Assistant, so automations keep working; only display names change.
- The school step no longer shows `[formatjs Error: MISSING_VALUE] ... "district" was not provided`. That happened when a stale cached translation was rendered against the newer step; the step now supplies the older `{district}` placeholder as well.

## [1.2.0] - 2026-09-18

### Added
- **Search by name during setup.** Type a district's name (e.g. `Souderton`, `Austin ISD`, `Fairfax County Public Schools`) instead of needing its exact Nutrislice address. Every matching district is searched, and the next step lists their schools to pick from, labelled by district when more than one matched.
  - Nutrislice has no public district directory, so names are matched against the web addresses districts commonly use (`name`, `namesd`, `nameschools`, initials, ...). Setup points to [Nutrislice Lookup](https://lookup.nutrislice.com) for districts that don't match.
  - Links and exact addresses still work, and a link that includes a school still skips straight to choosing menus.
- New `dark_icon.png` and `dark_logo.png` brand images for Home Assistant's dark theme.

### Changed
- Setup text and the error for a name that matches nothing now explain how to find your district.

### Fixed
- Entering a district that doesn't exist reported "Failed to connect to Nutrislice servers" instead of "district not found", because unknown districts fail at DNS. Now it only reports a connection problem when Nutrislice itself can't be reached.
- The integration icon and logo were the wrong image. They now use the Nutrislice mark.

## [1.1.0] - 2026-09-18

### Added
- **Calendar sync:** optionally copy upcoming meals into any writable Home Assistant calendar (Local Calendar, Google Calendar, CalDAV, ...) as all-day events. Choose the calendar under **Configure** > **Sync menus to calendar**.
  - Runs at startup and after every menu update.
  - Meals already on the target calendar are skipped, so nothing is duplicated.
  - Sync only adds events. Home Assistant offers no way to edit or delete calendar events, so a menu changed by the school after syncing is not updated.
- New `nutrislice.sync_calendar` action to sync immediately.

### Changed
- Minimum Home Assistant version is now 2024.11.0.
- README is no longer specific to elementary schools, and automation examples use current Home Assistant syntax.

### Fixed
- Options flow no longer sets `config_entry` explicitly, which stops working in Home Assistant 2025.12.
- "Today" is now determined by Home Assistant's configured time zone instead of the server's.
- The calendar entity no longer returns a meal that falls on the (exclusive) end of the requested range.
