/**
 * Data extraction module for Node.js crawler.
 *
 * Extracts structured company data from HTML:
 * - Phone numbers (E.164 normalization)
 * - Social media URLs (Facebook, LinkedIn, Twitter, Instagram)
 * - Physical addresses
 *
 * Design: Simple regex patterns, zero external HTML parsers (KISS).
 * Mirrors Python extract.py patterns for consistency.
 */

// ---------- Regex Patterns ----------

// Phone: Match common formats with word boundaries to avoid dates/prices
// Examples: (212) 555-1234, 212-555-1234, +1-212-555-1234, +44 20 1234 5678
const PHONE_PATTERN = /\b(?:\+?\d{1,3}[-.\s()]*)?(?:\(?\d{2,4}\)?[-.\s]*)?\d{2,4}[-.\s]*\d{2,4}(?:[-.\s]*\d{2,4})?\b/gi;

// Social URLs in href attributes
const FACEBOOK_PATTERN = /href=["'](https?:\/\/(?:www\.)?(?:facebook\.com|fb\.com)\/[^"']+)["']/gi;

const LINKEDIN_PATTERN = /href=["'](https?:\/\/(?:www\.)?linkedin\.com\/(?:company|in)\/[^"']+)["']/gi;

const TWITTER_PATTERN = /href=["'](https?:\/\/(?:www\.)?(?:twitter\.com|x\.com)\/[^"']+)["']/gi;

const INSTAGRAM_PATTERN = /href=["'](https?:\/\/(?:www\.)?instagram\.com\/[^"']+)["']/gi;

// Address patterns
const ADDRESS_KEYWORD_PATTERN = /(?:address|location|visit\s+us|headquarters?|office)[:\s]+([^<]+?(?:street|st|ave|avenue|road|rd|blvd|boulevard|drive|dr)[^<]{0,150})/gi;

const ADDRESS_STRUCTURED_PATTERN = /\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)\.?,?\s*(?:Suite|Ste|Unit|#)?\s*[A-Za-z0-9]*,?\s*[A-Za-z\s]+,\s*(?:[A-Z]{2}|[A-Za-z\s]+)\s*\d{4,5}(?:-\d{4})?/gi;

// ---------- Result Interface ----------

export interface ExtractResult {
  phones: string[];
  company_name: string | null;
  facebook_url: string | null;
  linkedin_url: string | null;
  twitter_url: string | null;
  instagram_url: string | null;
  address: string | null;
}

// ---------- Helper Functions ----------

/**
 * Strip HTML tags, preserving whitespace structure.
 */
function stripHtmlTags(html: string): string {
  if (!html) return '';
  
  // Replace block elements with spaces to preserve word boundaries
  let text = html.replace(/<(?:br|p|div|li|tr|td|th)[^>]*>/gi, ' ');
  // Remove all remaining tags
  text = text.replace(/<[^>]+>/g, '');
  // Normalize whitespace
  text = text.replace(/\s+/g, ' ');
  return text.trim();
}

/**
 * Normalize phone to E.164-like format.
 * Strips non-digits, adds country code if needed.
 */
function normalizePhone(raw: string, defaultCountry: string = 'US'): string | null {
  if (!raw) return null;
  
  const s = String(raw).trim();
  if (!s) return null;
  
  // Preserve leading '+' to detect intentional country code
  const hasPlus = s.startsWith('+');
  const digits = s.replace(/\D/g, '');
  
  if (!digits || digits.length < 8) return null;
  
  // If explicitly had + and digits, trust that
  if (hasPlus) {
    return '+' + digits;
  }
  
  // US handling
  if (defaultCountry.toUpperCase() === 'US') {
    if (digits.length === 11 && digits.startsWith('1')) {
      return '+' + digits;
    }
    if (digits.length === 10) {
      return '+1' + digits;
    }
  }
  
  // Fallback: return with + prefix if reasonable length
  return digits.length >= 8 ? '+' + digits : null;
}

/**
 * Canonicalize URL to 'host/path' format.
 * Strips www. prefix and normalizes.
 */
function canonicalHostPath(url: string): string | null {
  if (!url) return null;
  
  const v = url.trim();
  if (!v) return null;
  
  try {
    // Handle full URLs
    if (v.includes('://')) {
      const parsed = new URL(v);
      let host = parsed.hostname.toLowerCase();
      const path = parsed.pathname.replace(/^\/+|\/+$/g, '');
      
      if (host.startsWith('www.')) {
        host = host.slice(4);
      }
      
      return path ? `${host}/${path}` : host;
    }
    
    // Bare input: split at first '/'
    const parts = v.split('/');
    let host = parts[0].toLowerCase();
    const path = parts.slice(1).join('/').replace(/^\/+|\/+$/g, '');
    
    if (host.startsWith('www.')) {
      host = host.slice(4);
    }
    
    return path ? `${host}/${path}` : host;
  } catch {
    return null;
  }
}

/**
 * Canonicalize Facebook URL.
 * Normalizes fb.com to facebook.com, strips www.
 */
function canonicalizeFacebook(url: string | null): string | null {
  const c = canonicalHostPath(url || '');
  if (!c) return null;
  
  // Normalize fb.com to facebook.com
  let result = c;
  if (result.startsWith('fb.com/') || result === 'fb.com') {
    result = 'facebook.com' + (result.length > 6 ? result.slice(6) : '');
  }
  
  // If input was just a handle (no dot, no slash), assume Facebook handle
  if (!result.includes('/') && !result.includes('.')) {
    result = `facebook.com/${result}`;
  }
  
  // Remove duplicate prefixes
  while (result.includes('facebook.com/facebook.com')) {
    result = result.replace('facebook.com/facebook.com', 'facebook.com');
  }
  
  return `https://${result}`;
}

/**
 * Canonicalize LinkedIn URL.
 */
function canonicalizeLinkedin(url: string | null): string | null {
  const c = canonicalHostPath(url || '');
  return c && c.includes('linkedin.com') ? `https://${c}` : null;
}

/**
 * Canonicalize Twitter URL.
 * Accepts both twitter.com and x.com.
 */
function canonicalizeTwitter(url: string | null): string | null {
  const c = canonicalHostPath(url || '');
  return c && (c.startsWith('twitter.com') || c.startsWith('x.com')) ? `https://${c}` : null;
}

/**
 * Canonicalize Instagram URL.
 */
function canonicalizeInstagram(url: string | null): string | null {
  const c = canonicalHostPath(url || '');
  return c && c.startsWith('instagram.com') ? `https://${c}` : null;
}

/**
 * Normalize address text.
 * Simplifies whitespace and limits length.
 */
function normalizeAddress(raw: string | null): string | null {
  if (!raw) return null;
  
  const s = String(raw).trim();
  if (!s) return null;
  
  // Normalize whitespace
  const normalized = s.replace(/\s+/g, ' ').trim();
  
  // Limit length to 500 chars
  return normalized.length <= 500 ? normalized : normalized.slice(0, 500) + '...';
}

/**
 * Deduplicate array, preserving order.
 */
function dedupePreserveOrder(items: string[]): string[] {
  const seen = new Set<string>();
  return items.filter(item => {
    if (seen.has(item)) return false;
    seen.add(item);
    return true;
  });
}

// ---------- Extraction Functions ----------

/**
 * Extract phone numbers from HTML.
 * Returns array of E.164-formatted phone numbers.
 */
export function extractPhones(html: string | null): string[] {
  if (!html) return [];
  
  const text = stripHtmlTags(html);
  const matches = Array.from(text.matchAll(PHONE_PATTERN));
  
  const phones: string[] = [];
  for (const match of matches) {
    const raw = match[0];
    
    // Skip if looks like a date (YYYY-MM-DD or MM-DD-YYYY)
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw) || /^\d{2}[-/.]\d{2}[-/.]\d{4}$/.test(raw)) {
      continue;
    }
    
    // Skip if looks like a price (has currency symbols or decimal separator)
    if (/[$€£¥,.]/.test(raw) && /\.\d{2}$/.test(raw)) {
      continue;
    }
    
    const normalized = normalizePhone(raw);
    if (normalized) {
      phones.push(normalized);
    }
  }
  
  return dedupePreserveOrder(phones);
}

/**
 * Extract Facebook URL from HTML.
 * Returns first canonicalized Facebook URL or null.
 */
export function extractFacebook(html: string | null): string | null {
  if (!html) return null;
  
  const matches = Array.from(html.matchAll(FACEBOOK_PATTERN));
  
  for (const match of matches) {
    const url = match[1];
    const canonical = canonicalizeFacebook(url);
    if (canonical) return canonical;
  }
  
  return null;
}

/**
 * Extract LinkedIn URL from HTML.
 * Returns first canonicalized LinkedIn URL or null.
 */
export function extractLinkedin(html: string | null): string | null {
  if (!html) return null;
  
  const matches = Array.from(html.matchAll(LINKEDIN_PATTERN));
  
  for (const match of matches) {
    const url = match[1];
    const canonical = canonicalizeLinkedin(url);
    if (canonical) return canonical;
  }
  
  return null;
}

/**
 * Extract Twitter URL from HTML.
 * Returns first canonicalized Twitter/X URL or null.
 */
export function extractTwitter(html: string | null): string | null {
  if (!html) return null;
  
  const matches = Array.from(html.matchAll(TWITTER_PATTERN));
  
  for (const match of matches) {
    const url = match[1];
    const canonical = canonicalizeTwitter(url);
    if (canonical) return canonical;
  }
  
  return null;
}

/**
 * Extract Instagram URL from HTML.
 * Returns first canonicalized Instagram URL or null.
 */
export function extractInstagram(html: string | null): string | null {
  if (!html) return null;
  
  const matches = Array.from(html.matchAll(INSTAGRAM_PATTERN));
  
  for (const match of matches) {
    const url = match[1];
    const canonical = canonicalizeInstagram(url);
    if (canonical) return canonical;
  }
  
  return null;
}

/**
 * Extract physical address from HTML.
 * Returns first normalized address or null.
 */
export function extractAddress(html: string | null): string | null {
  if (!html) return null;
  
  const text = stripHtmlTags(html);
  
  // Try keyword-based pattern first
  const keywordMatches = Array.from(text.matchAll(ADDRESS_KEYWORD_PATTERN));
  for (const match of keywordMatches) {
    const address = match[1];
    if (address) {
      const normalized = normalizeAddress(address);
      if (normalized) return normalized;
    }
  }
  
  // Try structured pattern
  const structuredMatches = Array.from(text.matchAll(ADDRESS_STRUCTURED_PATTERN));
  for (const match of structuredMatches) {
    const address = match[0];
    if (address) {
      const normalized = normalizeAddress(address);
      if (normalized) return normalized;
    }
  }
  
  return null;
}

/**
 * Extract all data from HTML.
 * Returns object with all extracted fields.
 */
export function extractAll(html: string | null): ExtractResult {
  return {
    phones: extractPhones(html),
    company_name: null, // Will be derived from domain in main crawler
    facebook_url: extractFacebook(html),
    linkedin_url: extractLinkedin(html),
    twitter_url: extractTwitter(html),
    instagram_url: extractInstagram(html),
    address: extractAddress(html),
  };
}
