import pandas as pd
import requests
import io
import json
import os
import shutil
from glob import glob

# Configuration CPU pour marker
os.environ["TORCH_DEVICE"] = "cpu"
os.environ["INFERENCE_DEVICE"] = "cpu"

def extract_pdf_url(val):
    """Extrait l'URL du PDF depuis l'objet JSON présent dans la colonne url_pdf."""
    if not val:
        return None
    try:
        if isinstance(val, dict):
            return f"https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc/files/{val.get('id')}/download/"
        
        data = json.loads(val)
        if isinstance(data, list):
            data = data[0]
        
        file_id = data.get('id')
        if file_id:
            return f"https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc/files/{file_id}/download/"
    except Exception:
        pass
    return val

def process_pdfs_to_markdown(df, data_dir="data"):
    """Télécharge les PDFs et les convertit en Markdown avec marker-pdf."""
    print("Début de la conversion des PDFs en Markdown avec marker-pdf (Haute Qualité)...")
    
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import save_output
        
        print("  Chargement des modèles d'IA (cela peut prendre quelques minutes au premier lancement)...")
        # marker 1.10+ utilise create_model_dict
        model_dict = create_model_dict()
        # On initialise le convertisseur PDF avec des options pour CPU
        converter = PdfConverter(
            artifact_dict=model_dict,
            config={
                "disable_ocr": True, # Accélère grandement sur CPU pour les PDF natifs
                "disable_image_extraction": True # Gagne du temps sur CPU
            }
        )
        
    except Exception as e:
        print(f"  Erreur lors de l'initialisation de marker: {e}")
        return

    current_numbers = set()
    os.makedirs(data_dir, exist_ok=True)
    
    for _, row in df.iterrows():
        numero = str(row['numero']).replace("/", "_")
        url_pdf = row['url_pdf']
        final_md_path = os.path.join(data_dir, f"{numero}.md")
        current_numbers.add(f"{numero}.md")
        
        if not url_pdf or not url_pdf.startswith("http"):
            continue
            
        try:
            print(f"  Traitement de {numero}...")
            # 1. Téléchargement du PDF
            pdf_response = requests.get(url_pdf)
            pdf_response.raise_for_status()
            
            # Sauvegarde temporaire pour le convertisseur
            temp_pdf = f"temp_{numero}.pdf"
            with open(temp_pdf, "wb") as f:
                f.write(pdf_response.content)
            
            # 2. Conversion avec marker
            rendered = converter(temp_pdf)
            
            # 3. Sauvegarde du Markdown
            with open(final_md_path, "w", encoding="utf-8") as f:
                f.write(rendered.markdown)
                
            # Nettoyage
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            print(f"    Généré avec succès : {final_md_path}")
                
        except Exception as e:
            print(f"    Erreur pour {numero}: {e}")
            if 'temp_pdf' in locals() and os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            
    # Nettoyage des anciens fichiers Markdown
    print("Nettoyage des anciens fichiers Markdown...")
    all_md_files = glob(os.path.join(data_dir, "*.md"))
    for md_file in all_md_files:
        filename = os.path.basename(md_file)
        if filename not in current_numbers:
            print(f"  Suppression du fichier obsolète : {filename}")
            os.remove(md_file)

def main():
    url = "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/avis-de-vacances-de-poste-avp-drhfpnc/exports/parquet?lang=fr&timezone=Pacific%2FNoumea"
    
    print(f"Téléchargement des données depuis {url}...")
    response = requests.get(url)
    response.raise_for_status()
    
    df = pd.read_parquet(io.BytesIO(response.content))
    
    # Filtrage sur "OPT" et url_pdf non nul
    col_direction = 'acronymedirection'
    col_pdf = 'url_pdf'
    
    mask = (df[col_direction].astype(str).str.upper() == "OPT") & (df[col_pdf].notna())
    df_opt = df[mask].copy()
    
    # Traitement de la colonne url_pdf
    print("Extraction des URLs de téléchargement PDF...")
    df_opt['url_pdf'] = df_opt['url_pdf'].apply(extract_pdf_url)
    
    # Renommage des colonnes (Dictionnaire complet)
    renames = {
        'libelleposte': 'libelle_poste',
        'libelleemploirome': 'libelle_emploi_rome',
        'codeemploirome': 'code_emploi_rome',
        'datemiseenligne': 'date_mis_en_ligne',
        'libellecollectivite': 'libelle_collectivite',
        'libellecorpsgrade': 'libelle_corps_grade',
        'libellecorpsgrade2': 'libelle_corps_grade_2',
        'libelledomaine': 'libelle_domaine',
        'libelledomaine2': 'libelle_domaine_2',
        'dureeresidenceexigee': 'duree_residence_exigee',
        'dateapourvoir': 'date_a_pourvoir',
        'libelleposteapourvoir': 'date_a_pourvoir_libelle',
        'libelledirection': 'direction_libelle',
        'acronymedirection': 'direction_acronyme',
        'libelleservice': 'service_libelle',
        'lieutravail': 'lieu_travail',
        'datecreation': 'date_creation',
        'datecloture': 'date_cloture',
        'emploiresp': 'emploi_resp',
        'activitesprincipales': 'activites_principales',
        'activitessecondaires': 'activites_secondaires',
        'conditionsparticulieres': 'conditions_particulieres',
        'savoirfaire': 'savoir_faire',
        'commentairerepublication': 'commentaire_republication',
        'contacttelephone': 'contact_telephone',
        'contactemail': 'contact_email',
        'contactsecondaire': 'contact_secondaire',
        'contactsecondairetelephone': 'contact_secondaire_telephone',
        'contactsecondaireemail': 'contact_secondaire_email',
        'nbposteapourvoir': 'nb_postes_a_pourvoir',
        'apourvoirautre': 'a_pourvoir_autre',
        'collectivitenomrh': 'collectivite_nom_rh',
        'collectiviteadressedepot': 'collectivite_adresse_depot',
        'collectiviteadressepostale': 'collectivite_adresse_postale',
        'collectiviteemail': 'collectivite_email'
    }
    
    df_opt.rename(columns={k: v for k, v in renames.items() if k in df_opt.columns}, inplace=True)
    
    # Transformations spécifiques
    if 'libelle_emploi_rome' in df_opt.columns:
        df_opt['libelle_emploi_rome'] = df_opt['libelle_emploi_rome'].replace("Hors rome", "HORS_ROME")
    if 'code_emploi_rome' in df_opt.columns:
        df_opt['code_emploi_rome'] = df_opt['code_emploi_rome'].replace("N0000", "")
    if 'date_a_pourvoir_libelle' in df_opt.columns:
        df_opt['date_a_pourvoir_libelle'] = df_opt['date_a_pourvoir_libelle'].replace("immédiatement", "IMMEDIATEMENT")
    if 'emploi_resp' in df_opt.columns:
        df_opt['emploi_resp'] = df_opt['emploi_resp'].replace("Inspecteur", "")
    
    # Suppression de colonnes inutiles
    cols_to_drop = ['collectivitefax', 'piedpageavp']
    df_opt.drop(columns=[c for c in cols_to_drop if c in df_opt.columns], inplace=True)
    
    # Processus de conversion Markdown de haute qualité
    process_pdfs_to_markdown(df_opt)
    
    # Sauvegarde du CSV
    output_path = "data/avp_opt.csv"
    df_opt.to_csv(output_path, index=False, encoding='utf-8')
    
    print(f"Terminé. {len(df_opt)} lignes enregistrées dans {output_path}.")
    
    # Génération de l'index.md
    generate_index_md(df_opt)

def generate_index_md(df):
    """Génère un fichier index.md avec la liste des AVPs."""
    print("Génération de index.md...")
    
    index_content = """# AVPS OPT-NC

Bienvenue sur le site des **Avis de Vacances de Poste** de l'Office des Postes et Télécommunications de Nouvelle-Calédonie.

## 📋 Postes disponibles

Cette page recense les avis de vacances de poste publiés par l'OPT-NC, issus de [data.gouv.nc](https://data.gouv.nc).

### Liste des AVP disponibles

"""
    
    # Trier par numéro de référence décroissant
    df_sorted = df.sort_values('numero', ascending=False)
    
    for _, row in df_sorted.iterrows():
        numero = row.get('numero', '')
        libelle = row.get('libelle_poste', 'Poste disponible')
        
        # Limiter la longueur du libellé
        if len(libelle) > 80:
            libelle = libelle[:77] + "..."
        
        index_content += f"* [{numero} - {libelle}]({numero}/)\n"
    
    index_content += """
## 🔄 Mise à jour

Les données sont mises à jour quotidiennement de manière automatique.

---

*Données extraites de [data.gouv.nc](https://data.gouv.nc)*
"""
    
    # Écrire le fichier
    with open("data/index.md", "w", encoding="utf-8") as f:
        f.write(index_content)
    
    print(f"✅ Fichier index.md généré avec {len(df)} AVPs")

if __name__ == "__main__":
    main()
