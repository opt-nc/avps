# avps

[![Daily Update](https://github.com/opt-nc/avps/actions/workflows/daily_update.yml/badge.svg)](https://github.com/opt-nc/avps/actions/workflows/daily_update.yml)
[![Publish to GitHub Pages](https://github.com/opt-nc/avps/actions/workflows/publish-pages.yml/badge.svg)](https://github.com/opt-nc/avps/actions/workflows/publish-pages.yml)

AVPS de l'OPT-NC issus de data.gouv.nc

## 📚 Documentation

Les avis de vacances de poste sont automatiquement publiés sur GitHub Pages :

**🔗 [Consulter les AVPS](https://opt-nc.github.io/avps/)**

## 🔄 Mise à jour automatique

Les données sont mises à jour quotidiennement via GitHub Actions :
- Récupération automatique des données depuis data.gouv.nc
- Génération des fichiers Markdown avec extraction des informations
- Création d'une Pull Request automatique
- Merge et tagging automatique (format: `YYYY-MM-DD` avec incrémentation si nécessaire)
- Publication automatique sur GitHub Pages via Zensical

## 📊 Données

Les données sont stockées dans le dossier `data/` :
- `avp_opt.csv` : fichier CSV avec tous les AVPS
- `*.md` : fichiers Markdown individuels pour chaque AVP avec les images extraites
