"""Small typing shims to avoid importing optional heavy deps at module import time."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np  # noqa: F401
