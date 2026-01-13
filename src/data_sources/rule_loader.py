"""
Rule Loader Module - ENHANCED VERSION

Loads rules at application startup and provides helper functions
for retrieving relevant rules based on material properties.
Enhanced to work with new quantitative schema while maintaining backward compatibility.
"""

import logging
from typing import List, Dict, Optional
from src.data_sources.rule_storage import RuleStorage

logger = logging.getLogger(__name__)


class RuleLoader:
    """Loads and caches rules for fast access with enhanced schema support."""

    def __init__(self, rules_dir: str = "rules"):
        """
        Initialize rule loader.

        Args:
            rules_dir: Directory path for rule JSON files
        """
        self.storage = RuleStorage(rules_dir)
        self._cached_rules: Optional[List[Dict]] = None
        self._cache_loaded = False

    def load_rules(self, force_reload: bool = False) -> List[Dict]:
        """
        Load all rules from storage (with caching).

        Args:
            force_reload: If True, reload from disk even if cached

        Returns:
            List of all rule dictionaries (normalized to enhanced schema)
        """
        if not self._cache_loaded or force_reload:
            self._cached_rules = self.storage.load_rules()
            # Normalize rules to ensure backward compatibility
            self._cached_rules = [self._normalize_rule(r) for r in self._cached_rules]
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._cached_rules)} rules into cache")

        return self._cached_rules or []

    def _normalize_rule(self, rule: Dict) -> Dict:
        """
        Normalize rule to ensure backward compatibility.
        
        Ensures all rules have both old and new schema fields.
        
        Args:
            rule: Rule dictionary (may be old or new format)
            
        Returns:
            Normalized rule dictionary
        """
        normalized = rule.copy()
        
        # Ensure backward compatibility fields exist
        if "statistical_confidence" not in normalized and "confidence" in normalized:
            normalized["statistical_confidence"] = normalized["confidence"]
        if "confidence" not in normalized and "statistical_confidence" in normalized:
            normalized["confidence"] = normalized["statistical_confidence"]
        
        # Ensure category exists (for backward compatibility)
        if "category" not in normalized:
            # Infer from rule_type
            rule_type = normalized.get("rule_type", "")
            type_to_category = {
                "stability": "stability",
                "band_gap": "property_application",
                "mechanical": "property_application",
                "synthesis": "synthesis",
                "phase_stability": "stability"
            }
            normalized["category"] = type_to_category.get(rule_type, "material_property")
        
        # Ensure domain exists
        if "domain" not in normalized:
            normalized["domain"] = "general"
        
        return normalized

    def get_rules_for_analysis(self, material_properties: Dict) -> List[Dict]:
        """
        Get relevant rules based on material properties.

        Args:
            material_properties: Dictionary of material properties (e.g., band_gap, density, etc.)

        Returns:
            List of relevant rule dictionaries
        """
        # Load rules if not cached
        if not self._cache_loaded:
            self.load_rules()

        all_rules = self._cached_rules or []
        relevant_rules = []

        # Extract key terms from material properties
        property_terms = []
        for key, value in material_properties.items():
            if value is not None:
                # Add property name as keyword
                property_terms.append(key.lower())

                # Add value-based keywords if value is numeric
                if isinstance(value, (int, float)):
                    # For band gap, add relevant categories
                    if "band_gap" in key.lower() or "bandgap" in key.lower():
                        if value > 3.0:
                            property_terms.append("high band gap")
                            property_terms.append("optoelectronics")
                        elif value > 0:
                            property_terms.append("semiconductor")
                    # For stability indicators
                    if "formation_energy" in key.lower() or "energy_above_hull" in key.lower():
                        if value < 0:
                            property_terms.append("stable")
                            property_terms.append("negative formation energy")
                elif isinstance(value, str):
                    # Add string values as keywords
                    property_terms.append(value.lower())

        # Search for relevant rules using keywords
        for term in property_terms:
            matching_rules = self.storage.search_rules(term)
            relevant_rules.extend(matching_rules)

        # Also search by property name directly
        for key in material_properties.keys():
            property_rules = self.storage.get_rules(property=key, min_confidence=0.6)
            relevant_rules.extend(property_rules)

        # Remove duplicates (by rule_id if available, otherwise by rule_text)
        seen = set()
        unique_rules = []
        for rule in relevant_rules:
            rule_id = rule.get("rule_id")
            if rule_id is not None:
                if rule_id not in seen:
                    seen.add(rule_id)
                    unique_rules.append(self._normalize_rule(rule))
            else:
                rule_text = rule.get("rule_text", "")
                if rule_text and rule_text not in seen:
                    seen.add(rule_text)
                    unique_rules.append(self._normalize_rule(rule))

        # Sort by relevance (confidence)
        unique_rules.sort(key=lambda r: r.get("statistical_confidence", r.get("confidence", 0.0)), reverse=True)

        logger.info(f"Found {len(unique_rules)} relevant rules for material properties")
        return unique_rules

    def get_rules_by_category(self, category: str) -> List[Dict]:
        """
        Get rules by category (backward compatibility method).

        Args:
            category: Rule category ("material_property", "synthesis", "stability", "property_application")

        Returns:
            List of rules in the specified category (normalized)
        """
        if not self._cache_loaded:
            self.load_rules()

        # Filter cached rules by category
        if self._cached_rules:
            filtered = [r for r in self._cached_rules if r.get("category") == category]
            return [self._normalize_rule(r) for r in filtered]
        else:
            rules = self.storage.load_rules(category=category)
            return [self._normalize_rule(r) for r in rules]

    def get_rules_by_domain(self, domain: str, min_confidence: float = 0.6) -> List[Dict]:
        """
        Get rules by domain (new method).

        Args:
            domain: Domain name ("photovoltaics", "thermoelectric", "battery", etc.)
            min_confidence: Minimum confidence threshold

        Returns:
            List of rules for the specified domain (normalized)
        """
        if not self._cache_loaded:
            self.load_rules()

        rules = self.storage.get_rules(domain=domain, min_confidence=min_confidence)
        return [self._normalize_rule(r) for r in rules]

    def get_rules_by_property(self, property_name: str, min_confidence: float = 0.6) -> List[Dict]:
        """
        Get rules by property name (new method).

        Args:
            property_name: Property name ("formation_energy", "band_gap", etc.)
            min_confidence: Minimum confidence threshold

        Returns:
            List of rules for the specified property (normalized)
        """
        if not self._cache_loaded:
            self.load_rules()

        rules = self.storage.get_rules(property=property_name, min_confidence=min_confidence)
        return [self._normalize_rule(r) for r in rules]

    def get_rules_by_type(self, rule_type: str, min_confidence: float = 0.6) -> List[Dict]:
        """
        Get rules by rule type (new method).

        Args:
            rule_type: Rule type ("stability", "band_gap", "mechanical", "synthesis", "phase_stability")
            min_confidence: Minimum confidence threshold

        Returns:
            List of rules of the specified type (normalized)
        """
        if not self._cache_loaded:
            self.load_rules()

        rules = self.storage.get_rules(rule_type=rule_type, min_confidence=min_confidence)
        return [self._normalize_rule(r) for r in rules]

    def get_rule_stats(self) -> Dict:
        """
        Get statistics about loaded rules.

        Returns:
            Dictionary with rule statistics
        """
        return self.storage.get_rule_stats()

    def reload_cache(self) -> None:
        """Reload rules from storage into cache."""
        self.load_rules(force_reload=True)

    def get_rules_for_material(self, material_properties: Dict, domain: Optional[str] = None) -> List[Dict]:
        """
        Get rules relevant for a specific material and optional domain.

        Args:
            material_properties: Dictionary of material properties
            domain: Optional domain filter

        Returns:
            List of relevant rules (normalized)
        """
        if domain:
            # Get domain-specific rules
            domain_rules = self.get_rules_by_domain(domain, min_confidence=0.6)
            
            # Filter by material properties
            relevant = []
            for rule in domain_rules:
                property_name = rule.get("property", "")
                if property_name and property_name in material_properties:
                    relevant.append(rule)
            
            return relevant
        else:
            # Use general method
            return self.get_rules_for_analysis(material_properties)
