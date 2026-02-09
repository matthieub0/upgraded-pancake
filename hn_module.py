"""
Hacker News Signal Detection Module
Detects problem emergence and builder presence
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
from dataclasses import dataclass, asdict
import json


@dataclass
class HNSignal:
    """Output object from HN module"""
    hn_id: int
    title: str
    url: Optional[str]
    author: str
    created_at: datetime
    score: int
    num_comments: int
    
    # Analysis fields
    inferred_problem: str
    builder_present: bool
    technical_depth_score: int  # 0-10
    signal_type: str  # "show_hn", "problem_discussion", "launch"
    
    # Linked artifacts
    github_links: List[str]
    demo_links: List[str]
    docs_links: List[str]
    
    # Raw data
    text: Optional[str]
    comment_sample: List[Dict]
    
    def to_dict(self):
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        return d


class HNFetcher:
    """Fetch data from Hacker News APIs"""
    
    FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"
    ALGOLIA_BASE = "http://hn.algolia.com/api/v1"
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_story(self, story_id: int) -> Dict:
        """Get single story from Firebase API"""
        url = f"{self.FIREBASE_BASE}/item/{story_id}.json"
        response = self.session.get(url)
        return response.json()
    
    def get_show_hn_stories(self, days_back: int = 7) -> List[Dict]:
        """Get Show HN stories by checking recent stories"""
        # Firebase doesn't have a show_hn filter, so we check top/new stories
        # and filter for "Show HN" in title
        cutoff = datetime.now() - timedelta(days=days_back)
        cutoff_ts = int(cutoff.timestamp())
        
        stories = []
        
        # Get recent top stories
        url = f"{self.FIREBASE_BASE}/topstories.json"
        try:
            response = self.session.get(url, timeout=10)
            story_ids = response.json()[:200]  # Check last 200 top stories
            
            for story_id in story_ids:
                story = self.get_story(story_id)
                if not story:
                    continue
                
                # Check if it's a Show HN and recent enough
                title = story.get('title', '').lower()
                created_at = story.get('time', 0)
                
                if 'show hn' in title and created_at > cutoff_ts:
                    stories.append(story)
                
                # Stop if we have enough
                if len(stories) >= 30:
                    break
            
        except Exception as e:
            print(f"Error fetching Show HN stories: {e}")
        
        return stories
    
    def get_top_stories(self, limit: int = 100) -> List[int]:
        """Get top story IDs from Firebase"""
        url = f"{self.FIREBASE_BASE}/topstories.json"
        response = self.session.get(url)
        return response.json()[:limit]
    
    def search_by_keyword(self, query: str, days_back: int = 7) -> List[Dict]:
        """Search HN by scanning recent stories for keywords"""
        cutoff = datetime.now() - timedelta(days=days_back)
        cutoff_ts = int(cutoff.timestamp())
        
        stories = []
        query_lower = query.lower()
        
        # Get recent top stories
        url = f"{self.FIREBASE_BASE}/topstories.json"
        try:
            response = self.session.get(url, timeout=10)
            story_ids = response.json()[:200]  # Check last 200 stories
            
            for story_id in story_ids:
                story = self.get_story(story_id)
                if not story:
                    continue
                
                # Check if keyword matches and recent enough
                title = story.get('title', '').lower()
                text = story.get('text', '').lower() if story.get('text') else ''
                created_at = story.get('time', 0)
                
                if query_lower in title or query_lower in text:
                    if created_at > cutoff_ts:
                        stories.append(story)
                
                # Stop if we have enough
                if len(stories) >= 20:
                    break
            
        except Exception as e:
            print(f"Error searching for '{query}': {e}")
        
        return stories
    
    def get_item_comments(self, item_id: int, max_comments: int = 10) -> List[Dict]:
        """Get comments for an item (recursive fetch of top-level comments)"""
        item = self.get_story(item_id)
        kids = item.get('kids', [])[:max_comments]
        
        comments = []
        for kid_id in kids:
            comment = self.get_story(kid_id)
            if comment and comment.get('text'):
                comments.append({
                    'author': comment.get('by', ''),
                    'text': comment.get('text', ''),
                    'created_at': datetime.fromtimestamp(comment.get('time', 0))
                })
        
        return comments


class HNAnalyzer:
    """Analyze HN posts for signals"""
    
    BUILDER_PATTERNS = [
        r"i built",
        r"i made",
        r"i created",
        r"we built",
        r"we made",
        r"we're building",
        r"i'm building",
        r"my project",
        r"our project",
        r"show hn",
        r"i wrote",
        r"we wrote"
    ]
    
    EXPERIMENT_PATTERNS = [
        r"we're experimenting",
        r"i'm experimenting",
        r"trying to build",
        r"working on",
        r"side project"
    ]
    
    TECHNICAL_KEYWORDS = [
        'api', 'algorithm', 'architecture', 'backend', 'database', 'deployment',
        'distributed', 'framework', 'infrastructure', 'kubernetes', 'machine learning',
        'microservices', 'model', 'optimization', 'performance', 'scaling', 'security',
        'llm', 'ai', 'neural', 'embedding', 'vector', 'rag', 'fine-tuning'
    ]
    
    def __init__(self):
        self.builder_regex = re.compile('|'.join(self.BUILDER_PATTERNS), re.IGNORECASE)
        self.experiment_regex = re.compile('|'.join(self.EXPERIMENT_PATTERNS), re.IGNORECASE)
    
    def detect_builder_presence(self, title: str, text: Optional[str], comments: List[Dict], author: str) -> bool:
        """Detect if post author is a builder"""
        # Check title and text
        full_text = f"{title} {text or ''}"
        if self.builder_regex.search(full_text) or self.experiment_regex.search(full_text):
            return True
        
        # Check if author is active in comments (shows commitment)
        author_comments = [c for c in comments if c['author'] == author]
        if len(author_comments) >= 2:
            return True
        
        return False
    
    def calculate_technical_depth(self, title: str, text: Optional[str], comments: List[Dict]) -> int:
        """Score technical depth 0-10"""
        score = 0
        full_text = f"{title} {text or ''}".lower()
        
        # Keywords in title/text
        keyword_count = sum(1 for kw in self.TECHNICAL_KEYWORDS if kw in full_text)
        score += min(keyword_count, 3)
        
        # Comment engagement
        if len(comments) > 20:
            score += 2
        elif len(comments) > 10:
            score += 1
        
        # Technical discussion in comments
        comment_text = ' '.join([c['text'] for c in comments[:5]]).lower()
        technical_in_comments = sum(1 for kw in self.TECHNICAL_KEYWORDS if kw in comment_text)
        score += min(technical_in_comments, 3)
        
        # Code/GitHub discussion
        if 'github' in full_text or 'github' in comment_text:
            score += 2
        
        return min(score, 10)
    
    def extract_links(self, title: str, text: Optional[str], url: Optional[str]) -> Dict[str, List[str]]:
        """Extract GitHub, demo, and docs links"""
        full_text = f"{title} {text or ''} {url or ''}"
        
        github_pattern = r'https?://github\.com/[^\s\)\]\>]+'
        demo_pattern = r'https?://[^\s\)\]\>]*(?:demo|app|try|playground)[^\s\)\]\>]*'
        docs_pattern = r'https?://[^\s\)\]\>]*(?:docs|documentation|readme)[^\s\)\]\>]*'
        
        return {
            'github': list(set(re.findall(github_pattern, full_text, re.IGNORECASE))),
            'demo': list(set(re.findall(demo_pattern, full_text, re.IGNORECASE))),
            'docs': list(set(re.findall(docs_pattern, full_text, re.IGNORECASE)))
        }
    
    def infer_problem(self, title: str, text: Optional[str]) -> str:
        """Extract the problem being discussed/solved"""
        # Simple heuristic: look for problem indicators
        full_text = f"{title} {text or ''}"
        
        # Common problem patterns
        problem_patterns = [
            r"problem with (.*?)(?:\.|$)",
            r"difficulty (?:with|in) (.*?)(?:\.|$)",
            r"challenge (?:of|with) (.*?)(?:\.|$)",
            r"solution (?:to|for) (.*?)(?:\.|$)",
            r"helps? (?:with|you) (.*?)(?:\.|$)",
            r"solves? (.*?)(?:\.|$)"
        ]
        
        for pattern in problem_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        
        # Fallback: use title
        return title[:200]


class HNSignalDetector:
    """Main orchestrator for HN signal detection"""
    
    def __init__(self):
        self.fetcher = HNFetcher()
        self.analyzer = HNAnalyzer()
    
    def process_story(self, story_data: Dict, fetch_comments: bool = True) -> Optional[HNSignal]:
        """Process a single HN story into a signal"""
        
        # Basic filtering
        if story_data.get('type') != 'story':
            return None
        
        # Handle both Firebase and Algolia formats
        story_id = story_data.get('id') or story_data.get('objectID')
        title = story_data.get('title', '')
        author = story_data.get('by') or story_data.get('author', '')
        score = story_data.get('score') or story_data.get('points', 0)
        
        # Get comment count
        kids = story_data.get('kids', [])
        num_comments = story_data.get('descendants') or story_data.get('num_comments') or len(kids)
        
        # Skip low-engagement posts
        if score < 5 and num_comments < 3:
            return None
        
        # Get text and comments
        text = story_data.get('text') or story_data.get('story_text')
        url = story_data.get('url')
        
        comments = []
        if fetch_comments and num_comments > 0:
            comments = self.fetcher.get_item_comments(story_id)
        
        # Analyze
        builder_present = self.analyzer.detect_builder_presence(title, text, comments, author)
        technical_depth = self.analyzer.calculate_technical_depth(title, text, comments)
        links = self.analyzer.extract_links(title, text, url)
        inferred_problem = self.analyzer.infer_problem(title, text)
        
        # Determine signal type
        signal_type = "discussion"
        if 'show hn' in title.lower():
            signal_type = "show_hn"
        
        if builder_present and (links['github'] or links['demo']):
            signal_type = "launch"
        
        # Create timestamp - handle both formats
        timestamp = story_data.get('time') or story_data.get('created_at_i', 0)
        created_at = datetime.fromtimestamp(timestamp)
        
        return HNSignal(
            hn_id=story_id,
            title=title,
            url=url,
            author=author,
            created_at=created_at,
            score=score,
            num_comments=num_comments,
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
    
    def get_daily_signals(self, min_score: int = 10, min_technical_depth: int = 3) -> List[HNSignal]:
        """Get high-quality signals from the last 24 hours"""
        signals = []
        
        # Get Show HN posts
        print("Fetching Show HN posts...")
        show_hn_stories = self.fetcher.get_show_hn_stories(days_back=1)
        
        for story in show_hn_stories:
            signal = self.process_story(story)
            if signal and (signal.score >= min_score or signal.technical_depth_score >= min_technical_depth):
                signals.append(signal)
        
        # Get top stories with technical keywords
        print("Fetching technical discussions...")
        keywords = ['llm', 'ai', 'infrastructure', 'database', 'api', 'open source']
        for keyword in keywords:
            stories = self.fetcher.search_by_keyword(keyword, days_back=1)
            for story in stories[:10]:  # Limit per keyword
                signal = self.process_story(story, fetch_comments=False)
                if signal and signal.score >= 20 and signal.technical_depth_score >= min_technical_depth:
                    # Check if we already have this
                    if not any(s.hn_id == signal.hn_id for s in signals):
                        signals.append(signal)
        
        return signals
    
    def generate_briefing(self, signals: List[HNSignal]) -> str:
        """Generate human-readable briefing"""
        
        # Sort by score
        signals = sorted(signals, key=lambda s: s.score, reverse=True)
        
        briefing = f"# Hacker News Daily Briefing - {datetime.now().strftime('%Y-%m-%d')}\n\n"
        briefing += f"Found {len(signals)} high-quality signals\n\n"
        
        # Group by signal type
        show_hn = [s for s in signals if s.signal_type == "show_hn"]
        launches = [s for s in signals if s.signal_type == "launch"]
        discussions = [s for s in signals if s.signal_type == "discussion"]
        
        if launches:
            briefing += "## 🚀 Launches (Builder + Artifacts)\n\n"
            for signal in launches[:10]:
                briefing += f"**{signal.title}**\n"
                briefing += f"- Author: {signal.author} | Score: {signal.score} | Comments: {signal.num_comments}\n"
                briefing += f"- Problem: {signal.inferred_problem}\n"
                if signal.github_links:
                    briefing += f"- GitHub: {signal.github_links[0]}\n"
                if signal.demo_links:
                    briefing += f"- Demo: {signal.demo_links[0]}\n"
                briefing += f"- https://news.ycombinator.com/item?id={signal.hn_id}\n\n"
        
        if show_hn:
            briefing += "## 💡 Show HN\n\n"
            for signal in show_hn[:10]:
                briefing += f"**{signal.title}**\n"
                briefing += f"- Author: {signal.author} | Score: {signal.score} | Tech Depth: {signal.technical_depth_score}/10\n"
                briefing += f"- Problem: {signal.inferred_problem}\n"
                briefing += f"- https://news.ycombinator.com/item?id={signal.hn_id}\n\n"
        
        if discussions:
            briefing += "## 💬 Technical Discussions\n\n"
            for signal in discussions[:5]:
                briefing += f"**{signal.title}**\n"
                briefing += f"- Score: {signal.score} | Comments: {signal.num_comments} | Tech Depth: {signal.technical_depth_score}/10\n"
                briefing += f"- https://news.ycombinator.com/item?id={signal.hn_id}\n\n"
        
        return briefing


if __name__ == "__main__":
    detector = HNSignalDetector()
    
    print("Running HN Signal Detection...")
    signals = detector.get_daily_signals(min_score=10, min_technical_depth=3)
    
    print(f"\nFound {len(signals)} signals")
    
    # Generate briefing
    briefing = detector.generate_briefing(signals)
    print("\n" + briefing)
    
    # Save signals as JSON
    with open('hn_signals.json', 'w') as f:
        json.dump([s.to_dict() for s in signals], f, indent=2)
    
    print("\nSaved signals to hn_signals.json")
