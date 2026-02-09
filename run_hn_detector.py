#!/usr/bin/env python3
"""
Example usage of the HN Signal Detector

Run daily or weekly to get a briefing of interesting HN activity
"""

from hn_module import HNSignalDetector
import json
from datetime import datetime


def main():
    """Run the detector and save results"""
    
    detector = HNSignalDetector()
    
    print("🔍 Scanning Hacker News for signals...")
    print("=" * 60)
    
    # Get signals from last 24 hours
    # Adjust these thresholds based on what you want to see:
    # - min_score: HN points (10-20 is good for filtering noise)
    # - min_technical_depth: 0-10 score (3-5 catches technical content)
    signals = detector.get_daily_signals(
        min_score=10,
        min_technical_depth=3
    )
    
    print(f"\n✅ Found {len(signals)} high-quality signals\n")
    
    # Filter for most interesting: builder present + artifacts
    high_priority = [
        s for s in signals 
        if s.builder_present and (s.github_links or s.demo_links)
    ]
    
    print(f"🎯 {len(high_priority)} high-priority signals (builder + artifacts)\n")
    
    # Generate briefing
    briefing = detector.generate_briefing(signals)
    
    # Save to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save markdown briefing
    with open(f'briefing_{timestamp}.md', 'w') as f:
        f.write(briefing)
    print(f"📄 Saved briefing to briefing_{timestamp}.md")
    
    # Save raw JSON
    with open(f'signals_{timestamp}.json', 'w') as f:
        json.dump([s.to_dict() for s in signals], f, indent=2)
    print(f"💾 Saved raw signals to signals_{timestamp}.json")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for signal in high_priority[:5]:
        print(f"\n🚀 {signal.title}")
        print(f"   Author: {signal.author}")
        print(f"   Problem: {signal.inferred_problem}")
        if signal.github_links:
            print(f"   GitHub: {signal.github_links[0]}")
        print(f"   https://news.ycombinator.com/item?id={signal.hn_id}")


if __name__ == "__main__":
    main()
