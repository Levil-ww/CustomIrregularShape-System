"""Extract an actual repeating ornament period without carrying rectangular corners."""
import numpy as np


def extract_dark_period(strip):
    """Recognize periodic dark ink even when its background contains artwork."""
    dark = np.max(strip, axis=2) < 40
    mask = np.repeat(np.where(dark[..., None], 0, 255).astype(np.uint8), 3, axis=2)
    _, period = extract_period(mask)
    if not period or strip.shape[1] < 8 * period:
        return strip.copy(), 0
    start = (strip.shape[1] - period) // 2
    return strip[:, start:start + period].copy(), period


def extract_period(strip):
    height, width = strip.shape[:2]
    if width < 12:
        return strip.copy(), 0
    # Flat outline/background rows contribute no phase information. Use ornament rows only.
    variation = np.std(strip.astype(np.float32), axis=1).mean(axis=1)
    rows = np.flatnonzero(variation > max(2., variation.max() * .25))
    if rows.size == 0:
        return strip.copy(), 0
    rows = rows[np.linspace(0, len(rows) - 1, min(32, len(rows))).astype(int)]
    signature = strip[rows].astype(np.float32).mean(axis=(0, 2))
    stride = max(1, int(np.ceil(width / 4096)))
    signal = signature[::stride].astype(np.float64)
    signal -= signal.mean()
    variance = np.mean(signal**2)
    if variance < 1:
        return strip.copy(), 0
    n = len(signal)
    fft = np.fft.rfft(signal, n=2 * n)
    correlation = np.fft.irfft(fft * fft.conj(), n=2 * n)[:n]
    correlation /= np.arange(n, 0, -1) * variance
    for lag in range(2, max(2, n // 3)):
        if correlation[lag] < .90 or not (correlation[lag] > correlation[lag - 1] and correlation[lag] >= correlation[lag + 1]):
            continue
        candidates = range(max(3, lag * stride - stride), min(width // 3, lag * stride + stride) + 1)
        errors = [(float(np.mean((signature[p:] - signature[:-p])**2)), p) for p in candidates]
        if not errors:
            continue
        error, period = min(errors)
        # Check all selected rows too: their average alone can conceal alternating motifs.
        region = strip[rows].astype(np.float32)
        full_error = float(np.mean((region[:, period:] - region[:, :-period])**2))
        full_variance = float(np.mean(np.var(region, axis=1)))
        if full_error > max(3., full_variance * .12):
            continue
        start = (width - period) // 2
        return strip[:, start:start + period].copy(), period
    return strip.copy(), 0
