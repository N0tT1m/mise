-- Mise :: seed data
--
-- Only two things are seeded, and both are facts rather than content:
-- unit conversions, and the staple ingredients. Everything else in the
-- vocabulary is derived from the corpus by the pipeline. No sample recipes.

-- ------------------------------------------------------------------- units
-- volume -> millilitres, mass -> grams, count -> 1. US customary.

INSERT INTO units (name, kind, to_base) VALUES
    ('teaspoon',    'volume', 4.92892),
    ('tablespoon',  'volume', 14.7868),
    ('fluid ounce', 'volume', 29.5735),
    ('cup',         'volume', 236.588),
    ('pint',        'volume', 473.176),
    ('quart',       'volume', 946.353),
    ('gallon',      'volume', 3785.41),
    ('millilitre',  'volume', 1),
    ('litre',       'volume', 1000),
    ('gram',        'mass',   1),
    ('kilogram',    'mass',   1000),
    ('ounce',       'mass',   28.3495),
    ('pound',       'mass',   453.592),
    ('count',       'count',  1)
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------------ staples
--
-- Staples are excluded from recipes.required_ingredient_ids, so they never
-- appear as "missing". Without them almost nothing matches and every result
-- reads "you are missing: salt".
--
-- Kept deliberately short. Over-marking staples makes matches falsely
-- optimistic — the failure is quieter and worse than under-marking. Flour and
-- sugar are the usual next candidates; add them only if you truly always have
-- them, and let the user un-staple anything they have actually run out of.

INSERT INTO ingredients (canonical_name, display_name, category, is_staple) VALUES
    ('water',              'water',         'liquid',   true),
    ('salt',               'salt',          'seasoning', true),
    ('pepper.black',       'black pepper',  'seasoning', true),
    ('oil.cooking',        'cooking oil',   'fat',      true)
ON CONFLICT (canonical_name) DO NOTHING;

-- Aliases the extractor will hit constantly for the staples above. The rest of
-- the alias table is populated by the resolve stage.

INSERT INTO ingredient_aliases (ingredient_id, alias, origin)
SELECT i.id, a.alias, 'human'
FROM ingredients i
JOIN (VALUES
    ('salt',         'kosher salt'),
    ('salt',         'sea salt'),
    ('salt',         'table salt'),
    ('salt',         'fine sea salt'),
    ('pepper.black', 'freshly ground black pepper'),
    ('pepper.black', 'ground black pepper'),
    ('pepper.black', 'black peppercorns'),
    ('oil.cooking',  'vegetable oil'),
    ('oil.cooking',  'sunflower oil'),
    ('oil.cooking',  'canola oil'),
    ('oil.cooking',  'neutral oil'),
    ('water',        'cold water'),
    ('water',        'warm water'),
    ('water',        'hot water')
) AS a(canonical, alias) ON a.canonical = i.canonical_name
ON CONFLICT (alias) DO NOTHING;
