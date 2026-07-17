"""Window capture via PrintWindow.

Captures the game window's client area directly, even when the window
is behind other windows. All coordinates in config.json are pixels
inside this client-area image, so nothing breaks when the window moves.
"""

import ctypes

import cv2
import numpy as np
import win32gui
import win32ui

ctypes.windll.user32.SetProcessDPIAware()


class WindowNotFound(Exception):
    pass


def find_window(title_part: str) -> int:
    matches: list[int] = []

    def on_window(hwnd: int, _) -> None:
        title = win32gui.GetWindowText(hwnd)
        if win32gui.IsWindowVisible(hwnd) and title_part.lower() in title.lower():
            matches.append(hwnd)

    win32gui.EnumWindows(on_window, None)
    if not matches:
        raise WindowNotFound(
            f"Basliginda '{title_part}' gecen bir pencere bulunamadi. Oyun acik mi?"
        )
    return matches[0]


def grab_window(title_part: str) -> np.ndarray:
    """Grab the client area of the window as a BGR image."""
    hwnd = find_window(title_part)
    if win32gui.IsIconic(hwnd):
        raise WindowNotFound(
            "Oyun penceresi simge durumuna kucultulmus. Pencereyi ac "
            "(arkada kalabilir, kucultulmus olmasin yeter)."
        )
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width, height = right - left, bottom - top

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bmp)
    try:
        # 3 = PW_CLIENTONLY | PW_RENDERFULLCONTENT (works for GPU-rendered windows)
        ok = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        if not ok:
            raise RuntimeError("PrintWindow basarisiz oldu.")
        info = bmp.GetInfo()
        data = bmp.GetBitmapBits(True)
        img = np.frombuffer(data, dtype=np.uint8).reshape(
            (info["bmHeight"], info["bmWidth"], 4)
        )
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    finally:
        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
