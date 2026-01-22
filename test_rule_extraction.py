"""
Test script to verify the updated rule extraction pipeline on 3 sample papers.

This script tests:
1. All required fields are extracted
2. Schema validation works correctly
3. Uncertainty is calculated as (1 - confidence)
4. validation_status is set correctly
5. rule_id is zero-padded 6-digit
6. domain is always an array
7. edge_cases and fails_for are arrays
"""

import json
import logging
from typing import Tuple, List
from src.data_sources.rule_extractor import RuleExtractor
from src.data_sources.rule_storage import RuleStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sample paper abstracts for testing
SAMPLE_PAPERS = [
    {
        "title": "Charge Neutrality and Stability in Inorganic Compounds",
        "abstract": "We demonstrate that charge neutrality (sum of oxidation states × stoichiometry = 0) is required for stable compounds. Our analysis of 10,000 materials shows that compounds violating this rule have formation energies above 0.5 eV/atom. The rule holds for 99.8% of stable inorganic compounds, with exceptions only for mixed-valence systems.",
        "url": "http://arxiv.org/abs/test.00001",
        "publication_year": 2023
    },
    {
        "title": "Band Gap Engineering for Optoelectronic Applications",
        "abstract": "Materials with band gaps greater than 3.0 eV are suitable for optoelectronic applications including photovoltaics and LEDs. Our study of 500 semiconductor materials reveals that band gaps in the range 3.0-4.5 eV provide optimal performance for UV detectors. Materials with band gaps below 2.0 eV are metallic and unsuitable for these applications.",
        "url": "http://arxiv.org/abs/test.00002",
        "publication_year": 2023
    },
    {
        "title": "Formation Energy Thresholds for Thermodynamic Stability",
        "abstract": "Compounds with formation energies less than -1.0 eV/atom are thermodynamically stable and can be synthesized. Our database of 50,000 materials confirms this threshold with 95% accuracy. The rule fails for high-entropy alloys and metastable phases, which may have positive formation energies but remain stable due to kinetic barriers.",
        "url": "http://arxiv.org/abs/test.00003",
        "publication_year": 2023
    }
]

def validate_rule_schema(rule: dict, rule_index: int) -> Tuple[bool, List[str]]:
    """
    Validate a rule against the target schema.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    required_fields = [
        "rule_text", "rule_type", "property", "threshold_value", "threshold_unit",
        "operator", "range_start", "range_end", "application", "domain", "category",
        "evidence_strength", "statistical_confidence", "confidence", "uncertainty",
        "source_paper_id", "source_section", "publication_year", "validation_status",
        "edge_cases", "fails_for"
        # Note: rule_id is optional during extraction, added by storage
    ]
    
    # Check required fields
    for field in required_fields:
        if field not in rule:
            errors.append(f"Missing required field: {field}")
    
    # Validate rule_type
    valid_rule_types = ["chemical_constraint", "stability", "band_gap", "mechanical", "synthesis", "phase_stability"]
    if rule.get("rule_type") not in valid_rule_types:
        errors.append(f"Invalid rule_type: {rule.get('rule_type')}")
    
    # Validate operator
    valid_operators = ["=", ">", "<", ">=", "<=", "range"]
    if rule.get("operator") not in valid_operators:
        errors.append(f"Invalid operator: {rule.get('operator')}")
    
    # Validate operator "range" requires both range_start and range_end
    if rule.get("operator") == "range":
        if not isinstance(rule.get("range_start"), (int, float)) or not isinstance(rule.get("range_end"), (int, float)):
            errors.append("Operator 'range' requires both range_start and range_end to be numbers")
    
    # Validate threshold_value is number or null
    threshold_value = rule.get("threshold_value")
    if threshold_value is not None and not isinstance(threshold_value, (int, float)):
        errors.append(f"threshold_value must be number or null, got {type(threshold_value)}")
    
    # Validate domain is array
    domain = rule.get("domain")
    if not isinstance(domain, list):
        errors.append(f"domain must be an array, got {type(domain)}")
    elif len(domain) == 0:
        errors.append("domain array must not be empty")
    
    # Validate evidence_strength
    if rule.get("evidence_strength") not in ["strong", "medium", "weak"]:
        errors.append(f"evidence_strength must be 'strong', 'medium', or 'weak', got {rule.get('evidence_strength')}")
    
    # Validate confidence and uncertainty
    confidence = rule.get("confidence")
    uncertainty = rule.get("uncertainty")
    if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
        errors.append(f"confidence must be between 0 and 1, got {confidence}")
    if not isinstance(uncertainty, (int, float)) or not (0 <= uncertainty <= 1):
        errors.append(f"uncertainty must be between 0 and 1, got {uncertainty}")
    
    # Validate uncertainty ≈ (1 - confidence) within tolerance
    if abs((uncertainty + confidence) - 1.0) > 0.1:
        errors.append(f"uncertainty ({uncertainty}) + confidence ({confidence}) should ≈ 1.0, got {uncertainty + confidence}")
    
    # Validate validation_status
    if rule.get("validation_status") not in ["physics_based", "validated", "extracted"]:
        errors.append(f"validation_status must be 'physics_based', 'validated', or 'extracted', got {rule.get('validation_status')}")
    
    # Validate edge_cases and fails_for are arrays
    if not isinstance(rule.get("edge_cases"), list):
        errors.append(f"edge_cases must be an array, got {type(rule.get('edge_cases'))}")
    if not isinstance(rule.get("fails_for"), list):
        errors.append(f"fails_for must be an array, got {type(rule.get('fails_for'))}")
    
    # Validate rule_id format (optional - may be added during storage)
    rule_id = rule.get("rule_id")
    if rule_id:
        if not rule_id.startswith("rule_"):
            errors.append(f"rule_id must start with 'rule_', got {rule_id}")
        else:
            try:
                id_num = int(rule_id.split("_")[1])
                if len(rule_id.split("_")[1]) != 6:
                    errors.append(f"rule_id must be zero-padded 6-digit, got {rule_id}")
            except ValueError:
                errors.append(f"rule_id must have numeric suffix, got {rule_id}")
    # Note: rule_id is optional during extraction, will be added by storage
    
    return len(errors) == 0, errors

def test_extraction():
    """Test rule extraction on 3 sample papers."""
    logger.info("=" * 60)
    logger.info("Testing Updated Rule Extraction Pipeline")
    logger.info("=" * 60)
    
    extractor = RuleExtractor(min_confidence=0.5)  # Lower threshold for testing
    storage = RuleStorage(rules_dir="rules_test")
    
    all_rules = []
    all_errors = []
    
    for i, paper in enumerate(SAMPLE_PAPERS, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing Paper {i}: {paper['title']}")
        logger.info(f"{'='*60}")
        
        rules = extractor.extract_rules(
            abstract=paper["abstract"],
            paper_id=paper["url"],
            paper_title=paper["title"],
            publication_year=paper.get("publication_year")
        )
        
        logger.info(f"Extracted {len(rules)} rules")
        
        for j, rule in enumerate(rules, 1):
            logger.info(f"\n  Rule {j}:")
            logger.info(f"    rule_text: {rule.get('rule_text', 'N/A')[:80]}...")
            logger.info(f"    rule_type: {rule.get('rule_type')}")
            logger.info(f"    property: {rule.get('property')}")
            logger.info(f"    threshold_value: {rule.get('threshold_value')}")
            logger.info(f"    operator: {rule.get('operator')}")
            logger.info(f"    domain: {rule.get('domain')}")
            logger.info(f"    confidence: {rule.get('confidence')}")
            logger.info(f"    uncertainty: {rule.get('uncertainty')}")
            logger.info(f"    validation_status: {rule.get('validation_status')}")
            logger.info(f"    edge_cases: {rule.get('edge_cases')}")
            logger.info(f"    fails_for: {rule.get('fails_for')}")
            
            # Validate schema
            is_valid, errors = validate_rule_schema(rule, j)
            if not is_valid:
                logger.error(f"  ❌ Validation failed:")
                for error in errors:
                    logger.error(f"    - {error}")
                all_errors.extend([f"Paper {i}, Rule {j}: {e}" for e in errors])
            else:
                logger.info(f"  ✅ Schema validation passed")
            
            all_rules.append(rule)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Test Summary")
    logger.info(f"{'='*60}")
    logger.info(f"Total papers tested: {len(SAMPLE_PAPERS)}")
    logger.info(f"Total rules extracted: {len(all_rules)}")
    logger.info(f"Total validation errors: {len(all_errors)}")
    
    if all_errors:
        logger.error("\nValidation Errors:")
        for error in all_errors:
            logger.error(f"  - {error}")
    else:
        logger.info("\n✅ All rules passed schema validation!")
    
    # Save sample rules to file for inspection
    output_file = "test_extracted_rules.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_rules, f, indent=2, ensure_ascii=False)
    logger.info(f"\nSample rules saved to: {output_file}")
    
    return len(all_errors) == 0

if __name__ == "__main__":
    success = test_extraction()
    exit(0 if success else 1)
