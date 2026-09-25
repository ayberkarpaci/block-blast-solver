from snap import drop_window

CELL = 81.6  # board cell size at the reference window size


def test_middle_of_board_accepts_a_quarter_of_a_cell():
    window = drop_window(3, 3, 2, 2, 8, CELL, CELL)
    assert window.accepts(18, 18)
    assert window.accepts(-18, -18)
    # Logged failure: released 24 px off in the middle of the board.
    assert not window.accepts(8, 24)
    assert (window.aim_dx, window.aim_dy) == (0, 0)


def test_top_row_rejects_any_overhang_and_aims_inside():
    # Logged failures: pieces aimed at row 1 released 26 px and 7 px too high.
    window = drop_window(0, 4, 2, 2, 8, CELL, CELL)
    assert not window.accepts(0, 26)
    assert not window.accepts(0, 7)
    assert window.accepts(0, -CELL / 6)  # where the drag aims
    assert window.accepts(0, -18)  # too low stays on the board and snaps up
    assert window.aim_dy > 0 and window.aim_dx == 0


def test_left_column_rejects_overhang_and_aims_right():
    # Logged failure: aimed at column 1, released 22 px too far left.
    window = drop_window(3, 0, 2, 2, 8, CELL, CELL)
    assert not window.accepts(22, 0)
    assert window.accepts(-18, 0)
    assert window.aim_dx > 0


def test_bottom_right_corner_aims_up_and_left():
    window = drop_window(6, 6, 2, 2, 8, CELL, CELL)
    assert not window.accepts(-5, 0)  # too far right
    assert not window.accepts(0, -5)  # too far down
    assert window.accepts(18, 18)  # inward is fine
    assert window.aim_dx < 0 and window.aim_dy < 0
