"""
bazaar/app/ai_services.py

AI Features:
  - ai_suggest_tags_and_category(title, description) → {category, tags, confidence}
  - get_price_insight(category)                         → {avg, median, min, max, count}

Powered by the Google Gemini API with basic NLP text preprocessing (cleaning, stopwords, stemming).
"""

import os
import re
import statistics
from decimal import Decimal
from typing import List

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# NLTK imports for basic NLP preprocessing
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

# Ensure required NLTK data packages are available
for package in ('punkt', 'stopwords'):
    try:
        nltk.data.find(f'tokenizers/{package}' if package == 'punkt' else f'corpora/{package}')
    except LookupError:
        nltk.download(package, quiet=True)


# ── Allowed Categories & NLP Setup ──────────────────────────────────────────
VALID_CATEGORIES = [
    'Books',
    'Electronics',
    'Cycles',
    'Clothing',
    'Stationery',
    'Sports',
    'Hostel Gear',
    'Other',
]

stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))


def preprocess_text(text: str) -> str:
    """
    Basic NLP preprocessing pipeline:
    1. Lowercase text
    2. Remove punctuation/special characters
    3. Tokenize and remove stop words (e.g., 'the', 'is', 'at')
    4. Apply Porter stemming (e.g., 'running' -> 'run', 'books' -> 'book')
    """
    if not text:
        return ""
    
    # 1. Lowercase & strip symbols using regex
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # 2. Tokenize manually by splitting whitespace (lightweight & dependency-free)
    tokens = text.split()
    
    # 3. Filter stopwords and apply stemming
    processed_tokens = [
        stemmer.stem(token) for token in tokens 
        if token not in stop_words and len(token) > 1
    ]
    
    return ' '.join(processed_tokens)


# ── Pydantic Schema for Strict Output Formatting ─────────────────────────────
class ItemMetadata(BaseModel):
    category: str = Field(
        description=f"Must be strictly chosen from one of these categories: {', '.join(VALID_CATEGORIES)}"
    )
    tags: List[str] = Field(
        description="A list of 3 to 6 helpful lowercase keywords/tags extracted from the title and description."
    )
    confidence: float = Field(
        description="A confidence score between 0.0 and 1.0 indicating classification certainty."
    )


# Load AI settings even when this module is imported outside the Flask app.
load_dotenv()
gemini_api_key = os.environ.get('GEMINI_API_KEY')
gemini_model = os.environ.get('GEMINI_MODEL')
client = genai.Client(api_key=gemini_api_key)


def ai_suggest_tags_and_category(title: str, description: str = '') -> dict:
    """
    Preprocesses the raw text via basic NLP, then analyzes it using Gemini 
    to determine the category, tags, and confidence score.
    """
    # Run basic NLP preprocessing on inputs to clean noise
    clean_title = preprocess_text(title)
    clean_desc = preprocess_text(description)

    prompt = f"""
    Analyze the following preprocessed marketplace item listing. Classify it into the best-matching category, 
    extract smart keyword tags for searching, and provide a confidence level.
    
    Allowed Categories: {', '.join(VALID_CATEGORIES)}
    
    Cleaned Item Title: {clean_title}
    Cleaned Item Description: {clean_desc}
    (Original Title was: {title})
    """

    try:
        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ItemMetadata,
                temperature=0.1,
            ),
        )
        
        result = response.parsed
        category = result.category if result.category in VALID_CATEGORIES else 'Other'
        
        return {
            'category': category,
            'tags': result.tags,
            'confidence': float(result.confidence),
        }

    except Exception as e:
        print(f"Gemini API Error in ai_suggest_tags_and_category: {e}")
        return {
            'category': 'Other',
            'tags': [],
            'confidence': 0.0,
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