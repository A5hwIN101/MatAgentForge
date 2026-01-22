"""
OQMD Rules Merger

Merges OQMD-mined rules into existing rule system with backup and validation.

Usage:
    python src/data_sources/merge_oqmd_rules.py
"""

import json
import os
import shutil
from typing import List, Dict, Tuple
from datetime import datetime
from src.data_sources.rule_storage import RuleStorage


def create_backup(file_path: str) -> bool:
    """Create backup of a file."""
    if not os.path.exists(file_path):
        return False
    
    backup_path = file_path.replace('.json', '.backup.json')
    try:
        shutil.copy2(file_path, backup_path)
        print(f"  Created backup: {backup_path}")
        return True
    except Exception as e:
        print(f"  Warning: Could not create backup: {e}")
        return False


def is_duplicate_rule(rule1: Dict, rule2: Dict) -> bool:
    """
    Check if two rules are duplicates based on property, threshold_value, and operator.
    
    Args:
        rule1: First rule dictionary
        rule2: Second rule dictionary
        
    Returns:
        True if rules are duplicates
    """
    # Check property match
    if rule1.get('property') != rule2.get('property'):
        return False
    
    # Check operator match
    if rule1.get('operator') != rule2.get('operator'):
        return False
    
    # Check threshold_value match (within tolerance for floats)
    threshold1 = rule1.get('threshold_value')
    threshold2 = rule2.get('threshold_value')
    
    if threshold1 is None or threshold2 is None:
        # If one is None, check if both are None
        return threshold1 == threshold2
    
    # For numeric values, allow small tolerance
    if isinstance(threshold1, (int, float)) and isinstance(threshold2, (int, float)):
        return abs(threshold1 - threshold2) < 0.001
    
    return threshold1 == threshold2


def merge_rules(existing_rules: List[Dict], oqmd_rules: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Merge OQMD rules into existing rules.
    
    Args:
        existing_rules: List of existing rule dictionaries
        oqmd_rules: List of OQMD rule dictionaries
        
    Returns:
        Tuple of (merged_rules_list, merge_statistics_dict)
    """
    merged = existing_rules.copy()
    stats = {
        'total_existing': len(existing_rules),
        'total_oqmd': len(oqmd_rules),
        'new_rules_added': 0,
        'duplicates_found': 0,
        'duplicates_resolved': 0
    }
    
    # Create a lookup for existing rules by duplicate key
    existing_lookup = {}
    for rule in existing_rules:
        key = (rule.get('property'), rule.get('operator'), rule.get('threshold_value'))
        if key not in existing_lookup:
            existing_lookup[key] = []
        existing_lookup[key].append(rule)
    
    # Process each OQMD rule
    for oqmd_rule in oqmd_rules:
        key = (oqmd_rule.get('property'), oqmd_rule.get('operator'), oqmd_rule.get('threshold_value'))
        
        # Check for duplicates
        if key in existing_lookup:
            stats['duplicates_found'] += 1
            
            # Find matching existing rule
            matched = False
            for existing_rule in existing_lookup[key]:
                if is_duplicate_rule(existing_rule, oqmd_rule):
                    matched = True
                    stats['duplicates_resolved'] += 1
                    
                    # Keep higher confidence version
                    existing_conf = existing_rule.get('statistical_confidence', existing_rule.get('confidence', 0))
                    oqmd_conf = oqmd_rule.get('statistical_confidence', oqmd_rule.get('confidence', 0))
                    
                    if oqmd_conf > existing_conf:
                        # Update existing rule with OQMD data (higher confidence)
                        existing_rule.update({
                            'statistical_confidence': oqmd_conf,
                            'confidence': oqmd_conf,
                            'uncertainty': round(1.0 - oqmd_conf, 3),
                            'evidence_count': oqmd_rule.get('evidence_count', existing_rule.get('evidence_count', 0)),
                            'source_paper_id': f"{existing_rule.get('source_paper_id', 'unknown')}, oqmd_database_v1.5"
                        })
                        print(f"  Updated rule {existing_rule.get('rule_id')} with higher confidence from OQMD")
                    else:
                        # Add OQMD as additional source
                        existing_source = existing_rule.get('source_paper_id', '')
                        if 'oqmd' not in existing_source.lower():
                            existing_rule['source_paper_id'] = f"{existing_source}, oqmd_database_v1.5"
                    
                    break
            
            if not matched:
                # Similar but not exact duplicate, add as new rule
                merged.append(oqmd_rule)
                stats['new_rules_added'] += 1
        else:
            # New rule, add it
            merged.append(oqmd_rule)
            stats['new_rules_added'] += 1
    
    return merged, stats


def update_metadata(oqmd_rules: List[Dict], existing_metadata: Dict) -> Dict:
    """
    Update metadata with OQMD rule information.
    
    Args:
        oqmd_rules: List of OQMD rules
        existing_metadata: Existing metadata dictionary
        
    Returns:
        Updated metadata dictionary
    """
    metadata = existing_metadata.copy()
    
    # Add OQMD source entry
    oqmd_source_id = "oqmd_database_v1.5"
    if oqmd_source_id not in metadata:
        metadata[oqmd_source_id] = {
            "title": "OQMD Database v1.5",
            "authors": [],
            "url": "http://oqmd.org",
            "extraction_date": datetime.now().isoformat(),
            "rules_count": len(oqmd_rules)
        }
    
    # Add individual rule metadata
    for rule in oqmd_rules:
        rule_id = rule.get('rule_id')
        if rule_id:
            if rule_id not in metadata:
                metadata[rule_id] = {
                    "source": oqmd_source_id,
                    "extraction_date": datetime.now().isoformat(),
                    "evidence_count": rule.get('evidence_count', 0)
                }
    
    return metadata


def rebuild_index(rules: List[Dict]) -> Dict:
    """
    Rebuild index from all rules.
    
    Args:
        rules: List of all rule dictionaries
        
    Returns:
        Index dictionary
    """
    storage = RuleStorage()
    return storage._build_index(rules)


def test_integration():
    """Test that merged rules can be loaded successfully."""
    print("\n" + "=" * 60)
    print("Testing Integration")
    print("=" * 60)
    
    try:
        from src.data_sources.rule_loader import RuleLoader
        
        loader = RuleLoader()
        all_rules = loader.load_rules()
        
        print(f"✅ Successfully loaded {len(all_rules)} total rules")
        
        # Find OQMD rules
        oqmd_rules = [r for r in all_rules if 'oqmd' in r.get('source_paper_id', '').lower()]
        print(f"✅ Found {len(oqmd_rules)} OQMD rules in loaded set")
        
        # Print 3 sample OQMD rules
        print("\nSample OQMD rules (first 3):")
        for i, rule in enumerate(oqmd_rules[:3], 1):
            print(f"\n  Rule {i}: {rule.get('rule_id')}")
            print(f"    Text: {rule.get('rule_text', 'N/A')[:80]}...")
            print(f"    Property: {rule.get('property')}, Threshold: {rule.get('threshold_value')} {rule.get('threshold_unit')}")
            print(f"    Confidence: {rule.get('confidence')}, Evidence: {rule.get('evidence_count', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main merge function."""
    print("=" * 60)
    print("OQMD Rules Merger")
    print("=" * 60)
    
    # Load existing rules
    existing_rules_path = "rules/extracted_rules.json"
    if not os.path.exists(existing_rules_path):
        print(f"Error: {existing_rules_path} not found.")
        return
    
    print(f"Loading existing rules from {existing_rules_path}...")
    with open(existing_rules_path, 'r', encoding='utf-8') as f:
        existing_rules = json.load(f)
    print(f"  Loaded {len(existing_rules)} existing rules")
    
    # Load OQMD rules
    oqmd_rules_path = "data/oqmd_mined_rules.json"
    if not os.path.exists(oqmd_rules_path):
        print(f"Error: {oqmd_rules_path} not found. Run oqmd_rule_miner.py first.")
        return
    
    print(f"Loading OQMD rules from {oqmd_rules_path}...")
    with open(oqmd_rules_path, 'r', encoding='utf-8') as f:
        oqmd_rules = json.load(f)
    print(f"  Loaded {len(oqmd_rules)} OQMD rules")
    
    # Create backups
    print("\nCreating backups...")
    create_backup(existing_rules_path)
    
    metadata_path = "rules/rule_metadata.json"
    if os.path.exists(metadata_path):
        create_backup(metadata_path)
    
    # Merge rules
    print("\nMerging rules...")
    merged_rules, stats = merge_rules(existing_rules, oqmd_rules)
    
    print("\n" + "=" * 60)
    print("Merge Statistics")
    print("=" * 60)
    print(f"Total existing rules: {stats['total_existing']}")
    print(f"Total OQMD rules: {stats['total_oqmd']}")
    print(f"New rules added: {stats['new_rules_added']}")
    print(f"Duplicates found: {stats['duplicates_found']}")
    print(f"Duplicates resolved: {stats['duplicates_resolved']}")
    print(f"Total rules after merge: {len(merged_rules)}")
    
    # Save merged rules
    print(f"\nSaving merged rules to {existing_rules_path}...")
    with open(existing_rules_path, 'w', encoding='utf-8') as f:
        json.dump(merged_rules, f, indent=2, ensure_ascii=False)
    print("  ✅ Saved merged rules")
    
    # Update metadata
    print(f"\nUpdating metadata...")
    metadata_path = "rules/rule_metadata.json"
    existing_metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            existing_metadata = json.load(f)
    
    updated_metadata = update_metadata(oqmd_rules, existing_metadata)
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(updated_metadata, f, indent=2, ensure_ascii=False)
    print("  ✅ Updated metadata")
    
    # Rebuild index
    print(f"\nRebuilding index...")
    index = rebuild_index(merged_rules)
    
    index_path = "rules/rule_index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print("  ✅ Rebuilt index")
    
    # Test integration
    test_integration()
    
    print("\n" + "=" * 60)
    print("✅ Merge complete!")
    print("=" * 60)
    print(f"Total rules: {len(merged_rules)} (was {len(existing_rules)})")
    print(f"New OQMD rules added: {stats['new_rules_added']}")
    print(f"Backups created: extracted_rules.backup.json, rule_metadata.backup.json")


if __name__ == "__main__":
    main()
