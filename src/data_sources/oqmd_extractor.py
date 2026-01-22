"""
OQMD Data Extractor

Fetches materials from OQMD API, filters and cleans data, exports to CSV.

Usage:
    python src/data_sources/oqmd_extractor.py --limit 10000
"""

import argparse
import csv
import os
import time
import requests
from typing import List, Dict, Optional
from collections import OrderedDict


def fetch_batch(limit: int = 100, offset: int = 0) -> Optional[List[Dict]]:
    """
    Fetch a batch of materials from OQMD API.
    
    Args:
        limit: Number of materials to fetch per batch
        offset: Starting offset for pagination
        
    Returns:
        List of material dictionaries or None if error
    """
    url = f"http://oqmd.org/oqmdapi/formationenergy?limit={limit}&offset={offset}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try common keys
            if 'results' in data:
                return data['results']
            elif 'data' in data:
                return data['data']
            elif 'entries' in data:
                return data['entries']
            else:
                # If dict has list-like structure, try to extract
                return [data] if data else []
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching batch (offset={offset}): {e}")
        return None


def extract_composition(entry: Dict) -> Optional[str]:
    """Extract composition from OQMD entry."""
    # Try different possible field names
    for field in ['composition', 'name', 'formula', 'entry_id']:
        if field in entry and entry[field]:
            return str(entry[field])
    
    # Try to construct from elements if available
    if 'elements' in entry and 'counts' in entry:
        elements = entry['elements']
        counts = entry['counts']
        if elements and counts:
            return ''.join(f"{elem}{int(count) if count != 1 else ''}" 
                          for elem, count in zip(elements, counts))
    
    return None


def extract_field(entry: Dict, field_names: List[str]) -> Optional[float]:
    """Extract numeric field from entry, trying multiple field names."""
    for field in field_names:
        value = entry.get(field)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                continue
    return None


def clean_and_filter_entries(entries: List[Dict]) -> List[Dict]:
    """
    Clean and filter entries according to requirements.
    
    Filters:
    - Keep only entries with delta_e present
    - Keep only entries with formation_energy_per_atom present
    - Remove duplicates by composition
    """
    cleaned = []
    seen_compositions = set()
    
    for entry in entries:
        composition = extract_composition(entry)
        if not composition:
            continue
        
        # Extract required fields
        delta_e = extract_field(entry, ['delta_e', 'energy_above_hull', 'stability'])
        formation_energy = extract_field(entry, ['formation_energy_per_atom', 'formation_energy', 'delta_e'])
        band_gap = extract_field(entry, ['band_gap', 'bandgap', 'gap'])
        
        # Filter: must have delta_e and formation_energy
        if delta_e is None or formation_energy is None:
            continue
        
        # Remove duplicates by composition
        if composition in seen_compositions:
            continue
        seen_compositions.add(composition)
        
        cleaned.append({
            'composition': composition,
            'formation_energy': formation_energy,
            'band_gap': band_gap,  # Can be None
            'delta_e': delta_e
        })
    
    return cleaned


def export_to_csv(entries: List[Dict], output_path: str):
    """Export cleaned entries to CSV."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['composition', 'formation_energy', 'band_gap', 'delta_e']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for entry in entries:
            writer.writerow(entry)
    
    print(f"Exported {len(entries)} entries to {output_path}")


def main():
    """Main extraction function."""
    parser = argparse.ArgumentParser(description='Extract and clean OQMD data')
    parser.add_argument('--limit', type=int, default=10000, help='Total number of materials to fetch (default: 10000)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("OQMD Data Extractor")
    print("=" * 60)
    print(f"Target: Fetch {args.limit} materials from OQMD API")
    print()
    
    all_entries = []
    batch_size = 100
    offset = 0
    total_fetched = 0
    failed_batches = 0
    
    # Fetch in batches
    while total_fetched < args.limit:
        remaining = args.limit - total_fetched
        current_batch_size = min(batch_size, remaining)
        
        print(f"Fetching batch: offset={offset}, limit={current_batch_size}...", end=' ')
        
        batch = fetch_batch(limit=current_batch_size, offset=offset)
        
        if batch is None:
            failed_batches += 1
            print("FAILED")
            if failed_batches >= 3:
                print("Too many failed batches, stopping.")
                break
            time.sleep(1)
            continue
        
        if not batch:
            print("Empty batch, stopping.")
            break
        
        print(f"Got {len(batch)} entries")
        all_entries.extend(batch)
        total_fetched += len(batch)
        offset += len(batch)
        
        # Rate limiting: 0.5s delay between requests
        time.sleep(0.5)
        
        # If we got fewer than requested, we've reached the end
        if len(batch) < current_batch_size:
            break
    
    print()
    print(f"Total fetched: {total_fetched} entries")
    
    # Clean and filter
    print("Cleaning and filtering entries...")
    cleaned = clean_and_filter_entries(all_entries)
    
    # Statistics
    print()
    print("=" * 60)
    print("Extraction Summary")
    print("=" * 60)
    print(f"Total fetched: {total_fetched}")
    print(f"Total kept after filtering: {len(cleaned)}")
    print(f"Filtered out: {total_fetched - len(cleaned)}")
    print(f"Filter rate: {len(cleaned)/total_fetched*100:.1f}%" if total_fetched > 0 else "N/A")
    
    # Count entries with band gap
    with_bandgap = sum(1 for e in cleaned if e['band_gap'] is not None)
    print(f"Entries with band gap: {with_bandgap} ({with_bandgap/len(cleaned)*100:.1f}%)" if cleaned else "N/A")
    
    # Export to CSV
    output_path = "data/oqmd_cleaned.csv"
    export_to_csv(cleaned, output_path)
    
    print()
    print(f"✅ Extraction complete! Output: {output_path}")


if __name__ == "__main__":
    main()
