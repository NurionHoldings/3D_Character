#!/usr/bin/env python3
"""WXYZ quaternion helpers for NURION retarget (Convention §8)."""

from __future__ import annotations

from typing import Iterable

Quat = tuple[float, float, float, float]  # w, x, y, z
IDENTITY: Quat = (1.0, 0.0, 0.0, 0.0)


def normalize(q: Quat, eps: float = 1e-12) -> Quat:
    w, x, y, z = q
    n = (w * w + x * x + y * y + z * z) ** 0.5
    if n < eps:
        return IDENTITY
    return (w / n, x / n, y / n, z / n)


def hemisphere(q: Quat) -> Quat:
    """Convention §8: force w >= 0."""
    q = normalize(q)
    if q[0] < 0.0:
        return (-q[0], -q[1], -q[2], -q[3])
    return q


def conjugate(q: Quat) -> Quat:
    w, x, y, z = q
    return (w, -x, -y, -z)


def inverse(q: Quat) -> Quat:
    return hemisphere(conjugate(normalize(q)))


def multiply(a: Quat, b: Quat) -> Quat:
    """parent_first: R = a * b (column vectors)."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return hemisphere(
        (
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        )
    )


def quat_to_matrix(q: Quat) -> tuple[tuple[float, float, float], ...]:
    w, x, y, z = normalize(q)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return (
        (1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)),
        (2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)),
        (2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)),
    )


def mat_mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)
    )


def mat_approx_eq(a, b, tol: float = 1e-5) -> bool:
    for i in range(3):
        for j in range(3):
            if abs(a[i][j] - b[i][j]) > tol:
                return False
    return True


def mirror_yz(q: Quat) -> Quat:
    """Convention §19: S=diag(-1,1,1); q'=(w,x,-y,-z); hemisphere."""
    w, x, y, z = normalize(q)
    return hemisphere((w, x, -y, -z))


def mirror_conjugation_holds(q: Quat, tol: float = 1e-5) -> bool:
    """quat_to_matrix(mirror(q)) ≈ S R(q) S."""
    s = ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    r = quat_to_matrix(q)
    lhs = quat_to_matrix(mirror_yz(q))
    rhs = mat_mul(mat_mul(s, r), s)
    return mat_approx_eq(lhs, rhs, tol=tol)


def approx_eq(a: Quat, b: Quat, tol: float = 1e-4) -> bool:
    a, b = hemisphere(a), hemisphere(b)
    return all(abs(a[i] - b[i]) <= tol for i in range(4))


def from_iterable(values: Iterable[float]) -> Quat:
    w, x, y, z = values
    return hemisphere((float(w), float(x), float(y), float(z)))


def rotate_vector(q: Quat, v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Apply rotation q to vector v (same R used by conjugation on pure quaternions)."""
    q = normalize(q)
    pure: Quat = (0.0, float(v[0]), float(v[1]), float(v[2]))
    # q * v * q^{-1} without hemisphere on intermediate pure results
    aw, ax, ay, az = q
    bw, bx, by, bz = pure
    iw, ix, iy, iz = (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )
    # q^{-1} = conjugate for unit q
    cw, cx, cy, cz = aw, -ax, -ay, -az
    _, x, y, z = (
        iw * cw - ix * cx - iy * cy - iz * cz,
        iw * cx + ix * cw + iy * cz - iz * cy,
        iw * cy - ix * cz + iy * cw + iz * cx,
        iw * cz + ix * cy - iy * cx + iz * cw,
    )
    return (float(x), float(y), float(z))


def mirror_vector_yz(v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convention §19: S=diag(-1,+1,+1); v' = (-vx, vy, vz)."""
    return (-float(v[0]), float(v[1]), float(v[2]))
