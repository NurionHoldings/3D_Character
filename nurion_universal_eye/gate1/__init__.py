"""Gate 1 — Universal Face Basis (no EyePlane / convex eye / motion)."""

from .universal_face_basis import build_universal_face_basis
from .face_basis_validator import validate_face_basis

__all__ = ["build_universal_face_basis", "validate_face_basis"]
