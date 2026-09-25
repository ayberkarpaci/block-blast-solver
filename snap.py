"""When is a dragged piece close enough to release?

The game snaps a released piece onto the nearest cells, so in the middle
of the board being within a quarter of a cell of the target is safe.
Next to the board edge that is not enough: a piece that hangs over the
edge at all, even by a few pixels, is rejected. On each side where the
target touches the edge, the drag therefore aims a sixth of a cell
inside the board and releases only once the piece does not stick out.
"""

from dataclasses import dataclass

LOOSE = 1 / 4  # allowed error, as a fraction of a cell, where no edge is near
INSET = 1 / 6  # how far inside the board to aim next to an edge


@dataclass(frozen=True)
class DropWindow:
    """Allowed error (target minus measured piece position), in pixels,
    plus the offset to add to the target when aiming.

    Positive x error means the piece is left of the target, positive y
    error means it is above the target.
    """

    max_left: float  # err_x must stay below this
    max_right: float  # -err_x must stay below this
    max_up: float  # err_y must stay below this
    max_down: float  # -err_y must stay below this
    aim_dx: float = 0.0
    aim_dy: float = 0.0

    def accepts(self, err_x: float, err_y: float) -> bool:
        return (
            -self.max_right < err_x < self.max_left
            and -self.max_down < err_y < self.max_up
        )


def drop_window(row: int, col: int, rows: int, cols: int, grid: int,
                cell_w: float, cell_h: float) -> DropWindow:
    """Release window for a piece of `rows` x `cols` cells whose top-left
    cell goes to (row, col) on a `grid` x `grid` board."""
    left, right = col == 0, col + cols == grid
    top, bottom = row == 0, row + rows == grid
    return DropWindow(
        max_left=0.0 if left else LOOSE * cell_w,
        max_right=0.0 if right else LOOSE * cell_w,
        max_up=0.0 if top else LOOSE * cell_h,
        max_down=0.0 if bottom else LOOSE * cell_h,
        aim_dx=INSET * cell_w * (left - right),
        aim_dy=INSET * cell_h * (top - bottom),
    )
