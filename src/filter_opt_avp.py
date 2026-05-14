import pandas as pd
import requests
import io
import json
import os
import re
import shutil
import yaml
from glob import glob

# Configuration CPU pour marker
os.environ["TORCH_DEVICE"] = "cpu"
os.environ["INFERENCE_DEVICE"] = "cpu"

DIRECTIONS_OPT = {
    "DDI":  "Direction de la Distribution",
    "DT":   "Direction des Télécommunications",
    "DMI":  "Direction des Moyens",
    "DPO":  "Direction du Postal",
    "DSB":  "Direction des Services Bancaires",
    "DFI":  "Direction des Finances",
    "DSI":  "Direction des Systèmes d'Information",
    "AC":   "Agent Comptable",
    "DG":   "Direction Générale",
    "SG":   "Secrétariat Général",
    "DPSP": "Direction de la Poste et des Services de Proximité",
}

# Charger le référentiel OPT
def load_referentiel():
    """Charge le référentiel des directions et services depuis le YAML."""
    ref_path = "data/opt_referentiel.yml"
    if os.path.exists(ref_path):
        with open(ref_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {"directions": {}, "services": {}}

def extract_direction_from_content(content):
    """Extrait l'acronyme de sous-direction depuis le premier titre du markdown."""
    match = re.search(r'^#{1,3}\s+\*{0,2}([A-Z]{2,6})\s*[–-]', content, re.MULTILINE)
    if match:
        acronyme = match.group(1)
        if acronyme in DIRECTIONS_OPT:
            return acronyme, DIRECTIONS_OPT[acronyme]
    return None, None

def extract_service_from_libelle(libelle_poste, referentiel):
    """Extrait l'acronyme de service depuis le libellé du poste."""
    services = referentiel.get("services", {})
    # Chercher les acronymes de services dans le libellé
    for acronyme, info in services.items():
        if re.search(r'\b' + re.escape(acronyme) + r'\b', libelle_poste):
            return acronyme, info.get("nom", "")
    return None, None

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
    
    # Charger le référentiel
    referentiel = load_referentiel()
    
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
                "disable_image_extraction": False # Activer l'extraction d'images
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
            
            # 3. Sauvegarde du Markdown et des images
            # save_output attend: (rendered, output_dir, fname_base)
            output_files = save_output(rendered, output_dir=data_dir, fname_base=numero)
            
            # 4. Ajouter le front matter, un titre H1 et un lien vers le PDF original
            with open(final_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Récupérer les métadonnées depuis le CSV
            libelle_poste = row.get('libelle_poste', f'Poste {numero}')
            corps_grade    = row.get('libelle_corps_grade', '')
            direction      = row.get('direction_libelle', '')
            date_cloture   = str(row.get('date_cloture', ''))[:10]
            disponibilite  = row.get('date_a_pourvoir_libelle', '')
            
            # Supprimer les références aux images de type _page_*_Picture_*.jpeg (logos OPT)
            content = re.sub(r'!\[\]\(_page_\d+_Picture_\d+\.jpeg\)\s*\n?', '', content)
            
            # Supprimer les ":" en fin de ligne dans les titres en gras
            # Ex: "**Emploi RESPNC :**" devient "**Emploi RESPNC**"
            content = re.sub(r'\*\*([^*]+) :\*\*', r'**\1**', content)
            
            # Corriger les doubles tirets dans les listes (- -Item → - Item)
            content = re.sub(r'^([ \t]*)-\s+-', r'\1-', content, flags=re.MULTILINE)
            
            # Extraire l'acronyme de sous-direction depuis le contenu du MD
            acronyme_dir, libelle_dir = extract_direction_from_content(content)
            
            # Extraire le service depuis le libellé du poste
            acronyme_service, libelle_service = extract_service_from_libelle(libelle_poste, referentiel)
            
            # Construire le front matter YAML
            front_matter = '---\n'
            front_matter += f'title: "{libelle_poste.replace(chr(34), chr(39))}"\n'
            front_matter += f'numero: "{numero}"\n'
            if corps_grade:
                front_matter += f'corps_grade: "{corps_grade}"\n'
            if direction:
                front_matter += f'direction: "{direction}"\n'
            if acronyme_dir:
                front_matter += f'direction_interne_acronyme: "{acronyme_dir}"\n'
                front_matter += f'direction_interne: "{libelle_dir}"\n'
            if acronyme_service:
                front_matter += f'service_acronyme: "{acronyme_service}"\n'
                front_matter += f'service: "{libelle_service}"\n'
            if date_cloture and date_cloture != 'nan':
                front_matter += f'date_cloture: "{date_cloture}"\n'
            if disponibilite:
                front_matter += f'disponibilite: "{disponibilite}"\n'
                front_matter += f'disponible_immediatement: {"true" if disponibilite == "IMMEDIATEMENT" else "false"}\n'
            if url_pdf:
                front_matter += f'url_pdf: "{url_pdf}"\n'
            front_matter += '---\n\n'
            
            # Ajouter le lien PDF et le titre H1
            pdf_header = f'<div style="text-align: right; margin-bottom: 1em;"><a href="{url_pdf}" target="_blank" style="display: inline-block; padding: 8px 16px; background-color: #3f51b5; color: white; text-decoration: none; border-radius: 4px;">📄 Télécharger le PDF original</a></div>\n\n'
            page_title = f'# {libelle_poste}\n\n'
            content_with_header = front_matter + pdf_header + page_title + content
            
            with open(final_md_path, 'w', encoding='utf-8') as f:
                f.write(content_with_header)
            
            # Supprimer les fichiers images de logos extraits
            for img_file in glob(os.path.join(data_dir, f"{numero}_page_*_Picture_*.jpeg")):
                os.remove(img_file)
                print(f"    Image logo supprimée : {os.path.basename(img_file)}")
            
            # Nettoyage
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            print(f"    Généré avec succès : {final_md_path}")
            if output_files and output_files.get('images'):
                print(f"    Images extraites : {len(output_files['images'])}")
                
        except Exception as e:
            print(f"    Erreur pour {numero}: {e}")
            if 'temp_pdf' in locals() and os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            
    # Nettoyage des anciens fichiers Markdown et JSON
    print("Nettoyage des anciens fichiers Markdown et JSON...")
    all_md_files = glob(os.path.join(data_dir, "*.md"))
    for md_file in all_md_files:
        filename = os.path.basename(md_file)
        if filename not in current_numbers and filename != "index.md":
            print(f"  Suppression du fichier obsolète : {filename}")
            os.remove(md_file)
    
    # Nettoyage des fichiers JSON de métadonnées générés par marker
    all_json_files = glob(os.path.join(data_dir, "*_meta.json"))
    for json_file in all_json_files:
        os.remove(json_file)
        print(f"  Suppression des métadonnées : {os.path.basename(json_file)}")
    
    # Nettoyage de toutes les images de logos (_page_*_Picture_*.jpeg)
    print("Nettoyage des images de logos...")
    all_logo_images = glob(os.path.join(data_dir, "_page_*_Picture_*.jpeg"))
    for img_file in all_logo_images:
        os.remove(img_file)
        print(f"  Image logo supprimée : {os.path.basename(img_file)}")

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
        'numeroavp': 'numero',
        'datepublicationavp': 'date_publication_avp',
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
        df_opt['date_a_pourvoir_libelle'] = df_opt['date_a_pourvoir_libelle'].replace({
            "immédiatement": "IMMEDIATEMENT",
            "susceptible d'être vacant": "SUSCEPTIBLE_VACANT",
            "susceptible d'être vacant le": "SUSCEPTIBLE_VACANT",
            "vacant à partir du": "SUSCEPTIBLE_VACANT",
            "date": "A_DATE",
            "autre": "AUTRE",
        })
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
    
    # Génération du catalogue consolidé
    generate_consolidated_catalog(data_dir="data", output_dir="exports")
    
    # Génération du fichier de build info
    generate_build_info()

def generate_build_info():
    """Génère un fichier avec les infos de build (date et commit)."""
    import subprocess
    from datetime import datetime
    import pytz
    
    # Obtenir le commit SHA
    try:
        commit_sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], 
                                            stderr=subprocess.DEVNULL).decode().strip()
    except:
        commit_sha = "unknown"
    
    # Date actuelle en timezone Nouméa
    noumea_tz = pytz.timezone('Pacific/Noumea')
    now = datetime.now(noumea_tz)
    date_str = now.strftime("%d/%m/%Y à %H:%M")
    
    # Créer le fichier build_info.txt
    with open("data/build_info.txt", "w", encoding="utf-8") as f:
        f.write(f"{commit_sha}\n")
        f.write(f"{date_str}\n")
    
    print(f"✅ Build info: commit {commit_sha}, date {date_str}")

def generate_index_md(df):
    """Génère un fichier index.md avec la liste des AVPs."""
    print("Génération de index.md...")
    
    # Supprimer le sitemap.xml obsolète s'il existe dans data/
    # Zensical ou le processus de build doit gérer cela proprement
    if os.path.exists("data/sitemap.xml"):
        os.remove("data/sitemap.xml")
        print("🗑️ sitemap.xml obsolète supprimé")
    
    # Fonction helper pour extraire le front matter d'un fichier MD
    def extract_frontmatter(numero):
        """Extrait le front matter YAML d'un fichier markdown."""
        md_path = os.path.join("data", f"{numero}.md")
        if not os.path.exists(md_path):
            return {}
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extraire le front matter entre ---
            import re
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return {}
            
            # Parser le YAML
            import yaml
            frontmatter = yaml.safe_load(match.group(1))
            return frontmatter or {}
        except:
            return {}

    # Calculer les statistiques
    from datetime import datetime
    import pytz
    
    nb_postes = len(df)
    noumea_tz = pytz.timezone('Pacific/Noumea')
    now = datetime.now(noumea_tz)
    date_mise_a_jour = now.strftime("%d/%m/%Y à %Hh%M")
    
    # Section statistiques (uniquement si postes disponibles)
    stats_section = ""
    if nb_postes > 0:
        # Calculer la répartition par corps/grade
        corps_counts = df['libelle_corps_grade'].value_counts()
        
        # Générer le graphique Mermaid (pie chart)
        mermaid_pie = "```mermaid\npie title Répartition des postes par corps/grade\n"
        for corps, count in corps_counts.items():
            if pd.notna(corps):
                corps_label = str(corps).capitalize()
                mermaid_pie += f'    "{corps_label}" : {count}\n'
        mermaid_pie += "```"
        
        stats_section = f"""### 📈 Répartition par corps/grade

{mermaid_pie}
"""
    else:
        stats_section = "!!! info \"Information\"\n    Il n'y a aucun avis de vacance de poste disponible pour le moment."

    index_content = f"""# AVPS OPT-NC

Bienvenue sur le site des **Avis de Vacances de Poste** de l'Office des Postes et Télécommunications de Nouvelle-Calédonie.

## 📊 En bref

- **{nb_postes}** poste{'s' if nb_postes > 1 else ''} disponible{'s' if nb_postes > 1 else ''} actuellement
- 📅 Dernière mise à jour : **{date_mise_a_jour}** (Nouméa)
- 🔄 Prochaine mise à jour : demain à 00h00 (automatique)

{stats_section}

---

## 📋 Postes disponibles
"""

    if nb_postes > 0:
        index_content += """
Cette page recense les avis de vacances de poste publiés par l'OPT-NC, issus du dataset [avis-de-vacances-de-poste-avp-drhfpnc](https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc/information) disponible sur data.gouv.nc.

👉 **Retrouvez également les AVP sur le [site institutionnel OPT-NC](https://office.opt.nc/fr/emploi-et-carriere/postuler-lopt-nc/avp)**

### Liste des AVP disponibles

"""
        # Trier par numéro de référence décroissant
        df_sorted = df.sort_values('numero', ascending=False)
        
        for _, row in df_sorted.iterrows():
            numero = row.get('numero', '')
            libelle = row.get('libelle_poste', 'Poste disponible')
            url_pdf = row.get('url_pdf', '')
            direction_acronyme = row.get('direction_acronyme', '')
            direction_libelle = row.get('direction_libelle', '')
            lieu_travail = row.get('lieu_travail', '')
            date_a_pourvoir_libelle = row.get('date_a_pourvoir_libelle', '')
            date_cloture = row.get('date_cloture', '')
            date_publication = row.get('date_publication_avp', '')
            corps_grade = row.get('libelle_corps_grade', '')
            
            # Extraire les métadonnées du front matter
            frontmatter = extract_frontmatter(numero)
            direction_interne = frontmatter.get('direction_interne')
            direction_interne_acronyme = frontmatter.get('direction_interne_acronyme')
            service = frontmatter.get('service')
            service_acronyme = frontmatter.get('service_acronyme')
            disponibilite = frontmatter.get('disponibilite')
            disponible_immediatement = frontmatter.get('disponible_immediatement', False)
            
            # Limiter la longueur du libellé pour le titre
            libelle_court = libelle
            if len(libelle) > 80:
                libelle_court = libelle[:77] + "..."
            
            # Badge de disponibilité dans le titre
            badge_dispo = ""
            if disponible_immediatement or str(date_a_pourvoir_libelle).upper() == "IMMEDIATEMENT":
                badge_dispo = " 🟢"
            elif disponibilite == "SUSCEPTIBLE_VACANT":
                badge_dispo = " 🟡"
            
            # --- CALCUL DES NOUVEAUX BADGES ---
            badges_info = ""
            now = pd.Timestamp.now()
            
            # Badge NOUVEAU (si publié il y a moins de 3 jours)
            if pd.notna(date_publication):
                try:
                    pub_date = pd.to_datetime(date_publication)
                    if (now - pub_date).days <= 3:
                        badges_info += ' <span class="md-tag md-tag--new">NOUVEAU</span>'
                except:
                    pass
                    
            # Badge COMPTE À REBOURS (jours restants)
            if pd.notna(date_cloture):
                try:
                    cloture_date = pd.to_datetime(date_cloture)
                    jours_restants = (cloture_date - now).days
                    if jours_restants <= 7 and jours_restants >= 0:
                        badges_info += f' <span class="md-tag md-tag--urgent">J-{jours_restants}</span>'
                    elif jours_restants < 0:
                        badges_info += ' <span class="md-tag md-tag--closed">CLOS</span>'
                except:
                    pass
            
            # Créer une carte admonition avec les badges
            index_content += f'\n!!! info "{numero} - {libelle_court}{badge_dispo}{badges_info}"\n'
            
            # Direction interne (prioritaire si disponible)
            if direction_interne and direction_interne_acronyme:
                index_content += f"    **🏢 Direction :** {direction_interne} ({direction_interne_acronyme})  \n"
            elif pd.notna(direction_libelle) and direction_libelle:
                index_content += f"    **🏢 Direction :** {direction_libelle}"
                if pd.notna(direction_acronyme) and direction_acronyme:
                    index_content += f" ({direction_acronyme})"
                index_content += "  \n"
            elif pd.notna(direction_acronyme) and direction_acronyme:
                index_content += f"    **🏢 Direction :** {direction_acronyme}  \n"
            
            # Service (nouvelle donnée du front matter)
            if service and service_acronyme:
                index_content += f"    **🔧 Service :** {service} ({service_acronyme})  \n"
            
            # Lieu
            if pd.notna(lieu_travail) and lieu_travail:
                index_content += f"    **📍 Lieu :** {lieu_travail}  \n"
            
            # Date limite
            if pd.notna(date_cloture) and date_cloture:
                try:
                    date_obj = pd.to_datetime(date_cloture)
                    date_formatee = date_obj.strftime("%d/%m/%Y")
                    index_content += f"    **📅 Date limite :** {date_formatee}  \n"
                except:
                    pass
            
            # Corps/Grade
            if pd.notna(corps_grade) and corps_grade:
                index_content += f"    **💼 Corps :** {corps_grade.capitalize()}  \n"
            
            # Disponibilité
            if disponible_immediatement or str(date_a_pourvoir_libelle).upper() == "IMMEDIATEMENT":
                index_content += f"    **⚡ Disponibilité :** Immédiate  \n"
            elif disponibilite == "SUSCEPTIBLE_VACANT":
                index_content += f"    **🔔 Disponibilité :** Susceptible d'être vacant  \n"
            elif disponibilite == "A_DATE":
                index_content += f"    **📅 Disponibilité :** À date  \n"
            
            # Liens
            index_content += "    \n"
            if url_pdf:
                index_content += f'    [📖 Voir les détails]({numero}/){{ .md-button }} [📄 Télécharger le PDF]({url_pdf}){{ .md-button .md-button--primary target="_blank" }}\n'
            else:
                index_content += f'    [📖 Voir les détails]({numero}/){{ .md-button }}\n'
    
    index_content += """
## 📝 Comment postuler ?

Pour candidater à un poste :

1. **Consultez l'offre** qui vous intéresse ci-dessus
2. **Téléchargez le PDF** pour connaître tous les détails et critères requis
3. **Préparez votre dossier** de candidature selon les modalités indiquées dans l'AVP
4. **Déposez votre candidature** avant la date limite auprès du service RH de l'OPT-NC

💡 **Plus d'informations** : Rendez-vous sur le [site institutionnel OPT-NC](https://office.opt.nc/fr/emploi-et-carriere/postuler-lopt-nc/avp) pour connaître les modalités de candidature et les contacts RH.

---

## 🔄 Mise à jour

Les données sont mises à jour quotidiennement de manière automatique.

---

*Données extraites du dataset [avis-de-vacances-de-poste-avp-drhfpnc](https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc) disponible sur data.gouv.nc*
"""
    
    # Écrire le fichier
    with open("data/index.md", "w", encoding="utf-8") as f:
        f.write(index_content)
    
    # --- GÉNÉRATION DU FLUX RSS ---
    try:
        generate_rss_feed(df)
    except Exception as e:
        print(f"⚠️ Erreur lors de la génération du flux RSS: {e}")
    
    # --- ARCHIVAGE DES ANCIENS AVPS ---
    try:
        archive_old_avps(df)
    except Exception as e:
        print(f"⚠️ Erreur lors de l'archivage : {e}")
    
    print(f"✅ Fichier index.md généré avec {len(df)} AVPs")

def archive_old_avps(current_df, data_dir="data", arch_root="archives"):
    """Archive les AVPs qui ne sont plus dans le flux (texte uniquement)."""
    import os
    import re
    import datetime
    
    today_iso = datetime.datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.datetime.now().strftime("%Y")
    arch_dir = os.path.join(arch_root, current_year)
    
    if not os.path.exists(arch_dir):
        os.makedirs(arch_dir, exist_ok=True)
        
    current_numbers = set(current_df['numero'].astype(str).tolist())
    
    # Lister tous les fichiers MD dans data/ (exclure index.md)
    existing_files = [f for f in os.listdir(data_dir) if f.endswith('.md') and f != 'index.md']
    
    for filename in existing_files:
        numero = filename.replace('.md', '')
        
        if numero not in current_numbers:
            file_path = os.path.join(data_dir, filename)
            arch_path = os.path.join(arch_dir, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # --- NETTOYAGE DU CONTENU ---
            # 1. Supprimer le bouton PDF du début
            content = re.sub(r'<div.*?</div>', '', content, flags=re.DOTALL)
            
            # 2. Supprimer les images Markdown ![]()
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            
            # 3. Essayer de ne garder que le corps du texte (après les métadonnées)
            # On cherche "Activités principales" ou "Missions" ou "Profil"
            body_match = re.search(r'(#+.*?(?:Activités|Missions|Profil|Caractéristiques).*?)$', content, flags=re.DOTALL | re.IGNORECASE)
            if body_match:
                content = body_match.group(1)
            
            # 4. Ajouter le bandeau d'archive
            banner = f"""> [!IMPORTANT]\n> **AVIS ARCHIVÉ** : Ce poste a été retiré du flux officiel le {today_iso}.\n> Les informations ci-dessous sont conservées à titre historique uniquement.\n\n"""
            
            # Sauvegarder dans archives/YYYY/
            with open(arch_path, 'w', encoding='utf-8') as f:
                f.write(banner + content.strip())
            
            # 5. Supprimer le fichier original
            os.remove(file_path)
            print(f"📂 Archivage terminé pour l'AVP {numero} (Année {current_year})")

    # Nettoyage des images orphelines dans data/
    active_md_content = ""
    for filename in os.listdir(data_dir):
        if filename.endswith('.md'):
            try:
                with open(os.path.join(data_dir, filename), 'r', encoding='utf-8') as f:
                    active_md_content += f.read()
            except: pass
    
    for filename in os.listdir(data_dir):
        if filename.endswith(('.jpeg', '.jpg', '.png')):
            if filename not in active_md_content:
                os.remove(os.path.join(data_dir, filename))
                print(f"🗑️ Image orpheline supprimée : {filename}")


def extract_missions_from_md(numero, data_dir="data"):
    """Extrait le paragraphe Missions depuis le fichier markdown de l'AVP."""
    import re
    md_path = os.path.join(data_dir, f"{numero}.md")
    if not os.path.exists(md_path):
        return None
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(
        r'\*\*Missions?\s*:\*\*\s*(.*?)(?=\n\*\*|\n#{1,4}|\Z)',
        content, re.DOTALL | re.IGNORECASE
    )
    if match:
        text = match.group(1).strip()
        text = re.sub(r'\s+', ' ', text)
        return text[:500] + ('…' if len(text) > 500 else '')
    return None


def generate_rss_feed(df):
    """Génère un flux RSS simple pour les AVPs."""
    import datetime
    
    # Charger le référentiel
    referentiel = load_referentiel()
    
    rss = '<?xml version="1.0" encoding="UTF-8" ?>\n'
    rss += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">\n'
    rss += '<channel>\n'
    rss += '  <title>OPT-NC : AVPS en cours</title>\n'
    rss += '  <link>https://opt-nc.github.io/avps/</link>\n'
    rss += '  <description>Avis de vacances de poste en cours et publiés par l\'OPT-NC</description>\n'
    rss += '  <language>fr</language>\n'
    rss += f'  <lastBuildDate>{datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +1100")}</lastBuildDate>\n'
    rss += '  <atom:link href="https://opt-nc.github.io/avps/feed.xml" rel="self" type="application/rss+xml" />\n'
    rss += '  <image>\n'
    rss += '    <url>https://opt-nc.github.io/avps/assets/logo.png</url>\n'
    rss += '    <title>OPT-NC : AVPS en cours</title>\n'
    rss += '    <link>https://opt-nc.github.io/avps/</link>\n'
    rss += '  </image>\n'
    rss += '  <itunes:image href="https://opt-nc.github.io/avps/assets/logo.png" />\n'
    rss += '  <media:thumbnail url="https://opt-nc.github.io/avps/assets/logo.png" />\n'
    
    # Trier par date de mise en ligne décroissante
    df_sorted = df.sort_values('date_mis_en_ligne', ascending=False).head(20)
    
    for _, row in df_sorted.iterrows():
        numero = row.get('numero', '').replace("/", "_")
        libelle = row.get('libelle_emploi_rome', '')
        libelle_poste = row.get('libelle_poste', '')
        direction = row.get('direction_libelle', '')
        corps_grade = row.get('libelle_corps_grade', '')
        date_pub = row.get('date_mis_en_ligne', '')
        date_cloture = row.get('date_cloture', '')
        date_a_pourvoir_libelle = row.get('date_a_pourvoir_libelle', '')
        url_pdf = row.get('url_pdf', '')
        
        # Construire une description enrichie
        description = f'<p><strong>Poste :</strong> {libelle_poste}</p>\n'
        if direction:
            description += f'    <p><strong>Direction :</strong> {direction}</p>\n'
        if corps_grade:
            description += f'    <p><strong>Corps/Grade :</strong> {corps_grade}</p>\n'
        if date_a_pourvoir_libelle:
            description += f'    <p><strong>À pourvoir :</strong> {date_a_pourvoir_libelle}</p>\n'
        if pd.notna(date_cloture):
            try:
                date_cloture_obj = pd.to_datetime(date_cloture)
                date_cloture_fr = date_cloture_obj.strftime("%d/%m/%Y")
                description += f'    <p><strong>Date de clôture :</strong> {date_cloture_fr}</p>\n'
            except:
                pass
        missions = extract_missions_from_md(numero)
        if missions:
            description += f'    <p><strong>Missions :</strong> {missions}</p>\n'
        if url_pdf:
            description += f'    <p><a href="{url_pdf}">📄 Télécharger le PDF</a></p>'
        
        rss += '  <item>\n'
        rss += f'    <title>{numero} - {libelle_poste}</title>\n'
        rss += f'    <link>https://opt-nc.github.io/avps/{numero}/</link>\n'
        rss += f'    <guid isPermaLink="true">https://opt-nc.github.io/avps/{numero}/</guid>\n'
        rss += f'    <description><![CDATA[\n    {description}\n  ]]></description>\n'
        if pd.notna(date_pub):
            try:
                pub_obj = pd.to_datetime(date_pub)
                rss += f'    <pubDate>{pub_obj.strftime("%a, %d %b %Y %H:%M:%S +1100")}</pubDate>\n'
            except:
                pass
        rss += '  <category>Emploi</category>\n'
        
        # Ajouter les catégories de direction et service depuis le MD
        md_path = os.path.join("data", f"{numero}.md")
        if os.path.exists(md_path):
            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            # Extraire direction
            acronyme_dir, libelle_dir = extract_direction_from_content(md_content)
            if acronyme_dir and libelle_dir:
                rss += f'  <category>{libelle_dir}</category>\n'
            # Extraire service
            acronyme_service, libelle_service = extract_service_from_libelle(libelle_poste, referentiel)
            if acronyme_service and libelle_service:
                rss += f'  <category>{libelle_service}</category>\n'
        
        rss += '  </item>\n'
        
    rss += '</channel>\n'
    rss += '</rss>'
    
    with open("data/feed.xml", "w", encoding="utf-8") as f:
        f.write(rss)
    print("✅ Flux RSS généré : data/feed.xml")

def generate_consolidated_catalog(data_dir="data", output_dir="exports"):
    """Génère un fichier consolidé avec toutes les annonces AVP."""
    import re
    import os
    
    print("Génération du catalogue consolidé...")
    
    # Créer le répertoire exports s'il n'existe pas
    os.makedirs(output_dir, exist_ok=True)
    
    # Récupérer tous les fichiers MD (sauf index.md)
    md_files = [f for f in os.listdir(data_dir) 
                if f.endswith('.md') and f != 'index.md']
    
    # Trier par numéro d'AVP (décroissant)
    md_files.sort(reverse=True)
    
    catalog_content = """# Catalogue des Avis de Vacances de Poste OPT-NC

Ce fichier consolidé contient toutes les annonces AVP de l'Office des Postes et Télécommunications de Nouvelle-Calédonie.

**Source :** [https://opt-nc.github.io/avps/](https://opt-nc.github.io/avps/)

**Nombre d'annonces :** {count}

---

"""
    
    catalog_content = catalog_content.format(count=len(md_files))
    
    for md_file in md_files:
        numero = md_file.replace('.md', '')
        md_path = os.path.join(data_dir, md_file)
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extraire le front matter (optionnel - on peut le garder en commentaire)
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
            
            if frontmatter_match:
                frontmatter = frontmatter_match.group(1)
                body = frontmatter_match.group(2)
                
                # Parser le titre depuis le front matter
                title_match = re.search(r'^title:\s*"([^"]+)"', frontmatter, re.MULTILINE)
                title = title_match.group(1) if title_match else numero
            else:
                body = content
                title = numero
            
            # Supprimer le bouton HTML de téléchargement PDF
            body = re.sub(r'<div style="text-align: right.*?</div>\n*', '', body, flags=re.DOTALL)
            
            # Supprimer les images
            body = re.sub(r'!\[\]\([^)]+\)\s*\n*', '', body)
            
            # Décaler tous les titres d'un niveau (H1 → H2, H2 → H3, etc.)
            # On doit traiter de H6 à H1 pour éviter les conflits
            body = re.sub(r'^##### ', '###### ', body, flags=re.MULTILINE)  # H5 → H6
            body = re.sub(r'^#### ', '##### ', body, flags=re.MULTILINE)     # H4 → H5
            body = re.sub(r'^### ', '#### ', body, flags=re.MULTILINE)       # H3 → H4
            body = re.sub(r'^## ', '### ', body, flags=re.MULTILINE)         # H2 → H3
            body = re.sub(r'^# ', '## ', body, flags=re.MULTILINE)           # H1 → H2
            
            # Ajouter le titre H1 de l'annonce
            catalog_content += f"\n# {numero} - {title}\n\n"
            
            # Ajouter le contenu
            catalog_content += body.strip() + "\n\n"
            catalog_content += "---\n\n"
            
            print(f"  ✓ {numero}")
            
        except Exception as e:
            print(f"  ✗ Erreur avec {md_file}: {e}")
    
    # Écrire le fichier consolidé
    output_path = os.path.join(output_dir, "avp_catalog.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(catalog_content)
    
    print(f"✅ Catalogue consolidé généré : {output_path}")
    print(f"   {len(md_files)} annonces consolidées")

if __name__ == "__main__":
    main()
