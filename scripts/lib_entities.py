from pathlib import Path
import yaml

_NLP = None  # cache spaCy model

def _get_nlp():
    global _NLP
    if _NLP is not None:
        return _NLP
    try:
        import spacy
        _NLP = spacy.load("en_core_web_sm")
    except Exception:
        _NLP = None
    return _NLP

def load_alias_map(path: Path) -> dict:
    if path.exists():
        return yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return {}

def load_stopwords(path: Path) -> set:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or []
        return set(data)
    return set()

def _canonicalize(name: str, alias_map: dict) -> str:
    return alias_map.get(name, name)

def extract_entities_optional(text: str, stopwords: set, alias_map: dict) -> dict:
    nlp = _get_nlp()
    if not nlp:
        return {'people': [], 'places': [], 'organizations': []}

    doc = nlp(text or "")
    b = {'people': [], 'places': [], 'organizations': []}
    for ent in doc.ents:
        raw = ent.text.strip()
        if not raw or raw in stopwords:
            continue
        if ent.label_ == 'PERSON':
            b['people'].append(_canonicalize(raw, alias_map))
        elif ent.label_ in ('GPE', 'LOC', 'FAC'):
            b['places'].append(_canonicalize(raw, alias_map))
        elif ent.label_ == 'ORG':
            b['organizations'].append(_canonicalize(raw, alias_map))
    for k in b:
        seen, out = set(), []
        for v in b[k]:
            if v not in seen:
                seen.add(v); out.append(v)
        b[k] = out
    return b

def merge_entities(meta: dict, inferred: dict) -> dict:
    out = {'people': [], 'places': [], 'organizations': []}
    meta_ents = (meta or {}).get('entities', {})
    for k in out:
        explicit = meta_ents.get(k, []) or []
        merged = explicit + [x for x in (inferred or {}).get(k, []) if x not in explicit]
        out[k] = merged
    return out
