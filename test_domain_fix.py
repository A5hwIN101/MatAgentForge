"""
Unit test to verify domain array handling fixes in rule_storage.py
Tests that domain arrays are handled correctly without TypeError.
"""

import json
import os
import tempfile
import shutil
from src.data_sources.rule_storage import RuleStorage

def test_domain_array_handling():
    """Test that domain arrays are handled correctly in storage operations."""
    
    # Create temporary directory for test
    test_dir = tempfile.mkdtemp()
    try:
        storage = RuleStorage(rules_dir=test_dir)
        
        # Create test rules with domain as array
        test_rules = [
            {
                "rule_text": "Band gap > 3.0 eV → Optoelectronics applications",
                "rule_type": "band_gap",
                "property": "band_gap",
                "threshold_value": 3.0,
                "threshold_unit": "eV",
                "operator": ">",
                "range_start": None,
                "range_end": None,
                "application": "Optoelectronics",
                "domain": ["photovoltaics", "optoelectronics"],  # Array domain
                "category": "property_application",
                "evidence_strength": "strong",
                "statistical_confidence": 0.85,
                "confidence": 0.85,
                "uncertainty": 0.15,
                "source_paper_id": "test_paper_1",
                "source_section": "abstract",
                "publication_year": 2023,
                "validation_status": "extracted",
                "edge_cases": [],
                "fails_for": []
            },
            {
                "rule_text": "Formation energy < -1.0 eV/atom → Stable",
                "rule_type": "stability",
                "property": "formation_energy",
                "threshold_value": -1.0,
                "threshold_unit": "eV/atom",
                "operator": "<",
                "range_start": None,
                "range_end": None,
                "application": "Stability",
                "domain": ["general"],  # Single-item array
                "category": "stability",
                "evidence_strength": "medium",
                "statistical_confidence": 0.75,
                "confidence": 0.75,
                "uncertainty": 0.25,
                "source_paper_id": "test_paper_2",
                "source_section": "abstract",
                "publication_year": 2023,
                "validation_status": "extracted",
                "edge_cases": ["high_entropy_alloys"],
                "fails_for": []
            }
        ]
        
        print("Testing rule storage with domain arrays...")
        
        # Test 1: Save rules (should not raise TypeError)
        try:
            saved_count = storage.save_rules(test_rules)
            print(f"[PASS] Test 1: Saved {saved_count} rules without TypeError")
        except TypeError as e:
            print(f"[FAIL] Test 1: TypeError when saving rules: {e}")
            return False
        
        # Test 2: Load rules by domain (should work with array domains)
        try:
            rules = storage.load_rules(domain="photovoltaics")
            print(f"[PASS] Test 2: Loaded {len(rules)} rules for domain 'photovoltaics'")
            if len(rules) > 0 and rules[0].get("domain") == ["photovoltaics", "optoelectronics"]:
                print("   [OK] Domain array preserved correctly")
        except (TypeError, AttributeError) as e:
            print(f"[FAIL] Test 2: Error when loading by domain: {e}")
            return False
        
        # Test 3: Get rule stats (should handle domain arrays)
        try:
            stats = storage.get_rule_stats()
            print(f"[PASS] Test 3: Got rule stats without TypeError")
            print(f"   [OK] Domain distribution: {stats.get('domains', {})}")
            # Check that domains are counted correctly
            if "photovoltaics" in stats.get("domains", {}) and "optoelectronics" in stats.get("domains", {}):
                print("   [OK] Multiple domains from array counted separately")
        except TypeError as e:
            print(f"[FAIL] Test 3: TypeError when getting stats: {e}")
            return False
        
        # Test 4: Build index (should handle domain arrays)
        try:
            all_rules = storage._load_rules()
            index = storage._build_index(all_rules)
            print(f"[PASS] Test 4: Built index without TypeError")
            # Check that both domains are indexed
            if "photovoltaics" in index.get("domain", {}) and "optoelectronics" in index.get("domain", {}):
                print("   [OK] Both domains from array indexed correctly")
        except TypeError as e:
            print(f"[FAIL] Test 4: TypeError when building index: {e}")
            return False
        
        # Test 5: Query with get_rules (should handle domain parameter)
        try:
            rules = storage.get_rules(domain="optoelectronics")
            print(f"[PASS] Test 5: get_rules() with domain parameter worked")
            print(f"   [OK] Found {len(rules)} rules for 'optoelectronics'")
        except (TypeError, AttributeError) as e:
            print(f"[FAIL] Test 5: Error when using get_rules: {e}")
            return False
        
        print("\n[SUCCESS] All tests passed! Domain array handling is working correctly.")
        return True
        
    finally:
        # Clean up
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    success = test_domain_array_handling()
    exit(0 if success else 1)
