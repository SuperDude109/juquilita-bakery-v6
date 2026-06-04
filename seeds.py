"""Seed data for the Juquilita Bakery v2 prototype.

The catalog is intentionally verbose because the original prototype collapsed many
visually distinct Mexican breads into a handful of generic products. Prices are
seeded from the Juquilita public menu text where available. Items in the same
public price group keep that group price and record the pricing basis.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

TODAY = date.today()

CATEGORIES: list[dict[str, Any]] = [
    {"key": "savory", "name_en": "Savory breads", "name_es": "Panes salados", "sort_order": 10, "description_en": "Bolillos, teleras, pambazo bread, and stuffed savory breads.", "description_es": "Bolillos, teleras, pan para pambazo y panes rellenos salados."},
    {"key": "oaxacan", "name_en": "Oaxacan breads", "name_es": "Panes oaxaqueños", "sort_order": 20, "description_en": "Pan amarillo, serrano bread, pan de yema, semitas, and ojaldra.", "description_es": "Pan amarillo, serrano, pan de yema, semitas y ojaldra."},
    {"key": "cookies", "name_en": "Cookies and polvorones", "name_es": "Galletas y polvorones", "sort_order": 30, "description_en": "Mexican sugar cookies, sprinkle cookies, jam cookies, and pecan cookies.", "description_es": "Galletas de azúcar, grageas, fresa, piña, chocolate y nuez."},
    {"key": "fluffy", "name_en": "Conchas and fluffy breads", "name_es": "Conchas y pan esponjado", "sort_order": 40, "description_en": "Semisweet fluffy breads with shell toppings, sugar, sprinkles, or chocolate.", "description_es": "Panes esponjados semidulces con concha, azúcar, grageas o chocolate."},
    {"key": "dense", "name_en": "Shortening breads", "name_es": "Pan de manteca", "sort_order": 50, "description_en": "Denser semisweet breads with powdered sugar, shortening, sesame, or fillings.", "description_es": "Pan semidulce más denso con azúcar, manteca, ajonjolí o rellenos."},
    {"key": "empanadas", "name_en": "Empanadas and filled breads", "name_es": "Empanadas y pan relleno", "sort_order": 60, "description_en": "Pumpkin, Bavarian cream, pineapple, apple, cajeta, and filled hand pies.", "description_es": "Calabaza, crema Bavaria, piña, manzana, cajeta y panes rellenos."},
    {"key": "pastries", "name_en": "Puff pastries and danishes", "name_es": "Hojaldres y daneses", "sort_order": 70, "description_en": "Orejas, banderillas, campechanas, barquillos, cuernos, flautas, and mil hojas.", "description_es": "Orejas, banderillas, campechanas, barquillos, cuernos, flautas y mil hojas."},
    {"key": "donuts_churros", "name_en": "Donuts and churros", "name_es": "Donas y churros", "sort_order": 80, "description_en": "Sugar donuts, twists, chocolate donuts, filled donuts, plain and filled churros.", "description_es": "Donas de azúcar, trenzas, chocolate, rellenas, churros simples y rellenos."},
    {"key": "desserts", "name_en": "Desserts and slices", "name_es": "Postres y rebanadas", "sort_order": 90, "description_en": "Tres leches slices, flan, chocoflan, fruit tarts, bread pudding, and mini desserts.", "description_es": "Rebanadas de tres leches, flan, chocoflan, tartas, budín y postres chicos."},
    {"key": "cakes", "name_en": "Cakes and trays", "name_es": "Pasteles y charolas", "sort_order": 100, "description_en": "Simple tres leches cakes, custard trays, and custom celebration cakes.", "description_es": "Pasteles tres leches sencillos, charolas de flan y pasteles personalizados."},
    {"key": "seasonal", "name_en": "Seasonal breads", "name_es": "Pan de temporada", "sort_order": 110, "description_en": "Pan de Muerto, Rosca de Reyes, and holiday preorder items.", "description_es": "Pan de Muerto, Rosca de Reyes y pedidos de temporada."},
]

SETTINGS: list[dict[str, str]] = [
    {"key": "business_name", "value": "Juquilita Bakery LLC", "value_type": "text", "label": "Business name"},
    {"key": "address", "value": "325 South Cumberland Street, Morristown, TN 37813", "value_type": "text", "label": "Address"},
    {"key": "phone", "value": "(423) 307-8244", "value_type": "text", "label": "Phone"},
    {"key": "text_phone", "value": "(423) 307-9003", "value_type": "text", "label": "Text number"},
    {"key": "email", "value": "Juquilitabakery@outlook.com", "value_type": "text", "label": "Email"},
    {"key": "timezone", "value": "America/New_York", "value_type": "text", "label": "Timezone"},
    {"key": "sales_tax_rate", "value": "0.0000", "value_type": "decimal", "label": "Sales tax rate. Configure before production."},
    {"key": "default_slot_capacity", "value": "6", "value_type": "integer", "label": "Pickup orders allowed per 30-minute window"},
    {"key": "cake_deposit_rate", "value": "0.40", "value_type": "decimal", "label": "Suggested cake deposit rate"},
    {"key": "large_order_deposit_threshold", "value": "75.00", "value_type": "money", "label": "Deposit suggested above subtotal"},
    {"key": "public_partner_cards_require_consent", "value": "true", "value_type": "boolean", "label": "Public partner cards require consent"},
]

# Active official footer hours seen on the public site during research. Times are 24-hour local values.
BUSINESS_HOURS: list[dict[str, Any]] = [
    {"weekday": 0, "day_en": "Monday", "day_es": "Lunes", "opens_at": "06:30", "closes_at": "20:30", "slot_capacity": 5, "profile": "official_footer"},
    {"weekday": 1, "day_en": "Tuesday", "day_es": "Martes", "opens_at": "07:00", "closes_at": "21:30", "slot_capacity": 6, "profile": "official_footer"},
    {"weekday": 2, "day_en": "Wednesday", "day_es": "Miércoles", "opens_at": "06:30", "closes_at": "21:30", "slot_capacity": 6, "profile": "official_footer"},
    {"weekday": 3, "day_en": "Thursday", "day_es": "Jueves", "opens_at": "06:30", "closes_at": "21:30", "slot_capacity": 6, "profile": "official_footer"},
    {"weekday": 4, "day_en": "Friday", "day_es": "Viernes", "opens_at": "06:30", "closes_at": "21:30", "slot_capacity": 8, "profile": "official_footer"},
    {"weekday": 5, "day_en": "Saturday", "day_es": "Sábado", "opens_at": "06:30", "closes_at": "21:30", "slot_capacity": 8, "profile": "official_footer"},
    {"weekday": 6, "day_en": "Sunday", "day_es": "Domingo", "opens_at": "06:30", "closes_at": "21:30", "slot_capacity": 7, "profile": "official_footer"},
]

PRICE_BASIS = {
    "official_menu": "Official Juquilita menu text supplied by source file.",
    "official_group_price": "Official menu group price applied to named bread variants in that group.",
    "quote": "Public source confirms item, but live price varies. Requires quote.",
    "admin_configured": "Editable admin price seeded for planning.",
}


def product(slug: str, es: str, en: str, category: str, price: float | None,
            description_es: str, description_en: str, *, subcategory: str = "",
            wholesale: float | None = None, unit: str = "each", stock: int = 60,
            stock_policy: str = "track", lead_hours: int = 0, order_mode: str = "order",
            featured: bool = False, bulk: bool = False, seasonal: bool = False,
            season_start: str = "", season_end: str = "", aliases: str = "",
            accent: str = "marigold", icon: str = "🥐", basis: str = "official_menu",
            allergens: str = "wheat, dairy, egg", ingredients: str = "", margin: float = 0.58,
            photo_status: str = "needs_real_photo") -> dict[str, Any]:
    if wholesale is None and price is not None:
        wholesale = round(price * 0.85, 2) if bulk or category in {"savory", "cookies", "fluffy", "pastries", "donuts_churros"} else None
    return {
        "slug": slug, "name_es": es, "name_en": en, "category_key": category, "subcategory": subcategory,
        "description_es": description_es, "description_en": description_en, "base_price": price, "wholesale_price": wholesale,
        "unit": unit, "stock_count": stock, "stock_policy": stock_policy, "lead_time_hours": lead_hours,
        "order_mode": order_mode, "is_featured": 1 if featured else 0, "is_bulk_friendly": 1 if bulk else 0,
        "is_seasonal": 1 if seasonal else 0, "season_start": season_start, "season_end": season_end,
        "search_terms": aliases, "image_accent": accent, "icon": icon, "price_basis": PRICE_BASIS[basis],
        "allergen_notes": allergens, "ingredient_notes": ingredients, "margin_estimate": margin,
        "photo_status": photo_status,
    }

PRODUCTS: list[dict[str, Any]] = []

# Savory breads.
PRODUCTS += [
    product("bolillo", "Bolillo", "Plain roll", "savory", 0.80, "Pan blanco para tortas, ajo, sopa o mesa familiar.", "Plain bread for subs, garlic bread, tomato soup, or table service.", subcategory="daily bread", wholesale=0.68, stock=320, bulk=True, featured=True, aliases="roll torta sub bread white bread", icon="🥖", accent="wheat"),
    product("telera", "Telera", "Sandwich roll", "savory", 0.80, "Pan suave y ancho para tortas y lonches.", "Soft sandwich roll for tortas and bakery sandwiches.", subcategory="daily bread", wholesale=0.68, stock=260, bulk=True, aliases="torta sandwich roll", icon="🥖", accent="cream"),
    product("panbasos", "Panbasos", "Pambazo bread", "savory", 0.80, "Pan blanco con harina para pambazos con salsa de guajillo.", "Flour-dusted white bread for pambazos with guajillo sauce.", subcategory="daily bread", wholesale=0.68, stock=210, bulk=True, aliases="pambazo panbazo panbaso", icon="🥖", accent="masa"),
    product("bolinachos", "Bolinachos", "Cream cheese jalapeño bread", "savory", 2.25, "Pan relleno de queso crema y jalapeño.", "Cream cheese and jalapeño stuffed bread.", subcategory="stuffed", wholesale=1.95, stock=70, featured=True, aliases="jalapeno cream cheese chile queso", icon="🌶️", accent="green"),
    product("pan-relleno", "Pan relleno", "Stuffed bread", "savory", 2.75, "Pan relleno salado con varias opciones.", "Savory stuffed bread with selectable fillings.", subcategory="stuffed", wholesale=2.35, stock=85, aliases="stuffed bread bean cheese pepperoni ham", icon="🧀", accent="red"),
    product("relleno-chorizo", "Relleno de chorizo", "Chorizo stuffed bread", "savory", 3.99, "Pan relleno con chorizo y papa.", "Chorizo and potato stuffed bread.", subcategory="stuffed", wholesale=3.49, stock=45, aliases="chorizo potato papa", icon="🌶️", accent="chile"),
]

# Oaxacan breads. The public menu groups these at 0.90.
for slug, es, en, aliases in [
    ("pan-amarillo", "Pan amarillo", "Yellow bread", "oaxaca yellow bread pan amarillo"),
    ("pan-serrano", "Pan serrano", "Serrano bread", "oaxaca serrano bread"),
    ("pan-de-yema", "Pan de yema", "Egg yolk bread", "egg yolk anise aniseed chocolate oaxaca"),
    ("semitas", "Semitas", "Oaxacan semitas", "semita cemita oaxaca"),
    ("ojaldra", "Ojaldra", "Oaxacan ojaldra", "hojaldra ojaldra oaxaca"),
]:
    PRODUCTS.append(product(slug, es, en, "oaxacan", 0.90, "Pan tradicional de Oaxaca, disponible diariamente según la vitrina.", "Traditional Oaxacan bread, available daily depending on the case.", subcategory="traditional", wholesale=0.76, stock=120, bulk=True, aliases=aliases, icon="🌾", accent="oaxaca", basis="official_group_price"))

# Cookies and polvorones, 0.90 group.
for slug, es, en, aliases in [
    ("polvoron-azucar", "Polvorón de azúcar", "Sugar polvorón", "sugar cookie polvoron white"),
    ("polvoron-rosa", "Polvorón con azúcar rosa", "Pink sugar polvorón", "pink sugar cookie rosa"),
    ("lima-fresa", "Lima con fresa", "Jam sugar cookie", "strawberry jelly jam cookie fresa"),
    ("zurrapa", "Zurrapa", "Three-color polvorón", "three color polvoron tricolor"),
    ("polvoron-grajea", "Polvorón con gragea", "Sprinkle polvorón", "sprinkle cookie gragea"),
    ("galleta-carita", "Galleta de carita", "Smiley cookie", "smiley face cookie kids"),
    ("galleta-corazon", "Galleta de corazón", "Heart sprinkle cookie", "heart shaped cookie corazon"),
    ("polvoron-chocolate", "Polvorón con pedazos de chocolate", "Chocolate-chip sugar cookie", "chocolate pieces cookie"),
    ("galleta-grajea", "Galleta de gragea", "Sprinkled cookie", "sprinkles chispas cookie"),
    ("polvoron-nuez", "Polvorón de nuez", "Pecan sugar cookie", "pecan nuez cookie"),
    ("sandia-cookie", "Sandía", "Watermelon shaped cookie", "watermelon sandia cookie"),
]:
    PRODUCTS.append(product(slug, es, en, "cookies", 0.90, "Galleta mexicana de azúcar con forma o cubierta específica.", "Mexican sugar cookie with a distinct shape or topping.", subcategory="polvorones", wholesale=0.76, stock=140, bulk=True, aliases=aliases, icon="🍪", accent="pink", basis="official_group_price"))

# Fluffy semisweet breads, 0.90 group.
for slug, es, en, aliases, icon in [
    ("concha", "Concha", "Concha sweet bread", "shell bread pan dulce pink yellow chocolate", "🐚"),
    ("chilindrina-chocolate", "Chilindrina de chocolate", "Chocolate chilindrina", "chocolate topped fluffy bread", "🍫"),
    ("bisquit", "Bisquit", "Sweet biscuit bread", "biscuit bisquit sweet bread", "🥯"),
    ("magdalena-simple", "Magdalena simple", "Plain magdalena", "muffin plain magdalena", "🧁"),
    ("magdalena-grajea", "Magdalena con gragea", "Sprinkle magdalena", "muffin sprinkles magdalena", "🧁"),
    ("marranito", "Marranito", "Molasses pig cookie bread", "pig bread puerquito molasses", "🐷"),
    ("rehilete-esponjado", "Rehilete esponjado", "Fluffy pinwheel", "pinwheel rehilete", "✳️"),
    ("nopal", "Nopal", "Nopal sweet bread", "cactus shaped bread", "🌵"),
    ("borracho", "Borracho", "Borracho sweet bread", "drunk bread syrup", "🍯"),
    ("borracho-chocolate", "Borracho de chocolate", "Chocolate borracho", "chocolate syrup bread", "🍫"),
    ("nube", "Nube", "Cloud bread", "cloud nube fluffy", "☁️"),
    ("bigote", "Bigote", "Mustache bread", "mustache pan dulce", "〰️"),
    ("corbata-mono", "Corbata o moño", "Bowtie bread", "bowtie fluffy margarine sugar", "🎀"),
    ("chirimoya", "Chirimoya", "Chirimoya bread", "chirimoya pan dulce", "🥐"),
    ("alcatraz", "Alcatraz", "Alcatraz bread", "alcatraz pan dulce", "🥐"),
    ("boquita", "Boquita", "Boquita bread", "boquitas pan dulce", "🥐"),
    ("tronco", "Tronco", "Log bread", "log trunk pan dulce", "🪵"),
    ("elotito", "Elotito", "Corn-shaped sweet bread", "corn shaped elote bread", "🌽"),
    ("gusano-polveado", "Gusano polveado", "Powdered worm bread", "worm shaped powdered bread", "〰️"),
    ("lengua", "Lengua", "Tongue shaped bread", "tongue pan dulce", "👅"),
    ("panadero", "Panadero", "Panadero sweet bread", "panadero bread", "🥐"),
    ("panadero-chocolate", "Panadero de chocolate", "Chocolate panadero", "chocolate panadero", "🍫"),
    ("nueces-normal", "Nueces normal", "Walnut-shaped bread", "walnut nuez shape", "🌰"),
]:
    PRODUCTS.append(product(slug, es, en, "fluffy", 0.90, "Pan esponjado semidulce de vitrina.", "Semisweet fluffy bread from the display case.", subcategory="pan dulce", wholesale=0.76, stock=150, bulk=True, featured=(slug == "concha"), aliases=aliases, icon=icon, accent="sunset", basis="official_group_price"))

# Shortening/dense breads, 0.90 group.
for slug, es, en, aliases in [
    ("pan-manteca", "Pan de manteca", "Shortening bread", "dense sugar shortening bread"),
    ("piedra", "Piedra", "Piedra bread", "stone bread piedra"),
    ("ladrillo", "Ladrillo", "Brick bread", "brick bread ladrillo"),
    ("cuerno", "Cuerno", "Horn bread", "horn bread cuerno"),
    ("arete", "Arete", "Ring bread", "ring bread arete"),
    ("arete-rosa", "Arete rosa", "Pink ring bread", "pink ring bread arete"),
    ("mono-ajonjolin", "Moño con ajonjolí", "Sesame bow bread", "sesame bow moño ajonjoli"),
    ("yoyo-ajonjolin", "Yoyo de ajonjolí", "Sesame yoyo", "sesame yoyo"),
    ("yoyo-grajea", "Yoyo de gragea", "Sprinkle yoyo", "sprinkles yoyo"),
    ("piez", "Piez", "Piez bread", "piez pan dulce"),
    ("piez-chocolate", "Piez de chocolate", "Chocolate piez", "piez chocolate"),
    ("cuernito-chocolate", "Cuernito polveado de chocolate", "Powdered chocolate horn", "horn chocolate powdered"),
    ("nueces-polveadas", "Nueces polveadas", "Powdered walnut bread", "powdered nueces bread"),
]:
    PRODUCTS.append(product(slug, es, en, "dense", 0.90, "Pan semidulce más denso con manteca, azúcar o ajonjolí.", "Denser semisweet bread with shortening, sugar, or sesame.", subcategory="pan de manteca", wholesale=0.76, stock=120, bulk=True, aliases=aliases, icon="🥐", accent="cream", basis="official_group_price"))

# Empanadas and filled hand breads.
for slug, es, en, aliases in [
    ("empanada-bavaria", "Empanada de crema Bavaria", "Bavarian cream empanada", "bavarian cream empanada"),
    ("empanada-calabaza", "Empanada de calabaza", "Pumpkin empanada", "pumpkin calabaza empanada"),
    ("empanada-manzana", "Empanada de manzana", "Apple empanada", "apple manzana empanada"),
    ("empanada-pina", "Empanada de piña", "Pineapple empanada", "pineapple pina empanada"),
]:
    PRODUCTS.append(product(slug, es, en, "empanadas", 1.15, "Empanada rellena horneada.", "Baked filled empanada.", subcategory="filled empanadas", wholesale=0.98, stock=100, bulk=True, aliases=aliases, icon="🥟", accent="gold", basis="official_menu"))
for slug, es, en, aliases in [
    ("taquito-fresa", "Taquito de fresa", "Strawberry filled taquito", "strawberry taquito fresa"),
    ("taquito-bavaria", "Taquito de crema Bavaria", "Bavarian cream taquito", "bavarian taquito"),
    ("empanadita-cajeta", "Empanadita de cajeta", "Cajeta mini empanada", "dulce leche cajeta mini empanada"),
    ("empanadita-pina", "Empanadita de piña", "Pineapple mini empanada", "mini pineapple pina"),
]:
    PRODUCTS.append(product(slug, es, en, "empanadas", 1.25 if "taquito" in slug else 0.65, "Pan relleno dulce de vitrina.", "Sweet filled bakery item from the case.", subcategory="small filled breads", wholesale=1.06 if "taquito" in slug else 0.55, stock=90, bulk=True, aliases=aliases, icon="🥟", accent="strawberry", basis="official_group_price"))

# Pastries and danishes.
for slug, es, en, price, aliases in [
    ("oreja", "Oreja", "Elephant ear pastry", 1.00, "elephant ear pastry oreja"),
    ("campechana", "Campechana", "Campechana pastry", 1.00, "campechana pastry"),
    ("banderilla", "Banderilla", "Banderilla pastry", 1.00, "banderilla pastry"),
    ("reganada", "Regañada", "Regañada pastry", 1.00, "reganada regañada pastry"),
    ("rebanada-mantequilla", "Rebanada con mantequilla", "Butter sugar slice", 1.00, "slice butter sugar rebanada"),
    ("cuerno-danes", "Cuerno de danés", "Danish croissant", 1.99, "danish croissant cuerno"),
    ("cono-danes-bavaria", "Cono danés con crema Bavaria", "Danish cone with Bavarian cream", 1.99, "cone danish bavarian cream"),
    ("barquillo-bavaria", "Barquillo de crema Bavaria", "Puff pastry cone", 1.99, "barquillo puff pastry cone bavarian"),
    ("dorado-fresa-manzana", "Empanada dorada", "Apple or strawberry turnover", 1.99, "turnover dorado strawberry apple"),
    ("canasta", "Canasta", "Fruit basket pastry", 1.99, "basket pastry fresa pina manzana"),
    ("taquito-dorado-guayaba-queso", "Taquito dorado de guayaba con queso", "Guava cream cheese pastry", 1.99, "guava cheese puff pastry"),
    ("manteconcha", "Manteconcha", "Manteconcha", 1.25, "muffin concha hybrid manteconcha"),
    ("flauta-fresa", "Flauta de fresa", "Strawberry flute pastry", 1.25, "strawberry flute flauta"),
    ("flauta-pina", "Flauta de piña", "Pineapple flute pastry", 1.25, "pineapple flute flauta"),
    ("mil-hojas-bavaria", "Mil hojas con crema Bavaria", "Mil hojas with Bavarian cream", 3.50, "mille feuille mil hojas bavarian"),
    ("mil-hojas-guayaba", "Mil hojas con guayaba", "Mil hojas with guava", 3.50, "mille feuille mil hojas guava"),
]:
    PRODUCTS.append(product(slug, es, en, "pastries", price, "Hojaldre o danés de vitrina.", "Puff pastry or danish from the display case.", subcategory="hojaldres", wholesale=round(price*0.85,2), stock=80, bulk=True, aliases=aliases, icon="🥐", accent="gold", basis="official_group_price"))

# Donuts and churros.
for slug, es, en, price, aliases in [
    ("churro-simple", "Churro", "Plain churro", 1.00, "fried cinnamon sugar churro"),
    ("churro-fresa", "Churro relleno de fresa", "Strawberry filled churro", 2.50, "filled churro strawberry"),
    ("churro-chocolate", "Churro relleno de chocolate", "Chocolate filled churro", 2.50, "filled churro chocolate"),
    ("churro-cajeta", "Churro relleno de cajeta", "Cajeta filled churro", 2.50, "filled churro caramel cajeta"),
    ("dona-azucar", "Dona de azúcar", "Sugar donut", 1.15, "sugar donut dona"),
    ("trenza", "Trenza", "Donut twist", 1.15, "twist donut trenza"),
    ("dona-glaseada", "Dona glaseada", "Glazed donut", 1.15, "glazed donut"),
    ("dona-chocolate", "Dona de chocolate", "Chocolate donut", 1.25, "chocolate donut"),
    ("dona-rellena-bavaria", "Dona rellena de crema Bavaria", "Bavarian cream filled donut", 1.25, "filled donut bavarian"),
]:
    PRODUCTS.append(product(slug, es, en, "donuts_churros", price, "Dona o churro hecho para vitrina diaria.", "Donut or churro made for the daily case.", subcategory="donas y churros", wholesale=round(price*0.85,2), stock=110, bulk=True, aliases=aliases, icon="🍩" if "dona" in slug or "trenza" in slug else "〰️", accent="cinnamon", basis="official_menu"))

# Desserts and slices.
for slug, es, en, price, desc_es, desc_en, aliases, icon in [
    ("budin-clasico", "Budín clásico", "Classic bread pudding", 1.89, "Budín de pan con pasas.", "Classic bread pudding with raisins.", "bread pudding raisins budin", "🍮"),
    ("budin-durazno-coco", "Budín de durazno y coco", "Peach coconut bread pudding", 1.89, "Budín de pan con durazno y coco.", "Bread pudding with peaches and coconut.", "bread pudding peach coconut", "🍮"),
    ("tres-leches-rebanada", "Rebanada de tres leches", "Tres leches cake slice", 3.25, "Pastel amarillo con relleno de fresa o piña bañado en tres leches.", "Yellow cake slice with strawberry or pineapple filling soaked in tres leches milk.", "tres leches slice cake", "🍰"),
    ("flan-individual", "Flan", "Caramel custard", 3.49, "Flan con caramelo, crema batida y cereza.", "Caramel custard topped with whipped cream and a cherry.", "flan custard caramel", "🍮"),
    ("chocoflan-individual", "Chocoflan", "Chocoflan slice", 3.89, "Flan con capa de pastel de chocolate.", "Caramel custard over chocolate cake.", "chocoflan chocolate flan", "🍫"),
    ("tarta-fruta", "Tarta de fruta", "Fruit tart", 3.99, "Mini pay con crema Bavaria o crema batida y fruta natural.", "Mini tart with Bavarian cream or whipped cream and fresh fruit.", "fruit tart pie", "🍓"),
    ("pinguino", "Pingüino", "Penguin cake", 2.75, "Pastelito relleno y cubierto con chocolate o crema.", "Small filled cake with chocolate or cream topping.", "pinguino penguin cake", "🐧"),
    ("tomatillo", "Tomatillo", "Tomatillo cake", 2.75, "Pastelito de vitrina con relleno y cubierta dulce.", "Small filled display cake with sweet coating.", "tomatillo cake", "🍰"),
    ("mechudo", "Mechudo", "Mechudo cake", 2.75, "Pastelito de vitrina con textura decorativa.", "Small display cake with decorative texture.", "mechudo cake", "🍰"),
    ("nino-envuelto", "Niño envuelto", "Rolled cake", 2.75, "Pastel enrollado relleno y cubierto.", "Rolled cake with filling and topping.", "rolled cake niño envuelto", "🍰"),
    ("cubilete-queso", "Cubilete de queso", "Mexican cheese pie", 1.25, "Pay de queso mexicano individual.", "Individual Mexican cheese pie.", "cheese pie cheesecake cubilete", "🥧"),
    ("beso-yoyo", "Beso / Yoyo", "Kiss or yoyo cookie sandwich", 1.25, "Pan dulce con relleno y cubierta de azúcar o coco.", "Sweet bread sandwich with filling and sugar or coconut topping.", "besos yoyo coconut jelly", "🍪"),
    ("mantecada-nuez", "Mantecada con nuez", "Pecan mantecada", 0.90, "Mantecada de vainilla con nuez.", "Vanilla muffin-style bread with pecan.", "muffin pecan mantecada", "🧁"),
    ("mantecada-chocolate", "Mantecada con gragea de chocolate", "Chocolate-sprinkle mantecada", 0.90, "Mantecada con gragea de chocolate.", "Muffin-style bread with chocolate sprinkles.", "muffin chocolate sprinkles", "🧁"),
    ("ojos-buey", "Ojos de buey", "Ox eye pastry", 1.25, "Pastelito de vitrina tipo ojo de buey.", "Ox-eye style display pastry.", "eyes ojos buey", "👁️"),
]:
    PRODUCTS.append(product(slug, es, en, "desserts", price, desc_es, desc_en, subcategory="desserts", wholesale=round(price*0.85,2), stock=70, bulk=False, aliases=aliases, icon=icon, accent="rose", basis="official_menu" if price in [1.89, 3.25, 3.49, 3.89, 3.99] else "official_group_price"))

# Cakes and trays.
PRODUCTS += [
    product("mini-cake-tres-leches", "Mini cake tres leches", "Mini tres leches cake", "cakes", 21.99, "Mitad de un pastel 1/4 de plancha, sencillo, con fruta y tres leches.", "Half of a quarter-sheet cake, simple fruit-filled tres leches style.", subcategory="simple cakes", wholesale=19.50, unit="cake", stock=25, stock_policy="made_to_order", lead_hours=24, featured=True, aliases="mini cake tres leches", icon="🍰", accent="pink"),
    product("pastel-cuarto", "Pastel 1/4 de plancha", "1/4 sheet cake", "cakes", 45.00, "Pastel tres leches regular con fruta, sencillo, sin decoración elaborada.", "Regular fruit-filled tres leches quarter-sheet cake without elaborate decoration.", subcategory="simple cakes", wholesale=41.00, unit="cake", stock=18, stock_policy="made_to_order", lead_hours=48, featured=True, aliases="quarter sheet cake tres leches", icon="🎂", accent="cream"),
    product("pastel-medio", "Pastel 1/2 de plancha", "1/2 sheet cake", "cakes", 70.00, "Pastel tres leches regular con fruta, sencillo.", "Regular fruit-filled tres leches half-sheet cake.", subcategory="simple cakes", wholesale=64.00, unit="cake", stock=12, stock_policy="made_to_order", lead_hours=48, aliases="half sheet cake", icon="🎂", accent="rose"),
    product("pastel-plancha", "Pastel plancha completa", "Full sheet cake", "cakes", 100.00, "Pastel tres leches regular con fruta para eventos grandes.", "Regular fruit-filled tres leches full sheet cake for large events.", subcategory="simple cakes", wholesale=92.00, unit="cake", stock=8, stock_policy="made_to_order", lead_hours=72, aliases="full sheet cake party", icon="🎂", accent="marigold"),
    product("flan-charola", "Flan 1/4 de plancha", "Quarter-sheet flan tray", "cakes", 34.99, "Flan tamaño 1/4 de plancha con crema, frutas y cerezas.", "Quarter-sheet flan with whipped cream, fruit, and cherries.", subcategory="custard trays", wholesale=31.50, unit="tray", stock=12, stock_policy="made_to_order", lead_hours=24, aliases="flan tray quarter sheet", icon="🍮", accent="caramel"),
    product("chocoflan-10", "Chocoflan 10 pulgadas", "10 inch chocoflan", "cakes", 34.99, "Pastel de chocolate y flan de 10 pulgadas, decorado ligeramente.", "10 inch chocolate cake and flan, lightly decorated.", subcategory="custard trays", wholesale=31.50, unit="cake", stock=12, stock_policy="made_to_order", lead_hours=24, aliases="chocoflan ten inch", icon="🍫", accent="brown"),
    product("pastel-decorado", "Pastel decorado personalizado", "Custom decorated cake", "cakes", None, "Pastel personalizado para bodas, fiestas, quinceañeras, revelación de género u otra ocasión.", "Custom cake for weddings, parties, quinceañeras, gender reveals, or other occasions.", subcategory="custom cakes", unit="quote", stock=0, stock_policy="quote", lead_hours=72, order_mode="quote", aliases="custom cake wedding quinceanera gender reveal birthday", icon="🎂", accent="rose", basis="quote"),
]

# Seasonal breads.
PRODUCTS += [
    product("pan-muerto-azucar", "Pan de Muerto azúcar blanca", "White sugar Pan de Muerto", "seasonal", None, "Pan de Muerto con azúcar blanca y forma tradicional.", "Traditional Pan de Muerto with white sugar topping.", subcategory="day of the dead", unit="quote", stock=0, stock_policy="quote", lead_hours=24, order_mode="quote", seasonal=True, season_start="10-15", season_end="11-02", aliases="day of dead bread pan de muerto sugar", icon="💀", accent="marigold", basis="quote"),
    product("pan-muerto-rosa", "Pan de Muerto azúcar rosa", "Pink sugar Pan de Muerto", "seasonal", None, "Pan de Muerto estilo Puebla con azúcar rosa o roja.", "Puebla-style Pan de Muerto with pink or red sugar topping.", subcategory="day of the dead", unit="quote", stock=0, stock_policy="quote", lead_hours=24, order_mode="quote", seasonal=True, season_start="10-15", season_end="11-02", aliases="pink red sugar pan de muerto", icon="💀", accent="pink", basis="quote"),
    product("pan-muerto-yema-carita", "Pan de Muerto de yema con carita", "Oaxacan face Pan de Muerto", "seasonal", None, "Pan de yema estilo Oaxaca con carita de harina pintada.", "Oaxacan-style egg-yolk bread with painted flour face decoration.", subcategory="day of the dead", unit="quote", stock=0, stock_policy="quote", lead_hours=24, order_mode="quote", seasonal=True, season_start="10-15", season_end="11-02", aliases="oaxaca face pan de muerto yema", icon="💀", accent="oaxaca", basis="quote"),
    product("rosca-reyes", "Rosca de Reyes", "King cake ring", "seasonal", None, "Rosca hecha con masa de pan de yema, pasta dulce, frutas cristalizadas y figuras ocultas según tamaño.", "Ring bread made with pan de yema dough, sweet topping, candied citrus, and hidden figurines based on size.", subcategory="day of kings", unit="quote", stock=0, stock_policy="quote", lead_hours=48, order_mode="quote", seasonal=True, season_start="01-02", season_end="01-06", aliases="king cake rosca reyes baby figurines", icon="👑", accent="green", basis="quote"),
]

VARIANTS: list[dict[str, Any]] = [
    {"product_slug": "pan-relleno", "variant_type": "filling", "name_es": "Frijol refrito", "name_en": "Refried bean", "price_delta": 0, "wholesale_delta": 0, "is_default": 1},
    {"product_slug": "pan-relleno", "variant_type": "filling", "name_es": "Queso y jalapeño", "name_en": "Cheese and jalapeño", "price_delta": 0, "wholesale_delta": 0, "is_default": 0},
    {"product_slug": "pan-relleno", "variant_type": "filling", "name_es": "Mozzarella y pepperoni", "name_en": "Mozzarella and pepperoni", "price_delta": 0, "wholesale_delta": 0, "is_default": 0},
    {"product_slug": "pan-relleno", "variant_type": "filling", "name_es": "Jamón y queso", "name_en": "Ham and cheese", "price_delta": 0, "wholesale_delta": 0, "is_default": 0},
    {"product_slug": "pastel-cuarto", "variant_type": "filling", "name_es": "Fresa", "name_en": "Strawberry", "price_delta": 0, "wholesale_delta": 0, "is_default": 1},
    {"product_slug": "pastel-cuarto", "variant_type": "filling", "name_es": "Durazno", "name_en": "Peach", "price_delta": 0, "wholesale_delta": 0, "is_default": 0},
    {"product_slug": "pastel-cuarto", "variant_type": "filling", "name_es": "Piña", "name_en": "Pineapple", "price_delta": 0, "wholesale_delta": 0, "is_default": 0},
    {"product_slug": "pastel-cuarto", "variant_type": "filling", "name_es": "Coco", "name_en": "Coconut", "price_delta": 0, "wholesale_delta": 0, "is_default": 0},
    {"product_slug": "pastel-cuarto", "variant_type": "filling", "name_es": "Nuez", "name_en": "Pecan", "price_delta": 0, "wholesale_delta": 0, "is_default": 0},
]

# Apply common cake variants to all simple cakes.
for cake_slug in ["mini-cake-tres-leches", "pastel-medio", "pastel-plancha"]:
    for base in [v for v in VARIANTS if v["product_slug"] == "pastel-cuarto"]:
        copy = dict(base)
        copy["product_slug"] = cake_slug
        VARIANTS.append(copy)

for cake_slug in ["mini-cake-tres-leches", "pastel-cuarto", "pastel-medio", "pastel-plancha"]:
    for name_es, name_en, delta in [
        ("Pastel amarillo regular", "Regular yellow cake", 0),
        ("Chocolate", "Chocolate", 8),
        ("Fresa", "Strawberry", 8),
        ("Red Velvet", "Red Velvet", 10),
        ("Mocha", "Mocha", 10),
        ("Cream cheese pie filling", "Cream cheese pie filling", 12),
        ("Chocoflan", "Chocoflan", 16),
        ("Flan", "Flan", 14),
    ]:
        VARIANTS.append({"product_slug": cake_slug, "variant_type": "cake_flavor", "name_es": name_es, "name_en": name_en, "price_delta": delta, "wholesale_delta": round(delta * 0.75, 2), "is_default": 1 if delta == 0 else 0})

BUNDLES: list[dict[str, Any]] = [
    {"slug": "family-pan-dulce", "name_en": "Family pan dulce box", "name_es": "Caja familiar de pan dulce", "description_en": "12 mixed conchas, fluffy breads, cookies, and donuts.", "description_es": "12 piezas mixtas de conchas, pan esponjado, galletas y donas.", "items_json": '{"concha":4,"polvoron-azucar":2,"marranito":2,"dona-azucar":2,"oreja":2}', "sort_order": 1},
    {"slug": "wholesale-starter", "name_en": "Wholesale starter order", "name_es": "Pedido inicial para negocio", "description_en": "60 bolillos, 36 teleras, 30 panbasos, and 24 conchas.", "description_es": "60 bolillos, 36 teleras, 30 panbasos y 24 conchas.", "items_json": '{"bolillo":60,"telera":36,"panbasos":30,"concha":24}', "sort_order": 2},
    {"slug": "dessert-tray", "name_en": "Dessert tray preview", "name_es": "Charola de postres", "description_en": "Slices and custards for a small gathering.", "description_es": "Rebanadas y flanes para una reunión pequeña.", "items_json": '{"tres-leches-rebanada":6,"flan-individual":4,"chocoflan-individual":4,"tarta-fruta":4}', "sort_order": 3},
]

PROMOTIONS: list[dict[str, Any]] = [
    {"title": "Morning concha box", "code": "CONCHA10", "discount_type": "percent", "discount_value": 10, "min_subtotal": 12, "applies_to_role": "all", "category_key": "fluffy", "starts_on": TODAY.isoformat(), "ends_on": (TODAY + timedelta(days=21)).isoformat(), "is_active": 1, "max_redemptions": 150, "per_customer_limit": 2, "auto_apply": 0, "notes": "Temporary family box incentive."},
    {"title": "Approved shop bulk credit", "code": "PANMAYOR", "discount_type": "percent", "discount_value": 8, "min_subtotal": 75, "applies_to_role": "premium", "category_key": "all", "starts_on": TODAY.isoformat(), "ends_on": (TODAY + timedelta(days=45)).isoformat(), "is_active": 1, "max_redemptions": 200, "per_customer_limit": 8, "auto_apply": 1, "notes": "Automatic promo for approved premium buyers."},
    {"title": "Cake deposit thank you", "code": "CAKE5", "discount_type": "fixed", "discount_value": 5, "min_subtotal": 45, "applies_to_role": "all", "category_key": "cakes", "starts_on": TODAY.isoformat(), "ends_on": (TODAY + timedelta(days=30)).isoformat(), "is_active": 1, "max_redemptions": 75, "per_customer_limit": 1, "auto_apply": 0, "notes": "Encourage advance cake scheduling."},
]

PARTNERS: list[dict[str, Any]] = [
    {"name": "Demo Taquería Account", "category": "Restaurant", "city": "Morristown", "website": "", "contact_name": "Manager", "contact_email": "", "phone": "", "story": "Example wholesale profile for shops that buy bolillos, teleras, and pan dulce. Replace with a real approved business before publishing.", "highlight": "Bulk bolillo and pastry program", "public_visible": 1, "has_consent": 0, "monthly_volume_estimate": 420, "is_demo": 1},
    {"name": "Demo Mercado Account", "category": "Market", "city": "Hamblen County", "website": "", "contact_name": "Owner", "contact_email": "", "phone": "", "story": "Example partner card for a market countertop pan dulce display. Publish only after written consent.", "highlight": "Countertop pan dulce display", "public_visible": 1, "has_consent": 0, "monthly_volume_estimate": 280, "is_demo": 1},
    {"name": "Demo Café Account", "category": "Cafe", "city": "East Tennessee", "website": "", "contact_name": "Buyer", "contact_email": "", "phone": "", "story": "Example café buyer profile for morning pastry boxes, custards, and slices.", "highlight": "Morning pastry subscription", "public_visible": 1, "has_consent": 0, "monthly_volume_estimate": 180, "is_demo": 1},
]

EVENTS: list[dict[str, Any]] = [
    {"title": "Día de los Muertos", "event_date": f"{TODAY.year}-11-02", "start_date": f"{TODAY.year}-10-15", "end_date": f"{TODAY.year}-11-02", "focus_categories": "seasonal, oaxacan, desserts", "focus_products": "pan-muerto-azucar, pan-muerto-rosa, pan-muerto-yema-carita, pan-de-yema", "demand_multiplier": 2.8, "prep_notes": "Prepare colored sugar, face decorations, pan de yema dough schedule, bags, labels, and altar bread signage.", "marketing_notes": "Open bilingual preorder form by early October and promote family altar bundles.", "labor_notes": "Add decorator and front counter coverage during final week."},
    {"title": "Día de Reyes", "event_date": f"{TODAY.year + 1}-01-06", "start_date": f"{TODAY.year + 1}-01-02", "end_date": f"{TODAY.year + 1}-01-06", "focus_categories": "seasonal, oaxacan", "focus_products": "rosca-reyes, pan-de-yema", "demand_multiplier": 3.4, "prep_notes": "Forecast rosca sizes, hidden figurines, candied citrus, packaging, and pickup lanes.", "marketing_notes": "Launch rosca preorder landing section right after Christmas.", "labor_notes": "Schedule early-morning shaping and dedicated pickup counter."},
    {"title": "Mother’s Day cakes", "event_date": f"{TODAY.year + 1}-05-10", "start_date": f"{TODAY.year + 1}-05-01", "end_date": f"{TODAY.year + 1}-05-10", "focus_categories": "cakes, desserts", "focus_products": "pastel-cuarto, pastel-medio, mini-cake-tres-leches, tarta-fruta", "demand_multiplier": 2.2, "prep_notes": "Reserve cake boards, fruit, whipped topping, and decorator capacity.", "marketing_notes": "Promote cake deposits, pickup windows, and bilingual consultation.", "labor_notes": "Separate simple cake production from custom decoration."},
    {"title": "Graduation and quinceañera season", "event_date": f"{TODAY.year}-06-15", "start_date": f"{TODAY.year}-05-20", "end_date": f"{TODAY.year}-06-30", "focus_categories": "cakes, desserts", "focus_products": "pastel-plancha, pastel-medio, pastel-decorado, chocoflan-10", "demand_multiplier": 1.9, "prep_notes": "Track custom cake requests, flavor choices, inscriptions, and decorator capacity.", "marketing_notes": "Create party tray and cake inquiry content.", "labor_notes": "Cap decorated cake slots by decorator availability."},
    {"title": "Weekend breakfast rush", "event_date": f"{TODAY.year}-12-31", "start_date": f"{TODAY.year}-01-01", "end_date": f"{TODAY.year}-12-31", "focus_categories": "savory, fluffy, donuts_churros", "focus_products": "bolillo, telera, panbasos, concha, dona-azucar, churro-simple", "demand_multiplier": 1.35, "prep_notes": "Friday through Sunday need more front case replenishment and checkout prep.", "marketing_notes": "Push morning packs, coffee pairings, and fast pickup queues.", "labor_notes": "Add counter help before 10 AM on weekends."},
]
