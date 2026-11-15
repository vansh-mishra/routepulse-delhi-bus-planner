# RoutePulse demo video guide

This guide helps record a clear hackathon walkthrough. Aim for **2–3 minutes**, unless the submission portal specifies a different limit. Show the real application, not slides alone.

## Before recording

1. Run `python app.py` and open `http://127.0.0.1:5000/`.
2. Check `http://127.0.0.1:5000/api/health` and confirm the GTFS and ticketing counts are loaded.
3. Open the public planner in another browser tab. Use a known sample pair: **Kashmere Gate City Bus Terminal → Nehru Place Terminal**.
4. Use a date within the feed calendar and a departure time with a scheduled service. If the first search returns no options, try 08:00–09:00.
5. Close unrelated tabs, turn off notifications, hide personal information and never show `.env` or API keys.
6. Test the map loads. It uses Leaflet with OpenStreetMap standard raster tiles and requires no map API key.

## Recommended free recorder: OBS Studio

1. Download OBS Studio only from https://obsproject.com/download.
2. Open OBS and run the Auto-Configuration Wizard if prompted.
3. In **Sources**, select **+ → Window Capture** and choose your browser. Use Display Capture only if Window Capture does not work. Keep the browser maximised and zoom at 90–100% so labels remain readable.
4. In **Settings → Video**, use your display resolution (preferably 1920×1080) and 30 FPS. If your machine is not comfortable at 1080p, use 1280×720 at 30 FPS.
5. In **Settings → Output → Recording**, choose a local folder and record to MKV for crash resilience. After recording, use **File → Remux Recordings** to convert the MKV to MP4.
6. Check the Audio Mixer. Keep microphone audio clear; mute desktop audio if it is not needed.
7. Make a 10-second test recording and play it back before recording the final take.

OBS official quick start: https://obsproject.com/kb/quick-start-guide

## Suggested 2–3 minute walkthrough

| Time | What to show | Suggested narration |
|---|---|---|
| 0:00–0:15 | RoutePulse landing page | “RoutePulse is our Delhi bus journey planner for Transport Stack Hackathon Problem 1.” |
| 0:15–0:35 | Data insights page | “We use official GTFS stops, routes, trips, schedules and shapes, plus October ticket transactions for demand analysis.” |
| 0:35–1:20 | Journey planner | Search Kashmere Gate City Bus Terminal and Nehru Place Terminal; pick a departure time; show route alternatives and journey details. |
| 1:20–1:45 | Map | Show the selected route shape, boarding point, destination and OpenStreetMap attribution. |
| 1:45–2:05 | Theme toggle | Switch light to dark and back to demonstrate the saved preference. |
| 2:05–2:25 | Optional sign-up | Create/sign in with a dedicated demo account and save a journey. Do not show a personal password or email. |
| 2:25–2:45 | Health/API page | Briefly show loaded data status and explain the data sources. |
| 2:45–3:00 | Closing | State the current scope and honestly identify remaining historical GPS/live-feed validation work, if not yet integrated. |

## Accuracy and judging integrity

- Describe current journey times as **GTFS timetable-based estimates** until the historical vehicle GPS SQLite archive has been processed and evaluated.
- Describe `October-Delhi.csv` as **ticket transaction/demand data**, not GPS traces, road speeds or vehicle occupancy.
- Do not call the vehicle feed “live” during the recording unless the API key is configured and the `/api/vehicles` endpoint returns recent positions.
- Do not display any API key, `.env` file, personal browser bookmarks, private email, or account information.
- Do not imply that a dark-mode map tile style or a displayed marker proves live traffic prediction.

## Final export checklist

- MP4 file opens and audio is audible.
- Browser text and map labels are readable.
- No terminal errors, personal information or secrets are visible.
- Video shows at least one successful journey search from start to results.
- Video clearly states what data powers each feature.
