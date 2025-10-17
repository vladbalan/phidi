"""
Company data spider using native Scrapy extraction.
Uses CSS/XPath selectors and ItemLoaders following Scrapy best practices.
Implements extraction logic independently from regex-based crawlers for comparison.
"""
import csv
import re
import sys
from pathlib import Path
from typing import Generator, Optional

import scrapy
from scrapy.http import Response, HtmlResponse
from scrapy.loader import ItemLoader

# Add repo root to path for imports
_repo_root = Path(__file__).resolve().parents[5]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from phidi_spider.items import CompanyItem
from src.common.domain_utils import clean_domain


class CompanySpider(scrapy.Spider):
    """
    Spider that crawls company websites using native Scrapy extraction.
    
    Extraction Strategy:
    - Phones: Find tel: links and text patterns
    - Social: Extract href attributes from social domain links
    - Address: Look for address tags, schema.org markup, and common patterns
    - Company name: Extract from title, h1, meta tags
    
    Usage:
        scrapy crawl company -a input_file=domains.csv -a output_file=results.ndjson
    """
    
    name = "company"
    
    # Spider arguments
    input_file: Optional[str] = None
    output_path: Optional[str] = None
    
    # Phone pattern for text extraction
    _phone_pattern = re.compile(
        r'\b(?:\+?\d{1,3}[-.\s()]*)?'
        r'(?:\(?\d{2,4}\)?[-.\s]*)?'
        r'\d{2,4}[-.\s]*\d{2,4}[-.\s]*\d{2,4}\b'
    )
    
    def __init__(self, input_file: Optional[str] = None, output_file: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_file = input_file
        self.output_path = output_file
        
        if not self.input_file:
            raise ValueError("input_file argument is required")
        
        if not self.output_path:
            raise ValueError("output_file argument is required")
    
    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """Read domains from CSV and generate requests."""
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
                url = f"https://{domain}"
                
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    errback=self.handle_error,
                    meta={
                        'domain': domain,
                        'original_input': raw_domain
                    },
                    dont_filter=False
                )
            
            self.logger.info(f"Generated {domain_count} requests")
    
    def parse(self, response: Response):
        """
        Extract company data using native Scrapy selectors.
        Uses CSS/XPath for structured extraction.
        """
        domain = response.meta.get('domain', '')
        
        if not isinstance(response, HtmlResponse):
            # Non-HTML response
            return self._build_error_item(
                domain, response.url, response.status,
                error='non_html_response',
                error_message='Response is not HTML'
            )
        
        loader = ItemLoader(item=CompanyItem(), response=response)
        
        # Set metadata
        loader.add_value('domain', domain)
        loader.add_value('final_url', response.url)
        loader.add_value('status_code', response.status)
        loader.add_value('crawled', True)
        
        # Capture response time (download_latency is in seconds, convert to ms)
        download_latency = response.meta.get('download_latency', 0)
        response_time_ms = int(download_latency * 1000)
        loader.add_value('response_time_ms', response_time_ms)
        
        # Extract company name
        # Priority: og:site_name > title > h1
        loader.add_xpath('company_name', '//meta[@property="og:site_name"]/@content')
        loader.add_xpath('company_name', '//title/text()')
        loader.add_css('company_name', 'h1::text')
        
        # Extract phones
        # 1. From tel: links
        loader.add_xpath('phones', '//a[starts-with(@href, "tel:")]/@href')
        # 2. From text containing phone patterns
        phone_texts = response.xpath(
            '//p[contains(translate(., "PHNEOTLCA", "phneotlca"), "phone") or '
            'contains(translate(., "PHNEOTLCA", "phneotlca"), "call") or '
            'contains(translate(., "PHNEOTLCA", "phneotlca"), "tel") or '
            'contains(translate(., "PHNEOTLCA", "phneotlca"), "contact")]//text()'
        ).getall()
        for text in phone_texts:
            matches = self._phone_pattern.findall(text)
            for match in matches:
                loader.add_value('phones', match)
        
        # Extract Facebook
        loader.add_xpath(
            'facebook',
            '//a[contains(@href, "facebook.com") or contains(@href, "fb.com")]/@href'
        )
        
        # Extract LinkedIn
        loader.add_xpath(
            'linkedin',
            '//a[contains(@href, "linkedin.com/company/") or contains(@href, "linkedin.com/in/")]/@href'
        )
        
        # Extract Twitter/X
        loader.add_xpath(
            'twitter',
            '//a[contains(@href, "twitter.com") or contains(@href, "x.com")]/@href'
        )
        
        # Extract Instagram
        loader.add_xpath(
            'instagram',
            '//a[contains(@href, "instagram.com")]/@href'
        )
        
        # Extract address
        # Extract all address-related text and let the processor normalize it
        address_texts = []
        
        # 1. From address tag
        address_texts.extend(response.css('address::text').getall())
        
        # 2. From common CSS classes
        address_texts.extend(response.xpath(
            '//div[contains(@class, "address") or contains(@class, "location") or '
            'contains(@class, "contact")]//text()'
        ).getall())
        
        # 3. Filter and add to loader (skip CSS/JS and very short strings)
        for text in address_texts:
            if text and text.strip():
                clean_text = text.strip()
                # Skip CSS, JS, and other noise
                if len(clean_text) > 10 and not any(x in clean_text.lower() for x in ['@media', 'function', 'var ', '{', '}', ';']):
                    loader.add_value('address', clean_text)
        
        return loader.load_item()
    
    def handle_error(self, failure):
        """Handle request errors."""
        request = failure.request
        domain = request.meta.get('domain', '')
        
        # Determine error type
        error = 'request_failed'
        error_message = str(failure.value)
        
        # Try to get HTTP error status if available
        try:
            if hasattr(failure.value, 'response'):
                response = failure.value.response
                error = 'http_error'
                error_message = f'HTTP {response.status}'
        except Exception:
            pass
        
        return self._build_error_item(
            domain, request.url, None,
            error=error,
            error_message=error_message
        )
    
    def _build_error_item(self, domain: str, url: str, status: Optional[int],
                          error: str, error_message: str):
        """Build an item for failed requests."""
        loader = ItemLoader(item=CompanyItem())
        loader.add_value('domain', domain)
        loader.add_value('final_url', url)
        loader.add_value('status_code', status)
        loader.add_value('crawled', False)
        loader.add_value('response_time_ms', None)
        loader.add_value('error', error)
        loader.add_value('error_message', error_message)
        loader.add_value('company_name', None)
        loader.add_value('phones', [])
        loader.add_value('facebook', None)
        loader.add_value('linkedin', None)
        loader.add_value('twitter', None)
        loader.add_value('instagram', None)
        loader.add_value('address', None)
        return loader.load_item()
