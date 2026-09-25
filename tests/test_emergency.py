import threading

from emergency import watch_for_escape


def test_escape_runs_cleanup_then_exits():
    presses = iter([True, False, False, True])  # a stale press, then a real one later
    events = []
    done = threading.Event()

    def exit_(code):
        events.append(("exit", code))
        done.set()

    watch_for_escape(lambda: events.append("cleanup"), is_pressed=lambda: next(presses),
                     poll_seconds=0.001, exit=exit_)
    assert done.wait(2)
    assert events == ["cleanup", ("exit", 1)]


def test_exit_happens_even_if_cleanup_fails():
    done = threading.Event()
    codes = []

    def failing_cleanup():
        raise RuntimeError("window already gone")

    def exit_(code):
        codes.append(code)
        done.set()

    presses = iter([False, True])
    watch_for_escape(failing_cleanup, is_pressed=lambda: next(presses),
                     poll_seconds=0.001, exit=exit_)
    assert done.wait(2)
    assert codes == [1]


def test_no_exit_while_escape_is_not_pressed():
    exited = threading.Event()
    watch_for_escape(lambda: None, is_pressed=lambda: False, poll_seconds=0.001,
                     exit=lambda code: exited.set())
    assert not exited.wait(0.2)
