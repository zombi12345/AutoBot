from __future__ import annotations

# Топ-марки для РБ. Порядок стабильный — по нему индексы в callback_data.
BRANDS: dict[str, list[str]] = {
    "Audi": ["A3", "A4", "A5", "A6", "Q3", "Q5", "Q7", "Q8"],
    "BMW": ["3 Series", "5 Series", "7 Series", "X1", "X3", "X5", "X6", "X7", "M3", "M5"],
    "Volkswagen": ["Golf", "Passat", "Polo", "Tiguan", "Touareg", "Jetta", "Arteon"],
    "Mercedes-Benz": ["A", "C", "E", "S", "CLA", "GLA", "GLC", "GLE", "GLS", "V"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "C-HR", "Yaris"],
    "Nissan": ["Almera", "Juke", "Leaf", "Murano", "Qashqai", "X-Trail"],
    "Renault": ["Arkana", "Captur", "Duster", "Logan", "Megane", "Sandero"],
    "Kia": ["Ceed", "Cerato", "Optima", "Rio", "Seltos", "Sorento", "Sportage"],
    "Hyundai": ["Creta", "Elantra", "i30", "ix35", "Santa Fe", "Solaris", "Tucson"],
    "Skoda": ["Fabia", "Karoq", "Kodiaq", "Octavia", "Rapid", "Superb"],
    "Ford": ["Explorer", "Fiesta", "Focus", "Kuga", "Mondeo", "Mustang"],
    "Mazda": ["3", "6", "CX-5", "CX-7", "CX-9", "MX-5"],
    "Opel": ["Astra", "Corsa", "Insignia", "Mokka", "Zafira"],
    "Peugeot": ["2008", "3008", "308", "408", "5008", "508"],
    "Citroen": ["Berlingo", "C3", "C4", "C5"],
    "Lada": ["Granta", "Niva", "Vesta", "XRAY"],
    "Mitsubishi": ["ASX", "Eclipse Cross", "Lancer", "Outlander", "Pajero"],
    "Honda": ["Accord", "Civic", "CR-V", "Pilot"],
    "Volvo": ["S60", "S90", "V60", "XC60", "XC90"],
    "Land Rover": ["Defender", "Discovery", "Evoque", "Freelander", "Range Rover"],
    "Lexus": ["ES", "GX", "IS", "LX", "NX", "RX"],
    "Subaru": ["Forester", "Impreza", "Outback", "XV"],
    "Chevrolet": ["Aveo", "Captiva", "Cruze", "Lacetti"],
    "Dacia": ["Duster", "Logan", "Sandero"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y"],
    "Porsche": ["911", "Cayenne", "Macan", "Panamera"],
    "Infiniti": ["Q50", "QX50", "QX60", "QX70"],
    "Jeep": ["Cherokee", "Compass", "Grand Cherokee", "Wrangler"],
    "Suzuki": ["Grand Vitara", "Jimny", "SX4", "Vitara"],
    "Haval": ["Dargo", "F7", "H9", "Jolion"],
}

BRAND_NAMES: list[str] = list(BRANDS.keys())

# Годы — от свежих к старым (UX как на av.by)
YEARS: list[int] = list(range(2025, 2009, -1))

# Ценовые ступени, USD
PRICES: list[int] = [0, 3000, 5000, 8000, 10000, 15000, 20000, 30000, 50000, 100000]