# 🌿 HA Plants for Home Assistant

**HA Plants** is a custom integration for [Home Assistant](https://www.home-assistant.io/) that helps you manage and monitor your houseplants. Track when each plant was last watered or fertilized, define care intervals, and use the resulting `sensor.ha_plants_*` entities on your dashboard, in automations, or in any Lovelace card that can show sensor state and attributes.

# Features

- Track multiple plants with individual settings
- Custom watering intervals and postponements
- Optional **fertilizing intervals** (days between fertilizing; `0` turns off fertilizing reminders)
- **Reminder notifications** for watering and fertilizing: daily check at a time you choose, optional mobile/desktop notify entity, and optional persistent notifications in Home Assistant
- Indoor/outdoor plant designation
- Automatic daily updates for days since watering and fertilizing
- Logbook integration for activity tracking
- Manage plants and reminders from the integration **Configure** UI, or use **Developer tools → Actions** (`ha_plants.*` services)

# Requirements

- **Home Assistant 2025.4.4** or newer (this is the minimum version recorded in [`hacs.json`](hacs.json) for HACS installs).
- **Optional notify reminders:** if you set a **Notify entity**, HA Plants calls the **`notify.send_message`** action with `entity_id`, `title`, and `message`. Use a `notify.*` entity that implements the [Notify entity platform](https://www.home-assistant.io/integrations/notify/) in your setup. If you leave the notify field empty, you can still rely on **persistent notifications** only.
- **HACS** (optional): when installing through HACS, use a HACS version that satisfies the `"hacs"` field in [`hacs.json`](hacs.json) (currently **2.0.5** or newer).

# Installation

You can install this component in two ways: via [HACS](https://github.com/hacs/integration) or manually.

## Option A: Installing via HACS

### HA Plants integration

1. In HACS, open the **⋮** menu (top right) and choose **Custom repositories**.
2. Add **`https://github.com/dandoingdev/ha-plants`** as category **Integration**, then confirm **Add**.
3. Open **HACS → Integrations**, refresh if needed, then select **HA Plants**.
4. Click **Download**. A pop-up will show that the component is installed under `/config/custom_components/ha_plants`. Confirm **Download**.

5. **Image folder.** When HA Plants starts, it creates `/config/www/ha_plants/images` if it is missing (so you do not need to run `mkdir` yourself). Put plant photos there, or use any other path under `/config/www/` and set the plant’s `image` field to the matching `/local/...` URL.

## Option B: Manual Installation

### HA Plants integration

1. Clone or download this repository: [ha-plants](https://github.com/dandoingdev/ha-plants)
2. Copy the `custom_components/ha_plants` folder to your Home Assistant `config/custom_components/` directory: config/custom_components/ha_plants
3. Restart Home Assistant. The integration creates `/config/www/ha_plants/images` on startup when possible (same as the HACS install path above).

# Configuration

### HA Plants integration

HA Plants is set up only through the Home Assistant UI: do not add a `ha_plants:` block to `configuration.yaml`.

1. Go to **Settings > Devices & Services > Add integration**.
2. Search for **HA Plants** and add it.
3. Open **HA Plants** on the integration card, then **Configure** to open the menu: **Reminder notifications**, **Manage plants** (add / edit; you can delete from the edit screen), or **Manage RF/NFC tags** (link / remove). You can also use the **`ha_plants.*`** actions under **Developer tools → Actions** (for example **HA Plants: Create plant**).

### Reminder notifications

Reminders run **once per day** at the **reminder time** you set (Home Assistant’s local time). They only run when **Enable reminder notifications** is turned on.

| Setting | What it does |
| ------- | -------------- |
| **Enable reminder notifications** | Master switch; when off, no reminders are sent. |
| **Reminder time** | Hour and minute for the daily reminder pass (default 09:00). |
| **Notify entity (optional)** | A `notify.*` entity. If set, Home Assistant sends a notification with title **HA Plants** and a short message (see below) using the notify integration’s **`send_message`** action. Leave empty to skip push/mobile notify and only use persistent notifications (if enabled). |
| **Also show persistent notification** | When enabled (default), creates a **persistent_notification** in the UI so reminders stay visible until dismissed. |

Reminder messages use the title **HA Plants** and body text like `Monstera needs watering.` or `Monstera needs fertilizing.` (your plant’s display name is substituted).

**When a watering reminder is sent:** the plant is considered due when the sensor’s care state is **overdue**—that is, `days_since_watered` is at or past `watering_interval + watering_postponed`, or **last watered** is unknown (`Unknown` / never set). That matches the numeric care state on the sensor (lowest value when overdue or unknown).

**When a fertilizing reminder is sent:** you must set **`fertilizing_interval`** to a value greater than `0`, set **`last_fertilized`** to a known date, and **`days_since_fertilized`** must be greater than or equal to that interval. Each plant can get at most **one watering** and **one fertilizing** reminder **per calendar day** (tracked so repeats do not spam if the scheduler fires again).

After changing reminder options, the integration reloads and re-schedules the daily job automatically.

### Dashboard

Add **Entities**, **Mushroom**, template cards, or other Lovelace cards that can display your `sensor.ha_plants_*` entities and their attributes (for example `plant_name`, `days_since_watered`, and `image`).

# Plant Data Fields

## Sensors and attributes

HA Plants creates **one sensor entity per plant**. The entity id follows the pattern `sensor.ha_plants_<plant_id>`, where `<plant_id>` is the identifier you used when the plant was created (the same value as **`plant_name`** in the **HA Plants: Create Plant** action). Home Assistant may adjust the id when it registers the entity (for example normalization); if in doubt, open **Developer Tools → States** and search for `ha_plants`.

Each sensor’s **state** is a numeric care indicator (0–3) used by the integration. The fields below are exposed as **sensor attributes** (for automations, templates, and dashboard cards):

| Attribute                 | Description                                                         |
| ------------------------- | ------------------------------------------------------------------- |
| `plant_name`              | Name of the plant                                                   |
| `last_watered`            | Last watered date (e.g., `2026-07-30`) or `Unknown`                |
| `last_fertilized`         | Last fertilized date or `Unknown`                                   |
| `watering_interval`       | Days between waterings (default: `14`)                              |
| `watering_postponed`      | Extra days to postpone watering (default: `0`)                    |
| `fertilizing_interval`    | Days between fertilizing (`0` = off; no fertilizing reminders)      |
| `days_since_watered`      | Days since `last_watered` (updated at midnight)                   |
| `days_since_fertilized`   | Days since `last_fertilized` when a date is known; otherwise `0`    |
| `inside`                  | Whether the plant is indoors (`true` or `false`)                  |
| `image`                   | Image URL or path for the card (optional)                           |

When you call **Create Plant** / **Update Plant**, use the field names above; they are stored on the sensor as these attributes. Both actions accept **`fertilizing_interval`** (0–365 days).

**Services:** `ha_plants.create_plant`, `ha_plants.update_plant`, `ha_plants.delete_plant`, and `ha_plants.update_days_since_watered` (refreshes day counters for all plants; a midnight schedule also runs this automatically).

## Plant images

You can use your own photo (camera upload, image editor export, or a file downloaded from the web) and place it anywhere Home Assistant can serve under `/config/www/`.

**Recommended layout:** keep HA Plants files under `/config/www/ha_plants/` so uninstalling or backing up is straightforward. Home Assistant also provides a generic `/config/www/images/` folder; that works, but the **default HA Plants `www` layout** (`ha_plants/` and `ha_plants/images/`, matching the integration’s internal id) keeps plant photos grouped with this integration.

Examples:

- File on disk: `/config/www/ha_plants/Monstera.jpg` → URL for the `image` field: `/local/ha_plants/Monstera.jpg`
- File on disk: `/config/www/ha_plants/images/Monstera.jpg` → URL: `/local/ha_plants/images/Monstera.jpg`

Match the file name to how you reference the plant (e.g. **Monstera**) so it is easy to find. After adding or changing a file, set or update the `image` attribute via **HA Plants: Update Plant** (or set it when creating the plant) to that `/local/...` URL.

# Logbook Integration

HA Plants logs important events to the Home Assistant logbook. These entries help you keep track of changes made either manually or via automation.

- `Monstera was created.`
- `Monstera was updated.`
- `Monstera was deleted.`

These messages appear in Home Assistant’s **Logbook** panel.

# 🐛 Issues & Feedback

If you encounter any issues or would like to suggest improvements:

- 📌 Open an issue on GitHub: [https://github.com/dandoingdev/ha-plants/issues](https://github.com/dandoingdev/ha-plants/issues)
- 🙌 Pull requests are welcome!

Please include logs or reproduction steps when reporting bugs.

# 🧠 Roadmap

Planned features and improvements for future versions:

- ✅ Create, update, and delete plant entries
- ✅ Daily tracking of days since watering and fertilizing
- ✅ Fertilizing intervals and reminders
- ✅ Sensor entities suitable for dashboard and automation use
- ✅ Logbook integration
- ✅ Reminder notifications for watering and fertilizing (daily, optional notify + persistent)
- 🔜 Integration with moisture/humidity sensors
- 🔜 Multi-language support

Feel free to contribute to the roadmap or suggest new ideas!

# 📄 License

This project is licensed under the **MIT License**.
See the [LICENSE](LICENSE) file for full license text.

**Acknowledgements:** Development here picks up where [@xplanes](https://github.com/xplanes) left off with the earlier plant-tracking integration and companion card ecosystem—thanks for laying the groundwork.
