"""
Sentiment Service
=================
Lightweight news headline sentiment scoring using VADER.

VADER (Valence Aware Dictionary and sEntiment Reasoner) is fast, CPU-only,
and works well for short financial headlines — ideal for a t3.medium instance.

Thresholds:
    Bullish:  compound > 0.15
    Bearish:  compound < -0.15
    Neutral:  otherwise

Used by:
    flask_app/app/services/analyze_service.py
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Lazy-load VADER to avoid import cost on every request
_analyzer = None


def _get_analyzer():
    """Lazy-load the VADER sentiment analyzer (singleton)."""
    global _analyzer
    if _analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def _classify(compound: float) -> str:
    """Map compound score to a label."""
    if compound > 0.15:
        return 'Bullish'
    elif compound < -0.15:
        return 'Bearish'
    return 'Neutral'


def score_headlines(headlines: List[str]) -> List[Dict]:
    """
    Score a list of headline strings.

    Returns list of:
        {headline, sentiment_score (-1 to 1), sentiment_label}
    """
    analyzer = _get_analyzer()
    results = []
    for headline in headlines:
        try:
            scores = analyzer.polarity_scores(headline)
            compound = round(scores['compound'], 4)
            results.append({
                'headline': headline,
                'sentiment_score': compound,
                'sentiment_label': _classify(compound),
            })
        except Exception as e:
            logger.debug(f"Sentiment scoring failed for headline: {e}")
            results.append({
                'headline': headline,
                'sentiment_score': 0.0,
                'sentiment_label': 'Neutral',
            })
    return results


def aggregate_sentiment(scores: List[Dict]) -> Dict:
    """
    Aggregate scored headlines into an overall summary.

    Returns:
        {avg_score, bullish_count, bearish_count, neutral_count, label}
    """
    if not scores:
        return {
            'avg_score': 0.0,
            'bullish_count': 0,
            'bearish_count': 0,
            'neutral_count': 0,
            'label': 'Neutral',
        }

    total = sum(s['sentiment_score'] for s in scores)
    avg = round(total / len(scores), 4)

    bullish = sum(1 for s in scores if s['sentiment_label'] == 'Bullish')
    bearish = sum(1 for s in scores if s['sentiment_label'] == 'Bearish')
    neutral = sum(1 for s in scores if s['sentiment_label'] == 'Neutral')

    return {
        'avg_score': avg,
        'bullish_count': bullish,
        'bearish_count': bearish,
        'neutral_count': neutral,
        'label': _classify(avg),
    }
