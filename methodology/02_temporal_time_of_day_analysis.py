"""
Waymo Crash Data - Time-of-Day Temporal Analysis
================================================

This script analyzes crash patterns based on time of day using the merged NHTSA data:
1. Peak crash times for each day of the week
2. Location types by time-of-day (bars, intersections, highways, etc.)
3. Geospatial visualization with time-passage scrolling feature
4. Additional temporal insights

Usage: python 02_temporal_time_of_day_analysis.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, time
import re
import warnings
import os
import json

warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# Paths
BASE_DIR = '/Users/kateli/Desktop/Classes/COMM277T/bna-fuhgeddaboudit'
DATA_PATH = os.path.join(BASE_DIR, 'cleaned-data/waymo_merged_nhtsa_hub_CLEAN.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'figures/02_time_of_day_analysis')
WEBDEV_DIR = os.path.join(BASE_DIR, 'webdev')

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("="*70)
print("WAYMO CRASH DATA - TIME-OF-DAY ANALYSIS")
print("="*70)

# =============================================================================
# 1. LOAD AND PREPARE DATA
# =============================================================================

print("\n[1] Loading and preparing data...")

df = pd.read_csv(DATA_PATH)
print(f"Total records loaded: {len(df)}")

# Parse incident time
def parse_time(time_str):
    """Parse time string in various formats."""
    if pd.isna(time_str) or time_str == '' or str(time_str).strip() == '':
        return None
    try:
        time_str = str(time_str).strip()
        # Handle HH:MM format
        if ':' in time_str:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
        # Handle HHMM format
        elif len(time_str) == 4 and time_str.isdigit():
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
    except:
        pass
    return None

# Parse incident date
def parse_date(date_str):
    """Parse date string in various formats."""
    if pd.isna(date_str):
        return None
    try:
        date_str = str(date_str).strip()
        # Try MM/DD/YY format
        for fmt in ['%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d', '%d-%b-%Y']:
            try:
                return pd.to_datetime(date_str, format=fmt)
            except:
                continue
        # Fallback to pandas auto-detection
        return pd.to_datetime(date_str)
    except:
        return None

# Apply parsing
df['incident_time'] = df['Incident Time (24:00)'].apply(parse_time)
df['incident_date'] = df['Incident Date'].apply(parse_date)

# Filter rows with valid time data
df_time = df[df['incident_time'].notna()].copy()
print(f"Records with valid time data: {len(df_time)} ({len(df_time)/len(df)*100:.1f}%)")

# Extract temporal features
df_time['hour'] = df_time['incident_time'].apply(lambda x: x.hour if x else None)
df_time['minute'] = df_time['incident_time'].apply(lambda x: x.minute if x else None)

# Date features (from incident_date)
df_time_with_date = df_time[df_time['incident_date'].notna()].copy()
df_time_with_date['day_of_week'] = df_time_with_date['incident_date'].dt.day_name()
df_time_with_date['day_of_week_num'] = df_time_with_date['incident_date'].dt.dayofweek
df_time_with_date['month'] = df_time_with_date['incident_date'].dt.month
df_time_with_date['year'] = df_time_with_date['incident_date'].dt.year
df_time_with_date['is_weekend'] = df_time_with_date['day_of_week_num'].isin([5, 6])

print(f"Records with both time and date: {len(df_time_with_date)}")

# Create time period categories
def categorize_time_period(hour):
    """Categorize hour into meaningful time periods."""
    if pd.isna(hour):
        return 'Unknown'
    hour = int(hour)
    if 5 <= hour < 7:
        return 'Early Morning (5-7 AM)'
    elif 7 <= hour < 10:
        return 'Morning Rush (7-10 AM)'
    elif 10 <= hour < 12:
        return 'Late Morning (10 AM-12 PM)'
    elif 12 <= hour < 14:
        return 'Midday (12-2 PM)'
    elif 14 <= hour < 17:
        return 'Afternoon (2-5 PM)'
    elif 17 <= hour < 20:
        return 'Evening Rush (5-8 PM)'
    elif 20 <= hour < 23:
        return 'Night (8-11 PM)'
    else:  # 23, 0, 1, 2, 3, 4
        return 'Late Night (11 PM-5 AM)'

df_time['time_period'] = df_time['hour'].apply(categorize_time_period)
df_time_with_date['time_period'] = df_time_with_date['hour'].apply(categorize_time_period)

# =============================================================================
# 2. LOCATION TYPE EXTRACTION FROM NARRATIVES AND ADDRESSES
# =============================================================================

print("\n[2] Extracting location types from narratives and addresses...")

# Location type patterns
LOCATION_PATTERNS = {
    'Intersection': [
        r'\bintersection\b', r'\bcrossing\b', r'\bat\s+\w+\s+(and|&)\s+\w+',
        r'\bcrossroads\b', r'\bjunction\b'
    ],
    'Highway/Freeway': [
        r'\bhighway\b', r'\bfreeway\b', r'\bi-\d+', r'\binterstate\b',
        r'\bexpressway\b', r'\bhwy\b', r'\bramp\b', r'\bon-ramp\b', r'\boff-ramp\b'
    ],
    'Parking Lot/Garage': [
        r'\bparking\s*(lot|garage|structure)\b', r'\bparked\b', r'\bgarage\b',
        r'\bvalet\b', r'\bparking\b'
    ],
    'Commercial/Business District': [
        r'\bshopping\b', r'\bmall\b', r'\bstore\b', r'\bmarket\b', r'\bplaza\b',
        r'\bdowntown\b', r'\bbusiness\s*district\b', r'\bcommercial\b'
    ],
    'Residential Area': [
        r'\bresidential\b', r'\bneighborhood\b', r'\bapartment\b', r'\bcondo\b',
        r'\bhouse\b', r'\bhome\b'
    ],
    'Restaurant/Bar Area': [
        r'\brestaurant\b', r'\bbar\b', r'\bdiner\b', r'\bcafe\b', r'\bpub\b',
        r'\bnightclub\b', r'\bclub\b', r'\beating\b', r'\bdining\b'
    ],
    'Hotel/Tourism': [
        r'\bhotel\b', r'\bmotel\b', r'\bresort\b', r'\btourist\b', r'\bairport\b'
    ],
    'School/University': [
        r'\bschool\b', r'\buniversity\b', r'\bcollege\b', r'\bcampus\b',
        r'\beducation\b', r'\bacademy\b'
    ],
    'Hospital/Medical': [
        r'\bhospital\b', r'\bmedical\b', r'\bclinic\b', r'\bemergency\b',
        r'\bhealthcare\b'
    ],
    'Transit/Station': [
        r'\bstation\b', r'\btransit\b', r'\bbus\s*stop\b', r'\btrain\b',
        r'\bsubway\b', r'\bbart\b', r'\bmuni\b'
    ]
}

def extract_location_type(row):
    """Extract location type from narrative and address."""
    text = ''
    if pd.notna(row.get('Narrative')):
        text += str(row['Narrative']).lower() + ' '
    if pd.notna(row.get('Location Address / Description')):
        text += str(row['Location Address / Description']).lower() + ' '
    if pd.notna(row.get('Address')):
        text += str(row['Address']).lower()

    if not text.strip():
        return 'Unknown'

    # Check each pattern
    for loc_type, patterns in LOCATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return loc_type

    # Default: check if it's a street
    if re.search(r'\b(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|way|lane|ln)\b', text, re.IGNORECASE):
        return 'Street/Road'

    return 'Other/Unknown'

df_time['location_type'] = df_time.apply(extract_location_type, axis=1)
df_time_with_date['location_type'] = df_time_with_date.apply(extract_location_type, axis=1)

print("Location types identified:")
print(df_time['location_type'].value_counts())

# =============================================================================
# 3. ANALYSIS 1: Peak Crash Times by Day of Week
# =============================================================================

print("\n[3] Analyzing peak crash times by day of week...")

day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# Create hour x day heatmap data
hour_day_counts = df_time_with_date.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
hour_day_pivot = hour_day_counts.pivot(index='hour', columns='day_of_week', values='count').fillna(0)
hour_day_pivot = hour_day_pivot.reindex(columns=day_order)

# Find peak hours for each day
peak_hours_by_day = {}
for day in day_order:
    if day in hour_day_pivot.columns:
        peak_hour = hour_day_pivot[day].idxmax()
        peak_count = hour_day_pivot[day].max()
        peak_hours_by_day[day] = {'hour': int(peak_hour), 'count': int(peak_count)}

print("\nPeak crash hours by day of week:")
for day, info in peak_hours_by_day.items():
    print(f"  {day}: {info['hour']:02d}:00 ({info['count']} crashes)")

# Plot: Heatmap of crashes by hour and day
fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# 1. Main heatmap
ax1 = axes[0, 0]
sns.heatmap(hour_day_pivot, cmap='YlOrRd', annot=True, fmt='.0f', ax=ax1,
            cbar_kws={'label': 'Number of Crashes'}, linewidths=0.5)
ax1.set_title('Crash Frequency: Hour of Day × Day of Week', fontsize=14, fontweight='bold')
ax1.set_xlabel('Day of Week', fontsize=12)
ax1.set_ylabel('Hour of Day', fontsize=12)

# 2. Hourly distribution overall
ax2 = axes[0, 1]
hourly_total = df_time['hour'].value_counts().sort_index()
colors = ['#ff6b6b' if 7 <= h <= 9 or 17 <= h <= 19 else '#4dabf7' for h in range(24)]
ax2.bar(range(24), [hourly_total.get(h, 0) for h in range(24)], color=colors, alpha=0.8, edgecolor='black')
ax2.axvspan(7, 10, alpha=0.2, color='red', label='Morning Rush (7-10)')
ax2.axvspan(17, 20, alpha=0.2, color='orange', label='Evening Rush (5-8)')
ax2.set_xlabel('Hour of Day', fontsize=12)
ax2.set_ylabel('Number of Crashes', fontsize=12)
ax2.set_title('Overall Hourly Crash Distribution', fontsize=14, fontweight='bold')
ax2.set_xticks(range(0, 24, 2))
ax2.legend(loc='upper left')
ax2.grid(axis='y', alpha=0.3)

# 3. Weekday vs Weekend by hour
ax3 = axes[1, 0]
weekday_hourly = df_time_with_date[~df_time_with_date['is_weekend']].groupby('hour').size()
weekend_hourly = df_time_with_date[df_time_with_date['is_weekend']].groupby('hour').size()

x = range(24)
width = 0.35
weekday_vals = [weekday_hourly.get(h, 0) for h in x]
weekend_vals = [weekend_hourly.get(h, 0) for h in x]

ax3.bar([i - width/2 for i in x], weekday_vals, width, label='Weekday', color='steelblue', alpha=0.8)
ax3.bar([i + width/2 for i in x], weekend_vals, width, label='Weekend', color='coral', alpha=0.8)
ax3.set_xlabel('Hour of Day', fontsize=12)
ax3.set_ylabel('Number of Crashes', fontsize=12)
ax3.set_title('Weekday vs Weekend Hourly Patterns', fontsize=14, fontweight='bold')
ax3.legend()
ax3.set_xticks(range(0, 24, 2))
ax3.grid(axis='y', alpha=0.3)

# 4. Time period distribution
ax4 = axes[1, 1]
time_period_order = [
    'Early Morning (5-7 AM)', 'Morning Rush (7-10 AM)', 'Late Morning (10 AM-12 PM)',
    'Midday (12-2 PM)', 'Afternoon (2-5 PM)', 'Evening Rush (5-8 PM)',
    'Night (8-11 PM)', 'Late Night (11 PM-5 AM)'
]
time_period_counts = df_time['time_period'].value_counts()
time_period_counts = time_period_counts.reindex([t for t in time_period_order if t in time_period_counts.index])

colors_tp = ['#ffd93d', '#ff6b6b', '#6bcb77', '#4d96ff', '#ff8c42', '#ff6b6b', '#845ec2', '#2c3e50']
ax4.barh(range(len(time_period_counts)), time_period_counts.values, color=colors_tp[:len(time_period_counts)], alpha=0.8)
ax4.set_yticks(range(len(time_period_counts)))
ax4.set_yticklabels(time_period_counts.index, fontsize=10)
ax4.set_xlabel('Number of Crashes', fontsize=12)
ax4.set_title('Crashes by Time Period', fontsize=14, fontweight='bold')
ax4.grid(axis='x', alpha=0.3)
for i, v in enumerate(time_period_counts.values):
    ax4.text(v + 2, i, f'{v} ({v/len(df_time)*100:.1f}%)', va='center', fontsize=9)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'time_of_day_analysis.png'), dpi=300, bbox_inches='tight')
plt.close()
print(f"Saved: time_of_day_analysis.png")

# =============================================================================
# 4. ANALYSIS 2: Location Types by Time of Day
# =============================================================================

print("\n[4] Analyzing location types by time of day...")

# Create location x time period crosstab
loc_time = pd.crosstab(df_time['location_type'], df_time['time_period'], normalize='columns') * 100
loc_time = loc_time.reindex(columns=[t for t in time_period_order if t in loc_time.columns])

# Weekend night analysis (bars/restaurants)
weekend_night = df_time_with_date[
    (df_time_with_date['is_weekend']) &
    (df_time_with_date['hour'].isin([20, 21, 22, 23, 0, 1, 2, 3]))
]
weekday_day = df_time_with_date[
    (~df_time_with_date['is_weekend']) &
    (df_time_with_date['hour'].isin(range(9, 17)))
]

print("\nLocation type distribution - Weekend nights (8 PM - 3 AM):")
print(weekend_night['location_type'].value_counts(normalize=True).head(5) * 100)

print("\nLocation type distribution - Weekday daytime (9 AM - 5 PM):")
print(weekday_day['location_type'].value_counts(normalize=True).head(5) * 100)

# Plot location type analysis
fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# 1. Location type heatmap by time period
ax1 = axes[0, 0]
# Select top location types
top_locations = df_time['location_type'].value_counts().head(8).index
loc_time_filtered = loc_time.loc[loc_time.index.isin(top_locations)]
sns.heatmap(loc_time_filtered, cmap='Blues', annot=True, fmt='.1f', ax=ax1,
            cbar_kws={'label': '% of crashes in time period'}, linewidths=0.5)
ax1.set_title('Location Type × Time Period (%)', fontsize=14, fontweight='bold')
ax1.set_xlabel('Time Period', fontsize=12)
ax1.set_ylabel('Location Type', fontsize=12)
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

# 2. Weekend night vs Weekday day comparison
ax2 = axes[0, 1]
weekend_night_loc = weekend_night['location_type'].value_counts(normalize=True).head(6) * 100
weekday_day_loc = weekday_day['location_type'].value_counts(normalize=True).head(6) * 100

all_locs = list(set(weekend_night_loc.index) | set(weekday_day_loc.index))[:6]
x = range(len(all_locs))
width = 0.35

wn_vals = [weekend_night_loc.get(loc, 0) for loc in all_locs]
wd_vals = [weekday_day_loc.get(loc, 0) for loc in all_locs]

ax2.barh([i - width/2 for i in x], wn_vals, width, label='Weekend Night', color='purple', alpha=0.7)
ax2.barh([i + width/2 for i in x], wd_vals, width, label='Weekday Day', color='green', alpha=0.7)
ax2.set_yticks(range(len(all_locs)))
ax2.set_yticklabels(all_locs, fontsize=9)
ax2.set_xlabel('Percentage of Crashes (%)', fontsize=12)
ax2.set_title('Weekend Night vs Weekday Day: Location Types', fontsize=14, fontweight='bold')
ax2.legend()
ax2.grid(axis='x', alpha=0.3)

# 3. Hour x Location Type heatmap (selected locations)
ax3 = axes[1, 0]
hour_loc = pd.crosstab(df_time['hour'], df_time['location_type'])
hour_loc_filtered = hour_loc[[c for c in ['Intersection', 'Street/Road', 'Parking Lot/Garage',
                                           'Highway/Freeway', 'Commercial/Business District']
                              if c in hour_loc.columns]]
sns.heatmap(hour_loc_filtered, cmap='YlOrRd', ax=ax3, cbar_kws={'label': 'Count'})
ax3.set_title('Hour × Location Type', fontsize=14, fontweight='bold')
ax3.set_xlabel('Location Type', fontsize=12)
ax3.set_ylabel('Hour of Day', fontsize=12)

# 4. Lighting conditions by time
ax4 = axes[1, 1]
if 'Lighting' in df_time.columns:
    lighting_hour = pd.crosstab(df_time['hour'], df_time['Lighting'].fillna('Unknown'))
    # Filter for main lighting conditions
    main_lighting = [c for c in ['Daylight', 'Dark', 'Dark - Lighted', 'Dawn', 'Dusk']
                     if c in lighting_hour.columns]
    if main_lighting:
        lighting_hour[main_lighting].plot(kind='area', stacked=True, ax=ax4, alpha=0.7)
        ax4.set_xlabel('Hour of Day', fontsize=12)
        ax4.set_ylabel('Number of Crashes', fontsize=12)
        ax4.set_title('Lighting Conditions by Hour', fontsize=14, fontweight='bold')
        ax4.legend(title='Lighting', loc='upper right')
        ax4.set_xticks(range(0, 24, 2))
    else:
        ax4.text(0.5, 0.5, 'Lighting data not available', ha='center', va='center', transform=ax4.transAxes)
else:
    ax4.text(0.5, 0.5, 'Lighting data not available', ha='center', va='center', transform=ax4.transAxes)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'location_time_analysis.png'), dpi=300, bbox_inches='tight')
plt.close()
print(f"Saved: location_time_analysis.png")

# =============================================================================
# 5. ANALYSIS 3: Prepare Data for Time-Passage Map
# =============================================================================

print("\n[5] Preparing data for time-passage geospatial visualization...")

# Extract crashes with valid coordinates and time
df_geo = df_time_with_date.copy()

# Clean latitude/longitude
def clean_coord(val):
    """Clean coordinate value."""
    if pd.isna(val):
        return None
    try:
        val_str = str(val).strip()
        if 'PERSONALLY IDENTIFIABLE' in val_str.upper() or val_str == '':
            return None
        return float(val_str)
    except:
        return None

df_geo['lat'] = df_geo['Latitude'].apply(clean_coord)
df_geo['lon'] = df_geo['Longitude'].apply(clean_coord)

# Filter valid coordinates
df_geo_valid = df_geo[(df_geo['lat'].notna()) & (df_geo['lon'].notna()) &
                       (df_geo['lat'] != 0) & (df_geo['lon'] != 0)].copy()

# For crashes without coordinates, use city-based approximation
CITY_COORDS = {
    'SAN_FRANCISCO': (37.7749, -122.4194),
    'San Francisco': (37.7749, -122.4194),
    'PHOENIX': (33.4484, -112.0740),
    'Phoenix': (33.4484, -112.0740),
    'LOS_ANGELES': (34.0522, -118.2437),
    'Los Angeles': (34.0522, -118.2437),
    'AUSTIN': (30.2672, -97.7431),
    'Austin': (30.2672, -97.7431),
    'ATLANTA': (33.7490, -84.3880),
    'Atlanta': (33.7490, -84.3880)
}

def get_coords_from_city(row):
    """Get approximate coordinates from city if not available."""
    if pd.notna(row['lat']) and pd.notna(row['lon']):
        return row['lat'], row['lon']

    city = row.get('Location') or row.get('City')
    if city and city in CITY_COORDS:
        base_lat, base_lon = CITY_COORDS[city]
        # Add small random offset
        return base_lat + np.random.uniform(-0.02, 0.02), base_lon + np.random.uniform(-0.02, 0.02)
    return None, None

# Apply to all data
df_geo['lat_final'], df_geo['lon_final'] = zip(*df_geo.apply(get_coords_from_city, axis=1))
df_geo_mapped = df_geo[df_geo['lat_final'].notna()].copy()

print(f"Crashes with coordinates: {len(df_geo_valid)}")
print(f"Crashes mappable (including city approximation): {len(df_geo_mapped)}")

# Prepare JSON data for the time-passage map
map_data = []
for _, row in df_geo_mapped.iterrows():
    crash_data = {
        'lat': row['lat_final'],
        'lon': row['lon_final'],
        'hour': int(row['hour']) if pd.notna(row['hour']) else None,
        'day_of_week': row['day_of_week'],
        'day_num': int(row['day_of_week_num']) if pd.notna(row['day_of_week_num']) else None,
        'time_period': row['time_period'],
        'location_type': row['location_type'],
        'crash_type': row.get('Crash Type', 'Unknown'),
        'city': row.get('Location') or row.get('City', 'Unknown'),
        'date': row['incident_date'].strftime('%Y-%m-%d') if pd.notna(row['incident_date']) else None,
        'is_weekend': bool(row['is_weekend']) if pd.notna(row['is_weekend']) else False
    }
    map_data.append(crash_data)

# Save as JSON for web visualization
json_output_path = os.path.join(WEBDEV_DIR, 'crash_time_data.json')
with open(json_output_path, 'w') as f:
    json.dump(map_data, f)
print(f"Saved crash data for map: {json_output_path}")

# =============================================================================
# 6. ADDITIONAL INSIGHTS
# =============================================================================

print("\n[6] Generating additional insights...")

# Insight 1: Rush hour concentration
rush_hour_crashes = df_time[(df_time['hour'] >= 7) & (df_time['hour'] <= 9) |
                            (df_time['hour'] >= 17) & (df_time['hour'] <= 19)]
rush_hour_pct = len(rush_hour_crashes) / len(df_time) * 100
print(f"\nRush hour (7-9 AM & 5-7 PM) crashes: {len(rush_hour_crashes)} ({rush_hour_pct:.1f}%)")

# Insight 2: Late night analysis
late_night = df_time[(df_time['hour'] >= 23) | (df_time['hour'] <= 4)]
late_night_pct = len(late_night) / len(df_time) * 100
print(f"Late night (11 PM - 4 AM) crashes: {len(late_night)} ({late_night_pct:.1f}%)")

# Insight 3: Day vs Night comparison
daytime = df_time[(df_time['hour'] >= 6) & (df_time['hour'] < 20)]
nighttime = df_time[(df_time['hour'] >= 20) | (df_time['hour'] < 6)]
print(f"Daytime (6 AM - 8 PM): {len(daytime)} ({len(daytime)/len(df_time)*100:.1f}%)")
print(f"Nighttime (8 PM - 6 AM): {len(nighttime)} ({len(nighttime)/len(df_time)*100:.1f}%)")

# Insight 4: City-specific peak hours
print("\n[City-Specific Peak Hours]")
for city in df_time_with_date['Location'].dropna().unique():
    city_data = df_time_with_date[df_time_with_date['Location'] == city]
    if len(city_data) >= 10:
        peak_hour = city_data['hour'].mode()
        if len(peak_hour) > 0:
            print(f"  {city}: Peak at {int(peak_hour.iloc[0]):02d}:00 ({len(city_data)} total crashes)")

# Insight 5: Severity by time of day
severity_cols = ['Is Police-Reported', 'Is Any-Injury-Reported', 'Is Any Vehicle Airbag Deployment']
for col in severity_cols:
    if col in df_time.columns:
        df_time[col] = df_time[col].map({'True': True, 'False': False, True: True, False: False})

# Create severity score
df_time['severity_score'] = 0
if 'Is Police-Reported' in df_time.columns:
    df_time['severity_score'] += df_time['Is Police-Reported'].fillna(False).astype(int)
if 'Is Any-Injury-Reported' in df_time.columns:
    df_time['severity_score'] += df_time['Is Any-Injury-Reported'].fillna(False).astype(int) * 2
if 'Is Any Vehicle Airbag Deployment' in df_time.columns:
    df_time['severity_score'] += df_time['Is Any Vehicle Airbag Deployment'].fillna(False).astype(int) * 2

severity_by_period = df_time.groupby('time_period')['severity_score'].mean()
print("\n[Average Severity by Time Period]")
for period in time_period_order:
    if period in severity_by_period.index:
        print(f"  {period}: {severity_by_period[period]:.2f}")

# =============================================================================
# 7. CREATE SUMMARY VISUALIZATION
# =============================================================================

print("\n[7] Creating summary visualization...")

fig, axes = plt.subplots(2, 3, figsize=(18, 12))

# 1. Peak hours by day
ax1 = axes[0, 0]
peak_data = pd.DataFrame(peak_hours_by_day).T
ax1.bar(range(len(peak_data)), peak_data['hour'], color='steelblue', alpha=0.8, edgecolor='black')
ax1.set_xticks(range(len(peak_data)))
ax1.set_xticklabels(peak_data.index, rotation=45, ha='right')
ax1.set_ylabel('Peak Hour', fontsize=12)
ax1.set_title('Peak Crash Hour by Day', fontsize=14, fontweight='bold')
ax1.set_ylim(0, 24)
ax1.grid(axis='y', alpha=0.3)
for i, (day, info) in enumerate(peak_hours_by_day.items()):
    ax1.text(i, info['hour'] + 0.5, f"{info['hour']:02d}:00", ha='center', fontsize=9)

# 2. Rush hour concentration by city
ax2 = axes[0, 1]
rush_by_city = df_time_with_date.groupby('Location').apply(
    lambda x: len(x[(x['hour'] >= 7) & (x['hour'] <= 9) | (x['hour'] >= 17) & (x['hour'] <= 19)]) / len(x) * 100
    if len(x) > 0 else 0
).sort_values(ascending=False)
ax2.barh(range(len(rush_by_city)), rush_by_city.values, color='coral', alpha=0.8)
ax2.set_yticks(range(len(rush_by_city)))
ax2.set_yticklabels(rush_by_city.index)
ax2.set_xlabel('% of Crashes During Rush Hour', fontsize=12)
ax2.set_title('Rush Hour Crash Concentration by City', fontsize=14, fontweight='bold')
ax2.grid(axis='x', alpha=0.3)

# 3. Weekend night hotspots
ax3 = axes[0, 2]
weekend_night_by_loc = weekend_night['location_type'].value_counts().head(6)
ax3.pie(weekend_night_by_loc.values, labels=weekend_night_by_loc.index, autopct='%1.1f%%',
        colors=plt.cm.Set3(range(len(weekend_night_by_loc))))
ax3.set_title('Weekend Night Crashes\nby Location Type', fontsize=14, fontweight='bold')

# 4. Hourly pattern by crash type
ax4 = axes[1, 0]
top_crash_types = df_time['Crash Type'].value_counts().head(4).index
for ct in top_crash_types:
    ct_hourly = df_time[df_time['Crash Type'] == ct].groupby('hour').size()
    ax4.plot(range(24), [ct_hourly.get(h, 0) for h in range(24)], marker='o', label=ct, linewidth=2)
ax4.set_xlabel('Hour of Day', fontsize=12)
ax4.set_ylabel('Number of Crashes', fontsize=12)
ax4.set_title('Hourly Pattern by Crash Type', fontsize=14, fontweight='bold')
ax4.legend(fontsize=8, loc='upper right')
ax4.set_xticks(range(0, 24, 2))
ax4.grid(alpha=0.3)

# 5. Severity by time period
ax5 = axes[1, 1]
severity_period_ordered = severity_by_period.reindex([t for t in time_period_order if t in severity_by_period.index])
colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(severity_period_ordered)))
ax5.barh(range(len(severity_period_ordered)), severity_period_ordered.values, color=colors, alpha=0.8)
ax5.set_yticks(range(len(severity_period_ordered)))
ax5.set_yticklabels([t.split('(')[0].strip() for t in severity_period_ordered.index], fontsize=9)
ax5.set_xlabel('Average Severity Score', fontsize=12)
ax5.set_title('Severity by Time Period', fontsize=14, fontweight='bold')
ax5.axvline(df_time['severity_score'].mean(), color='red', linestyle='--', label='Overall Avg')
ax5.legend()
ax5.grid(axis='x', alpha=0.3)

# 6. Day/Night breakdown
ax6 = axes[1, 2]
day_night_data = [len(daytime), len(nighttime)]
day_night_labels = [f'Daytime\n(6 AM - 8 PM)\n{len(daytime)} crashes',
                    f'Nighttime\n(8 PM - 6 AM)\n{len(nighttime)} crashes']
colors = ['#ffd93d', '#2c3e50']
wedges, texts, autotexts = ax6.pie(day_night_data, labels=day_night_labels, autopct='%1.1f%%',
                                     colors=colors, explode=(0.02, 0.02), textprops={'fontsize': 10})
ax6.set_title('Day vs Night Crashes', fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'time_insights_summary.png'), dpi=300, bbox_inches='tight')
plt.close()
print(f"Saved: time_insights_summary.png")

# =============================================================================
# 8. EXPORT SUMMARY STATISTICS
# =============================================================================

print("\n[8] Exporting summary statistics...")

summary_stats = {
    'total_crashes_with_time': len(df_time),
    'total_crashes_with_time_and_date': len(df_time_with_date),
    'rush_hour_percentage': rush_hour_pct,
    'late_night_percentage': late_night_pct,
    'daytime_percentage': len(daytime)/len(df_time)*100,
    'nighttime_percentage': len(nighttime)/len(df_time)*100,
    'peak_hours_by_day': peak_hours_by_day,
    'most_common_time_period': df_time['time_period'].mode().iloc[0] if len(df_time['time_period'].mode()) > 0 else 'Unknown'
}

# Save summary
summary_path = os.path.join(OUTPUT_DIR, 'time_analysis_summary.json')
with open(summary_path, 'w') as f:
    json.dump(summary_stats, f, indent=2)
print(f"Saved: {summary_path}")

# =============================================================================
# FINAL SUMMARY
# =============================================================================

print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)

print(f"""
OUTPUT FILES:
  - {OUTPUT_DIR}/time_of_day_analysis.png
  - {OUTPUT_DIR}/location_time_analysis.png
  - {OUTPUT_DIR}/time_insights_summary.png
  - {OUTPUT_DIR}/time_analysis_summary.json
  - {WEBDEV_DIR}/crash_time_data.json

KEY FINDINGS:
  - Rush hour crashes (7-9 AM & 5-7 PM): {rush_hour_pct:.1f}%
  - Late night crashes (11 PM - 4 AM): {late_night_pct:.1f}%
  - Most common time period: {summary_stats['most_common_time_period']}
  - Mappable crashes for visualization: {len(df_geo_mapped)}

PEAK HOURS BY DAY:
""")
for day, info in peak_hours_by_day.items():
    print(f"  {day}: {info['hour']:02d}:00")

print("\n" + "="*70)
