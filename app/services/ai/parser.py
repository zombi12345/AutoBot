from __future__ import annotations

import json
import logging
import re

import aiohttp

from app.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты парсишь запросы для av.by. Верни ТОЛЬКО JSON с полями (null если не указано):
brand, model, year_from, year_to, price_from, price_to,
fuel_type (gasoline|diesel|hybrid|electric|gas),
transmission (automatic|manual|variator|robot),
body_type (sedan|hatchback|suv|wagon|coupe|minivan|pickup),
mileage_to, engine_cc_from, engine_cc_to.

Пример: "BMW X5 2019 дизель до 30000" -> {"brand":"BMW","model":"X5","year_from":2019,"year_to":null,"price_from":null,"price_to":30000,"fuel_type":"diesel","transmission":null,"body_type":null,"mileage_to":null,"engine_cc_from":null,"engine_cc_to":null}
"""

FIELDS = ["brand","model","year_from","year_to","price_from","price_to","fuel_type","transmission","body_type","mileage_to","engine_cc_from","engine_cc_to"]


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m: return None
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


async def parse_query(text):
    empty = {k: None for k in FIELDS}
    if not settings.ai_enabled or not settings.ai_api_key:
        return empty

    url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.ai_api_key}", "Content-Type": "application/json"}
    body = {"model": settings.ai_model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": text}],
            "temperature": 0.1, "max_tokens": 300}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
            async with s.post(url, headers=headers, json=body) as r:
                if r.status != 200:
                    log.warning("ai HTTP %s: %s", r.status, (await r.text())[:200])
                    return empty
                data = await r.json()
    except Exception as e:
        log.warning("ai fail: %s", e)
        return empty

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return empty

    parsed = _extract_json(content) or {}
    out = dict(empty)
    ints = {"year_from","year_to","price_from","price_to","mileage_to","engine_cc_from","engine_cc_to"}
    for k in FIELDS:
        v = parsed.get(k)
        if v in (None, "", "null"): continue
        if k in ints:
            try: out[k] = int(v)
            except: pass
        else:
            out[k] = str(v)
    return out