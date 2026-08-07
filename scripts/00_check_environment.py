import sys
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
import scipy

print("Python executable:")
print(sys.executable)

print("\nPackage versions:")
print("numpy:", np.__version__)
print("pandas:", pd.__version__)
print("xarray:", xr.__version__)
print("matplotlib:", matplotlib.__version__)
print("scipy:", scipy.__version__)

try:
    import cartopy
    print("cartopy:", cartopy.__version__)
except Exception as e:
    print("cartopy import failed:", e)

try:
    import metpy
    print("metpy:", metpy.__version__)
except Exception as e:
    print("metpy import failed:", e)

try:
    import cdsapi
    print("cdsapi: installed")
except Exception as e:
    print("cdsapi import failed:", e)

print("\nEnvironment check completed.")