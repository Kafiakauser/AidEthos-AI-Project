"""AidEthos — AI Matching Engine (TF-IDF + Cosine Similarity)"""
from __future__ import annotations
from datetime import date, datetime
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILL_W = 0.70
URGENCY_W = 0.30
HORIZON = 30


def _urgency_score(level: int, deadline: date | None) -> float:
    level_s = (max(1, min(10, level)) - 1) / 9.0
    if deadline is None:
        prox = 0.0
    else:
        days = (deadline - datetime.utcnow().date()).days
        prox = 1.0 if days <= 0 else (0.0 if days >= HORIZON else 1.0 - days / HORIZON)
    return round(0.6 * level_s + 0.4 * prox, 6)


def _skills_text(csv: str) -> str:
    return " ".join(t.strip().lower().replace(" ", "_") for t in csv.split(",") if t.strip())


def _crisis_text(c) -> str:
    s = _skills_text(c.required_skills)
    return f"{s} {s} {c.title.lower()} {c.description.lower()}"


def match_volunteer_to_crises(volunteer_skills: str, crises: List) -> List[dict]:
    if not crises:
        return []
    vol_text = _skills_text(volunteer_skills)
    corpus   = [vol_text] + [_crisis_text(c) for c in crises]
    try:
        vec    = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1)
        matrix = vec.fit_transform(corpus)
    except ValueError:
        return [_crisis_dict(c, 0.0) for c in crises]

    sims = cosine_similarity(matrix[0], matrix[1:])[0]
    results = []
    for i, c in enumerate(crises):
        score = round(SKILL_W * float(sims[i]) + URGENCY_W * _urgency_score(c.urgency_level, c.deadline), 4)
        results.append(_crisis_dict(c, score))
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results


def match_crisis_to_volunteers(crisis, volunteers: List) -> List[dict]:
    if not volunteers:
        return []
    corpus = [_crisis_text(crisis)] + [_skills_text(v.skills) for v in volunteers]
    try:
        vec    = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1)
        matrix = vec.fit_transform(corpus)
    except ValueError:
        return [_vol_dict(v, 0.0) for v in volunteers]

    sims  = cosine_similarity(matrix[0], matrix[1:])[0]
    urg   = _urgency_score(crisis.urgency_level, crisis.deadline)
    results = []
    for i, v in enumerate(volunteers):
        score = round(SKILL_W * float(sims[i]) + URGENCY_W * urg, 4)
        results.append(_vol_dict(v, score))
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results


def calculate_credibility(ngo_id: int, crisis_count: int, vol_count: int) -> float:
    score = min(10.0, 5.0 + crisis_count * 0.5 + vol_count * 0.08 + (ngo_id % 10) * 0.05)
    return round(score, 1)


def _crisis_dict(c, score: float) -> dict:
    return {
        "id": c.id, "ngo_id": c.ngo_id, "ngo_name": c.ngo_name,
        "title": c.title, "crisis_type": c.crisis_type,
        "description": c.description, "required_skills": c.required_skills,
        "urgency_level": c.urgency_level, "location": c.location,
        "deadline": str(c.deadline) if c.deadline else None,
        "contact_phone": c.contact_phone, "contact_email": c.contact_email,
        "is_active": c.is_active, "created_at": str(c.created_at),
        "match_score": score, "credibility_score": getattr(c, "credibility_score", 7.5),
        "volunteer_count": getattr(c, "volunteer_count", None),
    }


def _vol_dict(v, score: float) -> dict:
    return {
        "id": v.id, "name": v.name, "phone": v.phone, "email": v.email,
        "location": v.location, "skills": v.skills, "crisis_id": v.crisis_id,
        "created_at": str(v.created_at), "match_score": score,
    }
