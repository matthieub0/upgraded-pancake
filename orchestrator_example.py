"""
Example: How the Orchestration Agent Would Use HN Signals

This shows how to connect HN signals with other modules
for entity resolution and formation detection.
"""

from hn_module import HNSignal
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class EmergingFormation:
    """Output from orchestration agent - represents a potential startup forming"""
    formation_id: str
    people_involved: List[str]  # Names or identities
    inferred_angle: str  # What they're building
    evidence: Dict[str, List]  # Evidence from each module
    confidence_tags: Dict[str, float]  # formation, eu, execution scores
    state: str  # watch, active, stale
    first_seen: datetime
    last_updated: datetime


class OrchestrationExample:
    """
    Example of how the orchestrator combines signals
    This is pseudocode - actual implementation would need real data
    """
    
    def __init__(self):
        self.hn_signals = []
        self.github_signals = []  # From GitHub module
        self.talent_signals = []  # From LinkedIn module
        self.formations = []
    
    def entity_resolution_hn_to_github(self, hn_signal: HNSignal) -> List[str]:
        """
        Link HN post to GitHub identities
        
        Returns: List of GitHub usernames/orgs
        """
        identities = []
        
        # Method 1: Direct GitHub links in post
        for github_link in hn_signal.github_links:
            # Extract org/user from URL: github.com/username/repo
            parts = github_link.split('github.com/')
            if len(parts) > 1:
                identity = parts[1].split('/')[0]
                identities.append(identity)
        
        # Method 2: Check if HN username matches GitHub username
        # (Would need a mapping database or API lookup)
        # identities.append(self.hn_to_github_mapping.get(hn_signal.author))
        
        # Method 3: Scan commit authors from linked repos
        # for link in hn_signal.github_links:
        #     contributors = github_api.get_contributors(link)
        #     identities.extend(contributors)
        
        return list(set(identities))  # Remove duplicates
    
    def detect_european_formation(self, hn_signal: HNSignal) -> Dict[str, float]:
        """
        Score likelihood this is a European startup forming
        
        Returns: {
            'eu_problem': 0-1 score,
            'eu_location': 0-1 score,
            'eu_regulation': 0-1 score
        }
        """
        text = f"{hn_signal.title} {hn_signal.text or ''}".lower()
        
        scores = {
            'eu_problem': 0.0,
            'eu_location': 0.0,
            'eu_regulation': 0.0
        }
        
        # EU-specific problems
        eu_problems = [
            'gdpr', 'sepa', 'brexit', 'schengen',
            'eu data residency', 'european banking'
        ]
        if any(term in text for term in eu_problems):
            scores['eu_problem'] = 0.9
        
        # EU regulatory context
        regulations = [
            'ai act', 'dma', 'dsa', 'psd2', 'mifid',
            'eu regulation', 'eu directive'
        ]
        if any(reg in text for reg in regulations):
            scores['eu_regulation'] = 0.8
        
        # Location indicators
        eu_locations = [
            'berlin', 'london', 'paris', 'amsterdam', 'dublin',
            'stockholm', 'copenhagen', 'barcelona', 'munich'
        ]
        if any(loc in text for loc in eu_locations):
            scores['eu_location'] = 0.7
        
        return scores
    
    def combine_signals_example(self):
        """
        Example: How to combine HN + GitHub + LinkedIn signals
        """
        
        # Scenario: We have signals from different modules
        hn_signal_example = {
            'id': 39000001,
            'author': 'europeanfounder',
            'title': 'Show HN: GDPR-compliant data warehouse',
            'github_links': ['github.com/eu-data/warehouse'],
            'created_at': datetime(2026, 2, 1),
            'builder_present': True
        }
        
        github_signal_example = {
            'org': 'eu-data',
            'repo': 'warehouse',
            'created_at': datetime(2026, 1, 15),
            'star_velocity': 15,  # stars per day
            'maintainers': ['john_dev', 'sarah_eng']
        }
        
        talent_signal_example = {
            'people': ['John Smith', 'Sarah Chen'],
            'previous_company': 'Snowflake',
            'left_within_90_days': True,
            'roles': ['Senior Eng', 'Product Lead'],
            'move_to': 'Stealth'
        }
        
        # Orchestrator logic:
        # 1. Entity resolution: Are these the same people?
        # - "john_dev" from GitHub might be "John Smith" from LinkedIn
        # - "europeanfounder" from HN might be one of them
        # 2. Temporal alignment: Did these happen close together?
        # - Repo created Jan 15
        # - HN post Feb 1 (17 days later)
        # - LinkedIn exits Dec-Jan (before repo)
        # 3. Confidence building
        eu_scores = self.detect_european_formation(type('obj', (object,), hn_signal_example)())
        
        formation = {
            'formation_id': 'form_001',
            'inferred_angle': 'GDPR-compliant data warehouse for EU companies',
            'people_involved': ['John Smith', 'Sarah Chen', 'europeanfounder'],
            'evidence': {
                'hn': ['Post with builder signals, GitHub link'],
                'github': ['New org created, active development'],
                'talent': ['2 senior people left Snowflake within 90 days']
            },
            'confidence_tags': {
                'formation': 0.85,  # High: talent + repo + HN launch
                'eu_focus': sum(eu_scores.values()) / 3,  # Average EU scores
                'execution': 0.75  # Repo exists + Show HN
            },
            'state': 'active'  # Worth monitoring closely
        }
        
        return formation


def example_filtering_pipeline():
    """
    Example: Daily pipeline to filter HN signals for European formations
    """
    
    # Load HN signals from daily run
    with open('demo_signals.json') as f:
        signals = json.load(f)
    
    print("📊 HN Signal Filtering for European Formations\n")
    print("=" * 70)
    
    high_value_signals = []
    
    for signal_data in signals:
        # Reconstruct signal object (simplified)
        signal = type('Signal', (), signal_data)()
        
        # Filter criteria for European startup signals:
        
        # 1. Must have builder present
        if not signal_data.get('builder_present'):
            continue
        
        # 2. Must have artifacts (GitHub or demo)
        has_artifacts = (
            len(signal_data.get('github_links', [])) > 0 or
            len(signal_data.get('demo_links', [])) > 0
        )
        if not has_artifacts:
            continue
        
        # 3. Check for EU indicators
        text = f"{signal_data.get('title', '')} {signal_data.get('text', '')}".lower()
        
        eu_keywords = [
            'gdpr', 'eu', 'europe', 'european', 'sepa',
            'ai act', 'dma', 'psd2', 'brexit',
            'berlin', 'london', 'paris', 'amsterdam'
        ]
        
        has_eu_context = any(keyword in text for keyword in eu_keywords)
        
        # 4. Score technical depth
        tech_score = signal_data.get('technical_depth_score', 0)
        
        if has_eu_context and tech_score >= 3:
            high_value_signals.append({
                'title': signal_data.get('title'),
                'author': signal_data.get('author'),
                'github': signal_data.get('github_links', []),
                'problem': signal_data.get('inferred_problem'),
                'hn_url': f"https://news.ycombinator.com/item?id={signal_data.get('hn_id')}"
            })
    
    print(f"Found {len(high_value_signals)} EU-relevant formation signals:\n")
    
    for i, signal in enumerate(high_value_signals, 1):
        print(f"{i}. {signal['title']}")
        print(f"   Author: {signal['author']}")
        print(f"   Problem: {signal['problem']}")
        if signal['github']:
            print(f"   GitHub: {signal['github'][0]}")
        print(f"   {signal['hn_url']}\n")
    
    return high_value_signals


def example_weekly_summary():
    """
    Example: Generate weekly summary of formation signals
    """
    
    # In production, this would pull from a database of accumulated signals
    
    summary = """
    # Weekly Startup Formation Report - Week of Feb 3-9, 2026
    
    ## High Priority (Builder + EU Context + Artifacts)
    
    1. **GDPR-compliant data warehouse**
       - Evidence: Show HN post, GitHub org created, 2 ex-Snowflake employees
       - Confidence: Formation 85%, EU 90%, Execution 75%
       - Next: Monitor GitHub star velocity, check for incorporation
    
    2. **AI Act compliance monitoring**
       - Evidence: Show HN with demo, active in comments, GitHub repo
       - Confidence: Formation 75%, EU 95%, Execution 70%
       - Next: Track if they start hiring, check domain registration
    
    ## Watch List (Interesting but early)
    
    3. **SEPA payment infrastructure**
       - Evidence: High engagement HN post, mentions "we're building"
       - Missing: No GitHub yet, no confirmed team
       - Next: Monitor for repo creation or Show HN
    
    ## Stale (No progress in 30 days)
    
    4. **EU crypto wallet** - Last signal 35 days ago
    """
    
    return summary


if __name__ == "__main__":
    print("Running orchestration examples...\n")
    
    # Example 1: Filter HN signals for EU
    example_filtering_pipeline()
    
    print("\n" + "=" * 70)
    print("\nThis demonstrates:")
    print("1. ✅ How to filter HN signals for European relevance")
    print("2. ✅ What entity resolution logic looks like")
    print("3. ✅ How to score formation confidence")
    print("4. ✅ How to combine signals from multiple modules")
    print("\nNext step: Build the GitHub module for artifact tracking!")
