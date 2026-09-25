"""Emergency stop for auto-play: press ESC anywhere to halt at once.

The mouse-corner failsafe is not reliable while the bot drags: it moves
the cursor itself many times a second and overrides where the user
pushes it. The keyboard does not compete with the bot, so a watcher
thread polls ESC globally (the game window does not need focus) and,
when it is pressed, runs the cleanup and ends the process on the spot,
even in the middle of a drag.
"""

import os
import threading
import time
from typing import Callable

VK_ESCAPE = 0x1B


def escape_pressed() -> bool:
    """True if ESC is down now or was pressed since the last check."""
    import win32api

    return bool(win32api.GetAsyncKeyState(VK_ESCAPE) & 0x8001)


def watch_for_escape(
    on_stop: Callable[[], None],
    is_pressed: Callable[[], bool] = escape_pressed,
    poll_seconds: float = 0.02,
    exit: Callable[[int], None] = os._exit,
) -> threading.Thread:
    """Start a daemon thread that calls `on_stop` and exits on ESC.

    `os._exit` is used on purpose: it ends the process immediately,
    whatever the main thread is doing (sleeping inside a mouse move,
    waiting for an animation). `on_stop` does the cleanup first.
    """
    is_pressed()  # clear a press left over from before the watch started

    def run() -> None:
        while not is_pressed():
            time.sleep(poll_seconds)
        try:
            on_stop()
        except Exception as error:  # stopping matters more than cleanup
            print(f"Emergency cleanup failed: {error}", flush=True)
        exit(1)

    thread = threading.Thread(target=run, name="escape-watch", daemon=True)
    thread.start()
    return thread
