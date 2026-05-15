---
language:
- fr
license: cc-by-4.0
tags:
- employment
- job-posting
- nouvelle-calédonie
- opt-nc
- embeddings
- sentence-transformers
size_categories:
- n<1K
task_categories:
- sentence-similarity
- text-retrieval
pretty_name: "AVPS OPT-NC - Avis de Vacances de Poste"
---

# 📋 AVPS OPT-NC - Avis de Vacances de Poste

Dataset des **Avis de Vacances de Poste** de l'**Office des Postes et Télécommunications de Nouvelle-Calédonie** (OPT-NC), enrichi avec embeddings sémantiques.

🔗 **Site web :** [https://opt-nc.github.io/avps/](https://opt-nc.github.io/avps/)  
📊 **Source :** [data.gouv.nc](https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc/)  
💻 **Dépôt GitHub :** [opt-nc/avps](https://github.com/opt-nc/avps)

---

## 📦 Contenu du Dataset

### Fichiers disponibles

| Fichier | Description | Format |
|---------|-------------|--------|
| `avp_opt_with_embeddings.parquet` | **Dataset principal** avec embeddings BAAI/bge-m3 (dim: 1024) | Parquet |
| `avp_opt_enrichi.csv` | CSV enrichi avec données calculées (ville, direction, service) | CSV |
| `avp_opt_embeddings.jsonl` | Format JSONL avec texte structuré et métadonnées | JSONL |

### Structure des données

**Colonnes principales :**
- `id` : Numéro AVP (ex: "26-0672")
- `text` : Texte structuré pour embeddings (titre + missions + compétences)
- `embedding` : Vecteur d'embedding (float32[1024]) généré par BAAI/bge-m3
- `titre` : Intitulé du poste
- `corps_grade` : Corps ou grade du poste
- `direction_interne` : Direction OPT-NC (libellé complet)
- `direction_interne_acronyme` : Acronyme (DT, DPSP, DSI, etc.)
- `service` : Service interne (si applicable)
- `ville` : Ville normalisée (Nouméa, Koné, etc.)
- `lieu_travail` : Adresse complète du lieu de travail
- `date_cloture` : Date limite de candidature
- `disponible_immediatement` : Boolean - poste disponible immédiatement
- `url` : Lien vers la page web de l'offre
- `url_pdf` : Lien vers le PDF original

---

## 🚀 Utilisation

### Charger le dataset avec embeddings

```python
from datasets import load_dataset
import pandas as pd

# Charger le dataset
dataset = load_dataset("opt-nc/avps", data_files="avp_opt_with_embeddings.parquet")
df = dataset['train'].to_pandas()

# Accéder aux embeddings
embeddings = df['embedding'].tolist()
print(f"Dimension des embeddings : {len(embeddings[0])}")
```

### Recherche sémantique

```python
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Charger le modèle
model = SentenceTransformer('BAAI/bge-m3')

# Requête utilisateur
query = "Poste de directeur avec compétences en marketing et management"
query_embedding = model.encode([query], normalize_embeddings=True)[0]

# Calculer similarités
embeddings_matrix = np.array(df['embedding'].tolist())
similarities = cosine_similarity([query_embedding], embeddings_matrix)[0]

# Top 5 résultats
top_indices = similarities.argsort()[-5:][::-1]
for idx in top_indices:
    print(f"{df.iloc[idx]['titre']} (score: {similarities[idx]:.3f})")
    print(f"  Direction: {df.iloc[idx]['direction_interne']}")
    print(f"  Ville: {df.iloc[idx]['ville']}")
    print(f"  URL: {df.iloc[idx]['url']}\n")
```

### Analyse exploratoire

```python
# Statistiques par direction
print(df['direction_interne'].value_counts())

# Postes par ville
print(df['ville'].value_counts())

# Postes disponibles immédiatement
print(f"Postes immédiats : {df['disponible_immediatement'].sum()}")
```

---

## 🤖 Modèle d'Embeddings

**Modèle :** [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)  
**Dimension :** 1024  
**Normalisation :** Oui (cosine similarity ready)  
**Langue :** Multilingue (optimisé français)  

### Pourquoi bge-m3 ?
- ✅ SOTA pour le retrieval multilingue
- ✅ Excellent sur le français
- ✅ Performances supérieures aux alternatives (e5, mpnet)
- ✅ Normalisé pour similarity search

---

## 📊 Statistiques

- **Nombre d'offres :** ~30 (mis à jour quotidiennement)
- **Période :** Offres en cours de publication
- **Fréquence de mise à jour :** Quotidienne via GitHub Actions
- **Couverture :** Tous les postes OPT-NC publiés sur data.gouv.nc

---

## 🔄 Pipeline de Traitement

1. **Extraction** depuis data.gouv.nc (format Parquet)
2. **Conversion PDF → Markdown** via marker-pdf
3. **Enrichissement** : normalisation ville, extraction direction/service
4. **Structuration** : extraction sections clés (missions, compétences, activités)
5. **Génération embeddings** avec BAAI/bge-m3
6. **Export** CSV, JSONL, Parquet avec embeddings
7. **Publication** automatique sur HuggingFace

---

## 📜 Licence

**CC-BY-4.0** - Creative Commons Attribution 4.0 International

### Attribution requise :
```
© Office des Postes et Télécommunications de Nouvelle-Calédonie (OPT-NC)
Source : data.gouv.nc
Dataset enrichi disponible sous CC-BY-4.0
```

---

## 🤝 Contribution

Ce dataset est généré automatiquement. Pour signaler une erreur ou suggérer une amélioration :
- **GitHub Issues :** [opt-nc/avps/issues](https://github.com/opt-nc/avps/issues)
- **Contact :** via le dépôt GitHub

---

## 🔗 Liens Utiles

- 🌐 **Site web des AVPS :** [https://opt-nc.github.io/avps/](https://opt-nc.github.io/avps/)
- 💾 **Source originale :** [data.gouv.nc - AVP](https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc/)
- 💻 **Code source :** [opt-nc/avps sur GitHub](https://github.com/opt-nc/avps)
- 🏢 **OPT-NC :** [www.opt.nc](https://www.opt.nc)

---

## 📅 Dernière mise à jour

Mis à jour automatiquement quotidiennement via GitHub Actions.

---

**Tags:** #emploi #job-search #nouvelle-caledonie #opt-nc #embeddings #semantic-search #french #retrieval
