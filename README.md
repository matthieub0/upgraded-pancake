# Hacker News Signal Detection Module

## Overview

This module detects **problem emergence** and **builder presence** on Hacker News. It's the first component of your startup formation detection system.

### What It Does

- Scans HN for technical discussions and product launches
- Identifies builders actively working on problems
- Extracts GitHub repos, demos, and docs
- Scores technical depth and builder commitment
- Outputs structured signals for the orchestration agent

### What It Outputs

**HNSignal objects** containing:
- Inferred problem being solved
- Builder presence (true/false)
- Technical depth score (0-10)
- Linked artifacts (GitHub, demos, docs)
- Signal type (show_hn, launch, discussion)

## Quick Start

### Demo (No API Required)

```bash
python3 demo_hn_detector.py
```

This runs on mock data to show you how the system works.

### Production Setup

#### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 2. Network Setup

The HN APIs (Firebase and Algolia) are currently being blocked by the network proxy in this environment. For production:

**Option A: Run on a server with open internet access**
- AWS EC2, DigitalOcean, or any VPS
- No special API keys needed (HN APIs are public)

**Option B: Use a scraping service**
- [Apify HN scraper](https://apify.com/apify/hacker-news-scraper)
- [Scrapy with rotating proxies](https://github.com/scrapy/scrapy)

#### 3. Run Daily Detection

```bash
python3 run_hn_detector.py
```

This will:
1. Scan last 24 hours of HN
2. Filter for high-quality signals (score >10, tech depth >3)
3. Generate markdown briefing
4. Save raw JSON signals

#### 4. Schedule with Cron

Add to your crontab:

```bash
# Run every day at 9 AM
0 9 * * * cd /path/to/project && python3 run_hn_detector.py >> logs/hn_$(date +\%Y\%m\%d).log 2>&1
```

## Configuration

### Adjust Detection Thresholds

In `run_hn_detector.py`, modify:

```python
signals = detector.get_daily_signals(
    min_score=10,           # HN points threshold (default: 10)
    min_technical_depth=3   # Technical score 0-10 (default: 3)
)
```

**Recommendation:**
- `min_score=20` + `min_technical_depth=5` = Very high quality, fewer signals
- `min_score=10` + `min_technical_depth=3` = Balanced (recommended)
- `min_score=5` + `min_technical_depth=2` = More signals, more noise

### Customize Keywords

In `hn_module.py`, edit the technical keywords:

```python
class HNAnalyzer:
    TECHNICAL_KEYWORDS = [
        'api', 'algorithm', 'llm', 'ai',
        # Add your focus areas:
        'fintech', 'compliance', 'data warehouse',
        'privacy', 'encryption', 'regulatory'
    ]
```

## Output Format

### JSON Structure

```json
{
  "hn_id": 39000001,
  "title": "Show HN: Open-source alternative to Snowflake",
  "author": "europeanfounder",
  "score": 245,
  "num_comments": 87,
  "created_at": "2026-02-09T00:00:00",
  
  "inferred_problem": "EU data residency compliance for analytics",
  "builder_present": true,
  "technical_depth_score": 8,
  "signal_type": "launch",
  
  "github_links": ["https://github.com/eu-datawarehouse/snowflake-alt"],
  "demo_links": [],
  "docs_links": [],
  
  "comment_sample": [...]
}
```

### Markdown Briefing

Organized into three sections:
1. **🚀 Launches** - Builder + artifacts (highest priority)
2. **💡 Show HN** - Product launches without artifacts yet
3. **💬 Technical Discussions** - Problem discussions worth tracking

## How The Analysis Works

### 1. Builder Detection

Looks for patterns like:
- "I built...", "We built...", "Show HN"
- Author actively replying in comments (2+ replies)
- Links to GitHub/demos with first-person language

### 2. Technical Depth Scoring (0-10)

Combines:
- Technical keywords in title/text (max +3 points)
- Comment engagement (high engagement = +2)
- Technical discussion in comments (+3)
- GitHub/code links (+2)

**Score interpretation:**
- 0-2: General discussion
- 3-5: Technical conversation
- 6-8: Deep technical content
- 9-10: High-quality technical launch

### 3. Problem Inference

Extracts what problem is being solved:
- Pattern matching: "solution to X", "helps with Y", "solves Z"
- Fallback: Uses the post title

### 4. Link Extraction

Finds:
- **GitHub**: `github.com/...`
- **Demos**: URLs with "demo", "app", "try", "playground"
- **Docs**: URLs with "docs", "documentation", "readme"

## Signal Types

1. **launch** - Builder present + (GitHub OR demo link)
   - *Most valuable for your use case*
   - Indicates serious execution
   
2. **show_hn** - "Show HN" in title
   - Product announcement
   - May or may not have links yet
   
3. **discussion** - Everything else
   - Problem discussions
   - May reveal unaddressed markets

## Integration with Other Modules

### For the Orchestration Agent

The HN module outputs `HNSignal` objects. The orchestrator should:

1. **Entity Resolution**
   - Match HN usernames to GitHub profiles
   - Cross-reference GitHub links with GitHub module
   - Look for people from the LinkedIn talent module

2. **Pattern Detection**
   ```
   HNSignal (problem: "EU compliance for X")
   + TalentSignal (2-3 people from FinTech co)
   + GitHubSignal (new repo, star velocity)
   = High confidence formation
   ```

3. **Europe Filtering**
   - Look for EU-specific problems (GDPR, AI Act, SEPA, etc.)
   - Check if GitHub repos mention EU
   - Cross-reference with regulatory signals

### Example Flow

```
Day 1: HN post about "GDPR compliance is broken"
  → HNSignal created (problem identified)

Day 15: "Show HN: GDPR compliance tool"
  → HNSignal (builder present, GitHub link)
  → GitHub module finds new org
  
Day 30: LinkedIn shows 3 people left Stripe
  → Orchestrator connects the dots
  → EmergingFormation object created
```

## Filtering for European Signals

Add European filtering in `hn_module.py`:

```python
EU_KEYWORDS = [
    'gdpr', 'eu', 'europe', 'european', 'brexit',
    'sepa', 'ai act', 'dma', 'dsa', 'psd2',
    'schrems ii', 'regulatory', 'compliance'
]

def is_likely_european(signal: HNSignal) -> bool:
    text = f"{signal.title} {signal.text or ''}".lower()
    return any(keyword in text for keyword in EU_KEYWORDS)
```

## Troubleshooting

### "No signals found"

1. **Check thresholds** - Lower `min_score` and `min_technical_depth`
2. **Check timeframe** - Try `days_back=7` instead of 1
3. **Network issues** - Ensure HN API is accessible

### "Technical depth scores are low"

- Add more relevant keywords to `TECHNICAL_KEYWORDS`
- Check that comments are being fetched
- May need to adjust scoring weights

### "Missing some obvious launches"

- Check if they have "Show HN" in title
- Verify GitHub links are being extracted
- May need to add more builder patterns

## Next Steps

1. **Run the demo** to see how it works
2. **Review mock signals** in demo output
3. **Adjust thresholds** based on signal quality
4. **Set up production** on a server with API access
5. **Schedule daily runs** via cron
6. **Build the GitHub module** next (complements HN signals)

## Files

- `hn_module.py` - Core detection logic
- `run_hn_detector.py` - Production runner
- `demo_hn_detector.py` - Demo with mock data
- `requirements.txt` - Dependencies

## Questions?

The module is designed to be:
- **Conservative** - Filters out noise
- **Structured** - Outputs standardized signals
- **Extensible** - Easy to add European filtering

Adjust based on what signals you actually want to see!
