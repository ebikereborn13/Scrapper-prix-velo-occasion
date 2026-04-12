from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
from datetime import datetime

# --- CONFIGURATION TEST LOCAL ---
URL_CIBLE = "https://mint-bikes.com/collections/vtt-electrique-reconditionne"
NOM_FICHIER_LOCAL = "test_mintbikes.csv"
# --------------------------------

chrome_options = Options()
# chrome_options.add_argument("--headless") # Désactivé pour que tu puisses voir le test
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def extraire_details_precis(texte):
    # 1. Extraction du PRIX DE VENTE (le prix réduit)
    # On cherche le chiffre AVANT le symbole € qui suit "Prix réduit" ou le plus petit prix
    prix_tous = re.findall(r'(\d[\d\s ]*)\s*€', texte)
    prix_tous = [int(p.replace(" ", "").replace("\u202f", "")) for p in prix_tous]
    
    # Stratégie Mint Bikes : Le prix de vente est souvent après "Prix réduit" 
    # ou c'est la valeur minimale trouvée dans le bloc.
    prix_vente = min(prix_tous) if prix_tous else None
    
    # 2. Extraction du PRIX NEUF (Prix régulier)
    # Souvent associé au mot "neuf" dans le texte
    prix_neuf = max(prix_tous) if len(prix_tous) > 1 else None

    # 3. Extraction du KILOMÉTRAGE
    # On ignore les tailles (ex: 1.77m) en ciblant spécifiquement le mot "km"
    # On cherche un nombre suivi de "km", mais on évite les "(-550€)"
    km_match = re.search(r'(?:Environ\s*)?(\d+)\s*km', texte, re.IGNORECASE)
    km = km_match.group(1) if km_match else "0"

    # 4. Extraction de l'ANNÉE
    annee_match = re.search(r'(202\d|201\d)', texte)
    annee_velo = annee_match.group(1) if annee_match else ""

    # 5. Extraction MARQUE
    # On nettoie les mots parasites au début
    nettoyage_prefixe = re.sub(r'^(Nouveauté|SOLDES D\'HIVER|Baisse de prix \(.*?\))\s*', '', texte, flags=re.IGNORECASE)
    marque = nettoyage_prefixe.split()[0] if nettoyage_prefixe else "Inconnue"

    return marque, annee_velo, km, prix_vente, prix_neuf

def executer_test_local():
    print(f"\n--- TEST LOCAL MINT BIKES : {datetime.now().strftime('%H:%M:%S')} ---")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL_CIBLE)
        time.sleep(5) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Sur Mint, chaque produit est généralement dans une div de classe 'grid-product' ou similaire
        # On va chercher les liens de produits et remonter au conteneur
        items = soup.find_all('a', href=True)
        liens_produits = list(dict.fromkeys([l['href'] for l in items if '/products/' in l['href']]))

        data_list = []

        for link in liens_produits:
            element = soup.find('a', href=link)
            parent = element.find_parent('div') 
            # Si le parent immédiat est trop petit, on remonte plus haut pour avoir tout le texte
            if parent:
                # On essaie de capturer le bloc complet (titre + prix + infos)
                conteneur_produit = parent.find_parent('div', class_=re.compile(r'product|card|container'))
                texte_source = conteneur_produit.get_text(separator=" ").strip() if conteneur_produit else parent.get_text(separator=" ").strip()
                
                # Nettoyage des espaces doubles
                texte_clean = " ".join(texte_source.split())

                marque, annee, km, p_vente, p_neuf = extraire_details_precis(texte_clean)

                if p_vente:
                    data_list.append({
                        "Marque": marque,
                        "Année": annee,
                        "Kilométrage": km,
                        "Prix Vente (€)": p_vente,
                        "Prix Neuf (€)": p_neuf,
                        "Lien": f"https://mint-bikes.com{link}",
                        "Texte Brut": texte_clean[:150] # Pour vérification
                    })

        # Sauvegarde (écrase le fichier à chaque fois)
        df = pd.DataFrame(data_list)
        df.to_csv(NOM_FICHIER_LOCAL, index=False, encoding='utf-8-sig')
        print(f">>> SUCCÈS : {len(data_list)} vélos extraits dans {NOM_FICHIER_LOCAL}")

    except Exception as e:
        print(f"Erreur durant le scan : {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    executer_test_local()