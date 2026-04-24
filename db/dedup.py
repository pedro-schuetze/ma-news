from __future__ import annotations

import re
import unicodedata

_SUFFIXES = [
    "s.a.", "s/a", "s.a", "sa",
    "ltda.", "ltda", "ltd.", "ltd",
    "inc.", "inc",
    "corp.", "corp", "corporation",
    "co.", "co",
    "llc", "plc",
    "ag", "gmbh", "nv", "bv", "ab",
    "group", "holding", "holdings",
    "capital", "partners",
]

_PREFIXES = [
    # "Colombia's Ecopetrol" → "ecopetrol"
    r"^[a-z]+'s\s+",
    # "Brazil's Brava" → "brava"
    r"^brazil[\s']+", r"^colombia[\s']+", r"^india[\s']+",
    r"^china[\s']+", r"^japan[\s']+", r"^us\s+", r"^u\.s\.\s+",
    r"^uk\s+", r"^u\.k\.\s+",
]


def normalize_name(name: str | None) -> str | None:
    """Normaliza nome de empresa para dedup determinística.

    - lowercase
    - remove acentos
    - tira prefixos tipo "Colombia's ", "Brazil's "
    - tira sufixos societários (S.A., Ltda, Inc., Corp., etc.)
    - remove pontuação
    - colapsa espaços
    """
    if not name:
        return None

    s = name.strip().lower()

    # Remove acentos
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))

    # Prefixos de país
    for pattern in _PREFIXES:
        s = re.sub(pattern, "", s)

    # Remove parênteses e conteúdo entre eles (ex: "Generali (participação de €7,4bn)")
    s = re.sub(r"\([^)]*\)", " ", s)

    # Sufixos societários — precisa rodar ANTES de remover pontuação
    # para que "s.a." seja reconhecido como um token.
    # Tokeniza mantendo pontuação como parte dos tokens.
    tokens = re.split(r"\s+", s)
    while tokens and tokens[-1].strip(",.") in _SUFFIXES:
        tokens.pop()
    s = " ".join(tokens)

    # Agora remove pontuação
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None
