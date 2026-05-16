# bfl_asic/ml/__init__.py
"""Optional ML subsystem: round-reduced SHA-256 learnability instrument.

Importing this package is torch-free.  Only :func:`round_reduced_sha256`
(numpy-only) is re-exported here; everything that needs PyTorch lives in
submodules imported lazily by the CLI behind the ``[ml]`` extra.
"""
from bfl_asic.ml.roundreduced import round_reduced_sha256

__all__ = ["round_reduced_sha256"]
