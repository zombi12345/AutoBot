from __future__ import annotations

# Популярные в РБ марки + китайские бренды (2025-2026).
# Порядок стабилен — индексы в callback_data.
BRANDS: dict[str, list[str]] = {
    # китайские / новые для РБ
    "Belgee": ["X50", "S50", "X70"],
    "Geely": ["Atlas", "Coolray", "Emgrand", "Tugella", "Monjaro", "Okavango", "Binyue Cool", "EX5", "Preface"],
    "BYD": ["Song Plus", "Yuan Up", "Han", "Tang", "Seal", "Dolphin", "Atto 3", "Seagull"],
    "Dongfeng": ["Box", "Mage", "M5", "H30 Cross", "AX7"],
    "Voyah": ["Free", "Dreamer", "Passion"],
    "Deepal": ["S07", "SL03", "S05"],
    "Li Auto": ["L6", "L7", "L8", "L9", "MEGA"],
    "Haval": ["Jolion", "Dargo", "F7", "H9", "H6"],
    "Zeekr": ["001", "009", "X", "7X"],
    "Chery": ["Tiggo 4", "Tiggo 7 Pro", "Tiggo 8 Pro", "Tiggo 9", "Arrizo 8", "iCar 03"],
    "Jetour": ["X70 Plus", "X90 Plus", "Dashing", "Traveler"],
    "Exeed": ["TXL", "VX", "LX", "RX"],
    "Leapmotor": ["C11", "T03", "C01"],
    "Avatr": ["11", "12"],
    "Hongqi": ["H5", "HS5", "E-HS9"],
    "GAC": ["GS3", "GS8", "Emkoo"],
    "JAC": ["S3", "S5", "T6", "T8"],
    "FAW": ["Bestune T77", "Bestune B70", "Oley"],
    "Shineray": ["T30", "T32"],
    "BMG": ["X3", "X5"],
    "Москвич": ["3", "3е", "6"],
    "Zubr": ["Legenda", "Volat", "Talisman", "Zorka", "Relikt"],

    # европейские / массовые
    "Audi": ["A3", "A4", "A5", "A6", "A7", "A8", "Q3", "Q5", "Q7", "Q8", "e-tron", "TT"],
    "BMW": ["1 Series", "2 Series", "3 Series", "4 Series", "5 Series", "7 Series", "X1", "X3", "X5", "X6", "X7", "M3", "M5", "i3", "iX"],
    "Mercedes-Benz": ["A", "B", "C", "E", "S", "CLA", "GLA", "GLB", "GLC", "GLE", "GLS", "V", "Sprinter", "EQS"],
    "Volkswagen": ["Golf", "Passat", "Polo", "Tiguan", "Touareg", "Jetta", "Arteon", "ID.3", "ID.4", "ID.6", "Caddy", "Multivan"],
    "Skoda": ["Fabia", "Karoq", "Kodiaq", "Octavia", "Rapid", "Superb", "Enyaq"],
    "Opel": ["Astra", "Corsa", "Insignia", "Mokka", "Zafira", "Vectra"],
    "Peugeot": ["2008", "3008", "308", "408", "5008", "508", "Partner", "Boxer"],
    "Citroen": ["Berlingo", "C3", "C4", "C5", "Jumpy", "Jumper"],
    "Renault": ["Arkana", "Captur", "Duster", "Logan", "Megane", "Sandero", "Kaptur", "Trafic"],
    "Dacia": ["Duster", "Logan", "Sandero", "Jogger"],
    "Ford": ["Explorer", "Fiesta", "Focus", "Kuga", "Mondeo", "Mustang", "Transit", "Ranger"],
    "Fiat": ["500", "Panda", "Doblo", "Ducato"],
    "Seat": ["Ibiza", "Leon", "Ateca", "Tarraco"],
    "Volvo": ["S60", "S90", "V60", "V90", "XC40", "XC60", "XC90", "EX30", "EX90"],
    "Land Rover": ["Defender", "Discovery", "Evoque", "Freelander", "Range Rover", "Range Rover Sport"],
    "Jaguar": ["XE", "XF", "F-Pace", "I-Pace"],
    "Porsche": ["911", "Cayenne", "Macan", "Panamera", "Taycan"],
    "Mini": ["Cooper", "Countryman", "Clubman"],
    "Smart": ["Fortwo", "Forfour"],

    # японские
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "C-HR", "Yaris", "Prius", "Supra", "Hilux"],
    "Lexus": ["ES", "GX", "IS", "LX", "NX", "RX", "UX", "LM"],
    "Nissan": ["Almera", "Juke", "Leaf", "Murano", "Qashqai", "X-Trail", "Note", "Patrol", "Navara"],
    "Infiniti": ["Q50", "QX50", "QX60", "QX70", "QX80"],
    "Mazda": ["3", "6", "CX-3", "CX-5", "CX-7", "CX-9", "CX-60", "MX-5"],
    "Honda": ["Accord", "Civic", "CR-V", "Pilot", "HR-V", "Jazz"],
    "Mitsubishi": ["ASX", "Eclipse Cross", "Lancer", "Outlander", "Pajero", "L200"],
    "Subaru": ["Forester", "Impreza", "Outback", "XV", "Legacy"],
    "Suzuki": ["Grand Vitara", "Jimny", "SX4", "Vitara", "Swift"],
    "Daihatsu": ["Terios", "Materia", "Sirion"],

    # корейские
    "Hyundai": ["Creta", "Elantra", "i30", "ix35", "Santa Fe", "Solaris", "Tucson", "Palisade", "Staria", "IONIQ 5"],
    "Kia": ["Ceed", "Cerato", "Optima", "Rio", "Seltos", "Sorento", "Sportage", "Carnival", "EV6", "K5"],
    "SsangYong": ["Actyon", "Kyron", "Rexton", "Tivoli"],

    # американские
    "Chevrolet": ["Aveo", "Captiva", "Cruze", "Lacetti", "Malibu", "Tahoe", "Camaro"],
    "Cadillac": ["CTS", "Escalade", "XT5", "XT6"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y", "Cybertruck"],
    "Jeep": ["Cherokee", "Compass", "Grand Cherokee", "Wrangler", "Renegade"],
    "Dodge": ["Challenger", "Charger", "Durango"],
    "Chrysler": ["300C", "Pacifica"],
    "RAM": ["1500", "2500"],

    # отечественные / СНГ
    "Lada": ["Granta", "Niva", "Vesta", "XRAY", "Largus", "Kalina", "Priora"],
    "ВАЗ": ["2101", "2106", "2107", "2109", "2110", "2114", "2115"],
    "ГАЗ": ["Волга", "Газель", "Соболь", "Next"],
    "УАЗ": ["Patriot", "Hunter", "Profi", "Буханка"],
    "МАЗ": ["4370", "5440", "6317"],
    "Daewoo": ["Matiz", "Nexia", "Lanos", "Sens"],
    "Ravon": ["R2", "R4", "Nexia R3"],
}

BRAND_NAMES: list[str] = list(BRANDS.keys())

# Годы: 2026 → 1990 (для пагинации по 8 лет = 5 страниц)
YEARS: list[int] = list(range(2026, 1989, -1))

# Цены USD: от 0 до 200k ступенями
PRICES: list[int] = [
    0, 1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000,
    15000, 18000, 20000, 25000, 30000, 40000, 50000, 70000, 100000, 150000, 200000,
]