"""
bazaar/app/ai_services.py

AI Features:
  - ai_suggest_tags_and_category(title, description) → {category, tags, confidence}
  - get_price_insight(category)                       → {avg, median, min, max, count}

The tagging uses a keyword-matching approach that is lightweight, zero-cost,
and architecture-ready for replacing with a real AI/ML call later.
Price insights compute from live DB data.
"""

import statistics
from decimal import Decimal


# ── Category keyword map ──────────────────────────────────────────────────────
_CATEGORY_KEYWORDS = {
    'Books': [
        'book', 'textbook', 'novel', 'notes', 'guide', 'jee', 'neet', 'physics',
        'chemistry', 'maths', 'mathematics', 'biology', 'engineering', 'reference',
        'allen', 'fiitjee', 'dc pandey', 'irodov', 'hc verma', 'resnick',
        'mcq', 'study material', 'coaching', 'ncert', 'cbse',
    ],
    'Electronics': [
        'laptop', 'phone', 'mobile', 'charger', 'cable', 'earphone', 'headphone',
        'tablet', 'ipad', 'keyboard', 'mouse', 'monitor', 'speaker', 'camera',
        'hard drive', 'ssd', 'pendrive', 'usb', 'powerbank', 'power bank',
        'calculator', 'projector', 'router', 'wifi', 'smartwatch',
    ],
    'Cycles': [
        'cycle', 'bicycle', 'bike', 'mtb', 'gear', 'geared', 'cycling',
        'trek', 'hercules', 'atlas', 'BSA', 'puncture', 'helmet',
    ],
    'Clothing': [
        'shirt', 'jeans', 'kurta', 't-shirt', 'tshirt', 'jacket', 'hoodie',
        'sweater', 'shoes', 'sandals', 'clothing', 'clothes', 'dress',
        'formal', 'casual', 'trouser', 'coat', 'blazer',
    ],
    'Stationery': [
        'pen', 'pencil', 'notebook', 'file', 'folder', 'highlighter', 'marker',
        'stapler', 'scissors', 'ruler', 'stationery', 'A4', 'paper',
        'sticky notes', 'whiteboard',
    ],
    'Sports': [
        'cricket', 'football', 'badminton', 'tennis', 'basketball', 'volleyball',
        'gym', 'dumbbell', 'weights', 'mat', 'yoga', 'skipping', 'racket',
        'bat', 'ball', 'sports', 'fitness',
    ],
    'Hostel Gear': [
        'mattress', 'bedsheet', 'blanket', 'pillow', 'bucket', 'mug',
        'fan', 'lamp', 'bulb', 'extension', 'hostel', 'room', 'curtain',
        'hangers', 'shelf', 'rack', 'mirror', 'lock', 'cooler', 'heater',
        'iron', 'ironing', 'kettle',
    ],
}


def _text_lower(*parts) -> str:
    return ' '.join(str(p) for p in parts if p).lower()


def ai_suggest_tags_and_category(title: str, description: str = '') -> dict:
    """
    Analyse title + description and return suggested category + tags.

    Returns:
        {
            'category': str | None,
            'tags': [str, ...],
            'confidence': 'high' | 'medium' | 'low',
            'ai_powered': False   # set to True when real AI is wired in
        }

    Architecture note:
        To upgrade to a real AI model, replace the body of this function with an
        API call (e.g. OpenAI vision / text classification) and return the same
        dict structure. The rest of the codebase stays unchanged.
    """
    combined = _text_lower(title, description)
    scores = {}
    matched_keywords = []

    for category, keywords in _CATEGORY_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in combined]
        if hits:
            scores[category] = len(hits)
            matched_keywords.extend(hits)

    if not scores:
        return {'category': None, 'tags': [], 'confidence': 'low', 'ai_powered': False}

    best_category = max(scores, key=scores.get)
    best_score    = scores[best_category]

    # Build suggested tags from the matched keywords (deduplicated, ≤ 6)
    seen = set()
    tags = []
    for kw in matched_keywords:
        if kw not in seen:
            seen.add(kw)
            tags.append(kw)
        if len(tags) >= 6:
            break

    confidence = 'high' if best_score >= 3 else ('medium' if best_score >= 1 else 'low')

    return {
        'category':   best_category,
        'tags':       tags,
        'confidence': confidence,
        'ai_powered': False,   # flip to True when real AI is integrated
    }


def get_price_insight(category: str) -> dict | None:
    """
    Query the live DB for price statistics of available listings in a category.

    Returns None if no data is found, otherwise:
        {'avg': float, 'median': float, 'min': float, 'max': float, 'count': int}
    """
    try:
        from .models import Product
        prices = [
            float(p.price)
            for p in Product.query.filter_by(category=category, is_available=True).all()
            if p.price is not None
        ]
        if not prices:
            return None
        return {
            'avg':    round(sum(prices) / len(prices), 2),
            'median': round(statistics.median(prices), 2),
            'min':    round(min(prices), 2),
            'max':    round(max(prices), 2),
            'count':  len(prices),
        }
    except Exception:
        return None
