# =============================================================================
# HIS popup detection
# Each entry: (x, y, (R, G, B)) — all points must match within tolerance
# =============================================================================

# Popup area reference: (780,500) to (1140,600)
HIS_DETECTION_POINTS = [
    (820,  500, (196, 34,  34)),   # Red power icon (top-left of dialog)
    (960,  540, (43,  56,  82)),   # Dark navy body background (center)
    (925,  595, (31,  92,  148)),  # Blue "연장" (Extend) button
    (1000, 595, (125, 39,  42)),   # Red "종료" (End) button
]
HIS_COLOR_TOLERANCE = 15  # allowable RGB difference per channel

# Click "연장" (Extend) to dismiss the HIS timeout popup
HIS_CLICK_X = 925
HIS_CLICK_Y = 595

# =============================================================================
# intPC popup detection
# Each entry: (x, y, (R, G, B)) — all points must match within tolerance
# =============================================================================

# Popup area reference: (755,380) to (1165,550); button row at y≈620
INTPC_DETECTION_POINTS = [
    (960, 390, (0,   162, 235)),   # Bright blue "알림" (Notification) title bar
    (960, 465, (255, 255, 255)),   # White dialog body
    (880, 620, (53,  133, 171)),   # Teal "연장" (Extend) button
]
INTPC_COLOR_TOLERANCE = 15  # allowable RGB difference per channel

# Click "연장" (Extend) to dismiss the intPC timeout popup
INTPC_CLICK_X = 910
INTPC_CLICK_Y = 620

# =============================================================================
# intPC process / window identification
# =============================================================================

INTPC_PROCESS_NAME = "desktop-viewer.exe"
INTPC_WINDOW_TITLE = "인터넷 PC"  # partial match is fine

# =============================================================================
# Timing (seconds)
# =============================================================================

JIGGLE_INTERVAL    = 30    # Mouse jiggle cadence
HIS_CHECK_INTERVAL = 60    # HIS popup check cadence
INTPC_CHECK_INTERVAL = 300 # intPC popup check cadence (5 min)
IDLE_THRESHOLD     = 120   # Seconds of inactivity before intPC window switch
IDLE_POLL_INTERVAL = 3     # Idle monitor polling cadence

# =============================================================================
# GUI
# =============================================================================

WINDOW_ALWAYS_ON_TOP = True
LOG_MAX_LINES = 200  # Max lines kept in the GUI log area
