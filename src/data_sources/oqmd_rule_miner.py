"""
OQMD Rule Miner

Analyzes cleaned OQMD data and generates rules matching the existing schema.

Usage:
    python src/data_sources/oqmd_rule_miner.py
"""

import json
import os
import pandas as pd
from typing import List, Dict
from datetime import datetime


def load_existing_rules() -> tuple[List[Dict], int]:
    """
    Load existing rules and find the maximum rule_id.
    
    Returns:
        Tuple of (rules_list, max_rule_id_number)
    """
    rules_path = "rules/extracted_rules.json"
    
    if not os.path.exists(rules_path):
        return [], 0
    
    try:
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        # Find maximum rule_id
        max_id = -1
        for rule in rules:
            rule_id = rule.get('rule_id', '')
            if rule_id and rule_id.startswith('rule_'):
                try:
                    id_num = int(rule_id.split('_')[1])
                    max_id = max(max_id, id_num)
                except (ValueError, IndexError):
                    pass
        
        return rules, max_id + 1
    except Exception as e:
        print(f"Warning: Could not load existing rules: {e}")
        return [], 0


def calculate_confidence(sample_size: int, base: int = 10000) -> float:
    """Calculate confidence based on sample size."""
    return min(0.95, sample_size / base)


def create_rule(
    rule_text: str,
    rule_type: str,
    property_name: str,
    threshold_value: float,
    threshold_unit: str,
    operator: str,
    confidence: float,
    evidence_count: int,
    range_start: float = None,
    range_end: float = None,
    rule_id_counter: int = 0
) -> Dict:
    """
    Create a rule dictionary matching the existing schema.
    
    Returns:
        Rule dictionary with all required fields
    """
    uncertainty = round(1.0 - confidence, 3)
    
    # Determine evidence strength
    if confidence >= 0.85:
        evidence_strength = "strong"
    elif confidence >= 0.65:
        evidence_strength = "medium"
    else:
        evidence_strength = "weak"
    
    # Determine validation status
    if evidence_count > 1000:
        validation_status = "validated"
    else:
        validation_status = "extracted"
    
    # Map rule_type to category
    category_mapping = {
        "stability": "stability",
        "band_gap": "property_application",
        "mechanical": "property_application",
        "synthesis": "synthesis",
        "phase_stability": "stability",
        "chemical_constraint": "stability"
    }
    category = category_mapping.get(rule_type, "material_property")
    
    rule = {
        "rule_text": rule_text,
        "rule_type": rule_type,
        "property": property_name,
        "threshold_value": threshold_value,
        "threshold_unit": threshold_unit,
        "operator": operator,
        "range_start": range_start,
        "range_end": range_end,
        "application": "Materials database analysis",
        "domain": ["general"],
        "category": category,
        "evidence_strength": evidence_strength,
        "statistical_confidence": round(confidence, 3),
        "confidence": round(confidence, 3),
        "uncertainty": uncertainty,
        "source_paper_id": "oqmd_database_v1.5",
        "source_section": "database",
        "publication_year": None,
        "validation_status": validation_status,
        "rule_id": f"rule_{rule_id_counter:06d}",
        "edge_cases": [],
        "fails_for": [],
        "evidence_count": evidence_count,
        "validated_materials": []
    }
    
    return rule


def mine_stability_rules(df: pd.DataFrame, rule_id_counter: int) -> tuple[List[Dict], int]:
    """Mine stability rules from delta_e column."""
    rules = []
    
    # Filter valid delta_e values
    valid_delta_e = df[df['delta_e'].notna()]['delta_e']
    if len(valid_delta_e) == 0:
        return rules, rule_id_counter
    
    evidence_count = len(valid_delta_e)
    confidence = calculate_confidence(evidence_count)
    
    # Rule 1: 90th percentile threshold for stable materials
    threshold_90 = valid_delta_e.quantile(0.90)
    rule1 = create_rule(
        rule_text=f"Materials with energy above hull < {threshold_90:.3f} eV/atom are thermodynamically stable (90th percentile)",
        rule_type="stability",
        property_name="energy_above_hull",
        threshold_value=round(threshold_90, 3),
        threshold_unit="eV/atom",
        operator="<",
        confidence=confidence,
        evidence_count=evidence_count,
        rule_id_counter=rule_id_counter
    )
    rules.append(rule1)
    rule_id_counter += 1
    
    # Rule 2: 95th percentile threshold
    threshold_95 = valid_delta_e.quantile(0.95)
    rule2 = create_rule(
        rule_text=f"Materials with energy above hull < {threshold_95:.3f} eV/atom are highly stable (95th percentile)",
        rule_type="stability",
        property_name="energy_above_hull",
        threshold_value=round(threshold_95, 3),
        threshold_unit="eV/atom",
        operator="<",
        confidence=confidence,
        evidence_count=evidence_count,
        rule_id_counter=rule_id_counter
    )
    rules.append(rule2)
    rule_id_counter += 1
    
    # Rule 3: Median threshold
    threshold_median = valid_delta_e.median()
    rule3 = create_rule(
        rule_text=f"Typical energy above hull is {threshold_median:.3f} eV/atom (median)",
        rule_type="stability",
        property_name="energy_above_hull",
        threshold_value=round(threshold_median, 3),
        threshold_unit="eV/atom",
        operator="=",
        confidence=confidence,
        evidence_count=evidence_count,
        rule_id_counter=rule_id_counter
    )
    rules.append(rule3)
    rule_id_counter += 1
    
    # Rule 4: Range rule (10th to 90th percentile)
    threshold_10 = valid_delta_e.quantile(0.10)
    threshold_90_range = valid_delta_e.quantile(0.90)
    rule4 = create_rule(
        rule_text=f"Typical energy above hull range: {threshold_10:.3f} to {threshold_90_range:.3f} eV/atom (10th-90th percentile)",
        rule_type="stability",
        property_name="energy_above_hull",
        threshold_value=None,
        threshold_unit="eV/atom",
        operator="range",
        confidence=confidence,
        evidence_count=evidence_count,
        range_start=round(threshold_10, 3),
        range_end=round(threshold_90_range, 3),
        rule_id_counter=rule_id_counter
    )
    rules.append(rule4)
    rule_id_counter += 1
    
    return rules, rule_id_counter


def mine_formation_energy_rules(df: pd.DataFrame, rule_id_counter: int) -> tuple[List[Dict], int]:
    """Mine formation energy rules."""
    rules = []
    
    # Filter valid formation energy values
    valid_fe = df[df['formation_energy'].notna()]['formation_energy']
    if len(valid_fe) == 0:
        return rules, rule_id_counter
    
    evidence_count = len(valid_fe)
    confidence = calculate_confidence(evidence_count)
    
    # Rule 1: 10th percentile (very stable)
    threshold_10 = valid_fe.quantile(0.10)
    rule1 = create_rule(
        rule_text=f"Materials with formation energy < {threshold_10:.3f} eV/atom are highly stable (10th percentile)",
        rule_type="stability",
        property_name="formation_energy",
        threshold_value=round(threshold_10, 3),
        threshold_unit="eV/atom",
        operator="<",
        confidence=confidence,
        evidence_count=evidence_count,
        rule_id_counter=rule_id_counter
    )
    rules.append(rule1)
    rule_id_counter += 1
    
    # Rule 2: 90th percentile (less stable)
    threshold_90 = valid_fe.quantile(0.90)
    rule2 = create_rule(
        rule_text=f"Materials with formation energy > {threshold_90:.3f} eV/atom are less stable (90th percentile)",
        rule_type="stability",
        property_name="formation_energy",
        threshold_value=round(threshold_90, 3),
        threshold_unit="eV/atom",
        operator=">",
        confidence=confidence,
        evidence_count=evidence_count,
        rule_id_counter=rule_id_counter
    )
    rules.append(rule2)
    rule_id_counter += 1
    
    # Rule 3: Typical range (10th to 90th percentile)
    threshold_10_range = valid_fe.quantile(0.10)
    threshold_90_range = valid_fe.quantile(0.90)
    rule3 = create_rule(
        rule_text=f"Typical formation energy range: {threshold_10_range:.3f} to {threshold_90_range:.3f} eV/atom (10th-90th percentile)",
        rule_type="stability",
        property_name="formation_energy",
        threshold_value=None,
        threshold_unit="eV/atom",
        operator="range",
        confidence=confidence,
        evidence_count=evidence_count,
        range_start=round(threshold_10_range, 3),
        range_end=round(threshold_90_range, 3),
        rule_id_counter=rule_id_counter
    )
    rules.append(rule3)
    rule_id_counter += 1
    
    # Rule 4: Negative formation energy threshold (stable)
    negative_fe = valid_fe[valid_fe < 0]
    if len(negative_fe) > 100:
        threshold_median_neg = negative_fe.median()
        rule4 = create_rule(
            rule_text=f"Stable materials typically have formation energy < {threshold_median_neg:.3f} eV/atom (median of negative values)",
            rule_type="stability",
            property_name="formation_energy",
            threshold_value=round(threshold_median_neg, 3),
            threshold_unit="eV/atom",
            operator="<",
            confidence=calculate_confidence(len(negative_fe)),
            evidence_count=len(negative_fe),
            rule_id_counter=rule_id_counter
        )
        rules.append(rule4)
        rule_id_counter += 1
    
    return rules, rule_id_counter


def mine_band_gap_rules(df: pd.DataFrame, rule_id_counter: int) -> tuple[List[Dict], int]:
    """Mine band gap rules."""
    rules = []
    
    # Filter valid band gap values (non-null and positive)
    valid_bg = df[(df['band_gap'].notna()) & (df['band_gap'] > 0)]['band_gap']
    if len(valid_bg) == 0:
        return rules, rule_id_counter
    
    evidence_count = len(valid_bg)
    confidence = calculate_confidence(evidence_count)
    
    # Rule 1: Semiconductor range (0.1 to 4 eV)
    semiconductors = valid_bg[(valid_bg > 0.1) & (valid_bg < 4.0)]
    if len(semiconductors) > 50:
        median_bg = semiconductors.median()
        rule1 = create_rule(
            rule_text=f"Semiconductor materials typically have band gap around {median_bg:.2f} eV (median, 0.1-4 eV range)",
            rule_type="band_gap",
            property_name="band_gap",
            threshold_value=round(median_bg, 2),
            threshold_unit="eV",
            operator="=",
            confidence=calculate_confidence(len(semiconductors)),
            evidence_count=len(semiconductors),
            rule_id_counter=rule_id_counter
        )
        rules.append(rule1)
        rule_id_counter += 1
    
    # Rule 2: Wide band gap threshold (> 3 eV)
    wide_bg = valid_bg[valid_bg > 3.0]
    if len(wide_bg) > 50:
        threshold_median = wide_bg.median()
        rule2 = create_rule(
            rule_text=f"Wide band gap materials (> 3 eV) typically have band gap around {threshold_median:.2f} eV (median)",
            rule_type="band_gap",
            property_name="band_gap",
            threshold_value=round(threshold_median, 2),
            threshold_unit="eV",
            operator=">",
            confidence=calculate_confidence(len(wide_bg)),
            evidence_count=len(wide_bg),
            rule_id_counter=rule_id_counter
        )
        rules.append(rule2)
        rule_id_counter += 1
    
    # Rule 3: Narrow band gap threshold (< 2 eV)
    narrow_bg = valid_bg[valid_bg < 2.0]
    if len(narrow_bg) > 50:
        threshold_median = narrow_bg.median()
        rule3 = create_rule(
            rule_text=f"Narrow band gap materials (< 2 eV) typically have band gap around {threshold_median:.2f} eV (median)",
            rule_type="band_gap",
            property_name="band_gap",
            threshold_value=round(threshold_median, 2),
            threshold_unit="eV",
            operator="<",
            confidence=calculate_confidence(len(narrow_bg)),
            evidence_count=len(narrow_bg),
            rule_id_counter=rule_id_counter
        )
        rules.append(rule3)
        rule_id_counter += 1
    
    # Rule 4: Band gap range for semiconductors
    if len(semiconductors) > 50:
        bg_10 = semiconductors.quantile(0.10)
        bg_90 = semiconductors.quantile(0.90)
        rule4 = create_rule(
            rule_text=f"Semiconductor band gap range: {bg_10:.2f} to {bg_90:.2f} eV (10th-90th percentile, 0.1-4 eV)",
            rule_type="band_gap",
            property_name="band_gap",
            threshold_value=None,
            threshold_unit="eV",
            operator="range",
            confidence=calculate_confidence(len(semiconductors)),
            evidence_count=len(semiconductors),
            range_start=round(bg_10, 2),
            range_end=round(bg_90, 2),
            rule_id_counter=rule_id_counter
        )
        rules.append(rule4)
        rule_id_counter += 1
    
    return rules, rule_id_counter


def mine_correlation_rules(df: pd.DataFrame, rule_id_counter: int) -> tuple[List[Dict], int]:
    """Mine correlation rules between properties."""
    rules = []
    
    # Rule: Correlation between formation energy and stability
    valid_data = df[(df['formation_energy'].notna()) & (df['delta_e'].notna())]
    if len(valid_data) > 100:
        # Materials with negative formation energy and low delta_e are stable
        stable = valid_data[(valid_data['formation_energy'] < -0.5) & (valid_data['delta_e'] < 0.1)]
        if len(stable) > 50:
            rule = create_rule(
                rule_text="Materials with formation energy < -0.5 eV/atom and energy above hull < 0.1 eV/atom are thermodynamically stable",
                rule_type="stability",
                property_name="formation_energy",
                threshold_value=-0.5,
                threshold_unit="eV/atom",
                operator="<",
                confidence=calculate_confidence(len(stable)),
                evidence_count=len(stable),
                rule_id_counter=rule_id_counter
            )
            rules.append(rule)
            rule_id_counter += 1
    
    return rules, rule_id_counter


def main():
    """Main rule mining function."""
    print("=" * 60)
    print("OQMD Rule Miner")
    print("=" * 60)
    
    # Load existing rules to get next rule_id
    existing_rules, next_rule_id = load_existing_rules()
    print(f"Found {len(existing_rules)} existing rules")
    print(f"Starting rule_id counter at: rule_{next_rule_id:06d}")
    print()
    
    # Load cleaned data
    csv_path = "data/oqmd_cleaned.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run oqmd_extractor.py first.")
        return
    
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} entries")
    print()
    
    # Convert band_gap to float (handle NaN)
    df['band_gap'] = pd.to_numeric(df['band_gap'], errors='coerce')
    
    # Mine rules
    all_rules = []
    rule_id_counter = next_rule_id
    
    print("Mining stability rules from delta_e...")
    stability_rules, rule_id_counter = mine_stability_rules(df, rule_id_counter)
    all_rules.extend(stability_rules)
    print(f"  Generated {len(stability_rules)} stability rules")
    
    print("Mining formation energy rules...")
    fe_rules, rule_id_counter = mine_formation_energy_rules(df, rule_id_counter)
    all_rules.extend(fe_rules)
    print(f"  Generated {len(fe_rules)} formation energy rules")
    
    print("Mining band gap rules...")
    bg_rules, rule_id_counter = mine_band_gap_rules(df, rule_id_counter)
    all_rules.extend(bg_rules)
    print(f"  Generated {len(bg_rules)} band gap rules")
    
    print("Mining correlation rules...")
    corr_rules, rule_id_counter = mine_correlation_rules(df, rule_id_counter)
    all_rules.extend(corr_rules)
    print(f"  Generated {len(corr_rules)} correlation rules")
    
    print()
    print("=" * 60)
    print("Rule Mining Summary")
    print("=" * 60)
    print(f"Total rules generated: {len(all_rules)}")
    print(f"Rule ID range: rule_{next_rule_id:06d} to rule_{rule_id_counter-1:06d}")
    
    # Save rules
    output_path = "data/oqmd_mined_rules.json"
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_rules, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Rules saved to: {output_path}")
    
    # Print sample rules
    print()
    print("Sample rules (first 3):")
    for i, rule in enumerate(all_rules[:3], 1):
        print(f"\n  Rule {i}: {rule['rule_text']}")
        print(f"    Property: {rule['property']}, Threshold: {rule['threshold_value']} {rule['threshold_unit']}")
        print(f"    Confidence: {rule['confidence']}, Evidence: {rule['evidence_count']}")


if __name__ == "__main__":
    main()
