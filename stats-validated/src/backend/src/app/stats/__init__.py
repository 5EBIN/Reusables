"""Deterministic statistics for Acme (no model calls).

Every public function returns a `Stat` (or a dict of them). Below its minimum sample size a
function returns Stat(insufficient=True, ...) with the requirement, never a number.
Libraries: numpy, scipy, statsmodels, scikit-learn (BSD) and semopy (MIT) only.
"""
from .result import Stat, insufficient  # noqa: F401
