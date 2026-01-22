"""
Rule Extractor Module - ENHANCED VERSION

Uses LLM (Llama-3.1-8b-instant via Groq) to extract QUANTITATIVE, DOMAIN-AWARE, 
EVIDENCE-BACKED rules from paper abstracts.

Key Features:
- Domain-specific rule categories (PV, thermoelectric, battery, magnet, catalyst)
- Quantitative metrics with thresholds, ranges, uncertainty
- Statistical confidence based on frequency and evidence strength
- Convex hull stability baselines
- Enhanced confidence scoring (not just LLM certainty)
"""

import os
import json
import logging
import re
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

logger = logging.getLogger(__name__)


class RuleExtractor:
    """
    Extracts QUANTITATIVE, DOMAIN-AWARE, EVIDENCE-BACKED rules from paper abstracts.
    
    Rules must contain:
    - Specific thresholds, values, or numeric relationships
    - Domain context (PV, thermoelectric, battery, etc.)
    - Statistical confidence based on evidence
    - Quantitative format with units and operators
    """

    def __init__(self, model_name: str = "llama-3.1-8b-instant", min_confidence: float = 0.6):
        """
        Initialize the rule extractor.

        Args:
            model_name: Name of the Groq model to use
            min_confidence: Minimum confidence threshold for keeping rules (default: 0.6)
        """
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment variables")

        self.llm = ChatGroq(
            api_key=api_key,
            model=model_name,
            temperature=0.2  # Lower temperature for more deterministic rule extraction
        )
        self.min_confidence = min_confidence

        self.extraction_prompt_template = """You are an expert materials scientist. Extract ONLY quantitative, domain-specific rules from this abstract.

Abstract:
{abstract}

**CRITICAL: Extract ONLY quantitative rules with ALL required fields. Return ONLY valid JSON array.**

**REQUIRED SCHEMA - Each rule MUST have ALL these fields:**

{{
  "rule_type": "chemical_constraint|stability|band_gap|mechanical|synthesis|phase_stability",
  "property": "specific_property_name (e.g., charge_neutrality, energy_above_hull, band_gap, formation_energy, bulk_modulus, shear_modulus, temperature, pressure)",
  "threshold_value": NUMBER (e.g., 2.5, -1.0, 1000) or null - REQUIRED,
  "threshold_unit": "unit (e.g., eV, eV/atom, GPa, MPa, K, °C, dimensionless, Pauling scale)" - REQUIRED,
  "operator": "=|>|<|>=|<=|range" - REQUIRED,
  "range_start": NUMBER or null (REQUIRED if operator is "range"),
  "range_end": NUMBER or null (REQUIRED if operator is "range"),
  "application": "Specific use case or implication (e.g., Optoelectronics, Thermal stability, Bonding type prediction)",
  "domain": ["list", "of", "applicable", "domains"] - MUST be array, e.g., ["photovoltaics", "optoelectronics"] or ["general"],
  "category": "stability|material_property|property_application|synthesis",
  "evidence_strength": "strong|medium|weak",
  "statistical_confidence": NUMBER (0.0-1.0),
  "confidence": NUMBER (0.0-1.0),
  "uncertainty": NUMBER (0.0-1.0) - should be (1 - confidence),
  "rule_text": "Human-readable rule statement with threshold",
  "edge_cases": ["list", "of", "exceptions"] - array of edge cases or exceptions,
  "fails_for": ["list", "of", "failure", "cases"] - array of materials/conditions where rule fails,
  "evidence_count": INTEGER or null - number of materials/data points supporting rule if mentioned,
  "validated_materials": ["optional", "list"] - array of material examples if mentioned
}}

**EXAMPLE VALID RULE:**
{{
  "rule_type": "band_gap",
  "property": "band_gap",
  "threshold_value": 3.0,
  "threshold_unit": "eV",
  "operator": ">",
  "range_start": null,
  "range_end": null,
  "application": "Optoelectronics applications",
  "domain": ["photovoltaics", "optoelectronics"],
  "category": "property_application",
  "evidence_strength": "strong",
  "statistical_confidence": 0.85,
  "confidence": 0.85,
  "uncertainty": 0.15,
  "rule_text": "Band gap > 3.0 eV → Optoelectronics applications",
  "edge_cases": ["narrow_band_gap_semiconductors"],
  "fails_for": ["metallic_compounds"],
  "evidence_count": null,
  "validated_materials": []
}}

**RULE TYPES:**
- "chemical_constraint": Fundamental chemical rules (charge neutrality, Pauling rules, electronegativity)
- "stability": Formation energy, energy above hull thresholds
- "band_gap": Band gap thresholds for applications
- "mechanical": Bulk modulus, shear modulus thresholds
- "synthesis": Synthesis temperature, pressure, feasibility
- "phase_stability": Phase transition temperatures, pressures

**DOMAIN IDENTIFICATION:**
- "photovoltaics": PV, solar cell, solar energy
- "thermoelectric": Seebeck, ZT, thermoelectric
- "battery": electrode, anode, cathode, battery
- "magnet": magnetic, ferromagnetic, magnetization
- "catalyst": catalytic, electrocatalyst, catalyst
- "optoelectronics": LED, detector, optoelectronic
- "structural": aerospace, mechanical, structural
- "general": If unclear

**CRITICAL RULES:**
1. ALL fields must be populated (no "N/A", no empty strings, no null for required fields except where explicitly allowed)
2. threshold_value MUST be a NUMBER or null (not string)
3. operator MUST be one of: =, >, <, >=, <=, range
4. If operator is "range", BOTH range_start and range_end MUST be numbers (not null)
5. domain MUST be an ARRAY (even if ["general"])
6. evidence_strength MUST be "strong", "medium", or "weak" (NOT "moderate")
7. uncertainty should be calculated as (1 - confidence) if not explicitly stated
8. edge_cases and fails_for MUST be arrays (can be empty [])
9. If abstract has NO quantitative rules, return: []
10. Do NOT return vague text rules without numeric thresholds

**If you cannot extract quantitative data with ALL required fields, return empty array: []**

Return ONLY a JSON array. No markdown, no explanation, no additional text."""

    def validate_rule_schema(self, rule: dict) -> bool:
        """
        Validate rule has required fields with valid values.
        
        Args:
            rule: Rule dictionary to validate (can be raw or enhanced)
            
        Returns:
            True if rule has all required fields with valid values, False otherwise
        """
        required_fields = ['rule_type', 'property', 'threshold_value', 'operator', 'domain']
        
        for field in required_fields:
            value = rule.get(field)
            # Check if field is missing, None, 'N/A', or empty string
            if value is None or value == 'N/A' or value == '':
                logger.debug(f"Validation failed: field '{field}' is missing or invalid: {value}")
                return False
        
        # Additional validation
        # threshold_value must be a number (not string, not None)
        threshold_value = rule.get('threshold_value')
        if not isinstance(threshold_value, (int, float)):
            logger.debug(f"Validation failed: threshold_value is not a number: {type(threshold_value)}, value: {threshold_value}")
            return False
        
        # operator must be valid
        valid_operators = ['>', '<', '=', '>=', '<=', 'range']
        operator = rule.get('operator')
        if operator not in valid_operators:
            logger.debug(f"Validation failed: operator '{operator}' is not valid")
            return False
        
        # If operator is "range", both range_start and range_end must be numbers
        if operator == 'range':
            range_start = rule.get('range_start')
            range_end = rule.get('range_end')
            if not isinstance(range_start, (int, float)) or not isinstance(range_end, (int, float)):
                logger.debug(f"Validation failed: operator 'range' requires both range_start and range_end to be numbers")
                return False
        
        # domain must be an array (or at least not None/empty)
        domain = rule.get('domain')
        if not domain:
            logger.debug(f"Validation failed: domain is missing or empty: {domain}")
            return False
        
        # domain should be a list/array (handle backward compatibility with string)
        if isinstance(domain, str):
            # String is acceptable but we prefer array - this is backward compatible
            pass
        elif isinstance(domain, list):
            # Array must not be empty
            if len(domain) == 0:
                logger.debug(f"Validation failed: domain array is empty")
                return False
        else:
            logger.debug(f"Validation failed: domain is not string or array: {type(domain)}")
            return False
        
        # property must not be empty string
        property_name = rule.get('property')
        if not property_name or property_name.strip() == '':
            logger.debug(f"Validation failed: property is empty")
            return False
        
        # rule_type must be valid
        valid_rule_types = ["chemical_constraint", "stability", "band_gap", "mechanical", "synthesis", "phase_stability"]
        rule_type = rule.get('rule_type')
        if rule_type not in valid_rule_types:
            logger.debug(f"Validation failed: rule_type '{rule_type}' is not valid")
            return False
        
        return True

    def extract_rules(self, abstract: str, paper_id: str, paper_title: str = "", publication_year: Optional[int] = None) -> List[Dict]:
        """
        Extract quantitative, domain-aware rules from a paper abstract.
        
        Rules are enhanced with:
        - Frequency-based confidence adjustment
        - Domain identification
        - Statistical confidence calculation
        - Validation and normalization
        - Schema validation with retry logic

        Args:
            abstract: Paper abstract text
            paper_id: Unique identifier for the source paper
            paper_title: Optional paper title for context
            publication_year: Optional publication year

        Returns:
            List of enhanced rule dictionaries with quantitative fields
        """
        if not abstract or len(abstract.strip()) < 50:
            logger.warning(f"Abstract too short for paper {paper_id}, skipping")
            return []

        try:
            # Step 1: Initial extraction
            prompt = self.extraction_prompt_template.format(abstract=abstract)
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse and enhance rules
            raw_rules = self._parse_rules_from_response(response_text, paper_id, abstract, paper_title, publication_year)
            
            # Step 2: Validate schema
            valid_rules = [r for r in raw_rules if self.validate_rule_schema(r)]
            invalid_count = len(raw_rules) - len(valid_rules)
            
            # Step 3: Retry logic if too many invalid
            if len(raw_rules) > 0 and len(valid_rules) < len(raw_rules) * 0.5:
                logger.warning(
                    f"Only {len(valid_rules)}/{len(raw_rules)} rules passed validation for paper {paper_id}. "
                    f"Retrying with stricter prompt..."
                )
                
                # Retry with stricter prompt
                stricter_prompt = self._get_stricter_prompt(abstract, invalid_count)
                retry_response = self.llm.invoke(stricter_prompt)
                retry_response_text = retry_response.content if hasattr(retry_response, 'content') else str(retry_response)
                retry_rules = self._parse_rules_from_response(retry_response_text, paper_id, abstract, paper_title, publication_year)
                
                retry_valid = [r for r in retry_rules if self.validate_rule_schema(r)]
                
                if len(retry_valid) > len(valid_rules):
                    logger.info(f"Retry improved validation: {len(retry_valid)}/{len(retry_rules)} rules valid")
                    valid_rules = retry_valid
                    raw_rules = retry_rules  # Update for fallback processing
            
            # Step 4: Graceful fallback - accept invalid rules but flag them
            all_rules = []
            for rule in raw_rules:
                if self.validate_rule_schema(rule):
                    all_rules.append(rule)
                else:
                    # Flag incomplete schemas with low confidence
                    rule['confidence'] = min(rule.get('confidence', 0.5), 0.5)
                    rule['statistical_confidence'] = min(rule.get('statistical_confidence', 0.5), 0.5)
                    rule['validation_status'] = 'incomplete_schema'
                    logger.warning(
                        f"Rule extracted but schema incomplete for paper {paper_id}: "
                        f"rule_type={rule.get('rule_type')}, property={rule.get('property')}, "
                        f"domain={rule.get('domain')}"
                    )
                    # Still add the rule but with low confidence
                    all_rules.append(rule)
            
            # Log validation statistics
            total_extracted = len(raw_rules)
            total_valid = len([r for r in all_rules if self.validate_rule_schema(r)])
            total_incomplete = len([r for r in all_rules if r.get('validation_status') == 'incomplete_schema'])
            
            logger.info(
                f"Paper {paper_id}: Extracted {total_extracted} rules, "
                f"{total_valid} valid schema, {total_incomplete} incomplete schema"
            )
            
            # Filter by confidence threshold
            filtered_rules = [
                r for r in all_rules 
                if r.get('statistical_confidence', r.get('confidence', 0)) >= self.min_confidence
            ]
            
            logger.info(
                f"Filtered to {len(filtered_rules)} rules (confidence >= {self.min_confidence}) "
                f"from {len(all_rules)} total extracted from paper {paper_id}"
            )
            
            return filtered_rules

        except Exception as e:
            logger.error(f"Error extracting rules from paper {paper_id}: {e}")
            return []

    def _parse_rules_from_response(self, response_text: str, paper_id: str, abstract: str, 
                                   paper_title: str = "", publication_year: Optional[int] = None) -> List[Dict]:
        """
        Parse rules from LLM response and enhance with frequency-based confidence.
        
        Args:
            response_text: Raw LLM response text
            paper_id: Source paper ID
            abstract: Original abstract for frequency analysis
            paper_title: Paper title
            publication_year: Publication year
            
        Returns:
            List of parsed and enhanced rule dictionaries
        """
        rules = []

        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            # Parse JSON
            parsed_rules = json.loads(response_text)
            if not isinstance(parsed_rules, list):
                parsed_rules = [parsed_rules]

            # Process each rule
            for raw_rule in parsed_rules:
                if isinstance(raw_rule, dict):
                    # Store validation status before enhancement
                    was_valid_raw = self.validate_rule_schema(raw_rule)
                    
                    # Enhance rule (even if invalid - we'll flag it later)
                    enhanced_rule = self._enhance_rule(raw_rule, abstract, paper_id, paper_title, publication_year)
                    if enhanced_rule:
                        # Preserve validation status from raw rule
                        if not was_valid_raw:
                            enhanced_rule['_was_invalid_raw'] = True
                        rules.append(enhanced_rule)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from response for paper {paper_id}: {e}")
            logger.debug(f"Response text: {response_text[:200]}")

        except Exception as e:
            logger.error(f"Error parsing rules from response for paper {paper_id}: {e}")

        return rules

    def _enhance_rule(self, rule: Dict, abstract: str, paper_id: str, 
                     paper_title: str = "", publication_year: Optional[int] = None) -> Optional[Dict]:
        """
        Enhance a rule with frequency-based confidence, validation, and normalization.
        
        Args:
            rule: Raw rule dictionary from LLM
            abstract: Original abstract for frequency analysis
            paper_id: Source paper ID
            paper_title: Paper title
            publication_year: Publication year
            
        Returns:
            Enhanced rule dictionary or None if invalid
        """
        # Extract rule text (required)
        rule_text = rule.get("rule_text", "").strip()
        if not rule_text or len(rule_text) < 10:
            return None

        # Validate quantitative content
        if not self._has_numeric_content(rule_text):
            logger.debug(f"Skipping rule without numeric content: {rule_text[:50]}...")
            return None

        # Extract and validate fields
        rule_type = rule.get("rule_type", "stability")
        property_name = rule.get("property", "")
        threshold_value = rule.get("threshold_value")
        threshold_unit = rule.get("threshold_unit", "")
        operator = rule.get("operator", ">")
        # Normalize operator: convert "in_range" to "range" for backward compatibility
        if operator == "in_range":
            operator = "range"
        range_start = rule.get("range_start")
        range_end = rule.get("range_end")
        application = rule.get("application", "")
        domain_raw = rule.get("domain", "general")
        evidence_strength_raw = rule.get("evidence_strength", "medium")
        # Normalize evidence_strength: convert "moderate" to "medium"
        if evidence_strength_raw == "moderate":
            evidence_strength = "medium"
        else:
            evidence_strength = evidence_strength_raw if evidence_strength_raw in ["strong", "medium", "weak"] else "medium"
        statistical_confidence = float(rule.get("statistical_confidence", rule.get("confidence", 0.7)))
        confidence = float(rule.get("confidence", statistical_confidence))
        # Calculate uncertainty as (1 - confidence) if not provided or if it doesn't make sense
        uncertainty_raw = rule.get("uncertainty")
        if uncertainty_raw is None:
            uncertainty = round(1.0 - confidence, 3)
        else:
            uncertainty = float(uncertainty_raw)
            # Ensure uncertainty + confidence ≈ 1.0 (within 0.1 tolerance)
            if abs((uncertainty + confidence) - 1.0) > 0.1:
                uncertainty = round(1.0 - confidence, 3)
        
        # Extract new fields
        edge_cases_raw = rule.get("edge_cases", [])
        fails_for_raw = rule.get("fails_for", [])
        evidence_count = rule.get("evidence_count")
        validated_materials_raw = rule.get("validated_materials", [])
        
        # Ensure edge_cases and fails_for are arrays
        edge_cases = edge_cases_raw if isinstance(edge_cases_raw, list) else ([] if not edge_cases_raw else [str(edge_cases_raw)])
        fails_for = fails_for_raw if isinstance(fails_for_raw, list) else ([] if not fails_for_raw else [str(fails_for_raw)])
        validated_materials = validated_materials_raw if isinstance(validated_materials_raw, list) else ([] if not validated_materials_raw else [str(validated_materials_raw)])

        # Validate rule_type
        valid_rule_types = ["chemical_constraint", "stability", "band_gap", "mechanical", "synthesis", "phase_stability"]
        if rule_type not in valid_rule_types or rule_type in [None, "N/A", ""]:
            rule_type = "stability"  # Default

        # Handle domain - convert string to array if needed (backward compatibility)
        if isinstance(domain_raw, list):
            domain = domain_raw
        elif isinstance(domain_raw, str) and domain_raw not in [None, "N/A", ""]:
            domain = [domain_raw]
        else:
            domain = ["general"]
        
        # Validate domain values
        valid_domains = ["general", "photovoltaics", "thermoelectric", "battery", "magnet", 
                        "catalyst", "optoelectronics", "structural"]
        domain = [d for d in domain if d in valid_domains]
        if not domain:
            domain = ["general"]

        # Calculate frequency-based confidence adjustment
        frequency_boost = self._calculate_frequency_boost(rule_text, abstract)
        
        # Adjust statistical confidence based on frequency
        adjusted_confidence = min(1.0, confidence + frequency_boost)
        
        # Adjust based on evidence strength
        if evidence_strength == "strong":
            adjusted_confidence = min(1.0, adjusted_confidence + 0.1)
        elif evidence_strength == "weak":
            adjusted_confidence = max(0.0, adjusted_confidence - 0.1)
        
        # Recalculate uncertainty based on adjusted confidence
        uncertainty = round(1.0 - adjusted_confidence, 3)
        
        # Determine validation_status
        validation_status = self._determine_validation_status(rule_type, property_name, evidence_count, rule_text)
        
        # Map rule_type to category
        category = self._map_rule_type_to_category(rule_type)

        # Build enhanced rule with all required fields
        enhanced_rule = {
            "rule_text": rule_text,
            "rule_type": rule_type,
            "property": property_name,
            "threshold_value": threshold_value,
            "threshold_unit": threshold_unit,
            "operator": operator,
            "range_start": range_start,
            "range_end": range_end,
            "application": application,
            "domain": domain,
            "category": category,
            "evidence_strength": evidence_strength,
            "statistical_confidence": round(adjusted_confidence, 3),
            "confidence": round(adjusted_confidence, 3),
            "uncertainty": uncertainty,
            "source_paper_id": paper_id,
            "source_section": "abstract",
            "publication_year": publication_year,
            "validation_status": validation_status,
            "edge_cases": edge_cases,
            "fails_for": fails_for,
            "evidence_count": evidence_count,
            "validated_materials": validated_materials
        }

        return enhanced_rule

    def _get_stricter_prompt(self, abstract: str, invalid_count: int) -> str:
        """
        Generate a stricter prompt for retry when validation fails.
        
        Args:
            abstract: Paper abstract text
            invalid_count: Number of invalid rules from first attempt
            
        Returns:
            Stricter prompt string
        """
        return f"""You are an expert materials scientist. Extract ONLY quantitative, domain-specific rules with COMPLETE SCHEMA.

Abstract:
{abstract}

**CRITICAL: Previous extraction had {invalid_count} invalid rules with missing or "N/A" fields. This retry MUST return ONLY complete rules.**

**EVERY rule MUST have ALL these fields with REAL values (no "N/A", no null for required fields):**

REQUIRED FIELDS:
- "rule_type": MUST be one of: "chemical_constraint", "stability", "band_gap", "mechanical", "synthesis", "phase_stability"
- "property": MUST be a specific property name (e.g., "charge_neutrality", "formation_energy", "band_gap", "bulk_modulus", "energy_above_hull", "shear_modulus", "temperature", "pressure")
- "threshold_value": MUST be a NUMBER (e.g., 2.5, -1.0, 1000) or null - NOT "N/A"
- "threshold_unit": MUST be a unit string (e.g., "eV", "eV/atom", "GPa", "MPa", "K", "°C", "dimensionless", "Pauling scale")
- "operator": MUST be: "=", ">", "<", ">=", "<=", or "range"
- "range_start" and "range_end": MUST be numbers if operator is "range", null otherwise
- "domain": MUST be an ARRAY like ["photovoltaics"] or ["general"] - NOT string, NOT null
- "evidence_strength": MUST be "strong", "medium", or "weak" (NOT "moderate")
- "confidence": MUST be a NUMBER between 0.0 and 1.0
- "uncertainty": MUST be a NUMBER between 0.0 and 1.0 (should be 1 - confidence)
- "rule_text": MUST describe the quantitative rule
- "edge_cases": MUST be an array (can be empty [])
- "fails_for": MUST be an array (can be empty [])

**VALID EXAMPLE (copy this structure exactly):**
[
  {{
    "rule_type": "band_gap",
    "property": "band_gap",
    "threshold_value": 3.0,
    "threshold_unit": "eV",
    "operator": ">",
    "range_start": null,
    "range_end": null,
    "application": "Optoelectronics",
    "domain": ["photovoltaics", "optoelectronics"],
    "evidence_strength": "strong",
    "statistical_confidence": 0.85,
    "confidence": 0.85,
    "uncertainty": 0.15,
    "rule_text": "Band gap > 3.0 eV → Optoelectronics applications",
    "edge_cases": [],
    "fails_for": [],
    "evidence_count": null,
    "validated_materials": []
  }}
]

**CRITICAL:**
- If you cannot extract a rule with ALL required fields populated (no nulls, no "N/A"), DO NOT include it
- Return [] if abstract has no quantitative rules with complete schema
- domain MUST be an array: ["general"] or ["photovoltaics"] NOT "general" as string

Return ONLY valid JSON array. No markdown, no explanation."""

    def _calculate_frequency_boost(self, rule_text: str, abstract: str) -> float:
        """
        Calculate confidence boost based on how often rule concepts appear in abstract.
        
        Args:
            rule_text: Rule text to search for
            abstract: Abstract text
            
        Returns:
            Frequency boost (0.0 to 0.15)
        """
        # Extract key terms from rule
        key_terms = self._extract_key_terms(rule_text)
        
        # Count occurrences in abstract
        abstract_lower = abstract.lower()
        mentions = sum(1 for term in key_terms if term.lower() in abstract_lower)
        
        # Boost: 0.05 per mention, max 0.15
        boost = min(0.15, mentions * 0.05)
        return boost

    def _extract_key_terms(self, rule_text: str) -> List[str]:
        """Extract key terms from rule text for frequency matching."""
        # Extract property names, values, and applications
        terms = []
        
        # Common property names
        properties = ["formation energy", "band gap", "bulk modulus", "energy above hull", 
                     "shear modulus", "temperature", "pressure"]
        for prop in properties:
            if prop.lower() in rule_text.lower():
                terms.append(prop)
        
        # Extract numbers (as potential thresholds)
        numbers = re.findall(r'\d+\.?\d*', rule_text)
        terms.extend(numbers[:3])  # Limit to first 3 numbers
        
        return terms

    def _count_rule_mentions(self, rule_text: str, abstract: str) -> int:
        """Count how many times rule concepts are mentioned in abstract."""
        key_terms = self._extract_key_terms(rule_text)
        abstract_lower = abstract.lower()
        return sum(1 for term in key_terms if term.lower() in abstract_lower)

    def _determine_validation_status(self, rule_type: str, property_name: str, evidence_count: Optional[int], rule_text: str) -> str:
        """
        Determine validation_status based on rule characteristics.
        
        Args:
            rule_type: Type of rule
            property_name: Property name
            evidence_count: Number of evidence points if available
            rule_text: Rule text for pattern matching
            
        Returns:
            "physics_based", "validated", or "extracted"
        """
        # Check for physics-based rules (fundamental laws)
        physics_based_keywords = ["charge neutrality", "charge neutral", "pauling", "electronegativity", 
                                  "conservation", "thermodynamic", "fundamental"]
        rule_text_lower = rule_text.lower()
        property_lower = property_name.lower()
        
        if rule_type == "chemical_constraint":
            return "physics_based"
        
        if any(keyword in rule_text_lower or keyword in property_lower for keyword in physics_based_keywords):
            return "physics_based"
        
        # Check if evidence_count > 1000
        if evidence_count is not None and evidence_count > 1000:
            return "validated"
        
        # Default to extracted
        return "extracted"
    
    def _map_rule_type_to_category(self, rule_type: str) -> str:
        """Map new rule_type to legacy category for backward compatibility."""
        mapping = {
            "chemical_constraint": "stability",
            "stability": "stability",
            "band_gap": "property_application",
            "mechanical": "property_application",
            "synthesis": "synthesis",
            "phase_stability": "stability"
        }
        return mapping.get(rule_type, "material_property")

    def _has_numeric_content(self, rule_text: str) -> bool:
        """
        Check if a rule contains numeric values, thresholds, or quantitative indicators.
        
        Args:
            rule_text: The rule text to check
            
        Returns:
            True if rule contains numeric content, False otherwise
        """
        # Pattern to match numbers (including decimals, scientific notation)
        number_pattern = r'\d+\.?\d*'
        
        # Pattern to match comparison operators
        comparison_pattern = r'[<>≤≥≈~=]'
        
        # Common units in materials science
        units_pattern = r'\b(eV|GPa|MPa|K|°C|%|g/cm³|mol|ratio|Angstrom)\b'
        
        # Check for numbers
        has_number = bool(re.search(number_pattern, rule_text))
        
        # Check for comparison operators followed by potential numbers
        has_comparison = bool(re.search(comparison_pattern, rule_text))
        
        # Check for units (often indicates quantitative content)
        has_units = bool(re.search(units_pattern, rule_text, re.IGNORECASE))
        
        return has_number or (has_comparison and has_number) or has_units

    def extract_rules_from_papers(self, papers: List[Dict]) -> List[Dict]:
        """
        Extract quantitative, domain-aware rules from multiple papers.
        
        All rules are filtered to keep only those with confidence >= min_confidence.

        Args:
            papers: List of paper dictionaries with 'abstract', 'url', 'title', etc.

        Returns:
            Combined list of all extracted rules (already filtered by confidence threshold)
        """
        all_rules = []

        for paper in papers:
            abstract = paper.get("abstract", "")
            paper_id = paper.get("url", "")
            paper_title = paper.get("title", "")
            
            # Extract publication year if available
            publication_year = None
            date_published = paper.get("date_published", "")
            if date_published:
                year_match = re.search(r'\d{4}', date_published)
                if year_match:
                    try:
                        publication_year = int(year_match.group())
                    except ValueError:
                        pass

            if not paper_id:
                # Generate a simple ID from title
                paper_id = paper_title[:50].replace(" ", "_") if paper_title else f"paper_{len(all_rules)}"

            rules = self.extract_rules(abstract, paper_id, paper_title, publication_year)
            all_rules.extend(rules)

        logger.info(
            f"Extracted {len(all_rules)} total quantitative rules "
            f"(confidence >= {self.min_confidence}) from {len(papers)} papers"
        )
        return all_rules
