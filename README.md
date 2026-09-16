# Avenida Prestige Fruugo Feed

This repository generates the Avenida Prestige Fruugo product feed every day.

The private supplier feed URL must be stored in the GitHub Actions secret
`SUPPLIER_FEED_URL`. It must never be committed to the repository.

The public Fruugo feed is generated as `docs/fruugo.csv`.
