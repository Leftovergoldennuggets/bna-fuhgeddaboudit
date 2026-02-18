"""
Extract SF incidents with ONLY moderate/serious/fatal injury severity
for the scrollytelling visualization.
"""

import pandas as pd
import json
import re

# Load the data
df = pd.read_csv('/Users/kateli/Desktop/Classes/COMM277T/bna-fuhgeddaboudit/cleaned-data/waymo_merged_nhtsa_hub_CLEAN.csv')

print(f"Total records: {len(df)}")

# Check injury severity values
print("\nAll Injury Severity values:")
print(df['Highest Injury Severity Alleged'].value_counts())

# Filter for ONLY moderate/serious/fatal injuries (NOT minor)
severity_col = 'Highest Injury Severity Alleged'

def is_serious_injury(val):
    if pd.isna(val):
        return False
    val_lower = str(val).lower().strip()

    # Only include: Moderate, Serious, Fatality
    # Exclude: Minor (with or without hospitalization), No injuries, Unknown, Property Damage
    if 'fatal' in val_lower:
        return True
    if 'serious' in val_lower:
        return True
    if 'moderate' in val_lower:
        return True

    return False

df['is_serious'] = df[severity_col].apply(is_serious_injury)
serious_df = df[df['is_serious']].copy()

print(f"\nIncidents with moderate/serious/fatal injuries: {len(serious_df)}")
print("\nSeverity breakdown:")
print(serious_df[severity_col].value_counts())

# Check city distribution
print("\nCity distribution:")
print(serious_df['Location'].value_counts())

# Prepare data for web visualization
incidents = []

# City centroids
city_coords = {
    'SAN_FRANCISCO': (37.7749, -122.4194),
    'PHOENIX': (33.4484, -112.0740),
    'LOS_ANGELES': (34.0522, -118.2437),
    'AUSTIN': (30.2672, -97.7431),
    'ATLANTA': (33.7490, -84.3880)
}

import random
random.seed(42)  # For reproducibility

for idx, row in serious_df.iterrows():
    # Get coordinates
    lat = row.get('Latitude')
    lon = row.get('Longitude')

    try:
        if pd.notna(lat) and '[' not in str(lat):
            lat = float(lat)
        else:
            lat = None
    except:
        lat = None

    try:
        if pd.notna(lon) and '[' not in str(lon):
            lon = float(lon)
        else:
            lon = None
    except:
        lon = None

    city = str(row.get('Location', '')).upper().replace(' ', '_')

    # Use city centroid with offset if no coords
    if lat is None or lon is None:
        if city in city_coords:
            base_lat, base_lon = city_coords[city]
            lat = base_lat + (random.random() - 0.5) * 0.04
            lon = base_lon + (random.random() - 0.5) * 0.04
        else:
            continue

    # Get narrative
    narrative = str(row.get('Narrative', ''))
    if pd.isna(row.get('Narrative')) or narrative == 'nan':
        narrative = "Narrative not available for this incident."
    else:
        narrative = re.sub(r'\[XXX\]', '[REDACTED]', narrative)
        narrative = re.sub(r'\[MAY CONTAIN.*?\]', '', narrative)
        narrative = narrative.strip()
        if len(narrative) > 600:
            narrative = narrative[:600] + "..."

    # Get date and time
    date = str(row.get('Incident Date', row.get('Incident Date_nhtsa', '')))
    if pd.isna(row.get('Incident Date')) and pd.isna(row.get('Incident Date_nhtsa')):
        date = "Date not available"

    time = str(row.get('Incident Time (24:00)', ''))
    if pd.isna(row.get('Incident Time (24:00)')):
        time = "Time not available"

    # Get crash party
    crash_with = str(row.get('Crash With', ''))
    if pd.isna(row.get('Crash With')) or crash_with == '' or crash_with == 'nan':
        crash_with = "Unknown"

    # Clean up crash party categories
    crash_party_map = {
        'Passenger Car': 'Vehicle (Passenger Car)',
        'SUV': 'Vehicle (SUV)',
        'Pickup Truck': 'Vehicle (Pickup Truck)',
        'Heavy Truck': 'Vehicle (Heavy Truck)',
        'Van': 'Vehicle (Van)',
        'Bus': 'Vehicle (Bus)',
        'Motorcycle': 'Motorcyclist',
        'Non-Motorist: Cyclist': 'Cyclist',
        'Non-Motorist: Pedestrian': 'Pedestrian',
        'Non-Motorist: Scooter - Skateboard': 'Scooter/Skateboard',
        'Non-Motorist: Other': 'Other Non-Motorist',
        'Animal': 'Animal',
        'Other Fixed Object': 'Fixed Object',
        'Pole / Tree': 'Pole/Tree',
        'First Responder Vehicle': 'First Responder Vehicle'
    }
    crash_party = crash_party_map.get(crash_with, crash_with)

    # Get severity
    severity = str(row.get(severity_col, ''))

    # Get crash type
    crash_type = str(row.get('Crash Type', ''))
    if pd.isna(row.get('Crash Type')):
        crash_type = "Unknown"

    # Get address
    address = str(row.get('Location Address / Description', row.get('Address', '')))
    if pd.isna(row.get('Location Address / Description')) and pd.isna(row.get('Address')):
        address = "Location details not available"

    incident = {
        'id': len(incidents) + 1,
        'lat': lat,
        'lon': lon,
        'city': city.replace('_', ' ').title(),
        'date': date,
        'time': time,
        'crash_party': crash_party,
        'severity': severity,
        'crash_type': crash_type,
        'address': address,
        'narrative': narrative
    }
    incidents.append(incident)

print(f"\nTotal incidents extracted: {len(incidents)}")

# Filter to SF only
sf_incidents = [i for i in incidents if 'san francisco' in i['city'].lower()]
print(f"SF incidents: {len(sf_incidents)}")

# Print SF incidents for verification
print("\nSF Incidents:")
for inc in sf_incidents:
    print(f"  #{inc['id']}: {inc['severity']} - {inc['crash_party']} at {inc['address'][:40]}...")

# City data with centroids
city_data = {}
for city_name in ['San Francisco', 'Phoenix', 'Los Angeles', 'Austin', 'Atlanta']:
    count = len([i for i in incidents if city_name.lower() in i['city'].lower()])
    if count > 0:
        city_data[city_name] = {
            'lat': city_coords.get(city_name.upper().replace(' ', '_'), (0,0))[0],
            'lon': city_coords.get(city_name.upper().replace(' ', '_'), (0,0))[1],
            'count': count
        }

print(f"\nCity data: {city_data}")

# Save to JSON
output = {
    'sf_incidents': sf_incidents,
    'all_incidents': incidents,
    'city_data': city_data
}

with open('/Users/kateli/Desktop/Classes/COMM277T/bna-fuhgeddaboudit/webdev/serious_incidents.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to serious_incidents.json")
