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

# --- CONFIGURATION ---
nom_fichier = "test_mintbikes.csv"
chemin_bureau = os.path.join(os.path.expanduser("~"), "Desktop", nom_fichier)
URL_CIBLE = "https://mint-bikes.com/collections/vtt-electrique-reconditionne"

chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def extraire_marque_depuis_url(url):
    match = re.search(r'products/([a-zA-Z0-9]+)-', url)
    if match:
        marque = match.group(1).upper()
        return "SANTA CRUZ" if marque == "SANTA" else marque
    return "INCONNUE"

def extraire_prix_coherents(texte):
    # 1. NETTOYAGE DES PIÈGES (Baisse de prix, économies, LLD)
    t = texte.replace('\xa0', '').replace('\u202f', '').replace(' ', '')
    # Supprime les baisses négatives (ex: -640€)
    t = re.sub(r'-\d+€', '', t)
    # Supprime les pourcentages (ex: -34%)
    t = re.sub(r'-\d+%', '', t)
    # Supprime les économies
    t = re.sub(r'Économisez\d+€', '', t, flags=re.IGNORECASE)
    # Supprime les mentions mensuelles (LLD)
    t = re.sub(r'\d+€/mois', '', t, flags=re.IGNORECASE)

    # 2. CAPTURE DE TOUS LES NOMBRES RESTANTS FINISSANT PAR €
    prix_potentiels = re.findall(r'(\d+)€', t)
    prix_num = sorted([int(p) for p in prix_potentiels], reverse=True)

    if not prix_num:
        return None, None

    # Stratégie : Le plus grand est le prix NEUF (Régulier)
    p_neuf = prix_num[0]
    
    # On cherche le prix de VENTE parmi les autres
    p_vente = None
    for p in prix_num[1:]:
        # REGLE DE COHÉRENCE : 
        # - Le prix de revente doit être > 800€ (seuil VAE occasion)
        # - Le prix de revente ne peut pas être < 20% du prix neuf (ex: 600€ vs 6000€ = erreur)
        if p >= 800 and p > (p_neuf * 0.20):
            p_vente = p
            break
    
    # Si on n'a qu'un seul prix ou si aucun prix n'a passé le test de cohérence
    if p_vente is None and len(prix_num) > 0:
        if prix_num[0] > 800:
            p_vente = prix_num[0]
            p_neuf = None # On n'a que le prix de vente

    return p_vente, p_neuf

def extraire_km(texte):
    km_match = re.search(r'(?:Environ\s*)?(\d+)\s*km', texte, re.IGNORECASE)
    return km_match.group(1) if km_match else "0"

def executer_scan_final():
    print(f"\n--- SCAN MINT BIKES : STRATÉGIE DE COHÉRENCE ACTIVÉE ---")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(URL_CIBLE)
        time.sleep(5) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        produits = soup.find_all('a', href=True)
        liens = list(dict.fromkeys([l['href'] for l in produits if '/products/' in l['href']]))

        data_list = []

        for link in liens:
            full_url = f"https://mint-bikes.com{link}"
            element = soup.find('a', href=link)
            parent = element.find_parent('div', class_=re.compile(r'product|card|grid|container'))
            
            if not parent: continue
            
            texte_brut = parent.get_text(separator=" ").strip()
            
            marque = extraire_marque_depuis_url(full_url)
            p_vente, p_neuf = extraire_prix_coherents(texte_brut)
            km = extraire_km(texte_brut)
            
            # Année
            an_match = re.search(r'(20\d{2})', texte_brut)
            annee = an_match.group(1) if an_match else ""

            if p_vente:
                data_list.append({
                    "Marque": marque,
                    "Année": annee,
                    "Kilométrage": km,
                    "Prix Vente (€)": p_vente,
                    "Prix Neuf (€)": p_neuf,
                    "Lien": full_url
                })

        if data_list:
            df = pd.DataFrame(data_list)
            df.to_csv(chemin_bureau, index=False, encoding='utf-8-sig')
            print(f"SUCCÈS : Fichier '{nom_fichier}' créé sur le Bureau.")
            print(f"Vélos analysés : {len(data_list)}")
        else:
            print("Aucune donnée cohérente n'a pu être extraite.")

    except Exception as e:
        print(f"Erreur : {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    executer_scan_final()