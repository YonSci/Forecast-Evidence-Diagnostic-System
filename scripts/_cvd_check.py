"""One-off diagnostic (not part of the pipeline): simulate color-vision
deficiency on the discrete bin colors actually used by
scripts/27 and 28, and report the minimum adjacent-bin distance under
each simulation so palette choices are evidence-based, not guessed."""
import numpy as np
import matplotlib.pyplot as plt

# Simplified linear-RGB CVD simulation matrices (Coblis/Machado-style),
# adequate for a relative "which palette is worse" comparison.
CVD_MATRICES = {
    "protanopia": np.array([[0.567, 0.433, 0.000], [0.558, 0.442, 0.000], [0.000, 0.242, 0.758]]),
    "deuteranopia": np.array([[0.625, 0.375, 0.000], [0.700, 0.300, 0.000], [0.000, 0.300, 0.700]]),
    "tritanopia": np.array([[0.950, 0.050, 0.000], [0.000, 0.433, 0.567], [0.000, 0.475, 0.525]]),
}

PALETTES = {
    "RdBu_r (u200/div200/omega500)": ("RdBu_r", 16),
    "jet (u200_vectors speed)": ("jet", 9),
    "YlGnBu (qflux850)": ("YlGnBu", 9),
    "BrBG (mfc850)": ("BrBG", 12),
}


def simulate(rgb, matrix):
    return np.clip(rgb @ matrix.T, 0, 1)


def min_adjacent_distance(colors):
    d = np.linalg.norm(np.diff(colors, axis=0), axis=1) * 255
    return float(d.min()), int(np.argmin(d))


for label, (cmap_name, n) in PALETTES.items():
    cmap = plt.get_cmap(cmap_name)
    colors = np.array([cmap(x)[:3] for x in np.linspace(0, 1, n)])
    print(f"\n{label} -- {n} bins")
    base_min, base_idx = min_adjacent_distance(colors)
    print(f"  normal vision:   min adjacent dist = {base_min:6.1f}  (bins {base_idx}-{base_idx+1})")
    for cvd_name, matrix in CVD_MATRICES.items():
        sim = simulate(colors, matrix)
        d_min, d_idx = min_adjacent_distance(sim)
        flag = "  <-- LOW" if d_min < 25 else ""
        print(f"  {cvd_name:14s}: min adjacent dist = {d_min:6.1f}  (bins {d_idx}-{d_idx+1}){flag}")
