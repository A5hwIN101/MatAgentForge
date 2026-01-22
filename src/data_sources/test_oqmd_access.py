"""
Simple script to test OQMD API access and print 5 material entries.

Fetches materials from OQMD REST API and displays:
- Composition
- Formation Energy
- Band Gap
- Energy Above Hull (delta_e)
"""

import requests


def fetch_oqmd_materials(limit=5):
    """
    Fetch materials from OQMD API.
    
    Args:
        limit: Number of materials to fetch (default: 5)
        
    Returns:
        List of material dictionaries
    """
    url = f"http://oqmd.org/oqmdapi/formationenergy?limit={limit}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from OQMD: {e}")
        return None


def format_composition(entry):
    """
    Extract and format composition from OQMD entry.
    
    Args:
        entry: OQMD entry dictionary
        
    Returns:
        Formatted composition string (e.g., "Fe2O3")
    """
    # OQMD entries typically have composition in 'composition' or 'name' field
    # Try different possible field names
    if 'composition' in entry:
        return entry['composition']
    elif 'name' in entry:
        return entry['name']
    elif 'formula' in entry:
        return entry['formula']
    else:
        # Try to construct from elements if available
        if 'elements' in entry and 'counts' in entry:
            elements = entry['elements']
            counts = entry['counts']
            return ''.join(f"{elem}{count if count != 1 else ''}" 
                          for elem, count in zip(elements, counts))
        return "Unknown"


def print_materials(materials):
    """
    Print material entries in the requested format.
    
    Args:
        materials: List of material dictionaries or API response
    """
    if not materials:
        print("No materials found.")
        return
    
    # Handle different response formats
    if isinstance(materials, dict):
        # If response is a dict, check for common keys
        if 'results' in materials:
            entries = materials['results']
        elif 'data' in materials:
            entries = materials['data']
        elif 'entries' in materials:
            entries = materials['entries']
        else:
            # Assume the dict itself contains the entries
            entries = [materials]
    elif isinstance(materials, list):
        entries = materials
    else:
        print(f"Unexpected response format: {type(materials)}")
        return
    
    for i, entry in enumerate(entries[:5], 1):
        composition = format_composition(entry)
        
        # Extract formation energy (try different field names)
        formation_energy = entry.get('formation_energy', 
                                    entry.get('formation_energy_per_atom',
                                    entry.get('delta_e', None)))
        
        # Extract band gap
        band_gap = entry.get('band_gap', 
                           entry.get('bandgap',
                           entry.get('gap', None)))
        
        # Extract energy above hull (delta_e)
        delta_e = entry.get('delta_e',
                          entry.get('energy_above_hull',
                          entry.get('stability', None)))
        
        # Format output
        print(f"\nEntry {i}: {composition}")
        
        if formation_energy is not None:
            print(f"  Formation Energy: {formation_energy:.2f} eV/atom")
        else:
            print(f"  Formation Energy: N/A")
            
        if band_gap is not None:
            print(f"  Band Gap: {band_gap:.2f} eV")
        else:
            print(f"  Band Gap: N/A")
            
        if delta_e is not None:
            print(f"  Delta E: {delta_e:.2f} eV/atom")
        else:
            print(f"  Delta E: N/A")


def main():
    """Main function to fetch and print OQMD materials."""
    print("Fetching materials from OQMD...")
    print("=" * 50)
    
    materials = fetch_oqmd_materials(limit=5)
    
    if materials:
        print_materials(materials)
    else:
        print("Failed to fetch materials from OQMD API.")


if __name__ == "__main__":
    main()
