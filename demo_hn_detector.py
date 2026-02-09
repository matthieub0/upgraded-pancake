#!/usr/bin/env python3
"""
Demo HN Signal Detector with mock data
Shows how the system works without needing API access
"""

from hn_module import HNSignal, HNAnalyzer
from datetime import datetime, timedelta
import json


# Mock HN data - examples of what you'd see
MOCK_HN_DATA = [
    {
        "id": 39000001,
        "title": "Show HN: Open-source alternative to Snowflake for EU data residency",
        "by": "europeanfounder",
        "score": 245,
        "descendants": 87,
        "time": int((datetime.now() - timedelta(hours=8)).timestamp()),
        "type": "story",
        "url": "https://github.com/eu-datawarehouse/snowflake-alt",
        "text": "We built this because GDPR compliance was killing our data analytics. 6 months of nights and weekends. Currently running in production at 3 companies. Looking for feedback!"
    },
    {
        "id": 39000002,
        "title": "Show HN: Real-time compliance monitoring for AI Act",
        "by": "berlinai",
        "score": 189,
        "descendants": 54,
        "time": int((datetime.now() - timedelta(hours=5)).timestamp()),
        "type": "story",
        "url": None,
        "text": "With EU AI Act enforcement starting in 2026, we're building automated compliance checking. Demo: https://ai-act-demo.eu Open source repo: https://github.com/aiact/monitor"
    },
    {
        "id": 39000003,
        "title": "The problem with current API key management in Europe",
        "by": "securitydev",
        "score": 342,
        "descendants": 156,
        "time": int((datetime.now() - timedelta(hours=12)).timestamp()),
        "type": "story",
        "url": None,
        "text": "After the recent data breaches, European regulators are pushing hard on key rotation. Current tools don't meet the standards. What are people using?"
    },
    {
        "id": 39000004,
        "title": "Show HN: Stripe-like payments but SEPA-native",
        "by": "payments_guy",
        "score": 567,
        "descendants": 234,
        "time": int((datetime.now() - timedelta(hours=3)).timestamp()),
        "type": "story",
        "url": "https://eurapay.dev",
        "text": "Built over 18 months while working at Adyen. Quit 3 months ago to do this full-time. GitHub: https://github.com/eurapay/core"
    },
    {
        "id": 39000005,
        "title": "LLM fine-tuning is still too expensive for European startups",
        "by": "mlresearcher",
        "score": 423,
        "descendants": 189,
        "time": int((datetime.now() - timedelta(hours=6)).timestamp()),
        "type": "story",
        "url": None,
        "text": "US clouds charge 3-4x for EU regions. We're experimenting with distributed training across smaller EU providers. Early results promising."
    }
]

MOCK_COMMENTS = {
    39000001: [
        {"by": "europeanfounder", "text": "Happy to answer any questions! We're using ClickHouse under the hood with custom GDPR compliance layer."},
        {"by": "investor_account", "text": "This is exactly what we need. Are you raising?"},
        {"by": "europeanfounder", "text": "Not actively, but open to conversations. Email in profile."},
    ],
    39000002: [
        {"by": "berlinai", "text": "The demo shows real-time scanning of model cards and training data for AI Act Article 52 compliance."},
        {"by": "regulatory_expert", "text": "This could be huge. Most companies have no idea how to prepare."},
    ],
    39000004: [
        {"by": "payments_guy", "text": "Key difference vs Stripe: native SEPA instant, no USD conversion, and EU-based support for compliance questions."},
        {"by": "payments_guy", "text": "We're already processing €2M/month for 12 early customers."},
    ],
}


def create_demo_signals():
    """Create HNSignal objects from mock data"""
    analyzer = HNAnalyzer()
    signals = []
    
    for story in MOCK_HN_DATA:
        # Get mock comments
        comments = []
        for comment_data in MOCK_COMMENTS.get(story['id'], []):
            comments.append({
                'author': comment_data['by'],
                'text': comment_data['text'],
                'created_at': datetime.now()
            })
        
        # Analyze
        title = story['title']
        text = story.get('text')
        url = story.get('url')
        author = story['by']
        
        builder_present = analyzer.detect_builder_presence(title, text, comments, author)
        technical_depth = analyzer.calculate_technical_depth(title, text, comments)
        links = analyzer.extract_links(title, text, url)
        inferred_problem = analyzer.infer_problem(title, text)
        
        # Determine signal type
        signal_type = "discussion"
        if 'show hn' in title.lower():
            signal_type = "show_hn"
        if builder_present and (links['github'] or links['demo']):
            signal_type = "launch"
        
        signal = HNSignal(
            hn_id=story['id'],
            title=title,
            url=url,
            author=author,
            created_at=datetime.fromtimestamp(story['time']),
            score=story['score'],
            num_comments=story['descendants'],
            inferred_problem=inferred_problem,
            builder_present=builder_present,
            technical_depth_score=technical_depth,
            signal_type=signal_type,
            github_links=links['github'],
            demo_links=links['demo'],
            docs_links=links['docs'],
            text=text,
            comment_sample=comments[:5]
        )
        
        signals.append(signal)
    
    return signals


def main():
    print("🔍 Demo: HN Signal Detection")
    print("=" * 70)
    print("(Using mock data to demonstrate functionality)\n")
    
    signals = create_demo_signals()
    
    print(f"✅ Found {len(signals)} signals\n")
    
    # High priority signals
    high_priority = [
        s for s in signals 
        if s.builder_present and (s.github_links or s.demo_links)
    ]
    
    print(f"🎯 {len(high_priority)} HIGH-PRIORITY signals (builder + artifacts)\n")
    print("=" * 70)
    
    for signal in high_priority:
        print(f"\n{'🚀' if signal.signal_type == 'launch' else '💡'} {signal.title}")
        print(f"   Author: {signal.author} | Score: {signal.score} | Comments: {signal.num_comments}")
        print(f"   Type: {signal.signal_type.upper()}")
        print(f"   Problem: {signal.inferred_problem}")
        print(f"   Technical depth: {signal.technical_depth_score}/10")
        
        if signal.github_links:
            print(f"   🔗 GitHub: {signal.github_links[0]}")
        if signal.demo_links:
            print(f"   🔗 Demo: {signal.demo_links[0]}")
        
        if signal.comment_sample:
            print(f"   💬 Author activity:")
            author_comments = [c for c in signal.comment_sample if c['author'] == signal.author]
            for comment in author_comments[:2]:
                preview = comment['text'][:120] + "..." if len(comment['text']) > 120 else comment['text']
                print(f"      • {preview}")
        
        print(f"   🔗 https://news.ycombinator.com/item?id={signal.hn_id}")
    
    # Other signals
    other_signals = [s for s in signals if s not in high_priority]
    
    if other_signals:
        print("\n\n" + "=" * 70)
        print("📊 Other Technical Signals")
        print("=" * 70)
        
        for signal in other_signals:
            print(f"\n{'💬' if signal.signal_type == 'discussion' else '💡'} {signal.title}")
            print(f"   Score: {signal.score} | Comments: {signal.num_comments} | Tech: {signal.technical_depth_score}/10")
            print(f"   Problem: {signal.inferred_problem}")
            print(f"   🔗 https://news.ycombinator.com/item?id={signal.hn_id}")
    
    # Save to JSON
    signals_dict = []
    for s in signals:
        d = s.to_dict()
        # Convert comment timestamps
        for comment in d.get('comment_sample', []):
            if isinstance(comment.get('created_at'), datetime):
                comment['created_at'] = comment['created_at'].isoformat()
        signals_dict.append(d)
    
    with open('demo_signals.json', 'w') as f:
        json.dump(signals_dict, f, indent=2)
    
    print("\n\n" + "=" * 70)
    print("💾 Saved to demo_signals.json")
    print("\n📝 Next steps:")
    print("   1. Review the signal patterns above")
    print("   2. Adjust thresholds in hn_module.py if needed")
    print("   3. Set up API access to run against real HN data")
    print("   4. Schedule daily runs (cron job)")


if __name__ == "__main__":
    main()
