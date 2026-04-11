#!/usr/bin/env python3
"""Update zensical.toml with build info from build_info.txt"""

import sys
import os

def update_zensical_config():
    """Update zensical.toml with commit and date info."""
    
    # Lire les infos de build
    if not os.path.exists("data/build_info.txt"):
        print("⚠️  build_info.txt not found, using defaults")
        commit_sha = "unknown"
        date_str = "Date inconnue"
    else:
        with open("data/build_info.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
            commit_sha = lines[0].strip() if len(lines) > 0 else "unknown"
            date_str = lines[1].strip() if len(lines) > 1 else "Date inconnue"
    
    # Récupérer la version de zensical
    import subprocess
    try:
        result = subprocess.run(["uv", "tool", "run", "zensical", "--version"], capture_output=True, text=True, check=True)
        # La sortie est généralement "zensical 0.x.x"
        zensical_version = result.stdout.strip()
    except Exception:
        zensical_version = "Zensical"

    # Lire le fichier zensical.toml
    with open("zensical.toml", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Trouver et remplacer la section copyright
    new_copyright = f'''copyright = """
Copyright &copy; 2026 OPT-NC<br>
<small>Dernière mise à jour : {date_str} (Nouméa) | Commit : <a href="https://github.com/opt-nc/avps/commit/{commit_sha}" target="_blank">{commit_sha}</a></small><br>
<small>Propulsé par <a href="https://github.com/opt-nc/zensical" target="_blank">{zensical_version}</a></small>
"""'''
    
    # Remplacer la section copyright
    import re
    # Pattern pour capturer copyright = """...""" en multi-ligne
    pattern = r'copyright = """.*?"""'
    
    if re.search(pattern, content, flags=re.DOTALL):
        new_content = re.sub(pattern, new_copyright, content, flags=re.DOTALL)
        
        # Écrire le fichier mis à jour
        with open("zensical.toml", "w", encoding="utf-8") as f:
            f.write(new_content)
        
        print(f"✅ zensical.toml updated with commit {commit_sha} and date {date_str}")
    else:
        print("⚠️  Could not find copyright section in zensical.toml")
        sys.exit(1)

if __name__ == "__main__":
    update_zensical_config()
