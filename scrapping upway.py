from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import git
from datetime import datetime

# --- CONFIGURATION GITHUB ---
GITHUB_USER = "ebikereborn13"
GITHUB_TOKEN = "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"
REPO_NAME = "Scrapper-prix-velo-occasion" 

# --- CONFIGURATION DE L'INTERVALLE ---
# Modifiez ce chiffre selon vos besoins (ex: 1 pour chaque jour, 7 pour chaque semaine)
INTERVALLE_JOURS = 7 
# -------------------------------------

chrome_options = Options()
# chrome_options.add_argument("--headless") # Enlevez le '#' pour masquer la fenêtre Chrome
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def obtenir_nom_mois(numero_mois):
    mois = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 
        5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août", 
        9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
    }
    return mois.get(numero_mois, "Inconnu")

def extraire_details(texte):
    # Prix : Nettoyage des espaces pour les milliers
    texte_nettoyé = re.sub(r'(\d)\s+(\d{3})', r'\1\2', texte)
    prix_trouves = re.findall(r'(\d+)\s*€', texte_nettoyé)
    prix_trouves = [int(p) for p in prix_trouves]
    prix_vente = min(prix_trouves) if prix_trouves else None
    prix_neuf = max(prix_trouves) if len(prix_trouves) > 1 else None

    # Kilométrage : Suppression des tailles (1mXX) avant capture
    texte_sans_taille = re.sub(r'\dm\d{2}', '', texte)
    km_match = re.search(r'(\d[\d\s]*)\s*km', texte_sans_taille)
    km = km_match.group(1).replace(" ", "").strip() if km_match else "0"

    # Année du vélo
    annee_match = re.search(r'(20\d{2})', texte)
    annee_velo = annee_match.group(1) if annee_match else ""

    # Marque + Exception Santa Cruz
    if texte.lower().strip().startswith("santa cruz"):
        marque = "Santa Cruz"
    else:
        mots = texte.split()
        marque = mots[0] if mots else ""

    return marque, annee_velo, km, prix_vente, prix_neuf

def sauvegarder_et_pousser_github(data_list):
    print("Mise à jour de la base de données sur GitHub...")
    nom_fichier = "donnees_upway.csv"
    remote_url = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{REPO_NAME}.git"
    
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_dir)
    
    try:
        # Initialisation Git
        if not os.path.exists(os.path.join(repo_dir, '.git')):
            repo = git.Repo.init(repo_dir)
            repo.git.checkout('-b', 'main')
        else:
            repo = git.Repo(repo_dir)

        # Configuration du Remote
        if 'origin' in [r.name for r in repo.remotes]:
            repo.delete_remote('origin')
        repo.create_remote('origin', remote_url)

        # Fusion des données (Mode Historique)
        df_nouveau = pd.DataFrame(data_list)
        if os.path.exists(nom_fichier):
            df_ancien = pd.read_csv(nom_fichier, dtype={'Kilométrage': str})
            df_final = pd.concat([df_ancien, df_nouveau], ignore_index=True)
            df_final = df_final.drop_duplicates(subset=['Lien', 'Prix Vente (€)', 'Date Vente'])
        else:
            df_final = df_nouveau

        # Sauvegarde CSV avec encodage compatible Excel
        df_final.to_csv(nom_fichier, index=False, encoding='utf-8-sig')

        # Envoi GitHub
        repo.git.add(nom_fichier)
        if repo.is_dirty(untracked_files=True):
            repo.index.commit(f"Update : {len(data_list)} vélos")
            repo.git.push('origin', 'main', force=True)
            print(">>> SUCCÈS : Données envoyées sur GitHub.")
        else:
            print(">>> INFO : Aucune nouvelle donnée à uploader.")

    except Exception as e:
        print(f"Erreur de synchronisation : {e}")

def executer_scrapping():
    print(f"\n--- LANCEMENT DU SCAN : {datetime.now().strftime('%d/%m/%Y %H:%M')} ---")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    url = "https://upway.fr/collections/vtt"
    mots_inutiles = ["Nouveau", "Bon plan", "Bestseller", "neuf", "reconditionné", "Vendu"]

    try:
        driver.get(url)
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        produits = soup.find_all('a', href=True)
        liens_uniques = list(dict.fromkeys([l['href'] for l in produits if '/products/' in l['href']]))

        data_list = []
        now = datetime.now()

        for lien in liens_uniques:
            element = soup.find('a', href=lien)
            if element and element.find_parent('div'):
                parent = element.find_parent('div')
                texte_brut = parent.get_text(separator=" ").strip()
                for mot in mots_inutiles:
                    texte_brut = texte_brut.replace(mot, "").replace(mot.upper(), "")
                texte_final = " ".join(texte_brut.split())

                marque, annee_v, km, p_vente, p_neuf = extraire_details(texte_final)

                data_list.append({
                    "Date Vente": now.strftime("%d/%m/%Y"),
                    "Année Vente": now.year,
                    "Mois Vente": obtenir_nom_mois(now.month),
                    "Marque": marque,
                    "Année Vélo": annee_v,
                    "Kilométrage": km,
                    "Prix Vente (€)": p_vente,
                    "Prix Neuf (€)": p_neuf,
                    "Lien": f"https://upway.fr{lien}",
                    "Source": texte_final
                })

        if data_list:
            sauvegarder_et_pousser_github(data_list)
        
    finally:
        driver.quit()

if __name__ == "__main__":
    while True:
        executer_scrapping()
        
        # Calcul du temps d'attente
        secondes_attente = INTERVALLE_JOURS * 24 * 3600
        print(f"--- SCAN TERMINÉ. Prochain passage dans {INTERVALLE_JOURS} jour(s). ---")
        time.sleep(secondes_attente)