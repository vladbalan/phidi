# Crawler Comparison Report

## Coverage
- Python: 0/1001 sites (0.0%)
- Node: 0/1001 sites (0.0%)
- Scrapy: 644/1001 sites (64.3%)
- Scrapy-lite: 643/1001 sites (64.2%)
**Winner: Scrapy** (+1 sites)

## Speed
### Total Crawl Time
- Python: 2m 39s
- Node: 3m 25s
- Scrapy: 0m 55s
- Scrapy-lite: 0m 52s
**Winner: Scrapy-lite** (-153s, 74% faster)

### Avg Response Time (per request)
- Python: -
- Node: -
- Scrapy: 569ms
- Scrapy-lite: 512ms
**Winner: Scrapy-lite** (-57ms, 10% faster)

## Data Quality
- Python: 0.0 datapoints/site
- Node: 0.0 datapoints/site
- Scrapy: 1.6 datapoints/site
- Scrapy-lite: 17.9 datapoints/site
**Winner: Scrapy-lite** (+16.3 datapoints)

## Final Scores
*Formula: Score = 0.6 × Coverage + 0.4 × Quality*

*Quality = avg(phone_fill_rate, social_fill_rate, address_fill_rate)*

- **Scrapy-lite**: 0.617452 (coverage=0.642, quality=0.580)
- **Scrapy**: 0.521418 (coverage=0.643, quality=0.339)
- **Python**: 0.000000 (coverage=0.000, quality=0.000)
- **Node**: 0.000000 (coverage=0.000, quality=0.000)

## Recommendation
**Use Scrapy-lite crawler** (score: 0.617452)
This crawler provides the best balance of coverage (64.2%) and data quality.
Speed difference is acceptable.
