/**
 * Centralized crawler configuration loader.
 * Reads settings from configs/crawl.policy.yaml and provides defaults.
 */

import fs from "fs";
import path from "path";
import yaml from "yaml";

export interface HttpConfig {
  timeoutSeconds: number;
  concurrency: number;
  userAgent: string;
  followRedirects: boolean;
  maxRedirects: number;
}

export interface RetryConfig {
  maxAttempts: number;
  backoffBaseSeconds: number;
  jitterMaxSeconds: number;
  retryOn: string[];
  skipRetryOn: string[];
}

export interface ProtocolConfig {
  tryHttpsFirst: boolean;
  fallbackToHttp: boolean;
  httpFallbackOn: string[];
}

export interface CrawlerConfig {
  http: HttpConfig;
  retry: RetryConfig;
  protocol: ProtocolConfig;
}

const DEFAULT_CONFIG: CrawlerConfig = {
  http: {
    timeoutSeconds: 12,  // configDefaultOverride.timeout
    concurrency: 50,  // configDefaultOverride.concurrency
    userAgent: "Mozilla/5.0 (compatible; SpaceCrawler/1.0)",
    followRedirects: true,
    maxRedirects: 5,
  },
  retry: {
    maxAttempts: 3,
    backoffBaseSeconds: 0.5,
    jitterMaxSeconds: 0.5,
    retryOn: ["timeout", "connection_reset", "connection_refused", "temporary_error"],
    skipRetryOn: ["dns_error", "invalid_domain"],
  },
  protocol: {
    tryHttpsFirst: true,
    fallbackToHttp: true,
    httpFallbackOn: ["ssl_error", "certificate_error", "handshake_error"],
  },
};

/**
 * Load crawler configuration from YAML file.
 * Falls back to defaults if file doesn't exist or can't be parsed.
 */
export function loadCrawlerConfig(configPath?: string): CrawlerConfig {
  if (!configPath) {
    // Default: repo_root/configs/crawl.policy.yaml
    const repoRoot = path.resolve(__dirname, "../../../..");
    configPath = path.join(repoRoot, "configs", "crawl.policy.yaml");
  }

  // Return defaults if file doesn't exist
  if (!fs.existsSync(configPath)) {
    return DEFAULT_CONFIG;
  }

  try {
    const fileContent = fs.readFileSync(configPath, "utf-8");
    const data = yaml.parse(fileContent);

    if (!data) {
      return DEFAULT_CONFIG;
    }

    // Extract sections with defaults
    const httpData = data.http || {};
    const retryData = data.retry || {};
    const protocolData = data.protocol || {};

    return {
      http: {
        timeoutSeconds: httpData.timeout_seconds ?? DEFAULT_CONFIG.http.timeoutSeconds,
        concurrency: httpData.concurrency ?? DEFAULT_CONFIG.http.concurrency,
        userAgent: httpData.user_agent ?? DEFAULT_CONFIG.http.userAgent,
        followRedirects: httpData.follow_redirects ?? DEFAULT_CONFIG.http.followRedirects,
        maxRedirects: httpData.max_redirects ?? DEFAULT_CONFIG.http.maxRedirects,
      },
      retry: {
        maxAttempts: retryData.max_attempts ?? DEFAULT_CONFIG.retry.maxAttempts,
        backoffBaseSeconds: retryData.backoff_base_seconds ?? DEFAULT_CONFIG.retry.backoffBaseSeconds,
        jitterMaxSeconds: retryData.jitter_max_seconds ?? DEFAULT_CONFIG.retry.jitterMaxSeconds,
        retryOn: retryData.retry_on ?? DEFAULT_CONFIG.retry.retryOn,
        skipRetryOn: retryData.skip_retry_on ?? DEFAULT_CONFIG.retry.skipRetryOn,
      },
      protocol: {
        tryHttpsFirst: protocolData.try_https_first ?? DEFAULT_CONFIG.protocol.tryHttpsFirst,
        fallbackToHttp: protocolData.fallback_to_http ?? DEFAULT_CONFIG.protocol.fallbackToHttp,
        httpFallbackOn: protocolData.http_fallback_on ?? DEFAULT_CONFIG.protocol.httpFallbackOn,
      },
    };
  } catch (error) {
    // If anything goes wrong, return defaults
    console.warn(`Failed to load config from ${configPath}, using defaults:`, error);
    return DEFAULT_CONFIG;
  }
}

/**
 * Get default configuration (useful for testing).
 */
export function getDefaultConfig(): CrawlerConfig {
  return DEFAULT_CONFIG;
}

/**
 * Calculate exponential backoff delay with jitter.
 * 
 * Implements the formula: delay = base * (2 ^ attempt) + random_jitter
 * This prevents thundering herd problems when many requests retry simultaneously.
 * 
 * @param attempt - Current retry attempt (0-indexed)
 * @param config - RetryConfig with backoffBaseSeconds and jitterMaxSeconds
 * @returns Delay in milliseconds
 * 
 * @example
 * ```typescript
 * const config = { backoffBaseSeconds: 0.5, jitterMaxSeconds: 0.5 };
 * calculateBackoff(0, config); // First retry: ~500ms + jitter
 * calculateBackoff(1, config); // Second retry: ~1000ms + jitter
 * calculateBackoff(2, config); // Third retry: ~2000ms + jitter
 * ```
 */
export function calculateBackoff(attempt: number, config: RetryConfig): number {
  const baseDelayMs = Math.pow(2, attempt) * config.backoffBaseSeconds * 1000;
  const jitterMs = Math.random() * config.jitterMaxSeconds * 1000;
  return baseDelayMs + jitterMs;
}
