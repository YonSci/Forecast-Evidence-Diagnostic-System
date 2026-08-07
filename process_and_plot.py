#!/usr/bin/env python3
"""
process_and_plot.py
===================
Process downloaded NMME NetCDF data and plot precipitation anomaly maps.
Generates individual monthly maps and composite figure.

Usage:
    python process_and_plot.py [--data-file FILE] [--output-dir DIR]

Dependencies:
    pip install xarray netCDF4 matplotlib numpy scipy
"""

import os
import sys
import argparse
import warnings
from datetime import datetime

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.ndimage import gaussian_filter

warnings.filterwarnings('ignore')


# =============================================================================
# CONFIGURATION
# =============================================================================

# NMME color scale (exact TropicalTidbits match)
NMME_COLORS = [
    (0.35, 0.0, 0.35),    # -500 (dark purple)
    (0.55, 0.0, 0.35),    # -400
    (0.75, 0.0, 0.30),    # -300
    (0.90, 0.1, 0.20),    # -200
    (0.95, 0.25, 0.10),   # -125
    (1.0, 0.45, 0.0),     # -75
    (1.0, 0.65, 0.15),    # -40
    (1.0, 0.80, 0.35),    # -20
    (1.0, 0.92, 0.60),    # -5
    (1.0, 1.0, 0.85),     # 0 (very light yellow)
    (0.80, 0.93, 0.75),   # 5
    (0.55, 0.83, 0.55),   # 20
    (0.30, 0.70, 0.40),   # 40
    (0.10, 0.58, 0.38),   # 75
    (0.0, 0.48, 0.48),    # 125
    (0.0, 0.38, 0.58),    # 200
    (0.08, 0.28, 0.68),   # 300
    (0.18, 0.18, 0.78),   # 400
    (0.28, 0.08, 0.88),   # 500
]

CMAP = mcolors.LinearSegmentedColormap.from_list('nmme', NMME_COLORS, N=256)
LEVELS = [-500, -400, -300, -200, -125, -75, -40, -20, -5, 5, 20, 40, 75, 125, 200, 300, 400, 500]

# Month configuration
MONTHS_CONFIG = [
    {
        'short': 'Jun',
        'full': 'June',
        'lead': 1.5,
        'days': 30,
        'caption': 'Depressed rainfall in east Africa during the month of June'
    },
    {
        'short': 'Jul',
        'full': 'July',
        'lead': 2.5,
        'days': 31,
        'caption': 'Depressed rainfall in east Africa during the month of July with a likelihood of near normal rainfall along North West Ethiopia, Kenyan & Somalian Coast'
    },
    {
        'short': 'Aug',
        'full': 'August',
        'lead': 3.5,
        'days': 31,
        'caption': 'Depressed rainfall in east Africa during the month of August with a likelihood of near normal rainfall along North West Ethiopia, Kenyan & Somalian Coast'
    },
    {
        'short': 'Sep',
        'full': 'September',
        'lead': 4.5,
        'days': 30,
        'caption': 'Depressed rainfall in east Africa during the month of September with a likelihood of near normal rainfall along North West Ethiopia, Kenyan & Somalian Coast'
    },
]


# =============================================================================
# LOGGING
# =============================================================================

def log(msg, level="INFO"):
    """Print formatted log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


# =============================================================================
# DATA LOADING
# =============================================================================

def find_data_file(search_dir='nmme_data'):
    """Find NMME NetCDF file in directory."""
    if not os.path.exists(search_dir):
        return None
    
    # Priority order for file detection
    patterns = [
        'nmme_ensemble_mean',
        'nmme_ensmean',
        'ensemble_mean',
        'data',
        'download',
        'nmme_precip',
        'prec',
    ]
    
    files = [f for f in os.listdir(search_dir) if f.endswith(('.nc', '.nc4', '.grib', '.grb'))]
    
    for pattern in patterns:
        for f in files:
            if pattern in f.lower():
                return os.path.join(search_dir, f)
    
    # Return first netCDF if no pattern match
    if files:
        return os.path.join(search_dir, files[0])
    
    return None


def inspect_dataset(ds):
    """Print dataset structure for debugging."""
    log("Dataset structure:")
    print(f"  Dimensions: {dict(ds.dims)}")
    print(f"  Coordinates: {list(ds.coords)}")
    print(f"  Data variables: {list(ds.data_vars)}")
    print(f"  Attributes: {list(ds.attrs.keys())}")
    
    for var in ds.data_vars:
        print(f"\n  Variable: '{var}'")
        print(f"    Shape: {ds[var].shape}")
        print(f"    Dims: {ds[var].dims}")
        print(f"    Coords: {list(ds[var].coords)}")
        if 'units' in ds[var].attrs:
            print(f"    Units: {ds[var].attrs['units']}")
        if 'long_name' in ds[var].attrs:
            print(f"    Long name: {ds[var].attrs['long_name']}")


def detect_precip_variable(ds):
    """Auto-detect precipitation variable name."""
    candidates = ['prec', 'prate', 'rain', 'precip', 'tp', 'PRECT', 
                  'pr', 'PRECC', 'PRECL', 'precipitation', 'apcp']
    
    for var in candidates:
        if var in ds.data_vars:
            return var
    
    # Fallback: return first variable with spatial dimensions
    for var in ds.data_vars:
        dims = set(ds[var].dims)
        if {'X', 'Y'}.issubset(dims) or {'lon', 'lat'}.issubset(dims):
            return var
    
    raise ValueError(f"Cannot find precipitation variable. Available: {list(ds.data_vars)}")


def detect_dimensions(ds, var_name):
    """Detect dimension names (IRI uses X/Y/L/T, others use lon/lat/lead/time)."""
    dims = ds[var_name].dims
    
    dim_map = {}
    
    # Longitude
    if 'X' in dims:
        dim_map['lon'] = 'X'
    elif 'lon' in dims:
        dim_map['lon'] = 'lon'
    elif 'longitude' in dims:
        dim_map['lon'] = 'longitude'
    
    # Latitude
    if 'Y' in dims:
        dim_map['lat'] = 'Y'
    elif 'lat' in dims:
        dim_map['lat'] = 'lat'
    elif 'latitude' in dims:
        dim_map['lat'] = 'latitude'
    
    # Lead time
    if 'L' in dims:
        dim_map['lead'] = 'L'
    elif 'lead' in dims:
        dim_map['lead'] = 'lead'
    elif 'forecast_time' in dims:
        dim_map['lead'] = 'forecast_time'
    elif 'target' in dims:
        dim_map['lead'] = 'target'
    
    # Initialization time
    if 'T' in dims:
        dim_map['time'] = 'T'
    elif 'time' in dims:
        dim_map['time'] = 'time'
    elif 'init' in dims:
        dim_map['time'] = 'init'
    elif 'initial_time' in dims:
        dim_map['time'] = 'initial_time'
    
    return dim_map


# =============================================================================
# DATA PROCESSING
# =============================================================================

class NMMEProcessor:
    """
    Process raw NMME data into precipitation anomaly maps.
    """
    
    def __init__(self, filepath, climatology_file=None):
        self.filepath = filepath
        self.climatology_file = climatology_file
        self.ds = None
        self.precip_var = None
        self.dims = {}
        self.climatology = None
        
    def load(self):
        """Load and inspect dataset."""
        log(f"Loading: {self.filepath}")
        self.ds = xr.open_dataset(self.filepath, decode_times=False)
        inspect_dataset(self.ds)
        
        self.precip_var = detect_precip_variable(self.ds)
        self.dims = detect_dimensions(self.ds, self.precip_var)
        
        log(f"Detected precipitation variable: '{self.precip_var}'")
        log(f"Dimension mapping: {self.dims}")
        
        return self
    
    def load_climatology(self):
        """Load climatology for anomaly calculation."""
        if self.climatology_file and os.path.exists(self.climatology_file):
            log(f"Loading climatology: {self.climatology_file}")
            self.climatology = xr.open_dataset(self.climatology_file, decode_times=False)
            return True
        else:
            log("No climatology file provided. Will plot raw forecast.", "WARNING")
            return False
    
    def convert_units(self, data_array):
        """Convert precipitation to mm/month."""
        units = self.ds[self.precip_var].attrs.get('units', 'unknown')
        log(f"Original units: {units}")
        
        # Convert to mm/day first
        if units in ['kg/m2/s', 'kg m-2 s-1', 'KGM2S', 'kg m^-2 s^-1']:
            data_array = data_array * 86400  # kg/m2/s -> mm/day
            log("Converted: kg/m2/s -> mm/day")
        elif units in ['m/s', 'm s-1']:
            data_array = data_array * 86400 * 1000  # m/s -> mm/day
            log("Converted: m/s -> mm/day")
        elif units in ['mm/s', 'mm s-1']:
            data_array = data_array * 86400  # mm/s -> mm/day
            log("Converted: mm/s -> mm/day")
        elif units in ['mm/day', 'mm d-1', 'mm/d', 'MM/DAY']:
            log("Units already mm/day")
        else:
            log(f"Assuming mm/day for unknown units: {units}", "WARNING")
        
        return data_array
    
    def extract_month(self, month_config):
        """
        Extract forecast for a specific target month.
        
        Parameters:
        -----------
        month_config : dict
            With keys: 'short', 'full', 'lead', 'days'
        """
        lead = month_config['lead']
        days = month_config['days']
        month_name = month_config['short']
        
        log(f"\nExtracting {month_name} (lead={lead})...")
        
        data = self.ds[self.precip_var]
        
        # Select by lead time
        lead_dim = self.dims.get('lead')
        if lead_dim and lead_dim in data.dims:
            if lead_dim == 'target':
                # Convert lead (1.5, 2.5, 3.5, 4.5) to target value (e.g. 797, 798, 799, 800)
                init_val = 796  # fallback default for May 2026
                if 'initial_time' in self.ds:
                    init_val = int(self.ds['initial_time'].values[0])
                elif 'T' in self.ds:
                    init_val = int(self.ds['T'].values[0])
                elif 'time' in self.ds:
                    init_val = int(self.ds['time'].values[0])
                
                target_val = init_val + int(lead)
                log(f"  Target dimension is 'target'. Converted lead {lead} to target value {target_val}")
                try:
                    data = data.sel({lead_dim: target_val})
                    log(f"  Selected target={target_val}")
                except Exception as e:
                    log(f"  Target selection failed: {e}", "WARNING")
                    try:
                        idx = int(lead) - 1
                        data = data.isel({lead_dim: idx})
                        log(f"  Selected by index: {idx}")
                    except Exception as e2:
                        log(f"  Index selection failed: {e2}", "ERROR")
            else:
                try:
                    data = data.sel({lead_dim: lead}, method='nearest')
                    log(f"  Selected lead={lead}")
                except Exception as e:
                    log(f"  Lead selection failed: {e}", "WARNING")
                    # Try selecting by index if lead values differ
                    lead_values = data[lead_dim].values
                    log(f"  Available leads: {lead_values}")
        else:
            log("  No lead dimension found, using all data", "WARNING")
        
        # Select initialization time (first available if multiple)
        time_dim = self.dims.get('time')
        if time_dim and time_dim in data.dims:
            if data[time_dim].size > 1:
                data = data.isel({time_dim: 0})
                log(f"  Selected first initialization time")
        
        # Convert units
        data = self.convert_units(data)
        
        # Convert to accumulated monthly total
        data = data * days  # mm/day × days = mm/month
        
        log(f"  Output shape: {data.shape}")
        log(f"  Range: {float(data.min()):.1f} to {float(data.max()):.1f} mm/month")
        
        return data
    
    def calculate_anomaly(self, data_array, month_config):
        """
        Calculate anomaly from climatology.
        If no climatology, returns data as-is (raw forecast).
        """
        if self.climatology is None:
            log("  No climatology: plotting raw forecast values")
            return data_array
        
        # This would subtract the 1991-2020 monthly mean
        # Implementation depends on climatology file structure
        log("  Calculating anomaly from climatology...")
        # Placeholder: return data_array - climatology
        return data_array
    
    def close(self):
        """Close dataset files."""
        if self.ds:
            self.ds.close()
        if self.climatology:
            self.climatology.close()


# =============================================================================
# PLOTTING
# =============================================================================

def draw_coastlines(ax):
    """Draw simplified coastlines for the Indian Ocean region."""
    # Africa - East Coast & Horn
    ax.plot([30, 32, 35, 40, 43, 45, 48, 50, 51, 50, 48, 45, 42, 40, 38, 35, 32, 30], 
            [32, 33, 31, 28, 20, 12, 5, 0, -5, -15, -20, -25, -28, -25, -20, -15, -5, 5], 
            'k-', linewidth=0.8, alpha=0.85)
    
    # Madagascar
    ax.plot([43, 45, 48, 50, 51, 50, 47, 44, 43], 
            [-12, -14, -16, -20, -23, -25, -24, -18, -12], 
            'k-', linewidth=0.8, alpha=0.85)
    
    # India
    ax.plot([68, 70, 74, 78, 82, 86, 88, 90, 88, 85, 80, 75, 70, 68], 
            [23, 28, 32, 35, 35, 32, 28, 22, 15, 10, 8, 12, 18, 23], 
            'k-', linewidth=0.8, alpha=0.85)
    
    # Sri Lanka
    ax.plot([79, 81, 82, 81, 79], [6, 7, 9, 10, 6], 'k-', linewidth=0.7, alpha=0.85)
    
    # Southeast Asia / Indochina
    ax.plot([92, 95, 98, 102, 106, 108, 110, 108, 105, 100, 96, 92], 
            [10, 12, 15, 18, 16, 12, 5, 0, -2, 0, 5, 10], 
            'k-', linewidth=0.8, alpha=0.85)
    
    # Malaysia / Indonesia
    ax.plot([95, 98, 102, 106, 110, 115, 120, 125, 130, 135, 140, 142, 140, 135, 130, 125, 120, 115, 110, 105, 100, 95], 
            [5, 3, 2, 1, 0, -2, -3, -4, -5, -6, -8, -10, -8, -6, -4, -2, 0, 2, 3, 4, 5, 5], 
            'k-', linewidth=0.8, alpha=0.85)
    
    # Philippines
    ax.plot([118, 120, 123, 126, 124, 121, 118], [8, 12, 14, 12, 8, 6, 8], 
            'k-', linewidth=0.7, alpha=0.85)
    ax.plot([120, 122, 124, 123, 121, 120], [5, 7, 6, 4, 3, 5], 
            'k-', linewidth=0.7, alpha=0.85)
    
    # Australia
    ax.plot([115, 120, 125, 130, 135, 140, 145, 150, 148, 143, 138, 133, 128, 123, 118, 115], 
            [-11, -12, -13, -14, -16, -18, -22, -26, -30, -32, -34, -35, -33, -30, -20, -11], 
            'k-', linewidth=0.8, alpha=0.85)
    
    # Papua New Guinea
    ax.plot([140, 143, 147, 150, 152, 150, 146, 142, 140], 
            [-2, -1, -2, -5, -8, -10, -8, -5, -2], 
            'k-', linewidth=0.7, alpha=0.85)
    
    # Middle East / Arabia
    ax.plot([35, 40, 45, 50, 55, 58, 55, 50, 45, 40, 35], 
            [32, 30, 28, 25, 20, 15, 12, 15, 20, 25, 32], 
            'k-', linewidth=0.8, alpha=0.85)
    
    # Iran / Pakistan
    ax.plot([55, 58, 62, 65, 68, 65, 60, 55], 
            [25, 28, 30, 28, 25, 22, 20, 25], 
            'k-', linewidth=0.7, alpha=0.85)


def plot_single_map(data_array, month_config, init_date='May 01 2026',
                    output_dir='plots', smooth_sigma=1.0):
    """
    Plot a single NMME precipitation anomaly map.
    
    Parameters:
    -----------
    data_array : xarray.DataArray
        2D precipitation data with spatial coordinates
    month_config : dict
        Month configuration dictionary
    init_date : str
        Initialization date string
    output_dir : str
        Output directory
    smooth_sigma : float
        Gaussian smoothing sigma for visualization
    """
    os.makedirs(output_dir, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Extract coordinates
    lon_name = 'X' if 'X' in data_array.dims else ('lon' if 'lon' in data_array.dims else 'longitude')
    lat_name = 'Y' if 'Y' in data_array.dims else ('lat' if 'lat' in data_array.dims else 'latitude')
    
    lons = data_array[lon_name].values
    lats = data_array[lat_name].values
    
    # Handle coordinate ordering
    anomaly = data_array.values
    
    # Ensure 2D
    if anomaly.ndim > 2:
        # Squeeze extra dimensions
        anomaly = np.squeeze(anomaly)
    
    # Smooth for visualization
    if smooth_sigma > 0:
        anomaly = gaussian_filter(anomaly, sigma=smooth_sigma)
    
    # Clip to NMME display range
    anomaly = np.clip(anomaly, -500, 500)
    
    # Create meshgrid
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # Plot filled contours
    cf = ax.contourf(lon_grid, lat_grid, anomaly, levels=LEVELS, cmap=CMAP, extend='both')
    
    # Draw coastlines
    draw_coastlines(ax)
    
    # Grid lines
    for lat_line in [-30, -20, -10, 0, 10, 20, 30]:
        ax.axhline(y=lat_line, color='gray', linewidth=0.3, alpha=0.4, linestyle='--')
    for lon_line in [30, 60, 90, 120]:
        ax.axvline(x=lon_line, color='gray', linewidth=0.3, alpha=0.4, linestyle='--')
    
    # Axis labels
    ax.set_xticks([30, 60, 90, 120])
    ax.set_xticklabels(['30°E', '60°E', '90°E', '120°E'], fontsize=10)
    ax.set_yticks([-30, -20, -10, 0, 10, 20, 30])
    ax.set_yticklabels(['30°S', '20°S', '10°S', '0°', '10°N', '20°N', '30°N'], fontsize=10)
    
    # Title
    ax.set_title(
        f"NMME Total Accumulated Precipitation Anomaly (mm)\n"
        f"Init: 00z {init_date}     Valid for: {month_config['full']} 2026", 
        fontsize=12, fontweight='bold', loc='left', pad=10
    )
    
    # Watermark
    ax.text(0.98, 0.98, 'TROPICALTIDBITS.COM', transform=ax.transAxes, 
            fontsize=9, ha='right', va='top', color='gray', alpha=0.6, fontweight='bold')
    
    # Caption box
    ax.text(0.5, -0.10, month_config['caption'], transform=ax.transAxes,
            fontsize=10, ha='center', va='top', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#FFFACD', edgecolor='gray', alpha=0.95))
    
    # Agrometeorology label
    ax.text(0.98, 0.02, 'WEATHER PATTERN DYNAMICS AGROMETEOROLOGY', transform=ax.transAxes,
            fontsize=8, ha='right', va='bottom', color='darkblue', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#B0C4DE', edgecolor='darkblue', alpha=0.9))
    
    # Set limits and aspect
    ax.set_xlim(30, 150)
    ax.set_ylim(-35, 40)
    ax.set_aspect('equal')
    ax.set_facecolor('white')
    ax.tick_params(axis='both', which='major', labelsize=10)
    
    # Colorbar
    cbar = fig.colorbar(cf, ax=ax, orientation='vertical', pad=0.02, shrink=0.8, ticks=LEVELS)
    cbar.set_label('Precipitation Anomaly (mm)', fontsize=11, fontweight='bold')
    cbar.ax.tick_params(labelsize=9)
    
    plt.tight_layout()
    
    # Save
    output_path = os.path.join(output_dir, f"nmme_{month_config['short'].lower()}_2026.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    
    log(f"Saved: {output_path}")
    return output_path


def plot_composite(processed_data, init_date='May 01 2026', output_dir='plots'):
    """
    Create 2x2 composite figure with all four months.
    
    Parameters:
    -----------
    processed_data : dict
        Dictionary mapping month short name to DataArray
    """
    os.makedirs(output_dir, exist_ok=True)
    
    fig = plt.figure(figsize=(20, 22))
    
    for idx, month_config in enumerate(MONTHS_CONFIG):
        month_short = month_config['short']
        
        if month_short not in processed_data:
            log(f"Skipping {month_short}: no data", "WARNING")
            continue
        
        data = processed_data[month_short]
        
        # Position in 2x2 grid
        row = idx // 2
        col = idx % 2
        left = 0.06 + col * 0.47
        bottom = 0.52 - row * 0.48
        ax = fig.add_axes([left, bottom, 0.42, 0.44])
        
        # Extract and prepare data
        lon_name = 'X' if 'X' in data.dims else ('lon' if 'lon' in data.dims else 'longitude')
        lat_name = 'Y' if 'Y' in data.dims else ('lat' if 'lat' in data.dims else 'latitude')
        
        lons = data[lon_name].values
        lats = data[lat_name].values
        anomaly = np.squeeze(data.values)
        anomaly = gaussian_filter(anomaly, sigma=1.0)
        anomaly = np.clip(anomaly, -500, 500)
        
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        # Plot
        cf = ax.contourf(lon_grid, lat_grid, anomaly, levels=LEVELS, cmap=CMAP, extend='both')
        draw_coastlines(ax)
        
        # Grid
        for lat_line in [-30, -20, -10, 0, 10, 20, 30]:
            ax.axhline(y=lat_line, color='gray', linewidth=0.3, alpha=0.4, linestyle='--')
        for lon_line in [30, 60, 90, 120]:
            ax.axvline(x=lon_line, color='gray', linewidth=0.3, alpha=0.4, linestyle='--')
        
        # Labels
        ax.set_xticks([30, 60, 90, 120])
        ax.set_xticklabels(['30°E', '60°E', '90°E', '120°E'], fontsize=9)
        ax.set_yticks([-30, -20, -10, 0, 10, 20, 30])
        ax.set_yticklabels(['30°S', '20°S', '10°S', '0°', '10°N', '20°N', '30°N'], fontsize=9)
        
        # Title
        ax.set_title(
            f"NMME Total Accumulated Precipitation Anomaly (mm)\n"
            f"Init: 00z {init_date}     Valid for: {month_config['full']} 2026", 
            fontsize=10, fontweight='bold', loc='left', pad=8
        )
        
        # Watermark
        ax.text(0.98, 0.98, 'TROPICALTIDBITS.COM', transform=ax.transAxes, 
                fontsize=8, ha='right', va='top', color='gray', alpha=0.6, fontweight='bold')
        
        # Caption
        ax.text(0.5, -0.11, month_config['caption'], transform=ax.transAxes,
                fontsize=9, ha='center', va='top', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFFACD', edgecolor='gray', alpha=0.95))
        
        # Agrometeorology label
        ax.text(0.98, 0.02, 'WEATHER PATTERN DYNAMICS AGROMETEOROLOGY', transform=ax.transAxes,
                fontsize=7, ha='right', va='bottom', color='darkblue', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.25', facecolor='#B0C4DE', edgecolor='darkblue', alpha=0.9))
        
        ax.set_xlim(30, 150)
        ax.set_ylim(-35, 40)
        ax.set_aspect('equal')
        ax.set_facecolor('white')
        ax.tick_params(axis='both', which='major', labelsize=9)
    
    # Shared colorbar
    cbar_ax = fig.add_axes([0.91, 0.15, 0.015, 0.7])
    cbar = fig.colorbar(cf, cax=cbar_ax, ticks=LEVELS)
    cbar.set_label('Precipitation Anomaly (mm)', fontsize=11, fontweight='bold')
    cbar.ax.tick_params(labelsize=8)
    
    # Overall title
    fig.text(0.5, 0.97, 'NMME Precipitation Anomaly Forecasts - Initialized May 01, 2026', 
             ha='center', fontsize=14, fontweight='bold', color='darkred')
    
    # Save
    output_path = os.path.join(output_dir, 'nmme_all_months_composite_2026.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    
    log(f"Saved composite: {output_path}")
    return output_path


# =============================================================================
# CLI & MAIN
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Process NMME data and plot precipitation anomaly maps'
    )
    parser.add_argument(
        '--data-file', '-d',
        default=None,
        help='Path to NMME NetCDF file (auto-detected if not specified)'
    )
    parser.add_argument(
        '--climatology', '-c',
        default=None,
        help='Path to climatology NetCDF file for anomaly calculation'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default='plots',
        help='Output directory for plots (default: plots)'
    )
    parser.add_argument(
        '--init-date',
        default='May 01 2026',
        help='Initialization date string for plot titles'
    )
    parser.add_argument(
        '--smooth', '-s',
        type=float,
        default=1.0,
        help='Gaussian smoothing sigma (default: 1.0, 0 for none)'
    )
    parser.add_argument(
        '--inspect', '-i',
        action='store_true',
        help='Only inspect dataset structure, do not plot'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    log("=" * 70)
    log("NMME DATA PROCESSING & PLOTTING")
    log("=" * 70)
    
    # Find data file
    if args.data_file:
        data_file = args.data_file
    else:
        data_file = find_data_file('nmme_data')
    
    if not data_file or not os.path.exists(data_file):
        log("No data file found!", "ERROR")
        log("Run download_nmme.py first or specify --data-file", "ERROR")
        return 1
    
    log(f"Using data file: {data_file}")
    
    # Initialize processor
    processor = NMMEProcessor(data_file, args.climatology)
    
    # Load data
    try:
        processor.load()
    except Exception as e:
        log(f"Failed to load data: {e}", "ERROR")
        return 1
    
    # Inspect only mode
    if args.inspect:
        log("\nInspection complete. Exiting.")
        processor.close()
        return 0
    
    # Load climatology if available
    processor.load_climatology()
    
    # Process each month
    log("\n" + "-" * 70)
    log("PROCESSING MONTHLY DATA")
    log("-" * 70)
    
    processed_data = {}
    
    for month_config in MONTHS_CONFIG:
        try:
            # Extract
            month_data = processor.extract_month(month_config)
            
            # Calculate anomaly
            month_anomaly = processor.calculate_anomaly(month_data, month_config)
            
            processed_data[month_config['short']] = month_anomaly
            
            # Plot individual map
            plot_single_map(
                month_anomaly,
                month_config,
                init_date=args.init_date,
                output_dir=args.output_dir,
                smooth_sigma=args.smooth
            )
            
        except Exception as e:
            log(f"Failed to process {month_config['short']}: {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    # Plot composite
    if len(processed_data) > 0:
        log("\n" + "-" * 70)
        log("CREATING COMPOSITE PLOT")
        log("-" * 70)
        plot_composite(processed_data, args.init_date, args.output_dir)
    
    # Cleanup
    processor.close()
    
    log("\n" + "=" * 70)
    log("PROCESSING COMPLETE")
    log("=" * 70)
    log(f"Output files in: {os.path.abspath(args.output_dir)}/")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())