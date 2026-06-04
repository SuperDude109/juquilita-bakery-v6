# Research notes

The v2 catalog and workflows were derived from the supplied Juquilita Bakery source text and cross-checked against the public Juquilita website.

## Company identity

- Juquilita Bakery is described as established in 2007 and focused on traditional Mexican bread with an authentic Oaxacan style.
- The source text and public site name Oaxacan breads including pan amarillo, pan serrano, pan de yema, semitas, and seasonal breads such as Pan de Muerto and Rosca de Reyes.
- Public contact data seeded in settings: 325 South Cumberland Street, Morristown, TN 37813, phone `(423) 307-8244`, text `(423) 307-9003`, and `Juquilitabakery@outlook.com`.

## Pricing basis

Seeded prices use the supplied menu text when exact prices were available:

- Bolillo, Telera, Panbasos: $0.80
- Bolinachos: $2.25
- Pan relleno: $2.75
- Chorizo stuffed bread: $3.99
- Galletas and polvorones group: $0.90
- Spongy/fluffy bread group: $0.90
- Shortening bread group: $0.90
- Madalenas, bisquit, marranito group: $0.90
- Mini bread: $0.65
- Puff pastry with no filling and related simple pastries: $1.00
- Donuts: $1.15
- Filled empanadas: $1.15
- Chocolate or filled donuts: $1.25
- Other dessert style options: $1.25
- Bread pudding: $1.89
- Filled puff pastries: $1.99
- Filled churros: $2.50
- Pingüinos, tomatillos, mechudos, niños envueltos: $2.75
- Decorated mini cakes and mil hojas: $3.50
- Fruit tarts: $3.99
- Tres leches slice: $3.25
- Flan: $3.49
- Chocoflan: $3.89
- 1/4 sheet cake: $45
- 1/2 sheet cake: $70
- Full sheet cake: $100
- Mini cakes: $21.99
- Flan tray: $34.99
- Chocoflan tray: $34.99

When the source grouped multiple named breads under one price, v2 creates individual product records with the group price and stores the pricing basis as `Official menu group price applied to named bread variants in that group.`

## Hours

The supplied source text includes winter-style hours. The public site footer also currently shows a more specific weekly schedule. V2 seeds the official footer-style schedule as editable business hours and keeps the system configurable in the admin console.

## Partner showcase

No public source proved that specific real businesses buy wholesale from Juquilita. V2 keeps demo partner cards marked as demo and prevents public partner publishing unless `has_consent` is checked.
