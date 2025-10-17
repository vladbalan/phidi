/**
 * HTTP client module using undici.
 * 
 * Provides fast, async HTTP fetching with:
 * - Timeout handling
 * - Redirect tracking
 * - Error recovery with retries
 * - HTTP fallback for SSL errors
 * 
 * Design: undici is the official Node.js HTTP client, 5-10× faster than axios.
 */

import { request } from 'undici';
import { CrawlerConfig, calculateBackoff } from './config';

export interface FetchResult {
  html: string;
  statusCode: number;
  responseTimeMs: number;
  pageSizeBytes: number;
  redirectChain: string[] | null;
  error: string | null;
}

export interface FetchOptions {
  url: string;
  timeoutMs: number;
  userAgent: string;
  config?: CrawlerConfig;  // Optional config for retry/protocol settings
}

/**
 * Sleep for specified milliseconds (used for retry backoff).
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Fetch HTML from a single URL with timeout and error handling.
 * Does not include retry logic - see fetchHtml for retries.
 */
async function fetchOnce(url: string, timeoutMs: number, userAgent: string): Promise<FetchResult> {
  const startTime = Date.now();
  const redirectChain: string[] = [];
  
  try {
    const { statusCode, headers, body } = await request(url, {
      method: 'GET',
      headersTimeout: timeoutMs,
      bodyTimeout: timeoutMs,
      headers: {
        'User-Agent': userAgent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
    });
    
    // Track redirect chain if any
    const location = headers['location'];
    if (location) {
      redirectChain.push(String(location));
    }
    
    // Read body as text
    const html = await body.text();
    const responseTimeMs = Date.now() - startTime;
    
    return {
      html,
      statusCode,
      responseTimeMs,
      pageSizeBytes: Buffer.byteLength(html, 'utf8'),
      redirectChain: redirectChain.length > 0 ? redirectChain : null,
      error: null,
    };
  } catch (err: any) {
    const responseTimeMs = Date.now() - startTime;
    
    // Categorize error
    let errorMessage = 'Unknown error';
    let errorCode = err.code || '';
    
    if (errorCode === 'ETIMEDOUT' || errorCode === 'UND_ERR_HEADERS_TIMEOUT' || errorCode === 'UND_ERR_BODY_TIMEOUT') {
      errorMessage = `Timeout after ${responseTimeMs}ms`;
    } else if (errorCode === 'ENOTFOUND' || errorCode === 'EAI_AGAIN') {
      errorMessage = `DNS error: ${errorCode}`;
    } else if (errorCode === 'ECONNREFUSED') {
      errorMessage = 'Connection refused';
    } else if (errorCode === 'ECONNRESET') {
      errorMessage = 'Connection reset';
    } else if (errorCode.includes('SSL') || errorCode.includes('CERT') || err.message?.toLowerCase().includes('certificate')) {
      errorMessage = `SSL error: ${err.message || errorCode}`;
    } else if (err.message) {
      errorMessage = `HTTP error: ${err.message}`;
    }
    
    return {
      html: '',
      statusCode: 0,
      responseTimeMs,
      pageSizeBytes: 0,
      redirectChain: null,
      error: errorMessage,
    };
  }
}

/**
 * Fetch HTML from a URL using undici with retry logic.
 * 
 * Strategy:
 * - Try HTTPS first (configurable attempts with exponential backoff)
 * - If HTTPS fails with SSL errors, try HTTP (configurable attempts)
 * - Use jitter to avoid thundering herd
 * 
 * Returns fetch result with timing, status, and error info.
 */
export async function fetchHtml(options: FetchOptions): Promise<FetchResult> {
  // Use config values or fallback to defaults
  const maxRetries = options.config?.retry.maxAttempts ?? 3;
  
  // Build protocol list based on config
  const protocols: string[] = [];
  if (options.config?.protocol.tryHttpsFirst ?? true) {
    protocols.push('https');
  }
  if (options.config?.protocol.fallbackToHttp ?? true) {
    protocols.push('http');
  }
  if (protocols.length === 0) {
    protocols.push('https'); // Safe default
  }
  
  const startTime = Date.now();
  let lastError: string | null = null;
  
  // Extract domain from URL
  const urlObj = new URL(options.url);
  const domain = urlObj.hostname;
  
  for (const protocol of protocols) {
    const url = `${protocol}://${domain}${urlObj.pathname}${urlObj.search}`;
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const result = await fetchOnce(url, options.timeoutMs, options.userAgent);
      
      // Success - return immediately
      if (!result.error) {
        return result;
      }
      
      lastError = result.error;
      
      // Check if we should break out of retry loop for this protocol
      const errorLower = result.error.toLowerCase();
      
      // DNS errors: no point retrying with same protocol
      if (errorLower.includes('dns error') || errorLower.includes('enotfound')) {
        // DNS error on HTTPS? Try HTTP. DNS error on HTTP? Give up.
        break;
      }
      
      // SSL errors: immediately try HTTP fallback
      if (errorLower.includes('ssl') || errorLower.includes('certificate')) {
        break;
      }
      
      // For timeouts and connection errors, retry with backoff
      if (attempt < maxRetries - 1) {
        const backoff = options.config 
          ? calculateBackoff(attempt, options.config.retry)
          : Math.pow(2, attempt) * 500 + Math.random() * 500;
        await sleep(backoff);
      }
    }
  }
  
  // All retries exhausted
  return {
    html: '',
    statusCode: 0,
    responseTimeMs: Date.now() - startTime,
    pageSizeBytes: 0,
    redirectChain: null,
    error: lastError || 'Unknown error after retries',
  };
}
