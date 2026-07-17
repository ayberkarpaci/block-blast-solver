"""Interactive calibration.

Takes a full-screen screenshot and lets the user click, in order:

  1. top-left corner of the 8x8 board
  2. bottom-right corner of the 8x8 board
  3. top-left corner of the piece tray (area holding the 3 pieces)
  4. bottom-right corner of the piece tray

The four points are saved to config.json. Run again any time the game
window moves or is resized.
"""

import json

import cv2

from capture import grab_screen

CONFIG_PATH = "config.json"

STEPS = [
    ("board_tl", "Tahtanin SOL UST kosesine tikla"),
    ("board_br", "Tahtanin SAG ALT kosesine tikla"),
    ("tray_tl", "Parca alaninin SOL UST kosesine tikla"),
    ("tray_br", "Parca alaninin SAG ALT kosesine tikla"),
]

# Display is scaled down to fit on screen; clicks are mapped back to
# real screenshot pixels using this factor.
MAX_DISPLAY_WIDTH = 1400


def calibrate() -> None:
    print("3 saniye icinde oyun penceresinin acik ve gorunur oldugundan emin ol...")
    cv2.waitKey(3000)
    img = grab_screen()

    scale = min(1.0, MAX_DISPLAY_WIDTH / img.shape[1])
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
                (0, 255, 0),
                cv2.MARKER_CROSS,
                20,
                2,
            )
        if state["step"] < len(STEPS):
            label = STEPS[state["step"]][1]
            cv2.putText(
                canvas,
                f"{state['step'] + 1}/4: {label}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 255),
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
        "board_tl": points["board_tl"],
        "board_br": points["board_br"],
        "tray_tl": points["tray_tl"],
        "tray_br": points["tray_br"],
        "grid_size": 8,
        "fill_value_threshold": 140,
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Kaydedildi: {CONFIG_PATH}")
    print("Simdi test et:  python main.py read")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    calibrate()
