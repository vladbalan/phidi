"""
Company data spider for Phidi crawler.
Extracts phones, social media, and addresses from company websites.
Reuses existing extraction logic to maintain consistency with Python/Node crawlers.
"""
import csv
import sys
from pathlib import Path
from typing import Generator, Optional, Dict, Any

import scrapy
from scrapy.http import Response, HtmlResponse

# Add repo root to path for imports
_repo_root = Path(__file__).resolve().parents[5]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Reuse existing extraction functions (DRY principle)
from src.crawlers.python.extract import (
    extract_company_name,
    extract_phones,
    extract_facebook,
    extract_linkedin,
    extract_twitter,
    extract_instagram,
    extract_address
)
from src.common.domain_utils import clean_domain


def _build_record(domain: str, final_url: str, status: Optional[int], *, phones: Optional[list] = None,
                  company_name: Optional[str] = None,
                  facebook: Optional[str] = None, linkedin: Optional[str] = None,
                  twitter: Optional[str] = None, instagram: Optional[str] = None,
                  address: Optional[str] = None, crawled: bool = True,
                  response_time_ms: Optional[int] = None,
                  error: Optional[str] = None, error_message: Optional[str] = None) -> Dict[str, Any]:
    return {
        'domain': domain,
        'company_name': company_name,
        'phones': phones or [],
        'facebook': facebook,
        'linkedin': linkedin,
        'twitter': twitter,
        'instagram': instagram,
        'address': address,
        'status_code': status,
        'final_url': final_url,
        'crawled': crawled,
        'response_time_ms': response_time_ms,
        **({'error': error} if error else {}),
        **({'error_message': error_message} if error_message else {}),
    }


class CompanySpider(scrapy.Spider):
    """
    Spider that crawls company websites and extracts structured data.
    
    Usage:
        scrapy crawl company -a input_file=domains.csv -a output_file=results.ndjson
    """
    
    name = "company"
    
    # Spider arguments (set via -a flag or custom_settings)
    input_file: Optional[str] = None
    output_path: Optional[str] = None
    
    def __init__(self, input_file: Optional[str] = None, output_file: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_file = input_file
        self.output_path = output_file
        
        if not self.input_file:
            raise ValueError("input_file argument is required (use -a input_file=path/to/domains.csv)")
        
        if not self.output_path:
            raise ValueError("output_file argument is required (use -a output_file=path/to/output.ndjson)")
    
    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """
        Read domains from CSV and generate requests.
        Handles both headerless and header-containing CSV files.
        """
        assert self.input_file is not None  # for type-checkers
        input_path = Path(self.input_file)
        
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return
        
        self.logger.info(f"Reading domains from: {input_path}")
        
        with input_path.open('r', encoding='utf-8-sig', newline='') as f:
            # Peek at first line to detect header
            first_line = f.readline().strip()
            f.seek(0)
            
            # Skip header if present
            if first_line.lower() in ('domain', 'domains', 'website', 'url'):
                next(f)
            
            reader = csv.reader(f)
            domain_count = 0
            
            for row in reader:
                if not row or not row[0].strip():
                    continue
                
                raw_domain = row[0].strip()
                domain = clean_domain(raw_domain)
                
                if not domain:
                    self.logger.warning(f"Invalid domain skipped: {raw_domain}")
                    continue
                
                domain_count += 1
                
                # Try HTTPS first (Scrapy will handle retries and fallback via middleware)
                url = f"https://{domain}"
                
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    errback=self.handle_error,
                    meta={
                        'domain': domain,
                        'original_input': raw_domain
                    },
                    dont_filter=False  # Allow deduplication
                )
            
            self.logger.info(f"Generated {domain_count} requests from {input_path}")
    
    def parse(self, response: Response) -> Dict[str, Any]:
        """
        Extract company data from HTML response.
        Reuses existing extraction functions for consistency.
        """
        domain = response.meta.get('domain', '')
        if not isinstance(response, HtmlResponse):
            self.logger.warning(f"Non-HTML response for {domain} ({response.url}); skipping")
            raw_ct = response.headers.get('Content-Type', b'')
            if isinstance(raw_ct, bytes):
                ctype = raw_ct.decode('utf-8', errors='ignore')
            else:
                ctype = str(raw_ct) if raw_ct else ''
            return _build_record(
                domain,
                response.url,
                response.status if hasattr(response, 'status') else None,
                company_name=None,
                crawled=False,
                error='NonHtmlResponse',
                error_message=f'content_type={ctype}' if ctype else 'binary response'
            )

        html = response.text
        
        # Capture response time (download_latency is in seconds, convert to ms)
        download_latency = response.meta.get('download_latency', 0)
        response_time_ms = int(download_latency * 1000)
        
        # Extract data using shared utilities
        company_name = extract_company_name(html)
        phones = extract_phones(html)
        facebook = extract_facebook(html)
        linkedin = extract_linkedin(html)
        twitter = extract_twitter(html)
        instagram = extract_instagram(html)
        address = extract_address(html)
        
        # Build result in same format as Python/Node crawlers
        result = _build_record(
            domain,
            response.url,
            response.status,
            phones=phones,
            company_name=company_name,
            facebook=facebook,
            linkedin=linkedin,
            twitter=twitter,
            instagram=instagram,
            address=address,
            response_time_ms=response_time_ms,
            crawled=True,
        )
        
        self.logger.debug(f"Extracted data from {domain}: {len(phones)} phones, address={bool(address)}")
        
        return result
    
    def handle_error(self, failure) -> Dict[str, Any]:
        """
        Handle crawl errors gracefully.
        Returns error record in same format as successful crawls.
        """
        request = failure.request
        domain = request.meta.get('domain', '')
        
        error_type = failure.type.__name__ if failure.type else 'UnknownError'
        error_msg = str(failure.value) if failure.value else 'No error message'
        
        # Truncate long error messages
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + '...'
        
        self.logger.warning(f"Failed to crawl {domain}: {error_type} - {error_msg}")
        
        return _build_record(
            domain,
            request.url,
            None,
            company_name=None,
            crawled=False,
            error=error_type,
            error_message=error_msg,
        )
