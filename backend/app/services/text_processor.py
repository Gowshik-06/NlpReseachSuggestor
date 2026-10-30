"""
NLP text preprocessing and cleaning service.
Performs text cleaning, stopword filtering, and term extraction.
"""
import re
from typing import List, Set

COMMON_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "paper", "propose", "method",
    "model", "results", "approach", "show", "using", "used", "presents"
}


def clean_text(text: str) -> str:
    """Clean text by removing citation artifacts, markdown, excessive whitespace, and special characters."""
    if not text:
        return ""
    # Remove bracketed citations like [1], [2, 3], [et al. 2020]
    cleaned = re.sub(r"\[\d+(?:[,\s–-]+\d+)*\]", " ", text)
    cleaned = re.sub(r"\[[A-Za-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}\]", " ", cleaned)
    # Remove URLs
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    # Remove DOIs
    cleaned = re.sub(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", " ", cleaned)
    # Normalize unicode quotes and dashes
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    cleaned = cleaned.replace("—", " ").replace("–", " ")
    # Replace multiple spaces/newlines
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_keywords_from_text(text: str, top_k: int = 8) -> List[str]:
    """Simple term-frequency based keyphrase extraction without external heavy dependencies."""
    cleaned = clean_text(text).lower()
    # Extract candidate 1-gram and 2-gram words
    words = re.findall(r"\b[a-z]{3,20}\b", cleaned)
    freq = {}
    for w in words:
        if w not in COMMON_STOPWORDS:
            freq[w] = freq.get(w, 0) + 1

    # Extract bigrams
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i+1]
        if w1 not in COMMON_STOPWORDS and w2 not in COMMON_STOPWORDS:
            bigram = f"{w1} {w2}"
            freq[bigram] = freq.get(bigram, 0) + 2

    sorted_terms = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [term for term, _ in sorted_terms[:top_k]]
