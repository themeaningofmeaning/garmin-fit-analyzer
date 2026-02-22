# Ultra State - Architecture & Design Rules

## Core Philosophy
Ultra State is a local-first, premium desktop analytics app for ultra-distance and trail runners. It prioritizes a fast, native-feeling macOS aesthetic (Glassmorphism, dark zinc backgrounds) over web-app conventions. 

## Data Ingestion Rules
* **Manual FIT Files Only:** We rely on local `.fit` file imports via folder watching. We **do not** use Garmin API scrapers.
* **Strict Sport Guard:** The app exclusively processes `running` and `trail_running` activities. All other sports must be rejected at the parser level (`FitAnalyzer.analyze_file()` in `analyzer.py`). The guard returns `None` which `LibraryManager` treats as a clean skip, not a failure.

## UI & Visual Design Language
* **Strict Color Decoupling:**
    * **UI/Navigation Actions:** Mint/Emerald Green is strictly reserved for primary user actions (e.g., 'Copy for AI'). 
    * **Data States:** Blue = Recovery | Green = Base | Orange = Overload | Red = Overreaching.
    * **Monochrome Hardware:** Utility UI elements (like Focus mode) must use dark neutral/zinc colors with crisp white text and icons.

## Color Gradient — Single Source of Truth
The canonical Garmin 5-color speed gradient (Blue → Green → Yellow → Orange → Red) lives in **`analyzer.py`** as two public functions:
- `_get_speed_color(speed_mps, min_speed, max_speed)` — for raw speed values with a normalization range.
- `gradient_color_from_t(t)` — for a pre-normalized position `t` (0.0–1.0). Use this when you already have a normalized value (e.g., the dual-tone migration path in `app.py`).

**Do not re-implement this gradient anywhere else.** Import from `analyzer.py`.

## Refactoring Roadmap
Agentic IDEs must follow this strict sequence when refactoring `app.py`:
1.  **Extract Magic Strings:** Move all hardcoded UI labels to a central `constants.py`.
2.  **Decouple State:** Migrate from mutating instance variables to an observer/store pattern.
3.  **Componentize:** Extract UI elements into a `/components` directory only after steps 1 and 2.

## Auto-Update Strategy
Version checks use the GitHub Releases API (Option A — notification only). See `updater.py`.
The local app version is defined in `updater.py` as `APP_VERSION`. Bump this string with every release.
