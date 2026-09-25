"""Interactive calibration (manual fallback).

Normally config.json ships pre-measured coordinates and scales
automatically with the window size, so you rarely need this. Run it if
the game UI layout itself changes (e.g. after a game update).

Shows a capture of the game window; click, in order:

  1. top-left corner of the 8x8 board (inner playable area)
  2. bottom-right corner of the 8x8 board
  3. top-left corner of the piece tray (area holding the 3 pieces)
  4. bottom-right corner of the piece tray
"""

import json

import cv2

from capture import grab_window

CONFIG_PATH = "config.json"
DEFAULT_WINDOW_TITLE = "Block Blast"

STEPS = [
    ("board_tl", "Click the TOP-LEFT corner of the board"),
    ("board_br", "Click the BOTTOM-RIGHT corner of the board"),
    ("tray_tl", "Click the TOP-LEFT corner of the piece tray"),
    ("tray_br", "Click the BOTTOM-RIGHT corner of the piece tray"),
]

MAX_DISPLAY_HEIGHT = 1000


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def calibrate() -> None:
    try:
        window_title = load_config().get("window_title", DEFAULT_WINDOW_TITLE)
    except FileNotFoundError:
        window_title = DEFAULT_WINDOW_TITLE

    img = grab_window(window_title)
    scale = min(1.0, MAX_DISPLAY_HEIGHT / img.shape[0])
    display_base = cv2.resize(img, None, fx=scale, fy=scale)

    points: dict[str, list[int]] = {}
    state = {"step": 0}

    def redraw() -> None:
        canvas = display_base.copy()
        for name, _ in STEPS[: state["step"]]:
            x, y = points[name]
            cv2.drawMarker(
                canvas,
                (int(x * scale), int(y * scale)),
                (0, 0, 255),
                cv2.MARKER_CROSS,
                20,
                2,
            )
        if state["step"] < len(STEPS):
            label = STEPS[state["step"]][1]
            cv2.putText(
                canvas,
                f"{state['step'] + 1}/4: {label}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )
        cv2.imshow("Calibration", canvas)

    def on_mouse(event: int, x: int, y: int, flags: int, param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or state["step"] >= len(STEPS):
            return
        name = STEPS[state["step"]][0]
        points[name] = [round(x / scale), round(y / scale)]
        state["step"] += 1
        print(f"  {name} = {points[name]}")
        redraw()

    cv2.namedWindow("Calibration")
    cv2.setMouseCallback("Calibration", on_mouse)
    print("Click the 4 points in order in the window that opens. ESC cancels.")
    redraw()

    while state["step"] < len(STEPS):
        if cv2.waitKey(50) == 27:  # ESC
            cv2.destroyAllWindows()
            print("Calibration canceled.")
            return

    cv2.destroyAllWindows()

    config = {
        "window_title": window_title,
        "reference_size": [img.shape[1], img.shape[0]],
        "board_tl": points["board_tl"],
        "board_br": points["board_br"],
        "tray_tl": points["tray_tl"],
        "tray_br": points["tray_br"],
        "grid_size": 8,
        "fill_saturation_threshold": 70,
        "fill_value_threshold": 140,
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Saved: {CONFIG_PATH}")
    print("Now test it:  python main.py read")


if __name__ == "__main__":
    calibrate()
