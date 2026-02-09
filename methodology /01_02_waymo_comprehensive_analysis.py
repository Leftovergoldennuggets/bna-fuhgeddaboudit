

"""
Waymo Crash Data - Comprehensive Exploratory Analysis
=====================================================

This script performs:
1. Interactive visualization with Folium/Leaflet
2. Temporal analysis (time trends, day of week)
3. Spatial analysis (geographic clustering, severity correlations)

Usage: python waymo_comprehensive_analysis.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
import os

warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# Paths - use absolute paths
BASE_DIR = '/Users/kateli/Desktop/Classes/COMM277T/bna-fuhgeddaboudit'
DATA_PATH = os.path.join(BASE_DIR, 'cleaned-data/waymo_crashes_location.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'figures')

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
# 1. LOAD AND PREPARE DATA
# =============================================================================

print("="*70)
print("WAYMO CRASH DATA - COMPREHENSIVE ANALYSIS")
print("="*70)

# Load data
df = pd.read_csv(DATA_PATH)

print(f"\nTotal crashes: {len(df)}")
print(f"Columns: {df.columns.tolist()}")

# Rename columns for easier handling
df.columns = df.columns.str.strip()
col_mapping = {
    'SGO Report ID': 'report_id',
    'SGO Report Version': 'report_version',
    'SGO Amendment': 'amendment',
    'Year Month': 'year_month',
    'Location': 'city',
    'Crash Type': 'crash_type',
    'Is NHTSA Reportable In-Transport': 'nhtsa_reportable',
    'Is NHTSA Reportable In-Transport Delta-V Less than 1 MPH': 'low_severity',
    'Is Police-Reported': 'police_reported',
    'Is Any-Injury-Reported': 'injury_reported',
    'Is Any Vehicle Airbag Deployment': 'airbag_any',
    'Is Ego Vehicle Airbag Deployment': 'airbag_ego',
    'Is Suspected Serious Injury+': 'serious_injury',
    'Incident Date': 'incident_date',
    'Location Address / Description': 'address',
    'Zip Code': 'zip_code'
}
df = df.rename(columns=col_mapping)

# Parse dates
df['incident_date'] = pd.to_datetime(df['incident_date'], format='%m/%d/%Y', errors='coerce')

# Extract temporal features
df['year'] = df['incident_date'].dt.year
df['month'] = df['incident_date'].dt.month
df['month_name'] = df['incident_date'].dt.month_name()
df['day'] = df['incident_date'].dt.day
df['day_of_week'] = df['incident_date'].dt.day_name()
df['day_of_week_num'] = df['incident_date'].dt.dayofweek  # 0=Monday
df['is_weekend'] = df['day_of_week_num'].isin([5, 6])
df['quarter'] = df['incident_date'].dt.quarter

# Extract year-month for trend analysis
df['year_month_dt'] = df['incident_date'].dt.to_period('M')

# Clean city names
df['city_clean'] = df['city'].str.replace('_', ' ').str.title()

# Convert boolean columns
bool_cols = ['nhtsa_reportable', 'low_severity', 'police_reported',
             'injury_reported', 'airbag_any', 'airbag_ego', 'serious_injury']
for col in bool_cols:
    df[col] = df[col].map({'True': True, 'False': False, True: True, False: False})

# Create severity score (higher = more severe)
df['severity_score'] = (
    df['police_reported'].astype(int) * 1 +
    df['injury_reported'].astype(int) * 2 +
    df['airbag_any'].astype(int) * 2 +
    df['serious_injury'].astype(int) * 3
)

print(f"\nDate range: {df['incident_date'].min().date()} to {df['incident_date'].max().date()}")
print(f"Cities: {df['city_clean'].unique().tolist()}")
print(f"Crash types: {df['crash_type'].nunique()} unique types")

# =============================================================================
# 2. GEOCODING FOR INTERACTIVE MAP
# =============================================================================

print("\n" + "="*70)
print("GEOCODING ADDRESSES")
print("="*70)

# City center coordinates as fallback
CITY_COORDS = {
    'San Francisco': (37.7749, -122.4194),
    'Los Angeles': (34.0522, -118.2437),
    'Phoenix': (33.4484, -112.0740),
    'Austin': (30.2672, -97.7431),
    'Atlanta': (33.7490, -84.3880)
}

# Zip code approximate coordinates (for major zip codes in each city)
# This provides better location approximation than just city center
ZIP_COORDS = {
    # San Francisco
    '94102': (37.7815, -122.4160), '94103': (37.7726, -122.4099),
    '94104': (37.7914, -122.4020), '94105': (37.7893, -122.3946),
    '94107': (37.7654, -122.3958), '94108': (37.7917, -122.4073),
    '94109': (37.7917, -122.4217), '94110': (37.7489, -122.4150),
    '94111': (37.7987, -122.4001), '94112': (37.7201, -122.4428),
    '94114': (37.7589, -122.4354), '94115': (37.7857, -122.4358),
    '94116': (37.7437, -122.4867), '94117': (37.7699, -122.4425),
    '94118': (37.7816, -122.4608), '94121': (37.7784, -122.4917),
    '94122': (37.7584, -122.4858), '94123': (37.8003, -122.4378),
    '94124': (37.7325, -122.3880), '94127': (37.7353, -122.4585),
    '94131': (37.7423, -122.4370), '94132': (37.7243, -122.4810),
    '94133': (37.8002, -122.4104), '94134': (37.7197, -122.4131),
    '94158': (37.7707, -122.3878), '94014': (37.6880, -122.4698),
    '94080': (37.6553, -122.4180),
    # Los Angeles
    '90001': (33.9425, -118.2551), '90002': (33.9493, -118.2475),
    '90003': (33.9644, -118.2731), '90004': (34.0770, -118.3090),
    '90005': (34.0597, -118.3096), '90006': (34.0465, -118.2925),
    '90007': (34.0286, -118.2819), '90008': (34.0108, -118.3415),
    '90010': (34.0607, -118.3154), '90011': (34.0069, -118.2596),
    '90012': (34.0627, -118.2404), '90013': (34.0450, -118.2438),
    '90014': (34.0427, -118.2543), '90015': (34.0395, -118.2687),
    '90016': (34.0278, -118.3523), '90017': (34.0538, -118.2660),
    '90018': (34.0283, -118.3199), '90019': (34.0467, -118.3417),
    '90020': (34.0663, -118.3101), '90024': (34.0653, -118.4318),
    '90025': (34.0396, -118.4485), '90026': (34.0786, -118.2634),
    '90027': (34.1089, -118.2882), '90028': (34.0990, -118.3269),
    '90029': (34.0896, -118.2948), '90034': (34.0283, -118.3975),
    '90035': (34.0535, -118.3829), '90036': (34.0706, -118.3493),
    '90038': (34.0894, -118.3284), '90039': (34.1148, -118.2621),
    '90041': (34.1356, -118.2083), '90042': (34.1132, -118.1902),
    '90045': (33.9563, -118.3974), '90046': (34.1129, -118.3688),
    '90048': (34.0754, -118.3715), '90049': (34.0728, -118.4762),
    '90057': (34.0621, -118.2746), '90064': (34.0339, -118.4283),
    '90066': (34.0011, -118.4303), '90068': (34.1293, -118.3297),
    '90069': (34.0900, -118.3800), '90071': (34.0519, -118.2555),
    '90089': (34.0224, -118.2851), '90095': (34.0689, -118.4452),
    '90210': (34.0901, -118.4065), '90212': (34.0640, -118.4000),
    '90230': (33.9977, -118.3929), '90232': (34.0188, -118.3929),
    '90272': (34.0505, -118.5268), '90291': (33.9927, -118.4728),
    '90292': (33.9725, -118.4519), '90301': (33.9506, -118.3538),
    '90302': (33.9658, -118.3478), '90401': (34.0175, -118.4950),
    '90402': (34.0313, -118.5059), '90403': (34.0283, -118.4932),
    '90404': (34.0273, -118.4778), '90405': (34.0087, -118.4759),
    # Phoenix
    '85003': (33.4504, -112.0793), '85004': (33.4482, -112.0680),
    '85006': (33.4612, -112.0421), '85007': (33.4407, -112.0931),
    '85008': (33.4692, -111.9984), '85009': (33.4415, -112.1277),
    '85012': (33.5050, -112.0730), '85013': (33.5098, -112.0897),
    '85014': (33.5067, -112.0560), '85015': (33.5100, -112.1050),
    '85016': (33.5110, -112.0290), '85017': (33.5087, -112.1299),
    '85018': (33.5080, -111.9900), '85019': (33.5140, -112.1550),
    '85020': (33.5650, -112.0502), '85021': (33.5638, -112.0943),
    '85022': (33.6258, -112.0500), '85023': (33.6310, -112.1080),
    '85024': (33.6649, -112.0180), '85027': (33.6900, -112.1050),
    '85028': (33.5820, -111.9800), '85029': (33.6010, -112.1097),
    '85032': (33.6150, -111.9850), '85033': (33.4970, -112.1650),
    '85034': (33.4328, -112.0274), '85035': (33.4700, -112.1600),
    '85040': (33.3970, -112.0270), '85041': (33.3900, -112.0980),
    '85042': (33.3670, -112.0350), '85043': (33.4350, -112.1970),
    '85044': (33.3200, -111.9900), '85045': (33.3050, -112.0600),
    '85048': (33.3130, -111.9450), '85050': (33.6760, -111.9500),
    '85051': (33.5600, -112.1350), '85053': (33.6300, -112.1350),
    '85054': (33.6820, -111.9180), '85085': (33.7200, -112.0850),
    '85086': (33.7700, -112.1100), '85201': (33.4170, -111.8440),
    '85202': (33.3930, -111.8740), '85203': (33.4250, -111.8100),
    '85204': (33.4010, -111.7900), '85205': (33.4350, -111.7370),
    '85206': (33.4010, -111.7230), '85207': (33.4430, -111.6860),
    '85208': (33.3970, -111.6700), '85210': (33.3780, -111.8430),
    '85212': (33.3840, -111.6370), '85213': (33.4360, -111.8050),
    '85215': (33.4620, -111.7000), '85224': (33.3080, -111.8750),
    '85225': (33.3120, -111.8210), '85226': (33.3100, -111.9350),
    '85233': (33.3310, -111.8340), '85234': (33.3430, -111.7800),
    '85248': (33.2540, -111.8350), '85249': (33.2400, -111.7650),
    '85250': (33.5280, -111.9050), '85251': (33.4930, -111.9260),
    '85254': (33.6120, -111.9230), '85255': (33.6700, -111.8600),
    '85256': (33.5330, -111.8650), '85257': (33.4750, -111.8980),
    '85258': (33.5540, -111.8900), '85259': (33.5950, -111.8200),
    '85260': (33.6150, -111.8800), '85266': (33.7200, -111.8500),
    '85268': (33.5540, -111.7280), '85281': (33.4230, -111.9390),
    '85282': (33.3920, -111.9400), '85283': (33.3700, -111.9620),
    '85284': (33.3540, -111.9620), '85286': (33.3700, -111.9100),
    # Austin
    '78701': (30.2703, -97.7419), '78702': (30.2632, -97.7201),
    '78703': (30.2950, -97.7650), '78704': (30.2440, -97.7610),
    '78705': (30.2888, -97.7365), '78712': (30.2849, -97.7341),
    '78721': (30.2695, -97.6865), '78722': (30.2930, -97.7140),
    '78723': (30.3050, -97.6900), '78724': (30.2920, -97.6340),
    '78725': (30.2350, -97.6120), '78726': (30.4330, -97.8350),
    '78727': (30.4270, -97.7200), '78728': (30.4500, -97.6900),
    '78729': (30.4550, -97.7600), '78730': (30.3700, -97.8350),
    '78731': (30.3480, -97.7660), '78732': (30.3770, -97.8850),
    '78733': (30.3250, -97.8650), '78734': (30.3800, -97.9500),
    '78735': (30.2700, -97.8700), '78736': (30.2300, -97.9450),
    '78737': (30.1600, -97.9450), '78738': (30.3200, -97.9350),
    '78739': (30.1700, -97.8650), '78741': (30.2320, -97.7200),
    '78742': (30.2400, -97.6700), '78744': (30.1700, -97.7300),
    '78745': (30.2040, -97.8020), '78746': (30.2870, -97.8000),
    '78747': (30.1200, -97.7700), '78748': (30.1650, -97.8300),
    '78749': (30.2170, -97.8650), '78750': (30.4100, -97.8000),
    '78751': (30.3120, -97.7250), '78752': (30.3200, -97.6990),
    '78753': (30.3700, -97.6800), '78754': (30.3550, -97.6450),
    '78756': (30.3200, -97.7420), '78757': (30.3550, -97.7350),
    '78758': (30.3900, -97.7100), '78759': (30.4050, -97.7650),
    # Atlanta
    '30303': (33.7532, -84.3897), '30305': (33.8330, -84.3780),
    '30306': (33.7860, -84.3500), '30307': (33.7630, -84.3390),
    '30308': (33.7750, -84.3710), '30309': (33.7980, -84.3870),
    '30310': (33.7370, -84.4200), '30311': (33.7270, -84.4700),
    '30312': (33.7470, -84.3700), '30313': (33.7600, -84.4040),
    '30314': (33.7600, -84.4300), '30315': (33.7130, -84.3900),
    '30316': (33.7280, -84.3300), '30317': (33.7540, -84.3210),
    '30318': (33.7920, -84.4370), '30319': (33.8700, -84.3380),
    '30324': (33.8150, -84.3570), '30326': (33.8470, -84.3620),
    '30327': (33.8600, -84.4200), '30329': (33.8250, -84.3250),
    '30331': (33.7050, -84.5250), '30332': (33.7770, -84.3980),
    '30334': (33.7490, -84.3880), '30336': (33.7130, -84.5180),
    '30337': (33.6330, -84.4480), '30339': (33.8600, -84.4680),
    '30340': (33.8980, -84.2650), '30341': (33.8800, -84.2950),
    '30342': (33.8770, -84.3770), '30344': (33.6900, -84.4750),
    '30345': (33.8480, -84.2850)
}

def get_coordinates(row):
    """Get approximate coordinates for a crash based on zip code or city."""
    zip_code = str(row['zip_code']).strip() if pd.notna(row['zip_code']) else None
    city = row['city_clean']

    # Try zip code first
    if zip_code and zip_code in ZIP_COORDS:
        # Add small random offset for visualization
        lat, lon = ZIP_COORDS[zip_code]
        lat += np.random.uniform(-0.005, 0.005)
        lon += np.random.uniform(-0.005, 0.005)
        return lat, lon

    # Fall back to city center with larger offset
    if city in CITY_COORDS:
        lat, lon = CITY_COORDS[city]
        lat += np.random.uniform(-0.02, 0.02)
        lon += np.random.uniform(-0.02, 0.02)
        return lat, lon

    return None, None

# Apply geocoding
coords = df.apply(get_coordinates, axis=1)
df['latitude'] = coords.apply(lambda x: x[0])
df['longitude'] = coords.apply(lambda x: x[1])

geocoded_count = df['latitude'].notna().sum()
print(f"Geocoded {geocoded_count} of {len(df)} crashes ({geocoded_count/len(df)*100:.1f}%)")

# =============================================================================
# 3. INTERACTIVE MAP WITH FOLIUM
# =============================================================================

print("\n" + "="*70)
print("CREATING INTERACTIVE MAP")
print("="*70)

try:
    import folium
    from folium.plugins import MarkerCluster, HeatMap

    # Create base map centered on US
    center_lat = df['latitude'].mean()
    center_lon = df['longitude'].mean()

    # Create map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles='OpenStreetMap')

    # Color mapping for crash types
    crash_type_colors = {
        'V2V F2R': 'blue',           # Front to rear
        'V2V Lateral': 'green',       # Side collision
        'V2V Head-on': 'red',         # Head-on
        'V2V Backing': 'orange',      # Backing
        'V2V Intersection': 'purple', # Intersection
        'Single Vehicle': 'gray',
        'Pedestrian': 'darkred',
        'Cyclist': 'darkgreen',
        'Motorcycle': 'darkblue',
        'All Others': 'black',
        'Secondary Crash': 'pink'
    }

    # Create marker cluster
    marker_cluster = MarkerCluster(name='All Crashes').add_to(m)

    # Add markers for each crash
    df_with_coords = df[df['latitude'].notna()].copy()

    for _, row in df_with_coords.iterrows():
        # Determine color based on crash type
        crash_type = row['crash_type']
        color = crash_type_colors.get(crash_type, 'gray')

        # Create popup content
        popup_html = f"""
        <div style="width:250px">
            <h4 style="margin:0;color:#333;">Crash Report</h4>
            <hr style="margin:5px 0;">
            <b>Date:</b> {row['incident_date'].strftime('%Y-%m-%d') if pd.notna(row['incident_date']) else 'N/A'}<br>
            <b>City:</b> {row['city_clean']}<br>
            <b>Address:</b> {row['address']}<br>
            <b>Crash Type:</b> {row['crash_type']}<br>
            <b>Zip Code:</b> {row['zip_code']}<br>
            <hr style="margin:5px 0;">
            <b>Severity Indicators:</b><br>
            • Police Reported: {'Yes' if row['police_reported'] else 'No'}<br>
            • Injury Reported: {'Yes' if row['injury_reported'] else 'No'}<br>
            • Airbag Deployed: {'Yes' if row['airbag_any'] else 'No'}<br>
            • Serious Injury: {'Yes' if row['serious_injury'] else 'No'}<br>
            <b>Severity Score:</b> {row['severity_score']}/8
        </div>
        """

        # Add marker
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=6 + row['severity_score'] * 2,  # Size based on severity
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.6,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row['crash_type']} - {row['incident_date'].strftime('%Y-%m-%d') if pd.notna(row['incident_date']) else 'N/A'}"
        ).add_to(marker_cluster)

    # Add heatmap layer
    heat_data = df_with_coords[['latitude', 'longitude']].values.tolist()
    HeatMap(heat_data, name='Crash Density Heatmap', radius=15).add_to(m)

    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-size: 12px;">
        <h4 style="margin:0 0 8px 0;">Crash Types</h4>
        <i style="background:blue;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> V2V F2R (Front-to-Rear)<br>
        <i style="background:green;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> V2V Lateral (Side)<br>
        <i style="background:red;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> V2V Head-on<br>
        <i style="background:orange;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> V2V Backing<br>
        <i style="background:purple;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> V2V Intersection<br>
        <i style="background:darkred;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> Pedestrian<br>
        <i style="background:darkgreen;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> Cyclist<br>
        <i style="background:gray;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> Single Vehicle/Other<br>
        <hr>
        <small>Circle size = severity</small>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Add layer control
    folium.LayerControl().add_to(m)

    # Save map
    map_path = os.path.join(OUTPUT_DIR, 'waymo_crashes_interactive_map.html')
    m.save(map_path)
    print(f"Interactive map saved to: {map_path}")

    # Create city-specific maps
    for city in df['city_clean'].unique():
        city_df = df_with_coords[df_with_coords['city_clean'] == city]
        if len(city_df) > 0:
            city_center = (city_df['latitude'].mean(), city_df['longitude'].mean())

            city_map = folium.Map(location=city_center, zoom_start=12, tiles='OpenStreetMap')
            city_cluster = MarkerCluster(name=f'{city} Crashes').add_to(city_map)

            for _, row in city_df.iterrows():
                crash_type = row['crash_type']
                color = crash_type_colors.get(crash_type, 'gray')

                popup_html = f"""
                <b>Date:</b> {row['incident_date'].strftime('%Y-%m-%d') if pd.notna(row['incident_date']) else 'N/A'}<br>
                <b>Address:</b> {row['address']}<br>
                <b>Type:</b> {row['crash_type']}<br>
                <b>Severity:</b> {row['severity_score']}/8
                """

                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=6 + row['severity_score'] * 2,
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.6,
                    popup=folium.Popup(popup_html, max_width=250)
                ).add_to(city_cluster)

            # Add heatmap
            city_heat = city_df[['latitude', 'longitude']].values.tolist()
            HeatMap(city_heat, name='Density', radius=15).add_to(city_map)
            folium.LayerControl().add_to(city_map)

            city_map_path = os.path.join(OUTPUT_DIR, f'waymo_crashes_{city.lower().replace(" ", "_")}_map.html')
            city_map.save(city_map_path)
            print(f"  {city} map saved: {city_map_path}")

except ImportError:
    print("Folium not installed. Install with: pip install folium")
    print("Skipping interactive map creation.")

# =============================================================================
# 4. TEMPORAL ANALYSIS
# =============================================================================

print("\n" + "="*70)
print("TEMPORAL ANALYSIS")
print("="*70)

fig, axes = plt.subplots(2, 3, figsize=(18, 12))

# 1. Crashes over time (monthly trend)
monthly_counts = df.groupby('year_month_dt').size()
ax1 = axes[0, 0]
monthly_counts.plot(ax=ax1, marker='o', linewidth=2, markersize=4, color='steelblue')
ax1.set_xlabel('Month', fontsize=11)
ax1.set_ylabel('Number of Crashes', fontsize=11)
ax1.set_title('Monthly Crash Trend', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.tick_params(axis='x', rotation=45)

# 2. Day of week distribution
day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
day_counts = df['day_of_week'].value_counts().reindex(day_order)
ax2 = axes[0, 1]
colors_dow = ['steelblue']*5 + ['coral']*2
bars = ax2.bar(range(len(day_counts)), day_counts.values, color=colors_dow, alpha=0.8, edgecolor='black')
ax2.set_xticks(range(len(day_counts)))
ax2.set_xticklabels([d[:3] for d in day_counts.index], fontsize=10)
ax2.set_ylabel('Number of Crashes', fontsize=11)
ax2.set_title('Crashes by Day of Week', fontsize=13, fontweight='bold')
ax2.grid(axis='y', alpha=0.3)
for i, v in enumerate(day_counts.values):
    ax2.text(i, v + 2, str(v), ha='center', fontsize=9)

# 3. Monthly distribution
month_order = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']
month_counts = df['month_name'].value_counts().reindex(month_order).dropna()
ax3 = axes[0, 2]
ax3.plot(range(len(month_counts)), month_counts.values, marker='o', linewidth=2,
         color='teal', markersize=8)
ax3.fill_between(range(len(month_counts)), month_counts.values, alpha=0.3, color='teal')
ax3.set_xticks(range(len(month_counts)))
ax3.set_xticklabels([m[:3] for m in month_counts.index], fontsize=9)
ax3.set_ylabel('Number of Crashes', fontsize=11)
ax3.set_title('Crashes by Month', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)

# 4. Year-over-year comparison
yearly = df.groupby(['year', 'month']).size().reset_index(name='count')
ax4 = axes[1, 0]
for year in yearly['year'].unique():
    year_data = yearly[yearly['year'] == year]
    ax4.plot(year_data['month'], year_data['count'], marker='o', label=str(year), linewidth=2)
ax4.set_xlabel('Month', fontsize=11)
ax4.set_ylabel('Number of Crashes', fontsize=11)
ax4.set_title('Year-over-Year Comparison', fontsize=13, fontweight='bold')
ax4.legend(title='Year')
ax4.grid(True, alpha=0.3)
ax4.set_xticks(range(1, 13))

# 5. Quarterly distribution
quarterly = df.groupby(['year', 'quarter']).size().reset_index(name='count')
quarterly['period'] = quarterly['year'].astype(str) + ' Q' + quarterly['quarter'].astype(str)
ax5 = axes[1, 1]
ax5.bar(range(len(quarterly)), quarterly['count'].values, color='darkgreen', alpha=0.7, edgecolor='black')
ax5.set_xticks(range(len(quarterly)))
ax5.set_xticklabels(quarterly['period'], rotation=45, ha='right', fontsize=8)
ax5.set_ylabel('Number of Crashes', fontsize=11)
ax5.set_title('Quarterly Crash Counts', fontsize=13, fontweight='bold')
ax5.grid(axis='y', alpha=0.3)

# 6. Weekend vs Weekday
ax6 = axes[1, 2]
weekend_counts = df['is_weekend'].value_counts()
labels = ['Weekday', 'Weekend']
values = [weekend_counts.get(False, 0), weekend_counts.get(True, 0)]
colors_pie = ['steelblue', 'coral']
wedges, texts, autotexts = ax6.pie(values, labels=labels, autopct='%1.1f%%',
                                     colors=colors_pie, explode=(0.03, 0.03),
                                     textprops={'fontsize': 11})
ax6.set_title('Weekday vs Weekend', fontsize=13, fontweight='bold')

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'temporal_analysis.png'), dpi=300, bbox_inches='tight')
plt.close()  # Close figure instead of showing

# Print temporal summary
print("\n--- TEMPORAL SUMMARY ---")
print(f"Total crashes: {len(df)}")
print(f"Date range: {df['incident_date'].min().date()} to {df['incident_date'].max().date()}")
print(f"\nBusiest day: {day_counts.idxmax()} ({day_counts.max()} crashes)")
print(f"Quietest day: {day_counts.idxmin()} ({day_counts.min()} crashes)")
print(f"\nBusiest month: {month_counts.idxmax()} ({int(month_counts.max())} crashes)")
print(f"Quietest month: {month_counts.idxmin()} ({int(month_counts.min())} crashes)")
print(f"\nWeekday crashes: {values[0]} ({values[0]/sum(values)*100:.1f}%)")
print(f"Weekend crashes: {values[1]} ({values[1]/sum(values)*100:.1f}%)")

# =============================================================================
# 5. SPATIAL ANALYSIS
# =============================================================================

print("\n" + "="*70)
print("SPATIAL ANALYSIS")
print("="*70)

fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# 1. Crashes by city
city_counts = df['city_clean'].value_counts()
ax1 = axes[0, 0]
colors_city = plt.cm.Set2(range(len(city_counts)))
bars = ax1.barh(range(len(city_counts)), city_counts.values, color=colors_city, alpha=0.8)
ax1.set_yticks(range(len(city_counts)))
ax1.set_yticklabels(city_counts.index, fontsize=11)
ax1.set_xlabel('Number of Crashes', fontsize=11)
ax1.set_title('Crashes by City', fontsize=13, fontweight='bold')
ax1.grid(axis='x', alpha=0.3)
for i, v in enumerate(city_counts.values):
    ax1.text(v + 5, i, f'{v} ({v/len(df)*100:.1f}%)', va='center', fontsize=10)

# 2. Crash type distribution
crash_type_counts = df['crash_type'].value_counts()
ax2 = axes[0, 1]
ax2.barh(range(len(crash_type_counts)), crash_type_counts.values,
         color='teal', alpha=0.7, edgecolor='black')
ax2.set_yticks(range(len(crash_type_counts)))
ax2.set_yticklabels(crash_type_counts.index, fontsize=9)
ax2.set_xlabel('Number of Crashes', fontsize=11)
ax2.set_title('Crashes by Type', fontsize=13, fontweight='bold')
ax2.grid(axis='x', alpha=0.3)

# 3. Crash type by city heatmap
crash_city = pd.crosstab(df['crash_type'], df['city_clean'])
ax3 = axes[1, 0]
sns.heatmap(crash_city, annot=True, fmt='d', cmap='YlOrRd', ax=ax3,
            cbar_kws={'label': 'Count'})
ax3.set_title('Crash Type × City', fontsize=13, fontweight='bold')
ax3.set_xlabel('City', fontsize=11)
ax3.set_ylabel('Crash Type', fontsize=11)
plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

# 4. City distribution pie chart
ax4 = axes[1, 1]
colors_pie = plt.cm.Set3(range(len(city_counts)))
wedges, texts, autotexts = ax4.pie(city_counts.values, labels=city_counts.index,
                                     autopct='%1.1f%%', colors=colors_pie,
                                     textprops={'fontsize': 10})
ax4.set_title('Geographic Distribution', fontsize=13, fontweight='bold')

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'spatial_analysis.png'), dpi=300, bbox_inches='tight')
plt.close()  # Close figure instead of showing

# Print spatial summary
print("\n--- SPATIAL SUMMARY ---")
print(f"\nCrashes by city:")
for city, count in city_counts.items():
    print(f"  {city}: {count} ({count/len(df)*100:.1f}%)")

print(f"\nTop 5 crash types:")
for crash_type, count in crash_type_counts.head(5).items():
    print(f"  {crash_type}: {count} ({count/len(df)*100:.1f}%)")

# =============================================================================
# 6. SEVERITY ANALYSIS
# =============================================================================

print("\n" + "="*70)
print("SEVERITY ANALYSIS")
print("="*70)

fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# 1. Severity indicators breakdown
severity_cols = ['police_reported', 'injury_reported', 'airbag_any', 'serious_injury']
severity_counts = df[severity_cols].sum()
ax1 = axes[0, 0]
colors_sev = ['#ff6b6b', '#feca57', '#48dbfb', '#ff9ff3']
bars = ax1.bar(range(len(severity_counts)), severity_counts.values, color=colors_sev,
               alpha=0.8, edgecolor='black')
ax1.set_xticks(range(len(severity_counts)))
ax1.set_xticklabels(['Police Reported', 'Injury Reported', 'Airbag Deployed', 'Serious Injury'],
                    rotation=30, ha='right', fontsize=10)
ax1.set_ylabel('Number of Crashes', fontsize=11)
ax1.set_title('Severity Indicator Breakdown', fontsize=13, fontweight='bold')
ax1.grid(axis='y', alpha=0.3)
for i, v in enumerate(severity_counts.values):
    ax1.text(i, v + 5, f'{v}\n({v/len(df)*100:.1f}%)', ha='center', fontsize=9)

# 2. Severity score distribution
ax2 = axes[0, 1]
severity_dist = df['severity_score'].value_counts().sort_index()
ax2.bar(severity_dist.index, severity_dist.values, color='darkred', alpha=0.7, edgecolor='black')
ax2.set_xlabel('Severity Score', fontsize=11)
ax2.set_ylabel('Number of Crashes', fontsize=11)
ax2.set_title('Severity Score Distribution (0-8 scale)', fontsize=13, fontweight='bold')
ax2.grid(axis='y', alpha=0.3)

# 3. Severity by city
city_severity = df.groupby('city_clean')['severity_score'].mean().sort_values(ascending=False)
ax3 = axes[1, 0]
colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(city_severity)))
ax3.barh(range(len(city_severity)), city_severity.values, color=colors, alpha=0.8)
ax3.set_yticks(range(len(city_severity)))
ax3.set_yticklabels(city_severity.index, fontsize=11)
ax3.set_xlabel('Average Severity Score', fontsize=11)
ax3.set_title('Average Severity by City', fontsize=13, fontweight='bold')
ax3.grid(axis='x', alpha=0.3)
for i, v in enumerate(city_severity.values):
    ax3.text(v + 0.02, i, f'{v:.2f}', va='center', fontsize=10)

# 4. Severity by crash type
type_severity = df.groupby('crash_type')['severity_score'].mean().sort_values(ascending=False)
ax4 = axes[1, 1]
colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(type_severity)))
ax4.barh(range(len(type_severity)), type_severity.values, color=colors, alpha=0.8)
ax4.set_yticks(range(len(type_severity)))
ax4.set_yticklabels(type_severity.index, fontsize=9)
ax4.set_xlabel('Average Severity Score', fontsize=11)
ax4.set_title('Average Severity by Crash Type', fontsize=13, fontweight='bold')
ax4.grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'severity_analysis.png'), dpi=300, bbox_inches='tight')
plt.close()  # Close figure instead of showing

# Print severity summary
print("\n--- SEVERITY SUMMARY ---")
print(f"\nSeverity indicators:")
for col, count in severity_counts.items():
    print(f"  {col}: {count} ({count/len(df)*100:.1f}%)")
print(f"\nAverage severity score: {df['severity_score'].mean():.2f}")
print(f"Highest average severity city: {city_severity.index[0]} ({city_severity.values[0]:.2f})")
print(f"Highest average severity type: {type_severity.index[0]} ({type_severity.values[0]:.2f})")

# =============================================================================
# 7. CORRELATION ANALYSIS: TIME × LOCATION × SEVERITY
# =============================================================================

print("\n" + "="*70)
print("CORRELATION ANALYSIS")
print("="*70)

fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# 1. Day of week × City heatmap
dow_city = pd.crosstab(df['day_of_week'], df['city_clean'])
dow_city = dow_city.reindex(day_order)
ax1 = axes[0, 0]
sns.heatmap(dow_city, annot=True, fmt='d', cmap='Blues', ax=ax1)
ax1.set_title('Day of Week × City', fontsize=13, fontweight='bold')
ax1.set_xlabel('City', fontsize=11)
ax1.set_ylabel('Day of Week', fontsize=11)

# 2. Month × City heatmap
month_city = pd.crosstab(df['month_name'], df['city_clean'])
month_city = month_city.reindex([m for m in month_order if m in month_city.index])
ax2 = axes[0, 1]
sns.heatmap(month_city, annot=True, fmt='d', cmap='Greens', ax=ax2)
ax2.set_title('Month × City', fontsize=13, fontweight='bold')
ax2.set_xlabel('City', fontsize=11)
ax2.set_ylabel('Month', fontsize=11)

# 3. Severity by day of week
dow_severity = df.groupby('day_of_week')['severity_score'].mean().reindex(day_order)
ax3 = axes[1, 0]
colors_dow = ['steelblue']*5 + ['coral']*2
ax3.bar(range(len(dow_severity)), dow_severity.values, color=colors_dow, alpha=0.8, edgecolor='black')
ax3.set_xticks(range(len(dow_severity)))
ax3.set_xticklabels([d[:3] for d in dow_severity.index], fontsize=10)
ax3.set_ylabel('Average Severity Score', fontsize=11)
ax3.set_title('Average Severity by Day of Week', fontsize=13, fontweight='bold')
ax3.grid(axis='y', alpha=0.3)
ax3.axhline(df['severity_score'].mean(), color='red', linestyle='--', label='Overall Average')
ax3.legend()

# 4. Severity by month
month_severity = df.groupby('month_name')['severity_score'].mean()
month_severity = month_severity.reindex([m for m in month_order if m in month_severity.index])
ax4 = axes[1, 1]
ax4.plot(range(len(month_severity)), month_severity.values, marker='o', linewidth=2,
         color='darkred', markersize=8)
ax4.fill_between(range(len(month_severity)), month_severity.values, alpha=0.3, color='darkred')
ax4.set_xticks(range(len(month_severity)))
ax4.set_xticklabels([m[:3] for m in month_severity.index], fontsize=9)
ax4.set_ylabel('Average Severity Score', fontsize=11)
ax4.set_title('Average Severity by Month', fontsize=13, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.axhline(df['severity_score'].mean(), color='blue', linestyle='--', label='Overall Average')
ax4.legend()

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'correlation_analysis.png'), dpi=300, bbox_inches='tight')
plt.close()  # Close figure instead of showing

# =============================================================================
# 8. GEOGRAPHIC CLUSTERING ANALYSIS
# =============================================================================

print("\n" + "="*70)
print("GEOGRAPHIC CLUSTERING")
print("="*70)

# Top zip codes by crash count
zip_counts = df['zip_code'].value_counts().head(20)
print("\nTop 20 Zip Codes by Crash Count:")
for i, (zip_code, count) in enumerate(zip_counts.items(), 1):
    # Get city for this zip
    city = df[df['zip_code'] == zip_code]['city_clean'].mode()[0] if len(df[df['zip_code'] == zip_code]) > 0 else 'Unknown'
    print(f"  {i}. {zip_code} ({city}): {count} crashes ({count/len(df)*100:.1f}%)")

# Plot top zip codes
fig, ax = plt.subplots(figsize=(14, 8))
colors = plt.cm.tab20(range(len(zip_counts)))
ax.barh(range(len(zip_counts)), zip_counts.values, color=colors, alpha=0.8, edgecolor='black')
ax.set_yticks(range(len(zip_counts)))
labels = [f"{zip_code} ({df[df['zip_code']==zip_code]['city_clean'].mode()[0][:6] if len(df[df['zip_code']==zip_code]) > 0 else '?'})"
          for zip_code in zip_counts.index]
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel('Number of Crashes', fontsize=11)
ax.set_title('Top 20 Zip Codes by Crash Frequency (Crash Hotspots)', fontsize=14, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
ax.invert_yaxis()

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, 'geographic_clustering.png'), dpi=300, bbox_inches='tight')
plt.close()  # Close figure instead of showing

# =============================================================================
# 9. COMPREHENSIVE SUMMARY STATISTICS
# =============================================================================

print("\n" + "="*70)
print("COMPREHENSIVE SUMMARY")
print("="*70)

summary_stats = {
    'Total Crashes': len(df),
    'Date Range': f"{df['incident_date'].min().date()} to {df['incident_date'].max().date()}",
    'Cities': len(df['city_clean'].unique()),
    'Crash Types': df['crash_type'].nunique(),
    'Unique Zip Codes': df['zip_code'].nunique(),
    'Police Reported Rate': f"{df['police_reported'].sum()/len(df)*100:.1f}%",
    'Injury Reported Rate': f"{df['injury_reported'].sum()/len(df)*100:.1f}%",
    'Airbag Deployment Rate': f"{df['airbag_any'].sum()/len(df)*100:.1f}%",
    'Serious Injury Rate': f"{df['serious_injury'].sum()/len(df)*100:.1f}%",
    'Avg Severity Score': f"{df['severity_score'].mean():.2f}/8"
}

print("\n" + "-"*50)
for key, value in summary_stats.items():
    print(f"{key}: {value}")
print("-"*50)

# Save summary to CSV
df.to_csv(os.path.join(OUTPUT_DIR, 'waymo_crashes_processed.csv'), index=False)
print(f"\nProcessed data saved to: {OUTPUT_DIR}/waymo_crashes_processed.csv")

print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)
print(f"\nOutput files saved to: {OUTPUT_DIR}/")
print("  - waymo_crashes_interactive_map.html (All cities)")
print("  - waymo_crashes_[city]_map.html (City-specific maps)")
print("  - temporal_analysis.png")
print("  - spatial_analysis.png")
print("  - severity_analysis.png")
print("  - correlation_analysis.png")
print("  - geographic_clustering.png")
print("  - waymo_crashes_processed.csv")
