"""
Rule Storage System - ENHANCED VERSION

Manages persistent storage of extracted rules with:
- Enhanced rule schema with quantitative fields
- Rule validation and filtering
- Cross-paper validation
- Multi-dimensional indexing (property, domain, application, rule_type)
- Quality metrics and reporting
"""

import json
import hashlib
import os
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RuleStorage:
    """Manages storage and retrieval of extracted rules with enhanced schema."""

    def __init__(self, rules_dir: str = "rules"):
        """
        Initialize rule storage.

        Args:
            rules_dir: Directory path for storing rule JSON files
        """
        self.rules_dir = rules_dir
        self.rules_file = os.path.join(rules_dir, "extracted_rules.json")
        self.metadata_file = os.path.join(rules_dir, "rule_metadata.json")
        self.index_file = os.path.join(rules_dir, "rule_index.json")
        self.validation_file = os.path.join(rules_dir, "rule_validation.json")

        # Create directory if it doesn't exist
        os.makedirs(rules_dir, exist_ok=True)

        # Initialize files if they don't exist
        self._initialize_files()

    def _initialize_files(self) -> None:
        """Initialize JSON files if they don't exist."""
        if not os.path.exists(self.rules_file):
            with open(self.rules_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

        if not os.path.exists(self.metadata_file):
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

        if not os.path.exists(self.index_file):
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

        if not os.path.exists(self.validation_file):
            with open(self.validation_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

    def _hash_rule_text(self, rule_text: str) -> str:
        """
        Generate hash for rule text (for deduplication).

        Args:
            rule_text: Rule text to hash

        Returns:
            SHA256 hash of the normalized rule text
        """
        normalized = rule_text.lower().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _load_rules(self) -> List[Dict]:
        """Load all rules from JSON file."""
        try:
            with open(self.rules_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error loading rules file: {e}. Initializing empty list.")
            return []

    def _save_rules(self, rules: List[Dict]) -> None:
        """Save rules to JSON file."""
        try:
            with open(self.rules_file, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving rules file: {e}")
            raise

    def _load_metadata(self) -> Dict:
        """Load metadata from JSON file."""
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error loading metadata file: {e}. Initializing empty dict.")
            return {}

    def _save_metadata(self, metadata: Dict) -> None:
        """Save metadata to JSON file."""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata file: {e}")
            raise

    def _load_index(self) -> Dict:
        """Load index from JSON file."""
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error loading index file: {e}. Initializing empty dict.")
            return {}

    def _save_index(self, index: Dict) -> None:
        """Save index to JSON file."""
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving index file: {e}")
            raise

    def _load_validation(self) -> Dict:
        """Load validation data from JSON file."""
        try:
            with open(self.validation_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error loading validation file: {e}. Initializing empty dict.")
            return {}

    def _save_validation(self, validation: Dict) -> None:
        """Save validation data to JSON file."""
        try:
            with open(self.validation_file, "w", encoding="utf-8") as f:
                json.dump(validation, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving validation file: {e}")
            raise

    def _validate_rule(self, rule: Dict) -> Tuple[bool, str]:
        """
        Validate a rule against quality criteria.
        
        Args:
            rule: Rule dictionary to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check confidence threshold
        confidence = rule.get("statistical_confidence", rule.get("confidence", 0))
        if confidence < 0.6:
            return False, f"Confidence too low: {confidence:.2f} < 0.6"
        
        # Check uncertainty (flag high uncertainty)
        uncertainty = rule.get("uncertainty", 0)
        if uncertainty > 0.3:
            logger.warning(f"Rule has high uncertainty: {uncertainty:.2f}")
        
        # Check for required quantitative fields
        if not rule.get("property") and not rule.get("rule_text"):
            return False, "Missing property or rule_text"
        
        # Check for numeric content in rule_text
        rule_text = rule.get("rule_text", "")
        if not self._has_numeric_content(rule_text):
            return False, "Rule text lacks numeric content"
        
        return True, "Valid"

    def _has_numeric_content(self, text: str) -> bool:
        """Check if text contains numeric content."""
        import re
        number_pattern = r'\d+\.?\d*'
        return bool(re.search(number_pattern, text))

    def _normalize_rule(self, rule: Dict) -> Dict:
        """
        Normalize rule to enhanced schema format.
        
        Handles backward compatibility with old rule format.
        
        Args:
            rule: Rule dictionary (may be old or new format)
            
        Returns:
            Normalized rule dictionary
        """
        normalized = rule.copy()
        
        # Generate rule_id if missing (zero-padded 6-digit)
        if "rule_id" not in normalized:
            # Use hash-based ID, but ensure it's zero-padded 6-digit
            rule_hash = abs(hash(normalized.get('rule_text', ''))) % 1000000
            normalized["rule_id"] = f"rule_{rule_hash:06d}"
        
        # Ensure backward compatibility fields
        if "statistical_confidence" not in normalized and "confidence" in normalized:
            normalized["statistical_confidence"] = normalized["confidence"]
        if "confidence" not in normalized and "statistical_confidence" in normalized:
            normalized["confidence"] = normalized["statistical_confidence"]
        
        # Set default values for new fields if missing
        if "rule_type" not in normalized:
            # Infer from category
            category = normalized.get("category", "material_property")
            type_mapping = {
                "stability": "stability",
                "property_application": "band_gap",  # Default assumption
                "synthesis": "synthesis",
                "material_property": "stability"
            }
            normalized["rule_type"] = type_mapping.get(category, "stability")
        
        if "domain" not in normalized:
            normalized["domain"] = ["general"]
        # Ensure domain is always an array
        if isinstance(normalized.get("domain"), str):
            normalized["domain"] = [normalized["domain"]]
        elif not isinstance(normalized.get("domain"), list):
            normalized["domain"] = ["general"]
        
        if "evidence_strength" not in normalized:
            # Infer from confidence
            conf = normalized.get("statistical_confidence", 0.7)
            if conf >= 0.85:
                normalized["evidence_strength"] = "strong"
            elif conf >= 0.65:
                normalized["evidence_strength"] = "medium"  # Changed from "moderate" to "medium"
            else:
                normalized["evidence_strength"] = "weak"
        # Normalize "moderate" to "medium" for consistency
        if normalized.get("evidence_strength") == "moderate":
            normalized["evidence_strength"] = "medium"
        
        if "uncertainty" not in normalized:
            # Calculate uncertainty as (1 - confidence)
            conf = normalized.get("statistical_confidence", normalized.get("confidence", 0.7))
            normalized["uncertainty"] = round(1.0 - conf, 3)
        else:
            # Ensure uncertainty + confidence ≈ 1.0
            conf = normalized.get("statistical_confidence", normalized.get("confidence", 0.7))
            unc = normalized.get("uncertainty", 0.0)
            if abs((unc + conf) - 1.0) > 0.1:
                normalized["uncertainty"] = round(1.0 - conf, 3)
        
        if "validation_status" not in normalized:
            # Determine validation_status based on rule characteristics
            rule_type = normalized.get("rule_type", "")
            property_name = normalized.get("property", "")
            evidence_count = normalized.get("evidence_count")
            rule_text = normalized.get("rule_text", "")
            
            # Check for physics-based rules
            if rule_type == "chemical_constraint":
                normalized["validation_status"] = "physics_based"
            elif evidence_count is not None and evidence_count > 1000:
                normalized["validation_status"] = "validated"
            else:
                normalized["validation_status"] = "extracted"
        
        # Ensure edge_cases and fails_for are arrays
        if "edge_cases" not in normalized:
            normalized["edge_cases"] = []
        elif not isinstance(normalized.get("edge_cases"), list):
            normalized["edge_cases"] = [normalized["edge_cases"]] if normalized.get("edge_cases") else []
        
        if "fails_for" not in normalized:
            normalized["fails_for"] = []
        elif not isinstance(normalized.get("fails_for"), list):
            normalized["fails_for"] = [normalized["fails_for"]] if normalized.get("fails_for") else []
        
        # Ensure validated_materials is an array
        if "validated_materials" not in normalized:
            normalized["validated_materials"] = []
        elif not isinstance(normalized.get("validated_materials"), list):
            normalized["validated_materials"] = [normalized["validated_materials"]] if normalized.get("validated_materials") else []
        
        if "rule_frequency" not in normalized:
            normalized["rule_frequency"] = 1
        
        if "supported_by_papers" not in normalized:
            normalized["supported_by_papers"] = [normalized.get("source_paper_id", "unknown")]
        
        return normalized

    def _build_index(self, rules: List[Dict]) -> Dict:
        """
        Build multi-dimensional searchable index from rules.

        Args:
            rules: List of rule dictionaries

        Returns:
            Index dictionary with property, domain, application, rule_type mappings
        """
        index: Dict = {
            "property": {},
            "domain": {},
            "application": {},
            "rule_type": {},
            "category": {},  # For backward compatibility
            "keyword": {}
        }

        for i, rule in enumerate(rules):
            rule_id = rule.get("rule_id", i)

            # Index by property
            property_name = rule.get("property", "")
            if property_name:
                if property_name not in index["property"]:
                    index["property"][property_name] = []
                if rule_id not in index["property"][property_name]:
                    index["property"][property_name].append(rule_id)

            # Index by domain (handle both array and string for backward compatibility)
            domain = rule.get("domain", ["general"])
            if isinstance(domain, str):
                domain = [domain]
            elif not isinstance(domain, list):
                domain = ["general"]
            
            for d in domain:
                if d not in index["domain"]:
                    index["domain"][d] = []
                if rule_id not in index["domain"][d]:
                    index["domain"][d].append(rule_id)

            # Index by application
            application = rule.get("application", "")
            if application:
                if application not in index["application"]:
                    index["application"][application] = []
                if rule_id not in index["application"][application]:
                    index["application"][application].append(rule_id)

            # Index by rule_type
            rule_type = rule.get("rule_type", "")
            if rule_type:
                if rule_type not in index["rule_type"]:
                    index["rule_type"][rule_type] = []
                if rule_id not in index["rule_type"][rule_type]:
                    index["rule_type"][rule_type].append(rule_id)

            # Index by category (backward compatibility)
            category = rule.get("category", "material_property")
            if category not in index["category"]:
                index["category"][category] = []
            if rule_id not in index["category"][category]:
                index["category"][category].append(rule_id)

            # Index by keywords (simple word-based indexing)
            rule_text = rule.get("rule_text", "").lower()
            words = set(rule_text.split())
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            keywords = [w for w in words if len(w) > 3 and w not in stop_words]

            for keyword in keywords[:10]:  # Limit keywords per rule
                if keyword not in index["keyword"]:
                    index["keyword"][keyword] = []
                if rule_id not in index["keyword"][keyword]:
                    index["keyword"][keyword].append(rule_id)

        return index

    def _cross_validate_rules(self, rules: List[Dict]) -> Dict:
        """
        Cross-validate rules across papers to boost confidence.
        
        Args:
            rules: List of all rules
            
        Returns:
            Dictionary mapping rule hashes to validation info
        """
        validation = {}
        
        # Group rules by normalized rule text (similar rules)
        rule_groups: Dict[str, List[Dict]] = {}
        
        for rule in rules:
            rule_text = rule.get("rule_text", "").strip().lower()
            rule_hash = self._hash_rule_text(rule_text)
            
            if rule_hash not in rule_groups:
                rule_groups[rule_hash] = []
            rule_groups[rule_hash].append(rule)
        
        # For each group, check cross-paper validation
        for rule_hash, group_rules in rule_groups.items():
            if len(group_rules) > 1:
                # Rule appears in multiple papers
                papers = [r.get("source_paper_id") for r in group_rules]
                unique_papers = len(set(papers))
                
                validation[rule_hash] = {
                    "cross_validated": True,
                    "paper_count": unique_papers,
                    "rule_count": len(group_rules),
                    "confidence_boost": min(0.1, unique_papers * 0.02)  # Max 0.1 boost
                }
            else:
                validation[rule_hash] = {
                    "cross_validated": False,
                    "paper_count": 1,
                    "rule_count": 1,
                    "confidence_boost": 0.0
                }
        
        return validation

    def save_rules(self, rules_list: List[Dict], paper_metadata: Optional[Dict] = None) -> int:
        """
        Save new rules with validation, deduplication, and cross-paper validation.

        Args:
            rules_list: List of rule dictionaries to save
            paper_metadata: Optional metadata about the source paper

        Returns:
            Number of new rules added (after deduplication and validation)
        """
        existing_rules = self._load_rules()
        existing_hashes = {self._hash_rule_text(r.get("rule_text", "")) for r in existing_rules}

        new_rules = []
        rejected_rules = []
        
        for rule in rules_list:
            # Normalize rule
            normalized_rule = self._normalize_rule(rule)
            
            # Validate rule
            is_valid, reason = self._validate_rule(normalized_rule)
            if not is_valid:
                rejected_rules.append((normalized_rule.get("rule_text", ""), reason))
                continue
            
            # Check for duplicates
            rule_text = normalized_rule.get("rule_text", "")
            if not rule_text:
                continue

            rule_hash = self._hash_rule_text(rule_text)
            if rule_hash not in existing_hashes:
                # Add unique rule ID (zero-padded 6-digit)
                rule_counter = len(existing_rules) + len(new_rules)
                normalized_rule["rule_id"] = f"rule_{rule_counter:06d}"
                new_rules.append(normalized_rule)
                existing_hashes.add(rule_hash)
            else:
                # Update existing rule with new paper support
                for existing_rule in existing_rules:
                    if self._hash_rule_text(existing_rule.get("rule_text", "")) == rule_hash:
                        # Add paper to supported_by_papers
                        supported = existing_rule.get("supported_by_papers", [])
                        paper_id = normalized_rule.get("source_paper_id")
                        if paper_id and paper_id not in supported:
                            supported.append(paper_id)
                            existing_rule["supported_by_papers"] = supported
                            existing_rule["rule_frequency"] = len(supported)
                            # Boost confidence slightly
                            existing_rule["statistical_confidence"] = min(1.0, 
                                existing_rule.get("statistical_confidence", 0.7) + 0.02)
                            existing_rule["confidence"] = existing_rule["statistical_confidence"]

        if not new_rules and not rejected_rules:
            logger.info("No new rules to save (all duplicates)")
            return 0

        # Append new rules
        all_rules = existing_rules + new_rules
        
        # Cross-validate all rules
        validation = self._cross_validate_rules(all_rules)
        self._save_validation(validation)
        
        # Apply cross-validation confidence boosts
        for rule in all_rules:
            rule_hash = self._hash_rule_text(rule.get("rule_text", ""))
            if rule_hash in validation:
                val_info = validation[rule_hash]
                if val_info["cross_validated"]:
                    rule["statistical_confidence"] = min(1.0, 
                        rule.get("statistical_confidence", 0.7) + val_info["confidence_boost"])
                    rule["confidence"] = rule["statistical_confidence"]
                    rule["validation_status"] = "validated"
        
        self._save_rules(all_rules)

        # Update metadata
        if paper_metadata:
            metadata = self._load_metadata()
            paper_id = paper_metadata.get("url", paper_metadata.get("title", "unknown"))
            metadata[paper_id] = {
                "title": paper_metadata.get("title", ""),
                "authors": paper_metadata.get("authors", []),
                "url": paper_metadata.get("url", ""),
                "extraction_date": datetime.now().isoformat(),
                "rules_count": len(new_rules),
                "rejected_count": len(rejected_rules)
            }
            self._save_metadata(metadata)

        # Rebuild index
        index = self._build_index(all_rules)
        self._save_index(index)

        if rejected_rules:
            logger.warning(f"Rejected {len(rejected_rules)} rules: {rejected_rules[:3]}")
        
        logger.info(f"Saved {len(new_rules)} new rules (skipped {len(rules_list) - len(new_rules) - len(rejected_rules)} duplicates, rejected {len(rejected_rules)})")
        return len(new_rules)

    def load_rules(self, category: Optional[str] = None, property: Optional[str] = None,
                   domain: Optional[str] = None, rule_type: Optional[str] = None,
                   min_confidence: float = 0.0) -> List[Dict]:
        """
        Load rules with optional filtering.

        Args:
            category: Optional category filter (backward compatibility)
            property: Optional property filter
            domain: Optional domain filter
            rule_type: Optional rule_type filter
            min_confidence: Minimum confidence threshold

        Returns:
            List of filtered rule dictionaries
        """
        all_rules = self._load_rules()

        filtered_rules = all_rules

        if category:
            filtered_rules = [r for r in filtered_rules if r.get("category") == category]

        if property:
            filtered_rules = [r for r in filtered_rules if r.get("property") == property]

        if domain:
            # Domain is now an array, so check if the domain string is in the array
            filtered_rules = [
                r for r in filtered_rules 
                if isinstance(r.get("domain"), list) and domain in r.get("domain", [])
                or (isinstance(r.get("domain"), str) and r.get("domain") == domain)
            ]

        if rule_type:
            filtered_rules = [r for r in filtered_rules if r.get("rule_type") == rule_type]

        if min_confidence > 0:
            filtered_rules = [
                r for r in filtered_rules 
                if r.get("statistical_confidence", r.get("confidence", 0)) >= min_confidence
            ]

        logger.info(f"Loaded {len(filtered_rules)} rules (filtered from {len(all_rules)} total)")
        return filtered_rules

    def get_rules(self, property: Optional[str] = None, domain: Optional[str] = None,
                  application: Optional[str] = None, rule_type: Optional[str] = None,
                  min_confidence: float = 0.6) -> List[Dict]:
        """
        Get rules with multi-dimensional filtering (new API).

        Args:
            property: Filter by property name
            domain: Filter by domain
            application: Filter by application
            rule_type: Filter by rule_type
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching rule dictionaries
        """
        return self.load_rules(property=property, domain=domain, rule_type=rule_type, 
                              min_confidence=min_confidence)

    def search_rules(self, keyword: str) -> List[Dict]:
        """
        Search rules by keyword.

        Args:
            keyword: Search keyword

        Returns:
            List of matching rule dictionaries
        """
        keyword_lower = keyword.lower().strip()
        index = self._load_index()
        all_rules = self._load_rules()

        matching_rule_ids = set()

        # Search in keyword index
        keyword_index = index.get("keyword", {})
        if keyword_lower in keyword_index:
            matching_rule_ids.update(keyword_index[keyword_lower])

        # Also search in rule text directly (for partial matches)
        for rule in all_rules:
            rule_text = rule.get("rule_text", "").lower()
            if keyword_lower in rule_text:
                rule_id = rule.get("rule_id")
                if rule_id:
                    matching_rule_ids.add(rule_id)

        # Return matching rules
        rule_dict = {r.get("rule_id"): r for r in all_rules}
        matching_rules = [rule_dict[rid] for rid in matching_rule_ids if rid in rule_dict]

        logger.info(f"Found {len(matching_rules)} rules matching keyword '{keyword}'")
        return matching_rules

    def get_rule_stats(self) -> Dict:
        """
        Get comprehensive statistics about stored rules.

        Returns:
            Dictionary with detailed rule statistics
        """
        rules = self._load_rules()
        metadata = self._load_metadata()
        validation = self._load_validation()

        # Confidence distribution
        confidence_bins = {
            "high": 0,      # >= 0.8
            "medium": 0,    # 0.6-0.8
            "low": 0        # < 0.6
        }
        
        # Domain distribution
        domains = {}
        
        # Rule type distribution
        rule_types = {}
        
        # Cross-validated count
        cross_validated = 0
        
        for rule in rules:
            conf = rule.get("statistical_confidence", rule.get("confidence", 0))
            if conf >= 0.8:
                confidence_bins["high"] += 1
            elif conf >= 0.6:
                confidence_bins["medium"] += 1
            else:
                confidence_bins["low"] += 1
            
            # Domain is now an array, so iterate through each domain item
            domain = rule.get("domain", ["general"])
            if isinstance(domain, str):
                domain = [domain]
            elif not isinstance(domain, list):
                domain = ["general"]
            
            for d in domain:
                domains[d] = domains.get(d, 0) + 1
            
            rule_type = rule.get("rule_type", "unknown")
            rule_types[rule_type] = rule_types.get(rule_type, 0) + 1
            
            # Check if cross-validated
            rule_hash = self._hash_rule_text(rule.get("rule_text", ""))
            if rule_hash in validation and validation[rule_hash].get("cross_validated"):
                cross_validated += 1

        stats = {
            "total_rules": len(rules),
            "confidence_distribution": confidence_bins,
            "domains": domains,
            "rule_types": rule_types,
            "cross_validated_rules": cross_validated,
            "total_papers": len(metadata),
            "last_update": None
        }

        # Get last update time from metadata
        if metadata:
            dates = [m.get("extraction_date", "") for m in metadata.values() if m.get("extraction_date")]
            if dates:
                stats["last_update"] = max(dates)

        return stats
