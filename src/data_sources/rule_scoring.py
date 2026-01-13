"""
Rule Scoring Engine

Provides material scoring functionality based on extracted quantitative rules.
Implements domain-specific scoring with weighted rule matching.
"""

import logging
from typing import List, Dict, Optional, Tuple
from src.data_sources.rule_storage import RuleStorage

logger = logging.getLogger(__name__)


class RuleScoringEngine:
    """
    Scores materials based on extracted quantitative rules.
    
    Features:
    - Domain-specific scoring weights
    - Rule matching with threshold evaluation
    - Violation detection
    - Combined scoring logic
    """

    def __init__(self, rules_dir: str = "rules"):
        """
        Initialize the scoring engine.
        
        Args:
            rules_dir: Directory path for rule storage
        """
        self.storage = RuleStorage(rules_dir)
        
        # Domain-specific weights for different properties
        self.domain_weights = {
            "photovoltaics": {
                "band_gap": 0.4,
                "stability": 0.3,
                "formation_energy": 0.2,
                "energy_above_hull": 0.1
            },
            "thermoelectric": {
                "band_gap": 0.3,
                "stability": 0.25,
                "formation_energy": 0.2,
                "energy_above_hull": 0.15,
                "thermal_conductivity": 0.1
            },
            "battery": {
                "stability": 0.35,
                "formation_energy": 0.3,
                "energy_above_hull": 0.2,
                "mechanical": 0.15
            },
            "optoelectronics": {
                "band_gap": 0.5,
                "stability": 0.3,
                "formation_energy": 0.2
            },
            "structural": {
                "mechanical": 0.5,
                "stability": 0.3,
                "formation_energy": 0.2
            },
            "general": {
                "stability": 0.4,
                "formation_energy": 0.3,
                "energy_above_hull": 0.2,
                "band_gap": 0.1
            }
        }

    def score_material(self, material_properties: Dict, domain: str = "general") -> Dict:
        """
        Score a material based on extracted rules.
        
        Args:
            material_properties: Dictionary of material properties:
                - formation_energy (eV/atom)
                - energy_above_hull (eV/atom)
                - band_gap (eV)
                - bulk_modulus (GPa)
                - shear_modulus (GPa)
                - etc.
            domain: Target domain ("photovoltaics", "thermoelectric", "battery", etc.)
            
        Returns:
            Dictionary with scoring results:
            {
                "overall_score": 0.0-1.0,
                "domain_score": 0.0-1.0,
                "stability_score": 0.0-1.0,
                "property_score": 0.0-1.0,
                "synthesis_score": 0.0-1.0,
                "matched_rules": [list of rules that matched],
                "violated_rules": [list of rules that failed],
                "reasoning": "Why this material scored X"
            }
        """
        # Get relevant rules for domain
        rules = self.storage.get_rules(domain=domain, min_confidence=0.6)
        
        # Also get general rules
        general_rules = self.storage.get_rules(domain="general", min_confidence=0.6)
        all_rules = rules + general_rules
        
        # Remove duplicates
        seen_rule_ids = set()
        unique_rules = []
        for rule in all_rules:
            rule_id = rule.get("rule_id")
            if rule_id and rule_id not in seen_rule_ids:
                seen_rule_ids.add(rule_id)
                unique_rules.append(rule)
        
        # Evaluate rules
        matched_rules = []
        violated_rules = []
        rule_scores = {}
        
        for rule in unique_rules:
            match_result = self._evaluate_rule(rule, material_properties)
            
            if match_result["matched"]:
                matched_rules.append(rule)
                rule_scores[rule.get("rule_id")] = match_result["score"]
            else:
                violated_rules.append(rule)
        
        # Calculate domain-specific scores
        domain_score = self._calculate_domain_score(matched_rules, violated_rules, domain, material_properties)
        
        # Calculate component scores
        stability_score = self._calculate_stability_score(matched_rules, violated_rules, material_properties)
        property_score = self._calculate_property_score(matched_rules, violated_rules, material_properties)
        synthesis_score = self._calculate_synthesis_score(matched_rules, violated_rules, material_properties)
        
        # Calculate overall score (weighted combination)
        overall_score = self._calculate_overall_score(
            domain_score, stability_score, property_score, synthesis_score, domain
        )
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            overall_score, domain_score, matched_rules, violated_rules, domain
        )
        
        return {
            "overall_score": round(overall_score, 3),
            "domain_score": round(domain_score, 3),
            "stability_score": round(stability_score, 3),
            "property_score": round(property_score, 3),
            "synthesis_score": round(synthesis_score, 3),
            "matched_rules": matched_rules[:10],  # Limit to top 10
            "violated_rules": violated_rules[:10],  # Limit to top 10
            "reasoning": reasoning,
            "total_rules_evaluated": len(unique_rules),
            "rules_matched": len(matched_rules),
            "rules_violated": len(violated_rules)
        }

    def _evaluate_rule(self, rule: Dict, material_properties: Dict) -> Dict:
        """
        Evaluate if a material matches a rule.
        
        Args:
            rule: Rule dictionary
            material_properties: Material properties dictionary
            
        Returns:
            Dictionary with match result:
            {
                "matched": bool,
                "score": float (0.0-1.0),
                "reason": str
            }
        """
        property_name = rule.get("property", "")
        operator = rule.get("operator", ">")
        threshold_value = rule.get("threshold_value")
        range_start = rule.get("range_start")
        range_end = rule.get("range_end")
        uncertainty = rule.get("uncertainty", 0.0)
        confidence = rule.get("statistical_confidence", rule.get("confidence", 0.7))
        
        # Map property names to material_properties keys
        property_mapping = {
            "formation_energy": "formation_energy",
            "energy_above_hull": "energy_above_hull",
            "band_gap": "band_gap",
            "bulk_modulus": "bulk_modulus",
            "shear_modulus": "shear_modulus",
            "temperature": "temperature",
            "pressure": "pressure"
        }
        
        # Get material property value
        material_value = None
        for key, value in property_mapping.items():
            if property_name.lower() == key.lower():
                material_value = material_properties.get(key)
                break
        
        if material_value is None:
            # Try direct lookup
            material_value = material_properties.get(property_name)
        
        if material_value is None:
            return {
                "matched": False,
                "score": 0.0,
                "reason": f"Property {property_name} not available in material properties"
            }
        
        # Evaluate rule
        matched = False
        reason = ""
        
        if operator == "in_range" and range_start is not None and range_end is not None:
            # Range-based rule
            if range_start <= material_value <= range_end:
                matched = True
                reason = f"{property_name} = {material_value} is in range [{range_start}, {range_end}]"
            else:
                matched = False
                reason = f"{property_name} = {material_value} is outside range [{range_start}, {range_end}]"
        
        elif operator == ">" and threshold_value is not None:
            if material_value > threshold_value:
                matched = True
                reason = f"{property_name} = {material_value} > {threshold_value}"
            else:
                matched = False
                reason = f"{property_name} = {material_value} <= {threshold_value} (violated)"
        
        elif operator == "<" and threshold_value is not None:
            if material_value < threshold_value:
                matched = True
                reason = f"{property_name} = {material_value} < {threshold_value}"
            else:
                matched = False
                reason = f"{property_name} = {material_value} >= {threshold_value} (violated)"
        
        elif operator == "=" and threshold_value is not None:
            # Allow for uncertainty
            if abs(material_value - threshold_value) <= (uncertainty + 0.1):
                matched = True
                reason = f"{property_name} = {material_value} ≈ {threshold_value}"
            else:
                matched = False
                reason = f"{property_name} = {material_value} ≠ {threshold_value}"
        
        else:
            return {
                "matched": False,
                "score": 0.0,
                "reason": f"Unsupported operator or missing threshold: {operator}"
            }
        
        # Calculate score based on match and confidence
        if matched:
            score = confidence  # Use rule confidence as score
        else:
            score = 0.0
        
        return {
            "matched": matched,
            "score": score,
            "reason": reason
        }

    def _calculate_domain_score(self, matched_rules: List[Dict], violated_rules: List[Dict],
                                domain: str, material_properties: Dict) -> float:
        """Calculate domain-specific score."""
        if not matched_rules and not violated_rules:
            return 0.5  # Neutral if no rules
        
        # Get domain-specific rules
        domain_rules = [r for r in matched_rules + violated_rules if r.get("domain") == domain]
        
        if not domain_rules:
            return 0.5  # Neutral if no domain-specific rules
        
        # Weight by rule confidence
        total_weight = 0.0
        matched_weight = 0.0
        
        for rule in domain_rules:
            confidence = rule.get("statistical_confidence", rule.get("confidence", 0.7))
            weight = confidence
            
            total_weight += weight
            if rule in matched_rules:
                matched_weight += weight
        
        if total_weight == 0:
            return 0.5
        
        return matched_weight / total_weight

    def _calculate_stability_score(self, matched_rules: List[Dict], violated_rules: List[Dict],
                                  material_properties: Dict) -> float:
        """Calculate stability score based on stability rules."""
        stability_rules = [r for r in matched_rules + violated_rules 
                         if r.get("rule_type") == "stability" or "stability" in r.get("category", "").lower()]
        
        if not stability_rules:
            # Fallback: use formation_energy and energy_above_hull directly
            fe = material_properties.get("formation_energy")
            ehull = material_properties.get("energy_above_hull")
            
            score = 0.5
            if fe is not None:
                if fe < -1.0:
                    score += 0.2
                elif fe < 0:
                    score += 0.1
            if ehull is not None:
                if ehull < 0.05:
                    score += 0.2
                elif ehull < 0.1:
                    score += 0.1
            
            return min(1.0, score)
        
        # Calculate based on matched/violated stability rules
        total_weight = sum(r.get("statistical_confidence", 0.7) for r in stability_rules)
        matched_weight = sum(r.get("statistical_confidence", 0.7) for r in stability_rules if r in matched_rules)
        
        if total_weight == 0:
            return 0.5
        
        return matched_weight / total_weight

    def _calculate_property_score(self, matched_rules: List[Dict], violated_rules: List[Dict],
                                 material_properties: Dict) -> float:
        """Calculate property score based on property-application rules."""
        property_rules = [r for r in matched_rules + violated_rules 
                         if r.get("rule_type") in ["band_gap", "mechanical"] 
                         or "property_application" in r.get("category", "").lower()]
        
        if not property_rules:
            return 0.5
        
        total_weight = sum(r.get("statistical_confidence", 0.7) for r in property_rules)
        matched_weight = sum(r.get("statistical_confidence", 0.7) for r in property_rules if r in matched_rules)
        
        if total_weight == 0:
            return 0.5
        
        return matched_weight / total_weight

    def _calculate_synthesis_score(self, matched_rules: List[Dict], violated_rules: List[Dict],
                                   material_properties: Dict) -> float:
        """Calculate synthesis feasibility score."""
        synthesis_rules = [r for r in matched_rules + violated_rules 
                          if r.get("rule_type") == "synthesis"]
        
        if not synthesis_rules:
            return 0.5
        
        total_weight = sum(r.get("statistical_confidence", 0.7) for r in synthesis_rules)
        matched_weight = sum(r.get("statistical_confidence", 0.7) for r in synthesis_rules if r in matched_rules)
        
        if total_weight == 0:
            return 0.5
        
        return matched_weight / total_weight

    def _calculate_overall_score(self, domain_score: float, stability_score: float,
                                 property_score: float, synthesis_score: float, domain: str) -> float:
        """Calculate overall weighted score."""
        # Get domain weights
        weights = self.domain_weights.get(domain, self.domain_weights["general"])
        
        # Map component scores to weights
        overall = (
            stability_score * weights.get("stability", 0.3) +
            property_score * weights.get("band_gap", 0.2) +
            synthesis_score * weights.get("formation_energy", 0.2) +
            domain_score * 0.3  # Domain-specific boost
        )
        
        return min(1.0, max(0.0, overall))

    def _generate_reasoning(self, overall_score: float, domain_score: float,
                           matched_rules: List[Dict], violated_rules: List[Dict],
                           domain: str) -> str:
        """Generate human-readable reasoning for the score."""
        reasoning_parts = []
        
        reasoning_parts.append(f"Overall score: {overall_score:.2f} (domain: {domain})")
        
        if matched_rules:
            top_rule = matched_rules[0]
            reasoning_parts.append(f"Matched {len(matched_rules)} rules, including: {top_rule.get('rule_text', 'N/A')[:80]}")
        
        if violated_rules:
            top_violation = violated_rules[0]
            reasoning_parts.append(f"Violated {len(violated_rules)} rules, including: {top_violation.get('rule_text', 'N/A')[:80]}")
        
        # Score interpretation
        if overall_score >= 0.8:
            reasoning_parts.append("High score: Material shows strong alignment with domain-specific rules.")
        elif overall_score >= 0.6:
            reasoning_parts.append("Moderate score: Material meets most criteria but has some limitations.")
        elif overall_score >= 0.4:
            reasoning_parts.append("Low score: Material violates several important rules.")
        else:
            reasoning_parts.append("Very low score: Material shows poor alignment with established rules.")
        
        return " | ".join(reasoning_parts)
