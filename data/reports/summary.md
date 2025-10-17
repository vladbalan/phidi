# Crawler Comparison Report

## Coverage
- Scrapy-lite-aggressive: 650/1001 sites (64.9%)
- Scrapy-aggressive: 650/1001 sites (64.9%)
- Python-aggressive: 653/1001 sites (65.2%)
- Node-aggressive: 690/1001 sites (68.9%)
**Winner: Node-aggressive** (+37 sites)

## Speed
### Total Crawl Time
- Scrapy-lite-aggressive: 1m 18s
- Scrapy-aggressive: 1m 5s
- Python-aggressive: 5m 18s
- Node-aggressive: 6m 50s
**Winner: Scrapy-aggressive** (-345s, 84% faster)

### Avg Response Time (per request)
- Scrapy-lite-aggressive: 774ms
- Scrapy-aggressive: 536ms
- Python-aggressive: 1188ms
- Node-aggressive: 1352ms
**Winner: Scrapy-aggressive** (-816ms, 60% faster)

## Data Quality
- Scrapy-lite-aggressive: 17.9 datapoints/site
- Scrapy-aggressive: 1.6 datapoints/site
- Python-aggressive: 17.7 datapoints/site
- Node-aggressive: 6.4 datapoints/site
**Winner: Scrapy-lite-aggressive** (+0.2 datapoints)

## Final Scores
*Formula: Score = 0.6 × Coverage + 0.4 × Quality*

*Quality = avg(phone_fill_rate, social_fill_rate, address_fill_rate)*

- **Scrapy-lite-aggressive**: 0.621200 (coverage=0.649, quality=0.579)
- **Python-aggressive**: 0.619688 (coverage=0.652, quality=0.571)
- **Node-aggressive**: 0.532427 (coverage=0.689, quality=0.297)
- **Scrapy-aggressive**: 0.524174 (coverage=0.649, quality=0.336)

## Recommendation
**Use Scrapy-lite-aggressive crawler** (score: 0.621200)
This crawler provides the best balance of coverage (64.9%) and data quality.
Note: large speed difference.
