#!/usr/bin/env node
/**
 * Node crawler with real HTTP fetching and extraction.
 *
 * - Reads domains from a CSV (tries: domain, website, website_url, url, site, homepage; else first column)
 * - Processes in batches equal to --concurrency using Promise.allSettled
 * - Fetches HTML via undici and extracts company data via extract.ts
 * - Writes NDJSON lines to the output path with the expected fields
 * - Prints friendly progress logs and a completion summary
 *
 * KISS/DRY: Simple HTTP fetch + regex extraction, no complex parsing libraries.
 */

import fs from "fs";
import path from "path";
import { fetchHtml } from "./http";
import { extractAll } from "./extract";
import { loadCrawlerConfig } from "./config";

// Load centralized config (falls back to defaults if file not found)
const CONFIG = loadCrawlerConfig();

// ---------- Types ----------

export interface CrawlResult {
  domain: string;
  url: string;
  phones: string[];
  company_name?: string | null;
  facebook_url: string | null;
  linkedin_url: string | null;
  twitter_url: string | null;
  instagram_url: string | null;
  address: string | null;
  crawled_at: string; // ISO timestamp
  http_status: number;
  response_time_ms: number;
  page_size_bytes: number;
  method: string; // "http"
  error: string | null;
  _redirect_chain?: string[] | null;
  _note?: string | null;
}

export interface Args {
  input: string;
  output: string;
  concurrency: number;
  timeout: number; // seconds
  userAgent?: string;
  noColor?: boolean;
}

// ---------- CLI ----------

export function repoRoot(): string {
  // __dirname = .../src/crawlers/node/src
  return path.resolve(__dirname, "../../../..");
}

export function buildDefaultPaths() {
  const root = repoRoot();
  return {
    input: path.join(root, "data/inputs/sample-websites.csv"),
    output: path.join(root, "data/outputs/node_results.ndjson"),
  };
}

export function parseArgs(argv: string[] = process.argv.slice(2)): Args {
  const defaults = buildDefaultPaths();
  const args: Args = {
    input: defaults.input,
    output: defaults.output,
    concurrency: CONFIG.http.concurrency,
    timeout: CONFIG.http.timeoutSeconds,
    userAgent: CONFIG.http.userAgent,
    noColor: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => (i + 1 < argv.length ? argv[i + 1] : undefined);

    if (a.startsWith("--input=")) args.input = a.split("=", 2)[1];
    else if (a === "--input") args.input = next() ?? args.input, i++;
    else if (a.startsWith("--output=")) args.output = a.split("=", 2)[1];
    else if (a === "--output") args.output = next() ?? args.output, i++;
    else if (a.startsWith("--concurrency=")) args.concurrency = parseInt(a.split("=", 2)[1], 10);
    else if (a === "--concurrency") args.concurrency = parseInt(next() ?? `${args.concurrency}`, 10), i++;
    else if (a.startsWith("--timeout=")) args.timeout = parseFloat(a.split("=", 2)[1]);
    else if (a === "--timeout") args.timeout = parseFloat(next() ?? `${args.timeout}`), i++;
    else if (a.startsWith("--user-agent=")) args.userAgent = a.split("=", 2)[1];
    else if (a === "--user-agent") args.userAgent = next() ?? args.userAgent, i++;
    else if (a === "--no-color" || a === "--noColor") args.noColor = true;
  }

  return args;
}

// ---------- Small utils ----------

export function ensureParentDir(p: string) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
}

export function nowIso(): string {
  const d = new Date();
  // toISOString already ends with Z and includes milliseconds
  return d.toISOString();
}

export function canonicalDomain(value: string | undefined | null): string | null {
  if (!value) return null;
  let v = String(value).trim();
  if (!v) return null;
  try {
    if (v.includes("://")) {
      const u = new URL(v);
      v = u.hostname || u.host || u.pathname || v;
    }
  } catch {
    // ignore
  }
  v = v.toLowerCase();
  if (v.startsWith("www.")) v = v.slice(4);
  // strip path/query/fragment and trailing dots/slashes
  v = v.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].replace(/[./]+$/, "");
  return v || null;
}

export function dedupePreserveOrder(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const it of items) {
    if (!seen.has(it)) {
      seen.add(it);
      out.push(it);
    }
  }
  return out;
}

// Derive a simple company name from the domain (KISS):
// - take the left-most label
// - replace non-alphanumeric with spaces
// - title-case tokens and join with single space
export function deriveCompanyName(domain: string): string | null {
  try {
    const left = (domain || "").split(".")[0] || "";
    const tokens = left.replace(/[^a-z0-9]+/gi, " ").trim().split(/\s+/).filter(Boolean);
    const name = tokens.map((t) => t.charAt(0).toUpperCase() + t.slice(1)).join(" ");
    return name || null;
  } catch {
    return null;
  }
}

// Simple delimiter sniff: prefer comma, fall back to semicolon or tab
export function sniffDelimiter(headerLine: string): string {
  if ((headerLine.match(/,/g) || []).length >= (headerLine.match(/;/g) || []).length) {
    return ",";
  }
  if ((headerLine.match(/;/g) || []).length > 0) return ";";
  if ((headerLine.match(/\t/g) || []).length > 0) return "\t";
  return ",";
}

export function stripBOM(s: string): string {
  return s.charCodeAt(0) === 0xfeff ? s.slice(1) : s;
}

export function splitCsvLine(line: string, delimiter: string): string[] {
  // Minimal splitter: handles simple unquoted CSV. Good enough for scaffolding.
  return line.split(delimiter).map((x) => x.trim());
}

export function loadDomains(csvPath: string): string[] {
  if (!fs.existsSync(csvPath)) throw new Error(`Input CSV not found: ${csvPath}`);
  const raw = fs.readFileSync(csvPath, { encoding: "utf-8" });
  const text = stripBOM(raw);
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  if (lines.length === 0) return [];

  const headerLine = lines[0];
  const delimiter = sniffDelimiter(headerLine);
  const headers = splitCsvLine(headerLine, delimiter);

  const norm = (h: string) => h.trim().toLowerCase();
  const headerMap = new Map(headers.map((h, i) => [norm(h), i] as const));

  const preferred = ["domain", "website", "website_url", "url", "site", "homepage"];
  const candidateIdxs: number[] = [];
  for (const key of preferred) {
    const idx = headerMap.get(key);
    if (idx !== undefined) candidateIdxs.push(idx);
  }

  const hasKnownHeader = headers.some((h) => preferred.includes(norm(h)));
  const headerHasDelimiter = /[,;\t]/.test(headerLine);

  const domains: string[] = [];

  if (hasKnownHeader) {
    // Has a known header row
    for (let i = 1; i < lines.length; i++) {
      const row = splitCsvLine(lines[i], delimiter);
      let rawVal: string | null = null;
      for (const idx of candidateIdxs) {
        const v = row[idx];
        if (v && v.trim().length > 0) {
          rawVal = v.trim();
          break;
        }
      }
      if (rawVal === null && row.length > 0) rawVal = row[0];
      const d = canonicalDomain(rawVal);
      if (d) domains.push(d);
    }
  } else {
    // No known header present. If the line appears delimited, take first column for all rows; else treat as single-column file.
    if (headerHasDelimiter) {
      for (let i = 0; i < lines.length; i++) {
        const row = splitCsvLine(lines[i], delimiter);
        const d = canonicalDomain(row[0]);
        if (d) domains.push(d);
      }
    } else {
      for (const line of lines) {
        const d = canonicalDomain(line);
        if (d) domains.push(d);
      }
    }
  }

  return dedupePreserveOrder(domains);
}

export function chunked<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

/**
 * Fetch and extract data from a domain.
 * Uses real HTTP with undici + extract.ts.
 */
export async function fetchAndExtract(
  domain: string,
  timeoutSec: number,
  userAgent: string
): Promise<CrawlResult> {
  const url = `https://${domain}`;
  
  const fetchResult = await fetchHtml({
    url,
    timeoutMs: timeoutSec * 1000,
    userAgent,
    config: CONFIG,  // Pass config for retry/protocol settings
  });
  
  if (fetchResult.error) {
    return {
      domain,
      url,
      phones: [],
      company_name: deriveCompanyName(domain),
      facebook_url: null,
      linkedin_url: null,
      twitter_url: null,
      instagram_url: null,
      address: null,
      crawled_at: nowIso(),
      http_status: fetchResult.statusCode,
      response_time_ms: fetchResult.responseTimeMs,
      page_size_bytes: fetchResult.pageSizeBytes,
      method: "http",
      error: fetchResult.error,
      _redirect_chain: fetchResult.redirectChain,
      _note: null,
    };
  }
  
  // Extract data from HTML
  const extracted = extractAll(fetchResult.html);
  
  return {
    domain,
    url,
    phones: extracted.phones,
    company_name: extracted.company_name || deriveCompanyName(domain),
    facebook_url: extracted.facebook_url,
    linkedin_url: extracted.linkedin_url,
    twitter_url: extracted.twitter_url,
    instagram_url: extracted.instagram_url,
    address: extracted.address,
    crawled_at: nowIso(),
    http_status: fetchResult.statusCode,
    response_time_ms: fetchResult.responseTimeMs,
    page_size_bytes: fetchResult.pageSizeBytes,
    method: "http",
    error: null,
    _redirect_chain: fetchResult.redirectChain,
    _note: null,
  };
}

export function logBatchHeader(idx: number, total: number, size: number) {
  console.log(`Batch ${idx}/${total} (${size} domains)...`);
}

export function maybeLogBrowserFallback(domain: string) {
  if (domain.includes("javascript") || domain.includes("spa") || domain.includes("headless")) {
    console.log(`  ↳ Using browser fallback for ${domain}`);
  }
}

export async function run(args: Args): Promise<number> {
  // Color helpers (TTY only unless explicitly disabled)
  const COLORS = { 
    green: "\x1b[32m", 
    cyan: "\x1b[36m", 
    yellow: "\x1b[33m", 
    red: "\x1b[31m",
    reset: "\x1b[0m" 
  } as const;
  const useColor = !args.noColor && process.stdout.isTTY;
  const color = (s: string, c: keyof typeof COLORS) => (useColor ? `${COLORS[c]}${s}${COLORS.reset}` : s);
  const info = (s: string) => console.log(color(s, "cyan"));
  const ok = (s: string) => console.log(color(s, "green"));
  const warn = (s: string) => console.warn(color(s, "yellow"));
  const error = (s: string) => console.error(color(s, "red"));
  const domains = loadDomains(args.input);
  const total = domains.length;

  info("Node Crawler Starting");
  info(`  Domains: ${total}`);
  info(`  Concurrency: ${args.concurrency}`);
  info(`  Timeout: ${Math.floor(args.timeout)}s`);
  info(`  Output: ${args.output}`);

  ensureParentDir(args.output);
  const start = Date.now();

  const batches = chunked(domains, Math.max(1, args.concurrency));
  const totalBatches = batches.length;
  let written = 0;

  const out = fs.createWriteStream(args.output, { encoding: "utf-8" });

  for (let i = 0; i < totalBatches; i++) {
    const batch = batches[i];
    info(`Batch ${i + 1}/${totalBatches} (${batch.length} domains)...`);
    for (const d of batch) maybeLogBrowserFallback(d);

    const results = await Promise.all(
      batch.map((d) =>
        fetchAndExtract(d, args.timeout, args.userAgent || "Mozilla/5.0").catch((e: any): CrawlResult => ({
          domain: d,
          url: `https://${d}`,
          phones: [],
          company_name: deriveCompanyName(d),
          facebook_url: null,
          linkedin_url: null,
          twitter_url: null,
          instagram_url: null,
          address: null,
          crawled_at: nowIso(),
          http_status: 0,
          response_time_ms: 0,
          page_size_bytes: 0,
          method: "http",
          error: String(e?.message ?? e),
          _redirect_chain: null,
          _note: null,
        }))
      )
    );

    for (const r of results) {
      out.write(JSON.stringify(r) + "\n");
      written += 1;
    }
  }

  await new Promise((res) => out.end(res));

  const elapsed = (Date.now() - start) / 1000;
  const avg = elapsed > 0 ? written / elapsed : 0;

  console.log("");
  info("--------------------------------");
  info("--- Crawler finished: `node` ---");
  info("--------------------------------");
  console.log("");
  if (elapsed < 600) { // < 10 mins
    ok(`Completed in ${Math.floor(elapsed / 60)}m ${Math.floor(elapsed % 60)}s`);
  } else if (elapsed < 900) { // < 15 mins - yellow
    warn(`Completed in ${Math.floor(elapsed / 60)}m ${Math.floor(elapsed % 60)}s`);
  } else { // >= 15 mins - red
    error(`Completed in ${Math.floor(elapsed / 60)}m ${Math.floor(elapsed % 60)}s`);
  }
  console.log("");
  info("--------------------------------");
  console.log("");

  info(`Output: ${args.output}`);
  info(`Average: ${avg.toFixed(1)} domains/sec`);
  return 0;
}

async function main() {
  try {
    const args = parseArgs();
    const code = await run(args);
    process.exitCode = code;
  } catch (e: any) {
    console.error("Fatal error:", e?.stack || e?.message || e);
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}
