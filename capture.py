"""Screen capture helpers built on mss.

All coordinates in this project are pixel coordinates inside the
full-screen screenshot taken by mss. Calibration clicks happen on that
same screenshot, so the coordinates always line up regardless of
Windows DPI scaling.
"""

import numpy as np
import cv2
import mss


def grab_screen(monitor_index: int = 1) -> np.ndarray:
    """Grab a full screenshot of the given monitor as a BGR image."""
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        shot = sct.grab(monitor)
        img = np.asarray(shot)  # BGRA
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
