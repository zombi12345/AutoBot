from __future__ import annotations

import json
import logging
import re

import aiohttp

from app.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — парсер поисковых запросов для белорусского авторынка av.by.
Пользователь пишет, какую машину хочет. Извлеки поля и верни ТОЛЬКО JSON.

Поля (все опциональные, если не указано — null):
- brand: марка (BMW, Audi, Geely, Лада, ВАЗ…)
- model: модель (X5, A4, Coolray, Vesta…)
- year_from, year_to: целые годы (2018)
- price_from, price_to: целые в USD (30000)
- fuel_type: "gasoline" | "diesel" | "hybrid" | "electric" | "gas"
- transmission: "automatic" | "manual" | "variator" | "robot"
- body_type: "sedan" | "hatchback" | "suv" | "wagon" | "coupe" | "minivan" | "pickup"
- mileage_to: целое в км (150000)
- engine_cc_from, engine_cc_to: целое в см³ (1600)

Правила:
- "дизель" → fuel_type="diesel"
- "автомат" / "АКПП" → transmission="automatic"
- "механика" / "МКПП" → transmission="manual"
- "не дороже 30000" / "до 30к" → price_to=30000
- "пробег до 150" → mileage_to=150000
- "2018-2022" → year_from=2018, year_to=2022
- "1.6" / "1,6" → engine_cc_from=1600 (если "до 1.6" — engine_cc_to=1600)
- Если не уверен — null. НЕ выдумывай.

Пример:
"BMW X5 2019-2023 дизель автомат до 40000, пробег до 120к"
→ {"brand":"BMW","model":"X5","year_from":2019,"year_to":2023,"price_from":null,"price_to":40000,"fuel_type":"diesel","transmission":"automatic","body_type":null,"mileage_to":120000,"engine_cc_from":null,"engine_cc_to":null}
"""

FIELDS = [
    "brand", "model", "year_from", "year_to", "price_from", "price_to",
    "fuel_type", "transmission", "body_type", "mileage_to",
    "engine_cc_from", "engine_cc_to",
]


def _extract_json(text: str) -> dict | None:
    """LLM может обернуть в ```json ... ``` или добавить текст."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def parse_query(text: str) -> dict:
    """Возвращает dict с полями FIELDS (None для отсутствующих).
    При ошибке/выключенном AI — пустой dict (все None).
    """
    empty = {k: None for k in FIELDS}
    if not settings.ai_enabled or not settings.ai_api_key:
        return empty

    url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
        "max_tokens": 300,
    }

    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(url, headers=headers, json=body) as r:
                if r.status != 200:
                    log.warning("ai HTTP %s: %s", r.status, await r.text())
                    return empty
                data = await r.json()
    except Exception as e:
        log.warning("ai request fail: %s", e)
        return empty

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        log.warning("ai parse fail: %s, data=%s", e, str(data)[:200])
        return empty

    parsed = _extract_json(content)
    if parsed is None:
        log.warning("ai no json in: %s", content[:200])
        return empty

    out = dict(empty)
    for k in FIELDS:
        v = parsed.get(k)
        if v in (None, "", "null"):
            out[k] = None
        elif k in ("year_from", "year_to", "price_from", "price_to",
                   "mileage_to", "engine_cc_from", "engine_cc_to"):
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                out[k] = None
        else:
            out[k] = str(v)
    return out