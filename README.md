# ÉconoPulse V2.2 — Analyse

Version complète avec collecte automatique et première analyse d'impact.

## Structure
- index.html
- style.css
- app.js
- manifest.json
- sources.json
- scripts.py
- data/news.json
- .github/workflows/update-news.yml

## Déploiement
Remplace les fichiers du dépôt par cette version en conservant les chemins.
Puis : Actions → `Update ÉconoPulse news` → `Run workflow`.

Le moteur d'analyse ajoute un score de -100 à +100, une direction, une intensité, une confiance, une explication et les entreprises potentiellement favorisées/exposées.

Cette analyse est indicative et ne constitue pas une recommandation financière.
