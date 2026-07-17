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
    ("board_tl", "Tahtanin SOL UST kosesine tikla"),
    ("board_br", "Tahtanin SAG ALT kosesine tikla"),
    ("tray_tl", "Parca alaninin SOL UST kosesine tikla"),
    ("tray_br", "Parca alaninin SAG ALT kosesine tikla"),
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
        cv2.imshow("Kalibrasyon", canvas)

    def on_mouse(event: int, x: int, y: int, flags: int, param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or state["step"] >= len(STEPS):
            return
        name = STEPS[state["step"]][0]
        points[name] = [round(x / scale), round(y / scale)]
        state["step"] += 1
        print(f"  {name} = {points[name]}")
        redraw()

    cv2.namedWindow("Kalibrasyon")
    cv2.setMouseCallback("Kalibrasyon", on_mouse)
    print("Acilan pencerede sirayla 4 noktaya tikla. Iptal icin ESC.")
    redraw()

    while state["step"] < len(STEPS):
        if cv2.waitKey(50) == 27:  # ESC
            cv2.destroyAllWindows()
            print("Kalibrasyon iptal edildi.")
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
    print(f"Kaydedildi: {CONFIG_PATH}")
    print("Simdi test et:  python main.py read")


if __name__ == "__main__":
    calibrate()
