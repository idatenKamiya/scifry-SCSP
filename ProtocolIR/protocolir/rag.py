"""Lightweight local retrieval for semantic parsing context."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


MAX_CHARS_PER_DOC = 5000


@dataclass(frozen=True)
class RetrievedContext:
    source: str
    score: float
    text: str


def retrieve_context(query: str, *, top_k: int = 5, root: str = ".") -> List[RetrievedContext]:
    docs = _load_docs(Path(root))
    if not docs:
        return []

    query_terms = _terms(query)
    if not query_terms:
        return []

    doc_terms = [_terms(text) for _, text in docs]
    idf = _idf(doc_terms)
    query_vector = _vector(query_terms, idf)

    scored = []
    for (source, text), terms in zip(docs, doc_terms):
        score = _cosine(query_vector, _vector(terms, idf))
        if score > 0:
            scored.append(RetrievedContext(source=source, score=score, text=_trim(text)))

    return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]


def context_block(query: str, *, top_k: int = 5, root: str = ".") -> str:
    contexts = retrieve_context(query, top_k=top_k, root=root)
    if not contexts:
        return ""
    lines = ["Relevant local protocol/API context:"]
    for idx, item in enumerate(contexts, 1):
        lines.append(f"\n[Context {idx}: {item.source}, score={item.score:.3f}]\n{item.text}")
    return "\n".join(lines)


def _load_docs(root: Path) -> List[tuple[str, str]]:
    patterns = [
        "data/protocols_io_raw/**/*.txt",
        "data/expert_scripts/**/*.py",
        "data/expert_scripts_large/**/*.py",
        "README.md",
        "QUICKSTART.md",
    ]
    docs: List[tuple[str, str]] = []
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                if len(text.strip()) > 80:
                    docs.extend(_chunk(str(path), text))
    return docs


def _chunk(source: str, text: str) -> List[tuple[str, str]]:
    clean = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    chunks = []
    for start in range(0, len(clean), MAX_CHARS_PER_DOC):
        chunk = clean[start : start + MAX_CHARS_PER_DOC]
        chunks.append((f"{source}#{start // MAX_CHARS_PER_DOC}", chunk))
    return chunks


def _terms(text: str) -> List[str]:
    return [
        term
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text.lower())
        if term not in {"the", "and", "for", "with", "this", "that", "from", "into", "protocol"}
    ]


def _idf(docs: Iterable[List[str]]) -> dict[str, float]:
    docs = list(docs)
    counts: dict[str, int] = {}
    for terms in docs:
        for term in set(terms):
            counts[term] = counts.get(term, 0) + 1
    total = max(len(docs), 1)
    return {term: math.log((1 + total) / (1 + count)) + 1.0 for term, count in counts.items()}


def _vector(terms: List[str], idf: dict[str, float]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for term in terms:
        counts[term] = counts.get(term, 0) + 1
    return {term: count * idf.get(term, 1.0) for term, count in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(term, 0.0) for term, value in a.items())
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _trim(text: str) -> str:
    return text[:1800].strip()
