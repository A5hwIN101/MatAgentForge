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

        self.extraction_prompt_template = """You are an expert materials scientist. Extract QUANTITATIVE, DOMAIN-SPECIFIC RULES from the following research paper abstract.

Abstract:
{abstract}

**CRITICAL: Extract rules in QUANTITATIVE FORMAT with domain context.**

**RULE TYPES TO EXTRACT:**

1. **Stability Rules** (with convex hull thresholds):
   - "Formation energy < -2.0 eV/atom → Thermodynamically stable"
   - "Energy above hull < 0.05 eV/atom → Stable ground state"
   - "0.05 < Energy above hull < 0.1 eV/atom → Metastable, synthesizable"
   - "Energy above hull > 0.1 eV/atom → Unlikely to synthesize"

2. **Band Gap Rules** (with domain-specific applications):
   - "Band gap 1.0-1.5 eV → Photovoltaics (optimal for solar cells)"
   - "Band gap 3.0-5.0 eV → Optoelectronics (UV detectors)"
   - "Band gap 0.1-0.5 eV → Thermoelectric (good Seebeck coefficient)"

3. **Mechanical Rules** (with structural applications):
   - "Bulk modulus > 200 GPa → Structural applications (aerospace)"
   - "Shear modulus > 100 GPa → High-strength materials (battery electrodes)"

4. **Synthesis Rules** (with feasibility confidence):
   - "Stoichiometry ratio 1:1:3 → Perovskite structure (feasible, 85% confidence)"
   - "Formation energy difference < 0.5 eV → Metastable synthesis possible"

5. **Phase Stability Rules**:
   - "Temperature > 1000°C → High-temperature phase stable"
   - "Pressure > 10 GPa → High-pressure polymorph"

**REQUIRED OUTPUT FORMAT (JSON):**
Each rule MUST follow this exact structure:
{{
  "rule_type": "stability|band_gap|mechanical|synthesis|phase_stability",
  "property": "formation_energy|band_gap|bulk_modulus|energy_above_hull|shear_modulus|temperature|pressure",
  "threshold_value": 2.5,  // Single value for >, <, = operators
  "threshold_unit": "eV|eV/atom|GPa|Angstrom|K|°C",
  "operator": "<|>|=|in_range",  // Use "in_range" for range-based rules
  "range_start": null,  // For range-based rules (e.g., "1.0-1.5 eV")
  "range_end": null,  // For range-based rules
  "application": "Thermodynamically stable|Optoelectronics|Structural material|Photovoltaics|Thermoelectric",
  "domain": "general|photovoltaics|thermoelectric|battery|magnet|catalyst|optoelectronics|structural",
  "evidence_strength": "strong|moderate|weak",  // Based on how explicitly stated
  "statistical_confidence": 0.85,  // 0.0-1.0, based on frequency in abstract and evidence
  "uncertainty": 0.1,  // Statistical uncertainty in threshold (e.g., ±0.1 eV)
  "rule_text": "Human-readable rule text with threshold"
}}

**CONFIDENCE SCORING GUIDELINES:**
- statistical_confidence should be based on:
  * Frequency: If rule mentioned multiple times in abstract → higher confidence
  * Evidence strength: "strong" = 0.85-1.0, "moderate" = 0.65-0.84, "weak" = 0.5-0.64
  * Explicit thresholds: Rules with exact numbers → higher confidence
  * Domain specificity: Domain-specific rules → higher confidence

**DOMAIN IDENTIFICATION:**
- Identify the primary domain from context:
  * "photovoltaics" / "PV" / "solar cell" → domain: "photovoltaics"
  * "thermoelectric" / "Seebeck" / "ZT" → domain: "thermoelectric"
  * "battery" / "electrode" / "anode" / "cathode" → domain: "battery"
  * "magnet" / "magnetic" / "ferromagnetic" → domain: "magnet"
  * "catalyst" / "catalytic" / "electrocatalyst" → domain: "catalyst"
  * "optoelectronic" / "LED" / "detector" → domain: "optoelectronics"
  * "structural" / "aerospace" / "mechanical" → domain: "structural"
  * If unclear → domain: "general"

**CRITICAL REQUIREMENTS:**
- ALL rules MUST have quantitative thresholds (numbers with units)
- ALL rules MUST specify domain (even if "general")
- Reject vague statements without thresholds
- Extract convex hull stability rules explicitly (energy_above_hull thresholds)
- Include uncertainty estimates when mentioned

Return ONLY a JSON array of rules. If no quantitative rules can be extracted, return [].

JSON only, no additional text:"""

    def extract_rules(self, abstract: str, paper_id: str, paper_title: str = "", publication_year: Optional[int] = None) -> List[Dict]:
        """
        Extract quantitative, domain-aware rules from a paper abstract.
        
        Rules are enhanced with:
        - Frequency-based confidence adjustment
        - Domain identification
        - Statistical confidence calculation
        - Validation and normalization

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
            prompt = self.extraction_prompt_template.format(abstract=abstract)
            response = self.llm.invoke(prompt)

            # Extract text from response
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse and enhance rules
            rules = self._parse_rules_from_response(response_text, paper_id, abstract, paper_title, publication_year)
            
            # Filter by confidence threshold
            filtered_rules = [
                r for r in rules 
                if r.get('statistical_confidence', r.get('confidence', 0)) >= self.min_confidence
            ]
            
            logger.info(
                f"Extracted {len(filtered_rules)} rules (confidence >= {self.min_confidence}) "
                f"from {len(rules)} total extracted from paper {paper_id}"
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
            for rule in parsed_rules:
                if isinstance(rule, dict):
                    enhanced_rule = self._enhance_rule(rule, abstract, paper_id, paper_title, publication_year)
                    if enhanced_rule:
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
        range_start = rule.get("range_start")
        range_end = rule.get("range_end")
        application = rule.get("application", "")
        domain = rule.get("domain", "general")
        evidence_strength = rule.get("evidence_strength", "moderate")
        statistical_confidence = float(rule.get("statistical_confidence", 0.7))
        uncertainty = float(rule.get("uncertainty", 0.0))

        # Validate rule_type
        valid_rule_types = ["stability", "band_gap", "mechanical", "synthesis", "phase_stability"]
        if rule_type not in valid_rule_types:
            rule_type = "stability"  # Default

        # Validate domain
        valid_domains = ["general", "photovoltaics", "thermoelectric", "battery", "magnet", 
                        "catalyst", "optoelectronics", "structural"]
        if domain not in valid_domains:
            domain = "general"

        # Calculate frequency-based confidence adjustment
        frequency_boost = self._calculate_frequency_boost(rule_text, abstract)
        
        # Adjust statistical confidence based on frequency
        adjusted_confidence = min(1.0, statistical_confidence + frequency_boost)
        
        # Adjust based on evidence strength
        if evidence_strength == "strong":
            adjusted_confidence = min(1.0, adjusted_confidence + 0.1)
        elif evidence_strength == "weak":
            adjusted_confidence = max(0.0, adjusted_confidence - 0.1)

        # Build enhanced rule
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
            "category": self._map_rule_type_to_category(rule_type),  # For backward compatibility
            "evidence_strength": evidence_strength,
            "statistical_confidence": round(adjusted_confidence, 3),
            "confidence": round(adjusted_confidence, 3),  # For backward compatibility
            "uncertainty": round(uncertainty, 3),
            "source_paper_id": paper_id,
            "source_title": paper_title,
            "source_section": "abstract",
            "publication_year": publication_year,
            "rule_frequency": self._count_rule_mentions(rule_text, abstract),
            "validation_status": "extracted"
        }

        return enhanced_rule

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

    def _map_rule_type_to_category(self, rule_type: str) -> str:
        """Map new rule_type to legacy category for backward compatibility."""
        mapping = {
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
