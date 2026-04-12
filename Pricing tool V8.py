import pandas as pd
import numpy as np
from datetime import datetime

# --- PARAMÈTRES GÉNÉRAUX ---
SETTINGS = {
    "marge": 0.23,
    "marketing": 40,
    "transport": 75,
    "km_max": 1500,
    "reconditionnement_max": 190,
    "main_oeuvre_min": 30,
    "main_oeuvre_max": 60,
    "batterie_seuil": 500,
    "batterie_coef_sous_seuil": 0.9,
    "coef_moteur_reduit": 0.95,
    "moteurs_avec_decote": ["shimano", "yamaha"],
    "coef_type_reduit": 0.9,
    "types_avec_decote": ["suv", "vttae_light"],
    "boost_10": ["cube", "moustache"],
    "boost_05": ["haibike", "giant", "lapierre", "bulls", "scott", "focus", "specialized", "trek"],
    "revente_seuil_amortissement": 3500,
    "revente_stop_complet": 3999
}

def normalize(text):
    """Normalise les chaînes de caractères pour les comparaisons (minuscules, sans caractères spéciaux)"""
    if not text or pd.isna(text):
        return ""
    text = str(text).strip().lower()
    # Remplace tout ce qui n'est pas lettre ou chiffre par '_'
    return re.sub(r'[^a-z0-9]', '_', text)

import re # Requis pour la normalisation

def apply_safety_cap(price):
    """Lissage pour les tarifs de revente élevés (Amortissement asymptotique)"""
    threshold = SETTINGS["revente_seuil_amortissement"]
    hard_cap = SETTINGS["revente_stop_complet"]
    max_gain_possible = hard_cap - threshold
    
    if price <= threshold:
        return price

    excess = price - threshold
    attenuated_excess = (max_gain_possible * excess) / (excess + 1000)
    return threshold + attenuated_excess

def apply_commercial_rounding(price):
    """Arrondi psychologique (finit par 49 ou 99)"""
    if price <= 0: return 0
    base_hundred = (price // 100) * 100
    remainder = price % 100
    return (base_hundred + 49) if remainder < 50 else (base_hundred + 99)

def calculate_value(data_velo, df_coefficients, df_indicateurs):
    """
    Logique de calcul principale sans perte de fonctionnalité
    data_velo: dictionnaire contenant les infos du vélo
    """
    # 1. Préparation des variables
    marque = normalize(data_velo.get("Marque", ""))
    prix_origine = float(data_velo.get("PrixOrigine", 0))
    annee = int(data_velo.get("Annee", datetime.now().year))
    km = float(data_velo.get("Kilometrage", 0))
    capacite_batterie = float(data_velo.get("CapaciteBatterie", 0))
    moteur = normalize(data_velo.get("Motorisation", ""))
    type_velo = normalize(data_velo.get("TypeVelo", ""))
    
    age = max(0, datetime.now().year - annee)

    # 2. Récupération des Coefficients
    # On cherche la ligne correspondant à la marque dans le DataFrame des coefficients
    coef_row = df_coefficients[df_coefficients['marque_norm'] == marque]
    if coef_row.empty:
        return {"revente": 0, "reprise": 0}
    
    c = coef_row.iloc[0]
    decote_base = float(c['decote_base'])
    decote_annuelle = float(c['decote_annuelle'])
    decote_km = float(c['decote_kilometrique'])

    # --- ÉTAPE A : CALCUL REVENTE BRUTE ---
    value_revente = prix_origine * (1 - decote_base - decote_annuelle * age - decote_km * km)

    # Décotes spécifiques
    if moteur in SETTINGS["moteurs_avec_decote"]: value_revente *= SETTINGS["coef_moteur_reduit"]
    if type_velo in SETTINGS["types_avec_decote"]: value_revente *= SETTINGS["coef_type_reduit"]
    if marque == "moustache": value_revente *= 1.20 # Bonus spécifique Moustache

    # --- ÉTAPE B : CORRECTION MARCHÉ (HISTORIQUE) ---
    historique_marque = df_indicateurs[df_indicateurs['marque_norm'] == marque]
    correction = 1
    if not historique_marque.empty:
        # On filtre les taux d'erreur valides (Col K dans votre Google Script)
        taux_erreurs = historique_marque['taux_erreur'].dropna()
        if len(taux_erreurs) > 0:
            taux_moyen = taux_erreurs.mean()
            # Lissage si moins de 3 ventes
            correction = 1 + (taux_moyen / 2 if len(taux_erreurs) < 3 else taux_moyen)
    
    value_revente *= correction

    # --- ÉTAPE C : LISSAGE SÉCURITÉ ---
    value_revente = apply_safety_cap(value_revente)

    # --- ÉTAPE D : CALCUL REPRISE ---
    km_ratio = min(max(km, 0), SETTINGS["km_max"]) / SETTINGS["km_max"]
    reconditionnement = km_ratio * SETTINGS["reconditionnement_max"]
    main_oeuvre = SETTINGS["main_oeuvre_min"] + km_ratio * (SETTINGS["main_oeuvre_max"] - SETTINGS["main_oeuvre_min"])

    value_reprise = value_revente * (1 - SETTINGS["marge"])
    value_reprise -= (SETTINGS["marketing"] + SETTINGS["transport"] + reconditionnement + main_oeuvre)

    # Ajustements batterie & Boost
    if capacite_batterie > 0 and capacite_batterie < SETTINGS["batterie_seuil"]:
        value_reprise *= SETTINGS["batterie_coef_sous_seuil"]
        
    if marque in SETTINGS["boost_10"]: value_reprise *= 1.10
    elif marque in SETTINGS["boost_05"]: value_reprise *= 1.05

    return {
        "revente": apply_commercial_rounding(value_revente),
        "reprise": round(max(0, value_reprise))
    }