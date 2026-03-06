# Product Requirements Document: KeepAlive Tool

**Version:** 1.0
**Date:** 2026-03-06
**Status:** Draft

---

## 1. Executive Summary

The KeepAlive Tool is a lightweight, single-file Windows desktop application that prevents two native desktop applications (HIS and intPC) from timing out due to inactivity. It runs unobtrusively in the background on machines where users may be actively working, using a combination of mouse jiggling, periodic screenshot-based popup detection, and intelligent idle-aware window management to keep both applications logged in without interrupting the user.

The tool addresses a practical workflow pain point: users on closed-network Windows machines must stay logged into HIS and intPC, but these applications log out after periods of inactivity. Manually re-authenticating is disruptive and time-consuming. The KeepAlive Tool automates session maintenance silently and safely.

The MVP delivers a single `.exe` file with a small GUI featuring three independently toggleable checkboxes — one per function — that can be enabled or disabled at any time without restarting the application. No internet connection, installer, or configuration file is required.

---

## 2. Mission

**Mission Statement:** Eliminate session timeout interruptions for users of HIS and intPC on closed-network Windows machines, without interfering with the user's active work.

**Core Principles:**
1. **Non-intrusive:** Never interrupt the user while they are actively working. Respect user activity above all else.
2. **Zero-dependency distribution:** A single `.exe` file that runs on any Windows 10/11 machine with no install, no internet, no config files.
3. **Independent controls:** Each keepalive function can be toggled on/off at any time without affecting the others.
4. **Transparent operation:** Log every action with timestamps so users always know what the tool did and when.
5. **Minimal footprint:** Low CPU and memory usage; imperceptible mouse movements; no UI clutter.

---

## 3. Target Users

### Primary Persona: Clinical/Enterprise Desktop User
- Works on a Windows 10/11 machine connected to a closed, air-gapped, or restricted network
- Uses HIS (a native desktop application) and/or intPC (a native desktop application) daily
- Frequently steps away from their desk (meetings, patient care, etc.) and returns to find themselves logged out
- Not necessarily technical — expects to double-click an `.exe` and have it work
- May be actively using their computer while keepalive runs in the background

### Key Pain Points
- Re-authentication after idle timeout is disruptive and time-consuming
- Session timeouts happen unpredictably during workflows
- No ability to install third-party software via standard channels (closed network)
- Cannot tolerate tools that interfere with their active work (e.g., surprise window switches while typing)

### Technical Comfort Level
- Low to moderate; expects a simple GUI with minimal configuration
- Does not want to edit config files or run scripts
- Comfortable with a system tray-style persistent application

---

## 4. MVP Scope

### Core Functionality
- ✅ Mouse jiggler: moves mouse 1px right/left every 30 seconds to prevent OS idle/sleep
- ✅ HIS keepalive: background screenshot + pixel color detection + click every 60 seconds
- ✅ intPC keepalive: process check + idle-aware foreground + screenshot + pixel color detection + click every 5 minutes
- ✅ Jiggler-aware idle detection: distinguishes synthetic jiggler input from real user input
- ✅ Three independently toggleable checkboxes in a small tkinter GUI
- ✅ Timestamped status log displayed in the GUI
- ✅ All coordinates, colors, and timings hardcoded as constants with placeholder comments
- ✅ `--dry-run` CLI flag for safe first-run verification on target machine

### Technical
- ✅ Packaged as a single `.exe` via PyInstaller (`--onefile`)
- ✅ GitHub Actions workflow building on `windows-latest` runner
- ✅ Unit tests for detection logic with mock/fixture screenshots
- ✅ Thread-safe shared state using `threading.Lock` and `threading.Event`

### Integration
- ✅ Works with HIS native desktop application (popup detection via pixel color)
- ✅ Works with intPC native desktop application (process detection via psutil, window management via pywin32)

### Deployment
- ✅ Zero-dependency single file distribution (USB transfer to closed-network machines)
- ✅ No installer, no config file, no internet access required

### Out of Scope (Future Phases)
- ❌ System tray icon / minimize to tray
- ❌ Config file or GUI-based coordinate editor
- ❌ Support for more than 2 target applications
- ❌ Automatic coordinate detection / image template matching
- ❌ Scheduled enable/disable times
- ❌ Multi-monitor support beyond default primary screen behavior
- ❌ Auto-update mechanism
- ❌ Installer / MSI packaging
- ❌ Remote management or centralized deployment

---

## 5. User Stories

### US-01: Enable Mouse Jiggler
**As a** user who steps away from their desk frequently,
**I want to** check a checkbox to start the mouse jiggler,
**so that** my screen never locks or sleeps while the tool is running.

*Example:* User checks "Mouse Jiggle" before attending a 30-minute meeting. The OS never triggers the screensaver or sleep. They return and their desktop is exactly as they left it.

---

### US-02: Keep HIS Session Alive in the Background
**As a** HIS user,
**I want to** enable the HIS keepalive without changing what's on my screen,
**so that** HIS stays logged in even when I'm not interacting with it.

*Example:* User is working in a different application. Every 60 seconds, the tool silently checks whether HIS is showing a timeout popup using a pixel color check. If it sees the popup, it clicks the dismiss button without bringing HIS to the foreground or interrupting the user.

---

### US-03: Keep intPC Session Alive Without Interrupting Active Work
**As an** intPC user who occasionally steps away,
**I want** the tool to only bring intPC to the foreground when I'm not actively working,
**so that** it never disrupts me mid-task.

*Example:* User is typing a document. The tool detects activity and skips its 5-minute cycle entirely. Twenty minutes later, the user steps away. After 2 minutes of idle time, the tool brings intPC to the front, checks for a timeout popup, clicks if needed, and leaves intPC in the foreground.

---

### US-04: Toggle Functions Independently at Any Time
**As a** user,
**I want to** check and uncheck each function independently without restarting the app,
**so that** I can turn off the jiggler when presenting without stopping HIS keepalive.

*Example:* User checks all three boxes when they arrive at work. Before a screen-share call, they uncheck "Mouse Jiggle" only. HIS and intPC keepalive continue uninterrupted.

---

### US-05: See What the Tool Is Doing
**As a** user,
**I want to** see a log of recent actions in the GUI,
**so that** I know the tool is working and can diagnose problems.

*Example:* The status area shows:
```
[14:32:01] HIS check: no popup detected
[14:33:01] HIS check: popup detected, clicking dismiss
[14:35:00] intPC: user not idle, skipping cycle
```

---

### US-06: Verify Behavior Before Going Live (Dry Run)
**As a** technician deploying the tool,
**I want to** run the tool with `--dry-run` on the target machine,
**so that** I can confirm the detection logic is working without making any actual clicks.

*Example:* Run `keepalive.exe --dry-run`. The log shows "Would click at (542, 318)" instead of clicking. Confirms coordinate accuracy before enabling live mode.

---

### US-07: Run on a Closed-Network Machine with Zero Setup
**As an** IT technician,
**I want to** transfer a single `.exe` file via USB and run it with no installation,
**so that** deployment to air-gapped machines requires no additional steps.

*Example:* Copy `keepalive.exe` to desktop. Double-click. GUI appears. Done.

---

### US-08: Confirm No Interference with Active Mouse/Keyboard Use
**As a** user actively working at my computer,
**I want** the tool to never move my mouse or switch windows while I'm typing or clicking,
**so that** I can trust it won't cause errors in my work.

*Example:* User is filling in a form. The jiggler pauses automatically during HIS/intPC click cycles. intPC window management only activates after 2 minutes of confirmed user inactivity.

---

## 6. Core Architecture & Patterns

### High-Level Architecture
The application is a multi-threaded Python tkinter GUI with three independent background daemon threads, a shared state layer, and an optional idle monitoring thread.

```
main.py
  └── GUI (tkinter, main thread)
        ├── BooleanVar: jiggle_enabled, his_enabled, intpc_enabled
        └── Starts/stops daemon threads on checkbox change

Daemon Threads:
  ├── jiggler_thread       (Module 1)
  ├── his_thread           (Module 2)
  ├── intpc_thread         (Module 3)
  └── idle_monitor_thread  (runs when intpc_enabled=True)

Shared State:
  ├── jiggle_lock          (threading.Lock — pauses jiggler during clicks)
  ├── jiggle_in_progress   (bool flag — set around pyautogui moves)
  └── last_real_input_time (float — updated by idle monitor)
```

### Directory Structure
```
keepalive/
├── CLAUDE.md
├── requirements.txt
├── src/
│   ├── main.py              # Entry point, tkinter GUI, thread lifecycle
│   ├── jiggler.py           # Module 1: mouse jiggle loop
│   ├── his_keepalive.py     # Module 2: HIS screenshot + detect + click
│   ├── intpc_keepalive.py   # Module 3: intPC process check, window, detect + click
│   ├── idle_monitor.py      # Jiggler-aware idle detection
│   ├── screen_utils.py      # Screenshot capture and pixel color checking
│   ├── constants.py         # All coordinates, colors, timing constants
│   └── logger.py            # Append to GUI log area + optional file
├── tests/
│   ├── test_detection.py
│   └── fixtures/
├── build/
│   └── keepalive.spec
└── .github/
    └── workflows/
        └── build.yml
```

### Key Design Patterns
- **Daemon threads with stop events:** Each module thread loops on a `threading.Event` stop signal, checking `enabled` state via tkinter `BooleanVar`
- **Shared lock for click coordination:** `jiggle_lock` ensures the jiggler never moves the mouse during a click cycle from Module 2 or 3
- **Jiggler-aware idle detection:** Flag-based filtering of synthetic mouse movements to accurately measure true user idle time
- **Pixel color matching with tolerance:** Lightweight popup detection that avoids heavy template matching; configurable per-channel RGB tolerance
- **Hardcoded constants with TODO comments:** All coordinates and expected values live in `constants.py` with explicit placeholder markers

---

## 7. Feature Specifications

### Feature 1: Mouse Jiggler
- **Interval:** Every 30 seconds
- **Action:** Move mouse +1px on X axis, then -1px (returns to original position)
- **Pause behavior:** Acquires `jiggle_lock` check before moving; if lock is held by Module 2/3, waits
- **Flag behavior:** Sets `jiggle_in_progress = True` immediately before move, `False` immediately after
- **Condition:** Runs continuously when checkbox is enabled, regardless of user activity

### Feature 2: HIS Keepalive
- **Interval:** Every 60 seconds
- **Detection method:** Capture full screen with PIL; read pixel at `(HIS_CHECK_X, HIS_CHECK_Y)`; compare to `HIS_EXPECTED_COLOR` within `HIS_COLOR_TOLERANCE` per channel
- **On detection:** Click at `(HIS_CLICK_X, HIS_CLICK_Y)` using pyautogui; log action
- **Window management:** No foreground change required; HIS popup appears on top of whatever is visible
- **Lock usage:** Acquires `jiggle_lock` during screenshot-and-click cycle

### Feature 3: intPC Keepalive
- **Interval:** Every 5 minutes
- **Step 1 — Process check:** Use psutil to check for `INTPC_PROCESS_NAME` in running processes. If not found, log and skip.
- **Step 2 — Idle check:** Call `is_user_idle()`. If user is active, log "user not idle, skipping" and skip.
- **Step 3 — Foreground check:** Use win32gui to get foreground window. If intPC is not in front, bring it to front using `SetForegroundWindow`.
- **Step 4 — Popup detection:** Capture screenshot; check pixel at `(INTPC_CHECK_X, INTPC_CHECK_Y)` vs `INTPC_EXPECTED_COLOR`
- **Step 5 — Click if needed:** Click `(INTPC_CLICK_X, INTPC_CLICK_Y)` if popup detected; log result
- **Post-action:** Leave intPC in foreground (do not restore previous window)
- **Lock usage:** Acquires `jiggle_lock` during screenshot-and-click cycle

### Feature 4: Idle Detection
- **Poll interval:** Every 2-3 seconds (when intPC checkbox is enabled)
- **Mouse tracking:** If mouse position changed AND `jiggle_in_progress == False` → real user movement → update `last_real_input_time`
- **Keyboard tracking:** Poll `GetLastInputInfo` differential or `GetAsyncKeyState`; any keyboard activity → update `last_real_input_time`
- **`is_user_idle()` returns True if:** `time.time() - last_real_input_time >= IDLE_THRESHOLD (120s)`

### Feature 5: GUI
- Small fixed-size window, always on top (optional, configurable in constants)
- Three checkboxes: "Mouse Jiggle", "HIS", "intPC"
- Scrolling or fixed-height text log area showing last N actions with timestamps
- No start button — checkboxes are the control

### Feature 6: Dry Run Mode
- CLI flag: `--dry-run`
- Replaces all `pyautogui.click()` calls with log messages: `"[DRY RUN] Would click at (x, y)"`
- Replaces `SetForegroundWindow` calls with log: `"[DRY RUN] Would bring intPC to front"`
- All detection logic runs normally

---

## 8. Technology Stack

### Core Runtime
- **Python:** 3.11+
- **GUI:** `tkinter` (stdlib — no external GUI dependency)
- **Screenshots:** `Pillow (PIL)` 10.x
- **Mouse/keyboard automation:** `pyautogui` 0.9.x
- **Windows API:** `pywin32` (`win32gui`, `win32process`, `win32api`) 306+
- **Process detection:** `psutil` 5.9+
- **Idle detection:** `ctypes` (stdlib `GetLastInputInfo`)
- **Threading:** `threading` (stdlib)

### Build & Packaging
- **Packaging:** `PyInstaller` 6.x (`--onefile`)
- **CI Runner:** GitHub Actions `windows-latest`

### Testing
- **Test framework:** `pytest`
- **Mocking:** `unittest.mock` (stdlib)
- **Test fixtures:** Saved PNG screenshots in `tests/fixtures/`

### requirements.txt
```
Pillow>=10.0.0
pyautogui>=0.9.54
pywin32>=306
psutil>=5.9.0
pyinstaller>=6.0.0
pytest>=8.0.0
```

---

## 9. Security & Configuration

### Authentication/Authorization
- No authentication required; the tool runs as the logged-in user
- No network access, no credentials stored

### Configuration Management
All configuration is hardcoded in `constants.py`. No config files, environment variables, or registry entries.

```python
# constants.py — all values are PLACEHOLDERS (TODO: fill in real values)

# HIS popup detection
HIS_CHECK_X = 0       # TODO: fill in real value
HIS_CHECK_Y = 0       # TODO: fill in real value
HIS_EXPECTED_COLOR = (0, 0, 0)   # TODO: RGB tuple
HIS_COLOR_TOLERANCE = 10
HIS_CLICK_X = 0       # TODO: fill in real value
HIS_CLICK_Y = 0       # TODO: fill in real value

# intPC popup detection
INTPC_CHECK_X = 0     # TODO: fill in real value
INTPC_CHECK_Y = 0     # TODO: fill in real value
INTPC_EXPECTED_COLOR = (0, 0, 0) # TODO: RGB tuple
INTPC_COLOR_TOLERANCE = 10
INTPC_CLICK_X = 0     # TODO: fill in real value
INTPC_CLICK_Y = 0     # TODO: fill in real value

# intPC process/window identification
INTPC_PROCESS_NAME = "???.exe"   # TODO: fill in real process name
INTPC_WINDOW_TITLE = "???"       # TODO: fill in partial window title

# Timing
JIGGLE_INTERVAL = 30
HIS_CHECK_INTERVAL = 60
INTPC_CHECK_INTERVAL = 300
IDLE_THRESHOLD = 120
IDLE_POLL_INTERVAL = 3
```

### Security Scope
- **In scope:** Safe for use on shared/managed Windows desktops; no elevated privileges required; no network traffic generated
- **Out of scope:** The tool does not protect against unauthorized access to HIS or intPC; it only maintains existing authenticated sessions

### Deployment Considerations
- Distribute via USB or approved file transfer to closed-network machines
- No code signing in v1 (may trigger SmartScreen warning on first run; user must click "Run anyway")
- Consider code signing in a future phase if SmartScreen is a blocker

---

## 10. Success Criteria

### MVP Success Definition
The MVP is successful when a user on a target Windows 10/11 machine can:
1. Double-click `keepalive.exe` and see the GUI appear
2. Enable all three checkboxes
3. Step away for 10+ minutes and return to find HIS and intPC still logged in
4. Work actively at their computer without the tool interfering with their mouse or windows

### Functional Requirements
- ✅ Mouse jiggler moves mouse imperceptibly every 30 seconds when enabled
- ✅ HIS keepalive detects and dismisses timeout popup within 60 seconds of appearance
- ✅ intPC keepalive detects and dismisses timeout popup within 5 minutes of appearance
- ✅ intPC window management only activates after 2+ minutes of confirmed user idle
- ✅ Jiggler pauses during click cycles; resumes automatically
- ✅ Each checkbox can be toggled independently without restarting
- ✅ All actions are logged with timestamps in the GUI
- ✅ `--dry-run` mode logs actions without clicking
- ✅ Single `.exe` file with no external dependencies runs on Windows 10/11

### Quality Indicators
- CPU usage below 1% at idle
- Memory footprint below 50MB
- No pyautogui click fires while user is actively typing
- No window focus change while user is active

### User Experience Goals
- A non-technical user can configure and start the tool in under 2 minutes
- The GUI is small enough to leave open in a corner without obscuring work
- Log messages are plain English (not technical jargon)

---

## 11. Implementation Phases

### Phase 1: Core Infrastructure
**Goal:** Establish project skeleton, shared state, GUI, and logging

**Deliverables:**
- ✅ `constants.py` with all placeholder constants
- ✅ `logger.py` with GUI log area integration
- ✅ `main.py` with tkinter GUI: 3 checkboxes, log area, thread lifecycle management
- ✅ `screen_utils.py` with screenshot capture and pixel color check helpers
- ✅ GitHub Actions `build.yml` for Windows `.exe` artifact

**Validation:** GUI opens, checkboxes respond, log area receives messages, `.exe` builds successfully via CI

---

### Phase 2: Module 1 + Module 2
**Goal:** Implement mouse jiggler and HIS keepalive

**Deliverables:**
- ✅ `jiggler.py`: 30-second loop with `jiggle_lock` and `jiggle_in_progress` flag
- ✅ `his_keepalive.py`: 60-second loop with screenshot, pixel check, conditional click
- ✅ Shared lock coordination between jiggler and HIS module
- ✅ Unit tests for pixel detection logic in `test_detection.py`
- ✅ Fixture screenshots for test cases (popup present / popup absent)

**Validation:** Both modules run in parallel; jiggler pauses correctly during HIS click; log shows correct messages

---

### Phase 3: Module 3 + Idle Detection
**Goal:** Implement intPC keepalive with jiggler-aware idle detection

**Deliverables:**
- ✅ `idle_monitor.py`: 2-3 second polling loop with jiggle-aware mouse/keyboard tracking
- ✅ `intpc_keepalive.py`: 5-minute loop with process check, idle check, foreground management, popup detection, click
- ✅ `is_user_idle()` function returning accurate idle state
- ✅ Unit tests for idle detection logic
- ✅ Integration with `jiggle_lock` and `jiggle_in_progress` flag

**Validation:** intPC module correctly skips when user is active; correctly activates after 2 minutes idle; jiggler does not interfere with idle detection

---

### Phase 4: Integration, Dry Run, and Packaging
**Goal:** End-to-end integration, dry run mode, final `.exe` packaging

**Deliverables:**
- ✅ `--dry-run` CLI flag implemented across all modules
- ✅ Full integration test on a Windows machine (or VM) with actual HIS/intPC placeholder coordinates
- ✅ PyInstaller spec file (`keepalive.spec`) tuned for minimal size
- ✅ Final `requirements.txt` pinned
- ✅ README with transfer and first-run instructions
- ✅ Coordinate calibration guide for technician

**Validation:** `keepalive.exe --dry-run` logs all would-be actions; live mode correctly dismisses popups on target machine

---

## 12. Future Considerations

### Post-MVP Enhancements
- **System tray icon:** Minimize to tray instead of showing a window; right-click menu to toggle modules
- **GUI coordinate picker:** Click a screen location in a helper UI to capture coordinates, rather than hardcoding
- **Config file support:** Optional INI or JSON config for coordinates without rebuilding
- **Multi-monitor support:** Let user specify which screen to capture for each application

### Integration Opportunities
- **Additional applications:** Generalize Module 2/3 into a configurable "app keepalive" framework supporting N applications
- **Scheduled operation:** Auto-enable at login time, auto-disable at end of shift, using Windows Task Scheduler integration

### Advanced Features
- **Template matching fallback:** If pixel color is insufficient for popup detection, fall back to PIL image correlation with a fixture screenshot
- **Code signing:** Sign the `.exe` to prevent SmartScreen warnings and enable deployment via GPO
- **Centralized logging:** Optional write to a shared network log file for IT oversight (when network access is available)

---

## 13. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Pixel coordinates shift after Windows display scaling change or resolution change | HIS/intPC popups not detected; sessions time out | Medium | Document supported resolutions; add color tolerance; provide `--dry-run` for re-validation after any display change |
| `SetForegroundWindow` fails silently on modern Windows (focus-stealing protection) | intPC not brought to front; popup not dismissed | Medium | Use `AttachThreadInput` + `SetForegroundWindow` pattern from pywin32; log failures clearly; fall back to `FlashWindowEx` |
| SmartScreen or antivirus flags the `.exe` | Tool cannot run on target machine | Medium | Add to AV whitelist; document expected SmartScreen warning and "Run anyway" steps; consider code signing in Phase 5 |
| Jiggler moves mouse mid-user-click causing mis-click | User error; potential data entry mistake | Low | `jiggle_lock` acquired during any click cycle; jiggle interval (30s) is long relative to user click latency |
| psutil process name mismatch for intPC | intPC keepalive never activates | Low | Use `--dry-run` on target machine to verify process detection before go-live; document process name verification steps |

---

## 14. Appendix

### Related Documents
- `CLAUDE.md` — Detailed architecture spec and design decisions (source of truth for implementation)

### Key Dependencies
- `pywin32` — Windows API bindings for window management and input detection
- `pyautogui` — Cross-platform mouse/keyboard automation
- `Pillow` — Screenshot capture and pixel color reading
- `psutil` — Cross-platform process enumeration
- `PyInstaller` — Single-file `.exe` packaging

### Coordinate Calibration Procedure (for technician)
1. Run `keepalive.exe --dry-run` on the target machine
2. Trigger each application's timeout popup manually
3. Use a screenshot tool or the Windows Snipping Tool to capture the popup
4. Use an image editor (e.g., Paint, IrfanView) to identify the exact pixel coordinates and RGB color of the detection point and click target
5. Update `constants.py` with real values
6. Rebuild via GitHub Actions and distribute new `.exe`

### Timing Summary

| Function | Interval | Condition |
|---|---|---|
| Mouse jiggle | 30 seconds | Always when enabled (pauses during click cycles) |
| HIS popup check | 60 seconds | Always when HIS enabled |
| intPC process check | 5 minutes | Always when intPC enabled |
| intPC bring-to-front | 5 minutes | Only if user idle >= 2 min |
| intPC popup check | 5 minutes | Only when intPC is in foreground |
| Idle monitor polling | 2-3 seconds | When intPC checkbox is enabled |
