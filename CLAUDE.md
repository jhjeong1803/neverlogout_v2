# Screen Monitor Auto-Clicker (KeepAlive Tool)

## Overview
A lightweight Windows desktop tool that keeps two native desktop applications logged in on a machine where the user may also be actively working. Three independent functions controlled by checkboxes:
1. Mouse jiggling to prevent idle/sleep
2. HIS app session keepalive (background screenshot + click)
3. intPC app session keepalive (bring to front when user is idle, then screenshot + click)

Packaged as a single `.exe` for distribution to closed-network Windows machines with no internet access.

## Tech Stack
- Python 3.11+
- `tkinter` for GUI (no external GUI dependencies)
- `Pillow` (PIL) for screenshots
- `pyautogui` for mouse movement and clicking
- `pywin32` (`win32gui`, `win32process`, `win32api`) for window management and idle detection
- `psutil` for process detection
- `ctypes` for `GetLastInputInfo` (true user idle detection)
- `PyInstaller` for `.exe` packaging
- `threading` for background tasks without freezing GUI

## Architecture

### GUI (tkinter)
- Single small window, always on top optional
- 3 checkboxes, each independently toggleable at any time:
  - `☐ Mouse Jiggle` — toggles mouse jiggler
  - `☐ HIS` — toggles HIS session keepalive
  - `☐ intPC` — toggles intPC session keepalive
- Small status/log area at the bottom showing last action and timestamp
- No start/stop button needed — checkboxes directly enable/disable each function

### Module 1: Mouse Jiggler (checkbox 1)
- When enabled, moves the mouse by 1 pixel right then 1 pixel left every **30 seconds**
- Movement is imperceptible but prevents OS idle/sleep
- **Must pause** while Module 2 or Module 3 is actively performing a screenshot-and-click cycle (use a shared threading lock or flag)
- Resumes automatically after the other module's cycle completes
- Runs continuously regardless of user activity — even if user is working, jiggler keeps going

### Module 2: HIS Keepalive (checkbox 2)
- HIS is a **native desktop application** (not browser-based)
- Every **60 seconds**, take a screenshot of the full screen
- Check **hardcoded pixel coordinates** for a specific color value to detect if a session timeout popup is showing
- Detection method: **pixel color matching** at specific coordinates (lighter and faster than template matching)
- If popup detected: click the hardcoded button coordinate to dismiss it and stay logged in
- If popup not detected: do nothing, wait for next cycle
- This works in the **background** — does NOT need to bring HIS to front. HIS just needs to already be visible or the popup appears on top.
- Log every check and every click action with timestamp

### Module 3: intPC Keepalive (checkbox 3)
- intPC is a **native desktop application** (not browser-based)
- First, check if the intPC process is running using `psutil` (by process name)
- If process is NOT running: log it, do nothing, wait for next cycle
- If process IS running:
  - Every **5 minutes**, check if intPC window is in the foreground
  - If it is NOT in the foreground, bring it to front — **BUT only if the user has been idle for at least 2 minutes** (see Idle Detection below)
  - If user is NOT idle (actively working): skip this cycle, do not interrupt, try again in 5 minutes
  - Once intPC IS in the foreground (either already was, or we just brought it up):
    - Take a screenshot
    - Check hardcoded pixel coordinates for color match to detect session timeout popup
    - If popup detected: click hardcoded button coordinate to dismiss
    - If popup not detected: do nothing
  - After clicking, **leave intPC in the foreground** (do not restore previous window)
- Log every check, every bring-to-front action, and every click with timestamp

### Idle Detection (critical for Module 3)
- **PROBLEM**: The jiggler uses `pyautogui` which generates synthetic input events. Windows API `GetLastInputInfo` counts these as real input, so it will never report idle while jiggler is active.
- **SOLUTION — Jiggler-aware idle tracking**:
  1. Jiggler sets a flag `jiggle_in_progress = True` immediately before moving, and `False` immediately after
  2. A separate idle monitor thread polls mouse position every 2-3 seconds
  3. If mouse position changed since last poll AND `jiggle_in_progress` is `False` → this is real user input → update `last_real_input_time`
  4. Additionally monitor keyboard input via `GetAsyncKeyState` or polling `GetLastInputInfo` differential — any keyboard activity is always real user input → update `last_real_input_time`
  5. `is_user_idle()` returns `True` if `time.time() - last_real_input_time >= 120` (2 minutes)
- The idle monitor thread only needs to run when the intPC checkbox is enabled

### Thread Coordination
- Each module runs in its own daemon thread
- Shared state:
  - `jiggle_lock` — threading Lock. Acquired by Module 2 or 3 during their screenshot+click cycle. Jiggler checks this lock before moving.
  - `jiggle_in_progress` — boolean flag set by jiggler around its mouse move, used by idle detector to filter synthetic input
  - `last_real_input_time` — float timestamp updated by idle monitor thread
- All checkbox state changes are read from tkinter variables (thread-safe BooleanVar)

### Coordinate Configuration
- All detection coordinates, expected pixel colors, and click coordinates are **hardcoded as constants** at the top of the relevant module files or in a shared constants file
- Grouped clearly:
```python
# HIS popup detection
HIS_CHECK_X = ???
HIS_CHECK_Y = ???
HIS_EXPECTED_COLOR = (???, ???, ???)  # RGB
HIS_COLOR_TOLERANCE = 10             # allowable RGB difference per channel
HIS_CLICK_X = ???
HIS_CLICK_Y = ???

# intPC popup detection
INTPC_CHECK_X = ???
INTPC_CHECK_Y = ???
INTPC_EXPECTED_COLOR = (???, ???, ???)  # RGB
INTPC_COLOR_TOLERANCE = 10
INTPC_CLICK_X = ???
INTPC_CLICK_Y = ???

# intPC process/window identification
INTPC_PROCESS_NAME = "???.exe"
INTPC_WINDOW_TITLE = "???"  # partial match is fine

# Timing
JIGGLE_INTERVAL = 30        # seconds
HIS_CHECK_INTERVAL = 60     # seconds
INTPC_CHECK_INTERVAL = 300  # seconds (5 min)
IDLE_THRESHOLD = 120        # seconds (2 min)
IDLE_POLL_INTERVAL = 3      # seconds
```
- Placeholder values with clear `# TODO: fill in real values` comments

### Timing Summary
| Function | Interval | Condition |
|---|---|---|
| Mouse jiggle | 30 seconds | Always (pauses during other module clicks) |
| HIS check | 60 seconds | Always when enabled |
| intPC process check | 5 minutes | Always when enabled |
| intPC bring-to-front | 5 minutes | Only if user idle >= 2 min |
| intPC popup check | 5 minutes | Only when intPC is in foreground |
| Idle monitor polling | 2-3 seconds | Always running when intPC checkbox is enabled |

## Packaging
- Use PyInstaller to create a **single-file `.exe`** (`--onefile` flag)
- No external config files needed (everything hardcoded)
- Must work on Windows 10/11
- Target machines have **no internet access** (closed network)
- Build via GitHub Actions on `windows-latest` runner since development happens in Linux-based GitHub Codespace

## Project Structure
```
keepalive/
├── CLAUDE.md
├── requirements.txt
├── src/
│   ├── main.py              # Entry point, tkinter GUI setup
│   ├── jiggler.py           # Module 1: mouse jiggle logic
│   ├── his_keepalive.py     # Module 2: HIS screenshot + detect + click
│   ├── intpc_keepalive.py   # Module 3: intPC process check, window mgmt, detect + click
│   ├── idle_monitor.py      # Idle detection (jiggler-aware)
│   ├── screen_utils.py      # Shared screenshot and pixel-check helpers
│   ├── constants.py         # All hardcoded coordinates, colors, timing values
│   └── logger.py            # Simple logging to GUI status area and/or file
├── tests/
│   ├── test_detection.py    # Unit tests with mock screenshots
│   └── fixtures/            # Sample screenshot images for testing
├── build/
│   └── keepalive.spec       # PyInstaller spec file
└── .github/
    └── workflows/
        └── build.yml         # Windows .exe build via GitHub Actions
```

## Testing Strategy
Since development happens in a Linux Codespace but the app targets Windows:
- **Unit tests**: Test detection logic with saved fixture images (PIL Image objects). Mock `pyautogui` and `win32gui` calls.
- **Dry-run mode**: Add a `--dry-run` CLI flag that logs what would be clicked without actually clicking. Useful for first run on target machine.
- **Transfer**: Build `.exe` via GitHub Actions → download artifact → transfer to closed-network machine via USB or approved method → run and verify.

## Constraints
- Must not interfere with user's active work (no surprise window switches while user is typing/clicking)
- Must be a single `.exe` with zero external dependencies or config files
- Must be lightweight on CPU/memory
- All coordinates hardcoded — no config file needed for v1