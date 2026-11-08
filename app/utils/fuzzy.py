from __future__ import annotations

import difflib
import re

_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})

_VISUAL = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X",
    "а": "A", "в": "B", "е": "E", "к": "K", "м": "M", "н": "H",
    "о": "O", "р": "P", "с": "C", "т": "T", "у": "Y", "х": "X",
})

_SYNONYMS: dict[str, str] = {
    # немецкие
    "bmv": "BMW", "бмв": "BMW",
    "mers": "Mercedes-Benz", "mersedes": "Mercedes-Benz", "merin": "Mercedes-Benz",
    "мерс": "Mercedes-Benz", "мерседес": "Mercedes-Benz", "мерин": "Mercedes-Benz",
    "folts": "Volkswagen", "folks": "Volkswagen", "folksvagen": "Volkswagen",
    "фольц": "Volkswagen", "фолькс": "Volkswagen", "фольксваген": "Volkswagen",
    "ауди": "Audi", "порше": "Porsche", "порш": "Porsche",
    "опель": "Opel", "шкода": "Skoda", "шкоде": "Skoda", "мини": "Mini",
    # японские
    "тойота": "Toyota", "ниссан": "Nissan", "хонда": "Honda", "мазда": "Mazda",
    "мицубиси": "Mitsubishi", "митсубиси": "Mitsubishi", "митсу": "Mitsubishi",
    "субару": "Subaru", "лексус": "Lexus", "инфинити": "Infiniti",
    "дайхатсу": "Daihatsu",
    # корейские
    "хендай": "Hyundai", "хундай": "Hyundai", "хендэ": "Hyundai", "хундаи": "Hyundai",
    "киа": "Kia",
    "дэу": "Daewoo", "деу": "Daewoo",
    "ланос": "Daewoo", "lanos": "Daewoo",
    "матиз": "Daewoo", "matiz": "Daewoo",
    "нексия": "Daewoo", "nexia": "Daewoo",
    "сенс": "Daewoo", "sens": "Daewoo",
    "равон": "Ravon",
    "санг йонг": "SsangYong", "ссанг йонг": "SsangYong",
    # американские
    "шевроле": "Chevrolet", "шевролёт": "Chevrolet",
    "форд": "Ford", "джип": "Jeep", "кадиллак": "Cadillac",
    "тесла": "Tesla", "крайслер": "Chrysler", "додж": "Dodge",
    # французские
    "рено": "Renault", "пежо": "Peugeot", "ситроен": "Citroen",
    "дакия": "Dacia", "дача": "Dacia",
    # британские
    "ленд ровер": "Land Rover", "лендровер": "Land Rover", "ровер": "Land Rover",
    "ягуар": "Jaguar",
    # китайские
    "beldzhi": "Belgee", "белджи": "Belgee", "белги": "Belgee",
    "dzhili": "Geely", "джили": "Geely", "джилли": "Geely", "геели": "Geely",
    "чери": "Chery",
    "хавал": "Haval", "хавейл": "Haval", "хавел": "Haval",
    "эксид": "Exeed", "ексид": "Exeed", "иксид": "Exeed",
    "джетур": "Jetour", "джетор": "Jetour",
    "бид": "BYD", "бй": "BYD",
    "зеекр": "Zeekr", "зикр": "Zeekr",
    "воя": "Voyah", "воях": "Voyah",
    "дипал": "Deepal",
    "ли авто": "Li Auto", "лисян": "Li Auto", "ли сян": "Li Auto",
    "аватр": "Avatr",
    "хончи": "Hongqi", "хунци": "Hongqi", "хонци": "Hongqi",
    "донгфенг": "Dongfeng", "донг фенг": "Dongfeng", "дунфен": "Dongfeng",
    "леапмотор": "Leapmotor", "липмотор": "Leapmotor",
    # СНГ
    "жигули": "ВАЗ", "ваз": "ВАЗ", "лада": "Lada",
    "уаз": "УАЗ", "газ": "ГАЗ", "маз": "МАЗ",
    "москвич": "Москвич", "москвич 2141": "Москвич", "зубр": "Zubr",
}

# Популярные модели кириллицей / разговорные
_MODEL_SYNONYMS: dict[str, str] = {
    "камри": "Camry",
    "рав4": "RAV4", "рав 4": "RAV4", "рафик": "RAV4",
    "крузак": "Land Cruiser", "ленд крузер": "Land Cruiser", "прадо": "Land Cruiser",
    "хайлендер": "Highlander", "королла": "Corolla", "корола": "Corolla",
    "тигуан": "Tiguan", "тигуан": "Tiguan",
    "пассат": "Passat", "гольф": "Golf", "поло": "Polo", "джетта": "Jetta",
    "солярис": "Solaris", "соларис": "Solaris",
    "элантра": "Elantra", "туссан": "Tucson", "тусан": "Tucson",
    "санта фе": "Santa Fe", "сантафе": "Santa Fe",
    "спортейдж": "Sportage", "соренто": "Sorento", "оптима": "Optima",
    "фокус": "Focus", "мондео": "Mondeo", "фиеста": "Fiesta",
    "октавия": "Octavia", "суперб": "Superb", "рапид": "Rapid",
    "кодиак": "Kodiaq", "карог": "Karoq", "карок": "Karoq",
    "дастер": "Duster", "логан": "Logan", "сандеро": "Sandero",
    "сх5": "CX-5", "сх-5": "CX-5", "сх7": "CX-7", "сх9": "CX-9",
    "форд": "Focus",
    "астра": "Astra", "корса": "Corsa",
    "камри": "Camry",
    "м3": "M3", "м5": "M5",
    "пассат": "Passat",
    "круз": "Cruze", "авео": "Aveo", "лачетти": "Lacetti",
}


# ----- Расширение под русские модели av.by (1 серия, 5 серия, iX) -----
_MODEL_SYNONYMS.update({
    # BMW
    "5 series": "5 серия", "5series": "5 серия", "пятерка": "5 серия", "пятерочка": "5 серия",
    "3 series": "3 серия", "3series": "3 серия", "трешка": "3 серия", "трешечка": "3 серия",
    "7 series": "7 серия", "7series": "7 серия", "семерка": "7 серия",
    "1 series": "1 серия", "1series": "1 серия", "единичка": "1 серия",
    "2 series": "2 серия", "2series": "2 серия", "двушка": "2 серия",
    "4 series": "4 серия", "4series": "4 серия", "четверка": "4 серия",
    "6 series": "6 серия", "6series": "6 серия", "шестерка": "6 серия",
    "8 series": "8 серия", "8series": "8 серия", "восьмерка": "8 серия",
    "икс 5": "X5", "икс5": "X5", "икс-5": "X5", "икс пятый": "X5",
    "икс 3": "X3", "икс3": "X3", "икс-3": "X3", "икс третий": "X3",
    "икс 1": "X1", "икс1": "X1", "икс-1": "X1",
    "икс 6": "X6", "икс6": "X6", "икс-6": "X6",
    "икс 7": "X7", "икс7": "X7", "икс-7": "X7",
    # Mercedes
    "с класс": "C-класс", "ц класс": "C-класс", "с-класс": "C-класс",
    "е класс": "E-класс", "е-класс": "E-класс",
    "а класс": "A-класс", "а-класс": "A-класс",
    "s класс": "S-класс", "с-класс s": "S-класс",
    # Audi
    "а4": "A4", "а6": "A6", "а8": "A8", "а3": "A3", "а5": "A5", "а7": "A7",
    "ку 5": "Q5", "ку5": "Q5", "ку 7": "Q7", "ку7": "Q7", "ку 3": "Q3", "ку3": "Q3",
    # VW
    "пассат": "Passat", "тигуан": "Tiguan", "поло": "Polo", "гольф": "Golf",
    "джетта": "Jetta", "артеон": "Arteon", "туарег": "Touareg",
    # Toyota
    "камри": "Camry", "королла": "Corolla", "корола": "Corolla",
    "рав4": "RAV4", "рав 4": "RAV4", "рафик": "RAV4",
    "крузак": "Land Cruiser", "крузер": "Land Cruiser", "прадо": "Land Cruiser Prado",
    "ленд крузер": "Land Cruiser", "хайлендер": "Highlander",
    # Hyundai / Kia
    "солярис": "Solaris", "соларис": "Solaris",
    "элантра": "Elantra", "туссан": "Tucson", "тусан": "Tucson",
    "санта фе": "Santa Fe", "сантафе": "Santa Fe", "санта-фе": "Santa Fe",
    "спортейдж": "Sportage", "соренто": "Sorento", "оптима": "Optima",
    "сид": "Ceed", "церато": "Cerato", "рио": "Rio", "сельтос": "Seltos",
    # Ford
    "фокус": "Focus", "мондео": "Mondeo", "фиеста": "Fiesta",
    "куга": "Kuga", "мустанг": "Mustang",
    # Renault / Dacia
    "дастер": "Duster", "дастер": "Duster", "логан": "Logan", "сандеро": "Sandero",
    "аркана": "Arkana", "каптюр": "Kaptur", "меган": "Megane",
    # Skoda
    "октавия": "Octavia", "суперб": "Superb", "рапид": "Rapid",
    "кодиак": "Kodiaq", "карог": "Karoq", "карок": "Karoq", "фабия": "Fabia",
    # Mazda
    "сх5": "CX-5", "сх-5": "CX-5", "сх7": "CX-7", "сх9": "CX-9",
    "мазда 3": "3", "мазда 6": "6", "трешка мазда": "3",
    # Opel / Peugeot / Citroen
    "астра": "Astra", "корса": "Corsa", "инсигния": "Insignia", "мокка": "Mokka",
    "пежо 308": "308", "пежо 408": "408", "пежо 3008": "3008",
    # Chevrolet / Daewoo
    "круз": "Cruze", "авео": "Aveo", "лачетти": "Lacetti", "каптива": "Captiva",
    "матиз": "Matiz", "нексия": "Nexia", "ланос": "Lanos", "сенс": "Sens",
    # Китай
    "кулрей": "Coolray", "атлас": "Atlas", "тугелла": "Tugella",
    "монжаро": "Monjaro", "окаванго": "Okavango",
    "джолион": "Jolion", "дарго": "Dargo", "ф7": "F7", "ф7х": "F7x",
    "тигго": "Tiggo 4", "тиго": "Tiggo 4",
    # Лада
    "веста": "Vesta", "гранта": "Granta", "нива": "Niva", "ларгус": "Largus",
})


def normalize(s: str) -> str:
    s = s.strip().translate(_TRANSLIT).lower()
    s = re.sub(r"[\s\-_\.]+", "", s)
    return s


def _visual_normalize(s: str) -> str:
    s = s.strip().translate(_VISUAL).lower().translate(_TRANSLIT)
    s = re.sub(r"[\s\-_\.]+", "", s)
    return s


def _keys(s: str) -> set[str]:
    """Два ключа: транслит и visual-двойники. Оба используются для матча."""
    n = normalize(s)
    v = _visual_normalize(s)
    return {n, v}


def _lookup_synonym(query: str, models_mode: bool = False) -> str | None:
    q_raw = query.strip().lower()
    qn = normalize(q_raw)
    qv = _visual_normalize(q_raw)
    for dict_ in ([_MODEL_SYNONYMS, _SYNONYMS] if models_mode else [_SYNONYMS, _MODEL_SYNONYMS]):
        for q in (q_raw, qn, qv):
            if q in dict_:
                return dict_[q]
    return None


def find_brand(query: str, names: list[str], cutoff: float = 0.72) -> tuple[str | None, str]:
    if not query or not query.strip():
        return None, "none"
    syn = _lookup_synonym(query, models_mode=False)
    if syn is not None and syn in names:
        return syn, "fuzzy"
    qn = normalize(query)
    name_map = {normalize(n): n for n in names}
    if qn in name_map:
        return name_map[qn], "exact"
    qv = _visual_normalize(query)
    if qv in name_map:
        return name_map[qv], "exact"
    matches = difflib.get_close_matches(qn, list(name_map.keys()), n=1, cutoff=cutoff)
    if matches:
        return name_map[matches[0]], "fuzzy"
    matches = difflib.get_close_matches(qv, list(name_map.keys()), n=1, cutoff=cutoff)
    if matches:
        return name_map[matches[0]], "fuzzy"
    return None, "none"


def find_model(query: str, models: list[str], cutoff: float = 0.6) -> tuple[str | None, str]:
    if not query or not query.strip() or not models:
        return None, "none"
    # 1) синоним
    syn = _lookup_synonym(query, models_mode=True)
    if syn and syn in models:
        return syn, "fuzzy"
    # 2) по обоим ключам
    q_keys = _keys(query)
    model_key_map: dict[str, str] = {}
    for m in models:
        for k in _keys(m):
            model_key_map[k] = m
    for qk in q_keys:
        if qk in model_key_map:
            return model_key_map[qk], "exact"
    # 3) difflib по обоим ключам
    for qk in q_keys:
        matches = difflib.get_close_matches(qk, list(model_key_map.keys()), n=1, cutoff=cutoff)
        if matches:
            return model_key_map[matches[0]], "fuzzy"
    return None, "none"