# 🌿 HA Plants for Home Assistant

**HA Plants** is a custom integration for [Home Assistant](https://www.home-assistant.io/) that helps you manage and monitor your houseplants. Track when each plant was last watered or fertilized, define care intervals, and visualize everything with a custom card [Plant Diary Card](https://github.com/xplanes/ha-plant-diary-card).

This work has been inspired by [Plant tracker for Home Assistant](https://github.com/mountwebs/ha-plant-tracker).

# Features

- Track multiple plants with individual settings
- Custom watering intervals and postponements
- Optional **fertilizing intervals** (days between fertilizing; `0` turns off fertilizing reminders)
- **Reminder notifications** for watering and fertilizing: daily check at a time you choose, optional mobile/desktop notify entity, and optional persistent notifications in Home Assistant
- Indoor/outdoor plant designation
- Automatic daily updates for days since watering and fertilizing
- Logbook integration for activity tracking
- Manage plants and reminders from the integration **Configure** UI, or use **Developer tools → Actions** (`plant_diary.*` services)

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
4. Click **Download**. A pop-up will show that the component is installed under `/config/custom_components/plant_diary`. Confirm **Download**.

5. **Create folders for images and optional manual card files.** HACS does not create `www` subfolders for you. On the Home Assistant host, create a dedicated directory (SSH, **Terminal & SSH**, **File editor**, Samba, etc.), for example:

   ```bash
   mkdir -p /config/www/plant_diary/images
   ```

   Use `plant_diary/` for the Lovelace card script if you install it manually (see below). Put plant photos in that folder or in `plant_diary/images/` so they stay separate from the card file and are easy to back up or remove with the integration.

### Plant Diary Card

1. Go to the HACS **Frontend** tab (or **Dashboard resources**, depending on your HACS version).
2. Search for **Plant Diary Card** and open it.
3. Click **Download**. The JavaScript module will be added to your dashboard resources (for example `/hacsfiles/ha-plant-diary-card/ha-plant-diary-card.js`).

## Option B: Manual Installation

### HA Plants integration

1. Clone or download this repository: [ha-plants](https://github.com/dandoingdev/ha-plants)
2. Copy the `custom_components/plant_diary` folder to your Home Assistant `config/custom_components/` directory: config/custom_components/plant_diary
3. Create folders under `www` for images (and the card, if you use a manual card install):

   ```bash
   mkdir -p /config/www/plant_diary/images
   ```

4. Restart Home Assistant.

### Plant Diary Card

1. Clone or download the GitHub repository: [ha-plant-diary-card](https://github.com/xplanes/ha-plant-diary-card)
1. Place the file `ha-plant-diary-card.js` in your `config/www/plant_diary` directory: config/www/plant_diary/ha-plant-diary-card.js
1. Add the resource to your dashboard via **Settings > Dashboards > Resources**:

```yaml
URL: /local/plant_diary/ha-plant-diary-card.js
```

# Configuration

### HA Plants integration

HA Plants is set up only through the Home Assistant UI: do not add a `plant_diary:` block to `configuration.yaml`.

1. Go to **Settings > Devices & Services > Add integration**.
2. Search for **HA Plants** and add it.
3. Open **HA Plants** on the integration card, then **Configure** to open the menu: **Reminder notifications**, **Manage plants** (add / edit; you can delete from the edit screen), or **Manage RF/NFC tags** (link / remove). You can also use the **`plant_diary`** actions under **Developer tools → Actions** (for example **HA Plants: Create plant**).

### Reminder notifications

Reminders run **once per day** at the **reminder time** you set (Home Assistant’s local time). They only run when **Enable reminder notifications** is turned on.

| Setting | What it does |
| ------- | -------------- |
| **Enable reminder notifications** | Master switch; when off, no reminders are sent. |
| **Reminder time** | Hour and minute for the daily reminder pass (default 09:00). |
| **Notify entity (optional)** | A `notify.*` entity. If set, Home Assistant sends a notification with title **HA Plants** and a short message (see below) using the notify integration’s **`send_message`** action. Leave empty to skip push/mobile notify and only use persistent notifications (if enabled). |
| **Also show persistent notification** | When enabled (default), creates a **persistent_notification** in the UI so reminders stay visible until dismissed. |

Reminder messages use the title **HA Plants** and body text like `Monstera needs watering.` or `Monstera needs fertilizing.` (your plant’s display name is substituted).

**When a watering reminder is sent:** the plant is considered due when the sensor’s care state is **overdue**—that is, `days_since_watered` is at or past `watering_interval + watering_postponed`, or **last watered** is unknown (`Unknown` / never set), which matches the same logic the Plant Diary card uses for the lowest care state.

**When a fertilizing reminder is sent:** you must set **`fertilizing_interval`** to a value greater than `0`, set **`last_fertilized`** to a known date, and **`days_since_fertilized`** must be greater than or equal to that interval. Each plant can get at most **one watering** and **one fertilizing** reminder **per calendar day** (tracked so repeats do not spam if the scheduler fires again).

After changing reminder options, the integration reloads and re-schedules the daily job automatically.

### Plant Diary Card

1. Create a Dashboard using the Sidebar layout
2. Click Add Card and search for `Plant Diary Card`

# Plant Data Fields

## Sensors and attributes

HA Plants creates **one sensor entity per plant**. The entity id follows the pattern `sensor.plant_diary_<plant_id>`, where `<plant_id>` is the identifier you used when the plant was created (the same value as **`plant_name`** in the **HA Plants: Create Plant** action). Home Assistant may adjust the id when it registers the entity (for example normalization); if in doubt, open **Developer Tools → States** and search for `plant_diary`.

Each sensor’s **state** is a numeric care indicator (0–3) used by the integration and the Plant Diary card. The fields below are exposed as **sensor attributes** (and are what you usually show in automations, templates, and the card):

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

**Services:** `plant_diary.create_plant`, `plant_diary.update_plant`, `plant_diary.delete_plant`, and `plant_diary.update_days_since_watered` (refreshes day counters for all plants; a midnight schedule also runs this automatically).

## Plant images

You can use your own photo (camera upload, image editor export, or a file downloaded from the web) and place it anywhere Home Assistant can serve under `/config/www/`.

**Recommended layout:** keep HA Plants files under `/config/www/plant_diary/` so uninstalling or backing up is straightforward. Home Assistant also provides a generic `/config/www/images/` folder; that works, but a **`plant_diary`-specific folder** (or `plant_diary/images/`) keeps plant photos grouped with this integration.

Examples:

- File on disk: `/config/www/plant_diary/Monstera.jpg` → URL for the `image` field: `/local/plant_diary/Monstera.jpg`
- File on disk: `/config/www/plant_diary/images/Monstera.jpg` → URL: `/local/plant_diary/images/Monstera.jpg`

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
- ✅ Lovelace card for visualizing plant data
- ✅ Logbook integration
- ✅ Reminder notifications for watering and fertilizing (daily, optional notify + persistent)
- 🔜 Integration with moisture/humidity sensors
- 🔜 Multi-language support

Feel free to contribute to the roadmap or suggest new ideas!

# 📄 License

This project is licensed under the **MIT License**.
See the [LICENSE](LICENSE) file for full license text.

© 2025 [@xplanes](https://github.com/xplanes)
