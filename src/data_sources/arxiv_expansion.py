"""
arXiv expansion pipeline for materials-science papers.

Fetches papers from the arXiv API and transforms them into a JSON schema
compatible with downstream rule extraction.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set
from urllib.parse import quote_plus
from xml.etree import ElementTree

import requests


ARXIV_API_URL = "http://export.arxiv.org/api/query"
DEFAULT_USER_AGENT = "MatAgent-Forge/1.0 (+https://github.com/user/MatAgent-Forge)"
DEFAULT_KEYWORDS = [
    "band gap",
    "stability",
    "synthesis",
    "perovskite",
    "battery",
    "thermal",
    "mechanical",
    "formation energy",
    "crystal structure",
]
DEFAULT_CATEGORY = "cat:cond-mat.mtrl-sci"
MAX_RESULTS_PER_CALL = 50
MAX_BATCHES = 5

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


@dataclass(frozen=True)
class ExpansionConfig:
    """Runtime configuration for arXiv expansion."""

    rate_limit: float
    delay_seconds: float
    batches: int
    keywords: List[str]
    output_path: Path
    dry_run: bool
    user_agent: str = DEFAULT_USER_AGENT


def configure_logging() -> None:
    """Configure INFO logging with required timestamped format."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def project_root() -> Path:
    """Return repository root path based on current module location."""
    return Path(__file__).resolve().parents[2]


def load_simple_env(env_path: Path) -> Dict[str, str]:
    """Load .env-style key/value pairs without external dependencies."""
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def read_env_value(env_vars: Dict[str, str], key: str) -> Optional[str]:
    """Read a variable from process environment with .env fallback."""
    return os.getenv(key) or env_vars.get(key)


def parse_positive_float(value: Optional[str], default: float) -> float:
    """Parse positive float with fallback default."""
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def normalize_keywords(keyword_args: Optional[Sequence[str]]) -> List[str]:
    """Normalize keyword args into a clean list; fallback to defaults."""
    if not keyword_args:
        return list(DEFAULT_KEYWORDS)

    terms: List[str] = []
    for arg in keyword_args:
        for part in arg.split():
            cleaned = part.strip()
            if cleaned:
                terms.append(cleaned)
    return terms or list(DEFAULT_KEYWORDS)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for arXiv expansion script."""
    parser = argparse.ArgumentParser(description="Fetch arXiv materials science papers.")
    parser.add_argument("--batches", type=int, default=2, help="Number of 50-paper batches per keyword (max 5).")
    parser.add_argument(
        "--keywords",
        nargs="+",
        help="Space-separated custom keywords that override defaults.",
    )
    parser.add_argument(
        "--output",
        default=str(project_root() / "data" / "arxiv_papers.json"),
        help="Output JSON path.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch and transform without saving.")
    return parser.parse_args()


class ArxivClient:
    """Small arXiv client with politeness/rate-limiting behavior."""

    def __init__(self, rate_limit: float, delay_seconds: float, user_agent: str) -> None:
        """
        Initialize client.

        Args:
            rate_limit: Max requests per second.
            delay_seconds: Additional delay added before each request.
            user_agent: User-Agent header sent to arXiv.
        """
        self.rate_limit = rate_limit
        self.delay_seconds = delay_seconds
        self.min_interval = 1.0 / rate_limit if rate_limit > 0 else 0.0
        self.last_request_at: Optional[float] = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.logger = logging.getLogger(__name__)

    def _throttle(self) -> float:
        """Apply combined rate-limit and configured delay. Returns applied delay."""
        now = time.monotonic()
        since_last = 0.0 if self.last_request_at is None else now - self.last_request_at
        wait_for_rate = max(0.0, self.min_interval - since_last)
        applied_delay = wait_for_rate + self.delay_seconds
        if applied_delay > 0:
            time.sleep(applied_delay)
        return applied_delay

    def fetch(self, query: str, start: int, max_results: int = MAX_RESULTS_PER_CALL) -> Optional[str]:
        """
        Fetch one arXiv API response body.

        Args:
            query: arXiv search query string.
            start: Pagination offset.
            max_results: Number of results requested.

        Returns:
            Response text if successful, otherwise None.
        """
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        encoded_query = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        url = f"{ARXIV_API_URL}?{encoded_query}"

        applied_delay = self._throttle()
        timestamp = datetime.now().isoformat(timespec="seconds")

        try:
            response = self.session.get(url, timeout=30)
            self.last_request_at = time.monotonic()
            self.logger.info(
                "Request timestamp=%s query=%s start=%s status=%s delay_applied=%.3fs",
                timestamp,
                query,
                start,
                response.status_code,
                applied_delay,
            )
            if response.status_code == 503:
                self.logger.warning("arXiv returned 503. Backing off 5s and retrying once.")
                time.sleep(5.0)
                retry = self.session.get(url, timeout=30)
                self.last_request_at = time.monotonic()
                self.logger.info(
                    "Retry timestamp=%s query=%s start=%s status=%s delay_applied=5.000s",
                    datetime.now().isoformat(timespec="seconds"),
                    query,
                    start,
                    retry.status_code,
                )
                if retry.status_code == 200:
                    return retry.text
                self.logger.error("Retry failed for query=%s start=%s status=%s", query, start, retry.status_code)
                return None

            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            self.last_request_at = time.monotonic()
            self.logger.error(
                "Request error at %s for query=%s start=%s: %s",
                timestamp,
                query,
                start,
                str(exc),
            )
            return None


def extract_arxiv_id(entry_id: str) -> Optional[str]:
    """Extract canonical arXiv ID (e.g. 2401.12345) from entry id URL."""
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?$", entry_id.strip())
    return match.group(1) if match else None


def clean_text(value: Optional[str]) -> str:
    """Collapse whitespace and return single-line clean text."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def parse_published_date(raw_value: Optional[str]) -> Optional[str]:
    """Convert timestamp-like date into YYYY-MM-DD."""
    if not raw_value:
        return None
    date_part = raw_value.strip()[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_part):
        return date_part
    return None


def transform_entry(entry: ElementTree.Element) -> Optional[Dict[str, Any]]:
    """
    Transform one Atom entry into rule-extractor-ready schema.

    Args:
        entry: XML entry element from arXiv Atom response.

    Returns:
        Normalized paper record or None if invalid.
    """
    entry_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
    arxiv_id = extract_arxiv_id(entry_id)
    if not arxiv_id:
        logging.warning("Skipping invalid entry: missing/invalid arXiv id (%s)", entry_id)
        return None

    title = clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
    abstract = clean_text(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
    published = parse_published_date(entry.findtext("atom:published", default="", namespaces=ATOM_NS))
    primary = entry.find("arxiv:primary_category", namespaces=ATOM_NS)
    category_term = primary.attrib.get("term", "").strip() if primary is not None else ""

    author_names: List[str] = []
    for author in entry.findall("atom:author", namespaces=ATOM_NS):
        name = clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS))
        if name:
            author_names.append(name)

    if not title or not abstract or not published:
        logging.warning("Skipping invalid entry arXiv=%s (title/abstract/published missing)", arxiv_id)
        return None

    publication_year = int(published[:4])
    categories = [category_term] if category_term else []

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": author_names,
        "abstract": abstract,
        "published": published,
        "categories": categories,
        "source_paper_id": f"arxiv:{arxiv_id}",
        "source_section": "abstract",
        "publication_year": publication_year,
        "raw_text": f"{title}\n\n{abstract}",
    }


def parse_feed(xml_text: str) -> List[Dict[str, Any]]:
    """
    Parse arXiv Atom XML response into normalized paper records.

    Args:
        xml_text: Raw Atom XML response body.

    Returns:
        List of transformed paper records.
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        logging.error("Failed to parse arXiv XML: %s", str(exc))
        return []

    papers: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", namespaces=ATOM_NS):
        record = transform_entry(entry)
        if record:
            papers.append(record)
    return papers


def dedupe_papers(papers: Sequence[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
    """Remove exact duplicates by arxiv_id and return unique papers with duplicate count."""
    unique_by_id: Dict[str, Dict[str, Any]] = {}
    duplicates = 0
    for paper in papers:
        arxiv_id = str(paper.get("arxiv_id", ""))
        if not arxiv_id:
            continue
        if arxiv_id in unique_by_id:
            duplicates += 1
            continue
        unique_by_id[arxiv_id] = paper
    return list(unique_by_id.values()), duplicates


def save_json_safely(papers: Sequence[Dict[str, Any]], output_path: Path) -> None:
    """
    Validate and safely write output JSON with backup if file exists.

    Args:
        papers: Records to write.
        output_path: Target JSON path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(list(papers), indent=2, ensure_ascii=False)
    json.loads(payload)  # Validation gate before write

    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = output_path.with_suffix(output_path.suffix + f".bak.{timestamp}")
        shutil.copy2(output_path, backup_path)
        logging.info("Backed up existing file: %s", backup_path)

    output_path.write_text(payload + "\n", encoding="utf-8")
    logging.info("Saved %s papers to %s", len(papers), output_path)


def build_query(keyword: str) -> str:
    """Build arXiv search query combining category and keyword clause."""
    safe_keyword = keyword.strip()
    return f"{DEFAULT_CATEGORY} AND all:\"{safe_keyword}\""


def collect_papers(config: ExpansionConfig) -> List[Dict[str, Any]]:
    """
    Fetch papers across keywords and batches.

    Args:
        config: Expansion configuration.

    Returns:
        List of fetched (not deduped) paper records.
    """
    logger = logging.getLogger(__name__)
    client = ArxivClient(config.rate_limit, config.delay_seconds, config.user_agent)

    all_papers: List[Dict[str, Any]] = []
    for keyword in config.keywords:
        query = build_query(keyword)
        keyword_total = 0
        for batch in range(config.batches):
            start = batch * MAX_RESULTS_PER_CALL
            xml_text = client.fetch(query=query, start=start, max_results=MAX_RESULTS_PER_CALL)
            if not xml_text:
                continue
            batch_papers = parse_feed(xml_text)
            logger.info("Keyword=%s batch=%s fetched=%s", keyword, batch + 1, len(batch_papers))
            if not batch_papers and batch == 0:
                logger.info("No papers found for query: %s", query)
            all_papers.extend(batch_papers)
            keyword_total += len(batch_papers)
        logger.info("Keyword=%s total fetched across %s batches: %s", keyword, config.batches, keyword_total)
    return all_papers


def load_runtime_config(args: argparse.Namespace) -> ExpansionConfig:
    """
    Build runtime configuration from CLI args and env values.

    Args:
        args: Parsed CLI args.

    Returns:
        Populated ExpansionConfig.
    """
    env_path = project_root() / ".env"
    env_vars = load_simple_env(env_path)

    rate_limit = parse_positive_float(read_env_value(env_vars, "ARXIV_RATE_LIMIT"), 3.0)
    delay_seconds = parse_positive_float(read_env_value(env_vars, "ARXIV_DELAY_SECONDS"), 0.5)

    mp_api_key = read_env_value(env_vars, "MP_API_KEY")
    groq_api_key = read_env_value(env_vars, "GROQ_API_KEY")
    if not mp_api_key:
        logging.warning("MP_API_KEY is missing. Materials Project integrations may fail elsewhere.")
    if not groq_api_key:
        logging.warning("GROQ_API_KEY is missing. Rule extraction may fail elsewhere.")

    batches = max(1, min(int(args.batches), MAX_BATCHES))
    if int(args.batches) != batches:
        logging.warning("Adjusted --batches from %s to %s (allowed range: 1-%s).", args.batches, batches, MAX_BATCHES)

    keywords = normalize_keywords(args.keywords)
    output_path = Path(args.output).expanduser()

    return ExpansionConfig(
        rate_limit=rate_limit,
        delay_seconds=delay_seconds,
        batches=batches,
        keywords=keywords,
        output_path=output_path,
        dry_run=bool(args.dry_run),
    )


def main() -> int:
    """CLI entrypoint for arXiv expansion job."""
    configure_logging()
    start_time = time.perf_counter()

    args = parse_args()
    config = load_runtime_config(args)

    logging.info(
        "Starting arXiv expansion with rate_limit=%.2f req/s, delay=%.2fs, batches=%s, keywords=%s, dry_run=%s",
        config.rate_limit,
        config.delay_seconds,
        config.batches,
        len(config.keywords),
        config.dry_run,
    )

    fetched_papers = collect_papers(config)
    unique_papers, duplicate_count = dedupe_papers(fetched_papers)
    domains_found: Set[str] = {
        category
        for paper in unique_papers
        for category in paper.get("categories", [])
        if isinstance(category, str) and category
    }

    logging.info(
        "Fetched %s papers, %s duplicates removed, %s unique papers saved",
        len(fetched_papers),
        duplicate_count,
        len(unique_papers),
    )

    if config.dry_run:
        logging.info("Dry-run enabled. Skipping file write to %s", config.output_path)
    else:
        try:
            save_json_safely(unique_papers, config.output_path)
        except (OSError, json.JSONDecodeError) as exc:
            logging.error("Failed to write output file at %s: %s", config.output_path, str(exc))
            return 1

    elapsed = time.perf_counter() - start_time
    logging.info(
        "Summary: total_fetched=%s unique_saved=%s domains_found=%s time_taken=%.2fs",
        len(fetched_papers),
        len(unique_papers),
        sorted(domains_found),
        elapsed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
