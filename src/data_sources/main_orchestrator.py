"""
Main Orchestrator Module - ENHANCED VERSION

Orchestrates the full paper scraping and rule extraction pipeline with:
- Enhanced quality reporting
- Rule quality metrics
- Cross-paper validation statistics
- Domain distribution analysis
"""

import argparse
import logging
import sys
from typing import List, Dict
from src.data_sources.paper_scraper import PaperScraper
from src.data_sources.rule_extractor import RuleExtractor
from src.data_sources.rule_storage import RuleStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PaperScraperOrchestrator:
    """Orchestrates the paper scraping and rule extraction pipeline with quality reporting."""

    def __init__(self, rules_dir: str = "rules"):
        """
        Initialize the orchestrator.

        Args:
            rules_dir: Directory path for storing rule JSON files
        """
        self.scraper = PaperScraper()
        self.extractor = RuleExtractor(min_confidence=0.6)
        self.storage = RuleStorage(rules_dir)

    def run_pipeline(
        self,
        sources: List[str] = ["arxiv"],
        keywords: List[str] = None,
        limit: int = 10,
        **kwargs
    ) -> Dict:
        """
        Run the full pipeline: scrape papers → extract rules → store rules → quality report.

        Args:
            sources: List of sources to scrape ("arxiv", "pmc", or both)
            keywords: List of search keywords. Defaults to materials science keywords.
            limit: Maximum number of papers to process per source
            **kwargs: Additional arguments passed to scraper

        Returns:
            Dictionary with pipeline execution results including quality metrics
        """
        logger.info("=" * 60)
        logger.info("Starting Enhanced Paper Scraper Pipeline")
        logger.info("=" * 60)

        # Step 1: Scrape papers
        logger.info(f"\n[Step 1/4] Scraping papers from {sources}...")
        papers = self.scraper.scrape_papers(
            sources=sources,
            keywords=keywords,
            max_results=limit,
            **kwargs
        )

        if not papers:
            logger.warning("No papers found. Exiting pipeline.")
            return {
                "papers_scraped": 0,
                "rules_extracted": 0,
                "rules_saved": 0,
                "papers": [],
                "quality_report": {}
            }

        logger.info(f"Successfully scraped {len(papers)} papers")

        # Step 2: Extract rules
        logger.info(f"\n[Step 2/4] Extracting quantitative, domain-aware rules from {len(papers)} papers...")
        all_rules = []

        for i, paper in enumerate(papers, 1):
            logger.info(f"Processing paper {i}/{len(papers)}: {paper.get('title', 'Unknown')[:60]}...")
            abstract = paper.get("abstract", "")
            paper_id = paper.get("url", paper.get("title", f"paper_{i}"))
            paper_title = paper.get("title", "")
            
            # Extract publication year
            publication_year = None
            date_published = paper.get("date_published", "")
            if date_published:
                import re
                year_match = re.search(r'\d{4}', date_published)
                if year_match:
                    try:
                        publication_year = int(year_match.group())
                    except ValueError:
                        pass

            rules = self.extractor.extract_rules(abstract, paper_id, paper_title, publication_year)
            all_rules.extend(rules)

            # Store rules for this paper
            if rules:
                paper_metadata = {
                    "title": paper_title,
                    "authors": paper.get("authors", []),
                    "url": paper_id,
                    "date_published": date_published
                }
                saved_count = self.storage.save_rules(rules, paper_metadata)
                logger.info(f"  → Extracted {len(rules)} rules, saved {saved_count} new rules")

        logger.info(f"Successfully extracted {len(all_rules)} total rules")

        # Step 3: Quality report
        logger.info(f"\n[Step 3/4] Generating quality report...")
        quality_report = self.generate_quality_report()

        # Step 4: Final statistics
        logger.info(f"\n[Step 4/4] Pipeline complete!")
        stats = self.storage.get_rule_stats()
        
        # Print comprehensive statistics
        self.print_quality_report(quality_report, stats)

        logger.info("=" * 60)

        return {
            "papers_scraped": len(papers),
            "rules_extracted": len(all_rules),
            "rules_saved": stats['total_rules'],
            "papers": papers,
            "stats": stats,
            "quality_report": quality_report
        }

    def generate_quality_report(self) -> Dict:
        """
        Generate comprehensive quality report for stored rules.
        
        Returns:
            Dictionary with quality metrics
        """
        stats = self.storage.get_rule_stats()
        all_rules = self.storage.load_rules()
        
        # Confidence distribution
        confidence_dist = stats.get("confidence_distribution", {})
        high_conf = confidence_dist.get("high", 0)
        medium_conf = confidence_dist.get("medium", 0)
        low_conf = confidence_dist.get("low", 0)
        
        # Domain distribution
        domains = stats.get("domains", {})
        domain_specific = sum(count for domain, count in domains.items() if domain != "general")
        generic = domains.get("general", 0)
        
        # Cross-validated rules
        cross_validated = stats.get("cross_validated_rules", 0)
        
        # Rule type distribution
        rule_types = stats.get("rule_types", {})
        
        # Calculate quality metrics
        total_rules = stats.get("total_rules", 0)
        high_conf_pct = (high_conf / total_rules * 100) if total_rules > 0 else 0
        cross_validated_pct = (cross_validated / total_rules * 100) if total_rules > 0 else 0
        
        # Flag low-quality rules
        flagged_rules = [r for r in all_rules 
                        if r.get("statistical_confidence", r.get("confidence", 0)) < 0.6]
        
        # High uncertainty rules
        high_uncertainty_rules = [r for r in all_rules 
                                 if r.get("uncertainty", 0) > 0.3]
        
        report = {
            "total_rules": total_rules,
            "high_confidence": high_conf,
            "medium_confidence": medium_conf,
            "low_confidence": low_conf,
            "high_confidence_percentage": round(high_conf_pct, 1),
            "domains_covered": list(domains.keys()),
            "domain_specific_rules": domain_specific,
            "generic_rules": generic,
            "cross_validated_rules": cross_validated,
            "cross_validated_percentage": round(cross_validated_pct, 1),
            "rule_types": rule_types,
            "flagged_low_confidence": len(flagged_rules),
            "high_uncertainty_rules": len(high_uncertainty_rules),
            "quality_score": self._calculate_quality_score(stats, all_rules)
        }
        
        return report

    def _calculate_quality_score(self, stats: Dict, all_rules: List[Dict]) -> float:
        """
        Calculate overall quality score (0.0-1.0) for the rule set.
        
        Args:
            stats: Statistics dictionary
            all_rules: List of all rules
            
        Returns:
            Quality score (0.0-1.0)
        """
        if not all_rules:
            return 0.0
        
        total_rules = len(all_rules)
        
        # Factor 1: Confidence distribution (40% weight)
        confidence_dist = stats.get("confidence_distribution", {})
        high_conf = confidence_dist.get("high", 0)
        conf_score = high_conf / total_rules if total_rules > 0 else 0
        
        # Factor 2: Cross-validation (30% weight)
        cross_validated = stats.get("cross_validated_rules", 0)
        validation_score = cross_validated / total_rules if total_rules > 0 else 0
        
        # Factor 3: Domain specificity (20% weight)
        domains = stats.get("domains", {})
        domain_specific = sum(count for domain, count in domains.items() if domain != "general")
        domain_score = min(1.0, domain_specific / max(1, total_rules * 0.5))  # Target 50% domain-specific
        
        # Factor 4: Low uncertainty (10% weight)
        high_uncertainty = sum(1 for r in all_rules if r.get("uncertainty", 0) > 0.3)
        uncertainty_score = 1.0 - (high_uncertainty / total_rules) if total_rules > 0 else 1.0
        
        # Weighted combination
        quality_score = (
            conf_score * 0.4 +
            validation_score * 0.3 +
            domain_score * 0.2 +
            uncertainty_score * 0.1
        )
        
        return round(quality_score, 3)

    def print_quality_report(self, quality_report: Dict, stats: Dict) -> None:
        """
        Print formatted quality report to console.
        
        Args:
            quality_report: Quality report dictionary
            stats: Statistics dictionary
        """
        logger.info("\n" + "=" * 60)
        logger.info("RULE QUALITY REPORT")
        logger.info("=" * 60)
        
        logger.info(f"\nTotal rules: {quality_report['total_rules']}")
        
        # Confidence distribution
        logger.info(f"\nConfidence Distribution:")
        logger.info(f"  High confidence (≥0.8): {quality_report['high_confidence']} ({quality_report['high_confidence_percentage']}%)")
        logger.info(f"  Medium confidence (0.6-0.8): {quality_report['medium_confidence']}")
        logger.info(f"  Low confidence (<0.6): {quality_report['low_confidence']}", 
                   extra={"flagged": quality_report['low_confidence'] > 0})
        
        if quality_report['low_confidence'] > 0:
            logger.warning(f"  ⚠️  FLAGGED: {quality_report['low_confidence']} rules with confidence < 0.6")
        
        # Domain coverage
        logger.info(f"\nDomain Coverage:")
        logger.info(f"  Domains covered: {', '.join(quality_report['domains_covered']) if quality_report['domains_covered'] else 'None'}")
        logger.info(f"  Domain-specific rules: {quality_report['domain_specific_rules']}")
        logger.info(f"  Generic rules: {quality_report['generic_rules']}")
        
        # Cross-validation
        logger.info(f"\nCross-Validation:")
        logger.info(f"  Cross-validated (in 2+ papers): {quality_report['cross_validated_rules']} ({quality_report['cross_validated_percentage']}%)")
        
        # Rule types
        logger.info(f"\nRule Types:")
        for rule_type, count in quality_report['rule_types'].items():
            logger.info(f"  {rule_type}: {count}")
        
        # Quality flags
        if quality_report['flagged_low_confidence'] > 0:
            logger.warning(f"\n⚠️  Quality Flags:")
            logger.warning(f"  Low confidence rules: {quality_report['flagged_low_confidence']}")
        
        if quality_report['high_uncertainty_rules'] > 0:
            logger.warning(f"  High uncertainty rules: {quality_report['high_uncertainty_rules']}")
        
        # Overall quality score
        logger.info(f"\nOverall Quality Score: {quality_report['quality_score']:.3f}")
        if quality_report['quality_score'] >= 0.8:
            logger.info("  ✅ Excellent quality")
        elif quality_report['quality_score'] >= 0.6:
            logger.info("  ⚠️  Good quality, but room for improvement")
        else:
            logger.warning("  ❌ Quality needs improvement")
        
        logger.info("=" * 60)

    def print_sample_rules(self, num_samples: int = 5, min_confidence: float = 0.7) -> None:
        """
        Print sample rules to console for review.

        Args:
            num_samples: Number of sample rules to print
            min_confidence: Minimum confidence for sample rules
        """
        rules = self.storage.load_rules(min_confidence=min_confidence)
        if not rules:
            logger.info("No rules found in storage.")
            return

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Sample Rules (showing {min(num_samples, len(rules))} of {len(rules)}):")
        logger.info(f"{'=' * 60}")

        for i, rule in enumerate(rules[:num_samples], 1):
            logger.info(f"\nRule {i}:")
            logger.info(f"  Rule Type: {rule.get('rule_type', 'N/A')}")
            logger.info(f"  Property: {rule.get('property', 'N/A')}")
            logger.info(f"  Domain: {rule.get('domain', 'N/A')}")
            logger.info(f"  Confidence: {rule.get('statistical_confidence', rule.get('confidence', 0)):.2f}")
            logger.info(f"  Text: {rule.get('rule_text', 'N/A')}")
            logger.info(f"  Source: {rule.get('source_paper_id', 'N/A')[:80]}")


def main():
    """CLI entry point for the orchestrator."""
    parser = argparse.ArgumentParser(
        description="Enhanced Paper Scraper Pipeline: Extract quantitative, domain-aware rules from research papers"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of papers to process per source (default: 10)"
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["arxiv", "pmc", "both"],
        default="arxiv",
        help="Source to scrape: arxiv, pmc, or both (default: arxiv)"
    )
    parser.add_argument(
        "--keywords",
        type=str,
        nargs="+",
        default=None,
        help="Custom search keywords (default: materials science keywords)"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of sample rules to display after extraction (default: 5)"
    )

    args = parser.parse_args()

    # Parse source argument
    if args.source == "both":
        sources = ["arxiv", "pmc"]
    else:
        sources = [args.source]

    # Initialize orchestrator
    orchestrator = PaperScraperOrchestrator()

    # Run pipeline
    try:
        results = orchestrator.run_pipeline(
            sources=sources,
            keywords=args.keywords,
            limit=args.limit
        )

        # Print sample rules
        orchestrator.print_sample_rules(num_samples=args.samples)

        # Exit with success
        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
