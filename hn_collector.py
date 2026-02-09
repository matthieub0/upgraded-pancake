#!/usr/bin/env python3
"""
HN Signal Collector v1.0
========================
Collects and structures signals from Hacker News for startup formation detection.

Targets:
  - Show HN posts (builders announcing things)
  - High-engagement technical threads (problem emergence)
  - Author intent classification
  - Outbound link extraction (GitHub, demos, docs)

Output: JSON file with structured HNSignal objects

Usage:
  python3 hn_collector.py [lookback_days] [output_dir]
  python3 hn_collector.py 30 ./hn_signals
"""

import requests
import json
import time
import re
import os
import sys
import html
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────────────

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
HITS_PER_PAGE = 200
REQUEST_DELAY = 0.3  # seconds between API calls

# Collection thresholds
MIN_POINTS_SHOW_HN = 3           # low bar — catch early signals
MIN_POINTS_THREAD = 10           # for general stories
MIN_COMMENTS_THREAD = 25         # "high engagement" bar
COMMENT_FETCH_MIN_POINTS = 15    # fetch comments when post has this many points
COMMENT_FETCH_MIN_COMMENTS = 10  # or this many comments
MAX_COMMENTS_PER_POST = 12       # top N comments to store

# ── Intent Patterns ────────────────────────────────────────────────────────

BUILDER_PATTERNS = [
    r'\bi built\b', r'\bwe built\b', r'\bi made\b', r'\bwe made\b',
    r'\bi created\b', r'\bwe created\b', r'\blaunching\b', r'\bjust launched\b',
    r"\bwe'?re building\b", r"\bi'?m building\b", r'\bside project\b',
    r'\bopen.?source[d]?\b', r"\bwe'?re experimenting\b",
    r"\bi'?ve been working\b", r"\bwe'?ve been working\b",
    r'\bjust shipped\b', r'\bjust released\b',
    r'\bannouncing\b', r'\bintroducing\b', r'\bhere is my\b',
    r'\bhere is our\b', r'\bcheck out my\b', r'\bcheck out our\b',
]

EXPERIMENTER_PATTERNS = [
    r'\bexperimenting with\b', r'\bplaying with\b', r'\bprototype\b',
    r'\bproof of concept\b', r'\bpoc\b', r'\bhacking on\b',
    r'\btinkering\b', r'\bweekend project\b', r'\bearly.?stage\b',
    r'\balpha\b', r'\bbeta\b', r'\bwip\b',
]

# Monetisation-language patterns (signal of seriousness)
MONETISE_PATTERNS = [
    r'\bpricing\b', r'\bsubscription\b', r'\bsaas\b', r'\bmrr\b',
    r'\barr\b', r'\bpaying customers\b', r'\brevenue\b',
    r'\bfreemium\b', r'\benterprise\b', r'\bself.?hosted?\b',
    r'\bon.?prem\b', r'\bsign up\b', r'\bwaitlist\b',
]

# ── Link Patterns ──────────────────────────────────────────────────────────

GITHUB_REPO_RE = re.compile(r'https?://github\.com/([\w\-\.]+)/([\w\-\.]+)', re.I)
URL_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.I)
DEMO_INDICATORS = ['demo', 'try', 'playground', 'app.', 'live', 'preview']
DOC_INDICATORS = ['docs', 'documentation', 'wiki', 'readme', 'guide', 'tutorial', 'manual']
GITHUB_NOISE_PATHS = {'about', 'features', 'pricing', 'enterprise',
                      'settings', 'explore', 'topics', 'trending',
                      'collections', 'sponsors', 'notifications'}


def strip_html(text):
    """Strip HTML tags and decode entities."""
    if not text:
        return ''
    text = re.sub(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>', r' \1 ', text)  # keep hrefs
    text = re.sub(r'<p>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class HNCollector:
    """Collects and structures Hacker News signals."""

    def __init__(self, lookback_days=30, output_dir="hn_signals"):
        self.lookback_days = lookback_days
        self.output_dir = output_dir
        self.cutoff_ts = int(
            (datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp()
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "HNSignalCollector/1.0"})
        self.stats = defaultdict(int)

    # ── API helpers ────────────────────────────────────────────────────

    def _api_get(self, endpoint, params=None):
        time.sleep(REQUEST_DELAY)
        url = f"{ALGOLIA_BASE}/{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            self.stats['api_calls'] += 1
            return resp.json()
        except requests.RequestException as e:
            print(f"  [WARN] API error on {endpoint}: {e}")
            self.stats['api_errors'] += 1
            return None

    def _paginate(self, endpoint, params, max_pages=50):
        all_hits = []
        params = dict(params)
        params['hitsPerPage'] = HITS_PER_PAGE

        for page in range(max_pages):
            params['page'] = page
            data = self._api_get(endpoint, params)
            if not data or not data.get('hits'):
                break
            all_hits.extend(data['hits'])
            nb = data.get('nbPages', '?')
            print(f"    page {page + 1}/{nb} — {len(all_hits)} hits")
            if page + 1 >= data.get('nbPages', 0):
                break

        return all_hits

    # ── Collectors ─────────────────────────────────────────────────────

    def collect_show_hn(self):
        print(f"\n{'─'*60}")
        print(f"  Show HN posts  (last {self.lookback_days}d, ≥{MIN_POINTS_SHOW_HN} pts)")
        print(f"{'─'*60}")
        hits = self._paginate("search_by_date", {
            'tags': 'show_hn',
            'numericFilters': f'created_at_i>{self.cutoff_ts},points>{MIN_POINTS_SHOW_HN}',
        })
        self.stats['show_hn_collected'] = len(hits)
        print(f"  → {len(hits)} Show HN posts")
        return hits

    def collect_threads(self):
        print(f"\n{'─'*60}")
        print(f"  High-engagement threads  (last {self.lookback_days}d, "
              f"≥{MIN_COMMENTS_THREAD} comments, ≥{MIN_POINTS_THREAD} pts)")
        print(f"{'─'*60}")
        hits = self._paginate("search_by_date", {
            'tags': 'story',
            'numericFilters': (
                f'created_at_i>{self.cutoff_ts},'
                f'num_comments>{MIN_COMMENTS_THREAD},'
                f'points>{MIN_POINTS_THREAD}'
            ),
        })
        # exclude Show HN (collected separately)
        hits = [h for h in hits if 'show_hn' not in h.get('_tags', [])]
        self.stats['threads_collected'] = len(hits)
        print(f"  → {len(hits)} threads (excl. Show HN)")
        return hits

    # ── Comment fetching ───────────────────────────────────────────────

    def fetch_comments(self, story_id):
        data = self._api_get("search", {
            'tags': f'comment,story_{story_id}',
            'hitsPerPage': MAX_COMMENTS_PER_POST,
        })
        if not data:
            return []
        return data.get('hits', [])

    def _should_fetch_comments(self, post):
        return (post.get('points', 0) >= COMMENT_FETCH_MIN_POINTS
                or post.get('num_comments', 0) >= COMMENT_FETCH_MIN_COMMENTS)

    # ── Extraction helpers ─────────────────────────────────────────────

    @staticmethod
    def extract_links(text):
        if not text:
            return {'github_repos': [], 'demos': [], 'docs': [], 'other': []}
        links = {'github_repos': [], 'demos': [], 'docs': [], 'other': []}
        seen = set()

        for raw_url in URL_RE.findall(text):
            url = raw_url.rstrip('.,;:!?)')
            if url in seen:
                continue
            seen.add(url)

            repo_m = GITHUB_REPO_RE.search(url)
            if repo_m:
                slug = f"{repo_m.group(1)}/{repo_m.group(2)}"
                slug = slug.rstrip('.')
                if slug.split('/')[0].lower() not in GITHUB_NOISE_PATHS:
                    links['github_repos'].append(slug)
                continue

            url_lower = url.lower()
            if any(ind in url_lower for ind in DOC_INDICATORS):
                links['docs'].append(url)
            elif any(ind in url_lower for ind in DEMO_INDICATORS):
                links['demos'].append(url)
            else:
                links['other'].append(url)

        # deduplicate
        for k in links:
            links[k] = list(dict.fromkeys(links[k]))
        return links

    @staticmethod
    def classify_intent(title, text):
        combined = f"{title or ''} {text or ''}".lower()
        b = sum(1 for p in BUILDER_PATTERNS if re.search(p, combined))
        e = sum(1 for p in EXPERIMENTER_PATTERNS if re.search(p, combined))
        if b >= 2 or (b == 1 and e == 0):
            return 'builder'
        if e >= 1:
            return 'experimenter'
        return 'discussion'

    @staticmethod
    def detect_monetisation(title, text):
        combined = f"{title or ''} {text or ''}".lower()
        hits = [p for p in MONETISE_PATTERNS if re.search(p, combined)]
        return len(hits) > 0, hits

    # ── Signal builder ─────────────────────────────────────────────────

    def build_signal(self, post, post_type, comments=None):
        title = post.get('title', '')
        body = strip_html(post.get('story_text') or post.get('text') or '')
        url = post.get('url', '')

        # Links from post
        all_links = self.extract_links(f"{body} {url}")

        # Links + text from comments
        comment_objs = []
        if comments:
            for c in comments[:MAX_COMMENTS_PER_POST]:
                c_text = strip_html(c.get('comment_text') or c.get('text') or '')
                if c_text:
                    c_links = self.extract_links(c_text)
                    for k in all_links:
                        all_links[k].extend(c_links.get(k, []))
                    comment_objs.append({
                        'author': c.get('author', ''),
                        'text': c_text[:1500],
                        'points': c.get('points', 0),
                    })
            # deduplicate merged links
            for k in all_links:
                all_links[k] = list(dict.fromkeys(all_links[k]))

        intent = self.classify_intent(title, body)
        has_monetisation, monetise_hits = self.detect_monetisation(title, body)

        return {
            'id': f"hn_{post.get('objectID', '?')}",
            'hn_id': post.get('objectID'),
            'type': post_type,
            'title': title,
            'url': url,
            'hn_url': f"https://news.ycombinator.com/item?id={post.get('objectID')}",
            'author': post.get('author', ''),
            'points': post.get('points', 0),
            'num_comments': post.get('num_comments', 0),
            'created_at': post.get('created_at', ''),
            'created_at_ts': post.get('created_at_i', 0),
            'body_text': body[:3000] if body else None,
            'extracted_links': all_links,
            'author_intent': intent,
            'has_github': len(all_links['github_repos']) > 0,
            'has_demo': len(all_links['demos']) > 0,
            'has_docs': len(all_links['docs']) > 0,
            'has_monetisation_language': has_monetisation,
            'builder_present': intent in ('builder', 'experimenter'),
            'top_comments': comment_objs,
        }

    # ── Main pipeline ──────────────────────────────────────────────────

    def run(self):
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        os.makedirs(f"{self.output_dir}/raw", exist_ok=True)

        # 1. Collect
        show_hn = self.collect_show_hn()
        threads = self.collect_threads()

        # 2. Build signals
        print(f"\n{'─'*60}")
        print("  Building signals …")
        print(f"{'─'*60}")

        signals = []

        for i, post in enumerate(show_hn):
            comments = None
            if self._should_fetch_comments(post):
                comments = self.fetch_comments(post['objectID'])
                self.stats['comment_fetches'] += 1
            signals.append(self.build_signal(post, 'show_hn', comments))
            if (i + 1) % 50 == 0:
                print(f"    {i+1}/{len(show_hn)} Show HN processed")

        print(f"    ✓ {len(show_hn)} Show HN processed")

        for i, post in enumerate(threads):
            comments = None
            if self._should_fetch_comments(post):
                comments = self.fetch_comments(post['objectID'])
                self.stats['comment_fetches'] += 1
            signals.append(self.build_signal(post, 'technical_thread', comments))
            if (i + 1) % 100 == 0:
                print(f"    {i+1}/{len(threads)} threads processed")

        print(f"    ✓ {len(threads)} threads processed")

        # 3. Sort: builders first, then points
        signals.sort(key=lambda s: (
            s['builder_present'],
            s['has_github'],
            s['has_monetisation_language'],
            s['points'],
        ), reverse=True)

        # 4. Write output
        output = {
            'meta': {
                'collected_at': datetime.now(timezone.utc).isoformat(),
                'lookback_days': self.lookback_days,
                'cutoff_date': datetime.fromtimestamp(
                    self.cutoff_ts, tz=timezone.utc
                ).isoformat(),
                'total_signals': len(signals),
                'stats': dict(self.stats),
            },
            'signals': signals,
        }

        dated = f"{self.output_dir}/raw/hn_signals_{ts}.json"
        latest = f"{self.output_dir}/raw/hn_signals_latest.json"

        for path in (dated, latest):
            with open(path, 'w') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

        # 5. Summary
        builders = sum(1 for s in signals if s['author_intent'] == 'builder')
        with_gh  = sum(1 for s in signals if s['has_github'])
        with_demo = sum(1 for s in signals if s['has_demo'])
        with_mon = sum(1 for s in signals if s['has_monetisation_language'])

        print(f"\n{'═'*60}")
        print("  COLLECTION COMPLETE")
        print(f"{'═'*60}")
        print(f"  Total signals:        {len(signals)}")
        print(f"  Show HN:              {self.stats['show_hn_collected']}")
        print(f"  Threads:              {self.stats['threads_collected']}")
        print(f"  Builder intent:       {builders}")
        print(f"  With GitHub link:     {with_gh}")
        print(f"  With demo:            {with_demo}")
        print(f"  With monetisation:    {with_mon}")
        print(f"  API calls:            {self.stats['api_calls']}")
        print(f"  Output:               {dated}")
        print(f"{'═'*60}")

        return dated, latest


if __name__ == '__main__':
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    out  = sys.argv[2] if len(sys.argv) > 2 else 'hn_signals'
    collector = HNCollector(lookback_days=days, output_dir=out)
    collector.run()
