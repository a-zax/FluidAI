import re
from collections import Counter
from typing import Dict, List

from app.store import store


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def retrieve_documents(question: str, limit: int = 2) -> List[Dict[str, str]]:
    query_terms = Counter(tokenize(question))
    if not query_terms:
        return []

    scored_docs = []
    for doc in store.knowledge_docs:
        doc_terms = Counter(tokenize(f"{doc['title']} {doc['body']}"))
        score = sum(query_terms[token] * doc_terms[token] for token in query_terms)
        if score > 0:
            scored_docs.append((score, doc))

    unique_docs = []
    seen = set()
    for _, doc in sorted(scored_docs, key=lambda item: item[0], reverse=True):
        fingerprint = (doc["title"].lower(), doc["body"].lower())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique_docs.append(doc)
        if len(unique_docs) == limit:
            break

    return unique_docs
