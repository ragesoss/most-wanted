"""Minimal geohash encoder (stdlib only).

Geohash cells are the bundle sharding unit. At precision 4 a cell is
roughly 39 km x 19.5 km; at precision 5 roughly 4.9 km x 4.9 km. The
client downloads every cell overlapping its region of interest, so cell
size only affects transfer granularity, not matching correctness.
"""

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode(lat: float, lon: float, precision: int = 5) -> str:
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    bits = []
    even = True  # geohash interleaves starting with longitude
    while len(bits) < precision * 5:
        rng, value = (lon_range, lon) if even else (lat_range, lat)
        mid = (rng[0] + rng[1]) / 2
        if value >= mid:
            bits.append(1)
            rng[0] = mid
        else:
            bits.append(0)
            rng[1] = mid
        even = not even
    chars = []
    for i in range(0, len(bits), 5):
        chunk = bits[i : i + 5]
        idx = 0
        for b in chunk:
            idx = (idx << 1) | b
        chars.append(BASE32[idx])
    return "".join(chars)
