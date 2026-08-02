import sqlite3
import json
import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as str_app
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF

# --- CONFIGURATION DE LA PAGE ---
str_app.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

# --- DOSSIERS POUR LES FICHIERS ET LE LOGO ---
DOSSIER_UPLOADS = "uploads_devis"
DOSSIER_ETUDES = "uploads_etudes"
os.makedirs(DOSSIER_UPLOADS, exist_ok=True)
os.makedirs(DOSSIER_ETUDES, exist_ok=True)

CHEMIN_LOGO = "logo.png"

# --- STYLE CSS DESIGN & CORPORATE ---
str_app.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .stButton>button {
        border-radius: 8px; font-weight: 600; transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stButton>button:hover {
        transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 150, 255, 0.2); border-color: #1f6feb;
    }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 6px; border: 1px solid #30363d; background-color: #161b22; color: #c9d1d9; white-space: pre-wrap;
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    .badge-vert { background-color: #238636; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
    .badge-orange { background-color: #9e6a03; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
    .badge-rouge { background-color: #da3633; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
    .badge-notification { background-color: #f85149; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- ACTUALISATION AUTOMATIQUE ---
st_autorefresh(interval=5000, key="datarefreshcounter")

# --- INITIALISATION DE LA BASE DE DONNÉES SQLITE ---
def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS global_store (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS demandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, cahier_charges TEXT,
        montant REAL, fournisseur TEXT, statut TEXT, etape_actuelle TEXT, avis_achats TEXT,
        avis_finance TEXT, motif_refus TEXT, date TEXT, fichier_devis TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS etudes_metier (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, donnees_json TEXT,
        fichier_etude TEXT, destinataires_partage TEXT, date TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS commentaires_etudes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, etude_id INTEGER, auteur TEXT, commentaire TEXT, date TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cahiers_charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, contenu TEXT, date TEXT, destinataires_avis TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages_coordination (
        id INTEGER PRIMARY KEY AUTOINCREMENT, auteur TEXT, texte TEXT, date TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages_directs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, expediteur TEXT, destinataire TEXT, texte TEXT, date TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS journaux_bord (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, texte TEXT, auteur TEXT, date TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, acteur TEXT, action TEXT, details TEXT
    )''')
    
    cursor.execute("SELECT value FROM global_store WHERE key = 'budget_global'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('budget_global', ?)", (str(10000000.0),))
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('solde_restant', ?)", (str(10000000.0),))
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect("database.db", check_same_thread=False)

def get_valeur_globale(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_store WHERE key = ?", (key,))
    val = cursor.fetchone()
    conn.close()
    return float(val[0]) if val else 0.0

def set_valeur_globale(key, val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO global_store (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()

def ajouter_log(action, acteur, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs_audit (date, acteur, action, details) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), acteur, action, details)
    )
    conn.commit()
    conn.close()

# --- UTILISATEURS & RÔLES ---
UTILISATEURS = {
    "DEP1": {"nom": "Agriculture", "mdp": "DEP123", "type": "standard", "dept": "Agriculture"},
    "DEP2": {"nom": "Élevage & Halieutique", "mdp": "DEP123", "type": "standard", "dept": "Élevage & Halieutique"},
    "DEP3": {"nom": "Industrie & Transformation", "mdp": "DEP123", "type": "standard", "dept": "Industrie & Transformation"},
    "DEP4": {"nom": "Ressources Hydriques", "mdp": "DEP123", "type": "standard", "dept": "Ressources Hydriques"},
    "DEP5": {"nom": "Énergie & Maintenance", "mdp": "DEP123", "type": "standard", "dept": "Énergie & Maintenance"},
    "DEP6": {"nom": "Recherche & Développement", "mdp": "DEP123", "type": "standard", "dept": "Recherche & Développement"},
    "DEP7": {"nom": "Sécurité & HSE", "mdp": "DEP123", "type": "standard", "dept": "Sécurité & HSE"},
    "DEP8": {"nom": "Ressources Humaines & RSE", "mdp": "DEP123", "type": "standard", "dept": "Ressources Humaines & RSE"},
    "DEP9": {"nom": "Commercial & Marketing", "mdp": "DEP123", "type": "standard", "dept": "Commercial & Marketing"},
    "DEP10": {"nom": "IT & Data", "mdp": "DEP123", "type": "standard", "dept": "IT & Data"},
    "DEP11": {"nom": "Logistique", "mdp": "DEP123", "type": "standard", "dept": "Logistique"},
    "DEP12": {"nom": "Achats & Approvisionnements", "mdp": "DEP123", "type": "achats", "dept": "Achats & Approvisionnements"},
    "DEP13": {"nom": "Finance & Comptabilité", "mdp": "DEP123", "type": "finance", "dept": "Finance & Comptabilité"},
    "fondateur": {"nom": "Direction Générale - Pilotage Stratégique", "mdp": "mboro2026", "type": "fondateur", "dept": "Direction Générale"}
}

# --- CONNEXION ---
if os.path.exists(CHEMIN_LOGO):
    str_app.sidebar.image(CHEMIN_LOGO, use_column_width=True)
else:
    str_app.sidebar.markdown("## 🏢 Bureau d'Études")

str_app.sidebar.markdown("---")

if 'user_connecte' not in str_app.session_state:
    str_app.session_state.user_connecte = None

if str_app.session_state.user_connecte is None:
    str_app.sidebar.subheader("Connexion Collaborateur")
    username = str_app.sidebar.text_input("Identifiant")
    password = str_app.sidebar.text_input("Mot de passe", type="password")
    
    if str_app.sidebar.button("Se connecter"):
        if username in UTILISATEURS and UTILISATEURS[username]["mdp"] == password:
            str_app.session_state.user_connecte = username
            ajouter_log("Connexion", UTILISATEURS[username]["nom"], "Connexion réussie")
            str_app.rerun()
        else:
            str_app.sidebar.error("Identifiant ou mot de passe incorrect.")
    str_app.stop()
else:
    infos_user = UTILISATEURS[str_app.session_state.user_connecte]
    str_app.sidebar.success(f"Connecté en tant que :\n**{infos_user['nom']}**")
    str_app.sidebar.markdown("---")
    
    if str_app.session_state.user_connecte == "fondateur":
        if str_app.sidebar.button("🔄 Réinitialiser l'application (Reset)"):
            budget_init = get_valeur_globale("budget_global")
            set_valeur_globale("solde_restant", budget_init)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM demandes")
            cursor.execute("DELETE FROM etudes_metier")
            cursor.execute("DELETE FROM commentaires_etudes")
            cursor.execute("DELETE FROM cahiers_charges")
            cursor.execute("DELETE FROM messages_coordination")
            cursor.execute("DELETE FROM messages_directs")
            cursor.execute("DELETE FROM journaux_bord")
            cursor.execute("DELETE FROM logs_audit")
            conn.commit()
            conn.close()
            str_app.success("Application réinitialisée !")
            str_app.rerun()
        str_app.sidebar.markdown("---")

    if str_app.sidebar.button("Se déconnecter"):
        str_app.session_state.user_connecte = None
        str_app.rerun()

user_key = str_app.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

str_app.title(f"Tableau de Bord - {profil['nom']}")

def formater_badge_statut(statut):
    s = statut.lower()
    if "validé" in s or "approuvé" in s:
        return f'<span class="badge-vert">🟢 {statut}</span>'
    elif "refusé" in s or "annulé" in s:
        return f'<span class="badge-rouge">🔴 {statut}</span>'
    else:
        return f'<span class="badge-orange">🟠 {statut}</span>'

# ==========================================
# MODULE BESOINS & SUIVI (PROCESSUS DEMANDE D'ACHAT)
# ==========================================
def afficher_module_besoins_et_suivi(nom_departement, type_profil):
    str_app.subheader("🛒 Gestion des Demandes d'Achat & Validation Budgétaire")

    # --- SOUR-ONGLETS INTÉRIEURS ---
    tab_creer, tab_suivi, tab_validation = str_app.tabs([
        "1. Émettre une Demande d'Achat", 
        "2. Suivi de vos Demandes", 
        "3. Espace de Validation (Achats / Finance / DG)"
    ])

    # 1. ÉMETTRE UNE DEMANDE
    with tab_creer:
        with str_app.form(f"form_demande_{nom_departement}", clear_on_submit=True):
            titre = str_app.text_input("Intitulé du besoin / équipement")
            cahier_charges = str_app.text_area("Description synthétique de la demande")
            montant = str_app.number_input("Montant estimé ou devis (€)", min_value=0.0, step=100.0)
            fournisseur = str_app.text_input("Fournisseur pressenti (Optionnel)")
            fichier_devis = str_app.file_uploader("📎 Pièce jointe / Devis officiel (PDF/Image)", type=["pdf", "png", "jpg", "jpeg", "xlsx"])

            submit_demande = str_app.form_submit_button("🚀 Soumettre la demande d'achat")

            if submit_demande and titre and montant > 0:
                nom_devis = ""
                if fichier_devis is not None:
                    nom_devis = f"devis_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fichier_devis.name}"
                    with open(os.path.join(DOSSIER_UPLOADS, nom_devis), "wb") as f:
                        f.write(fichier_devis.getbuffer())

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nom_departement, titre, cahier_charges, montant, fournisseur,
                    "En attente validation Achats", "achats", "En attente", "En attente", "",
                    datetime.now().strftime("%Y-%m-%d %H:%M"), nom_devis
                ))
                conn.commit()
                conn.close()

                ajouter_log("Demande Achat", nom_departement, f"Demande créée : {titre} - {montant}€")
                str_app.success("Demande d'achat soumise aux Achats & Approvisionnements !")
                str_app.rerun()

    # 2. SUIVI DE MES DEMANDES
    with tab_suivi:
        conn = get_db_connection()
        df_demandes = pd.read_sql_query("SELECT * FROM demandes WHERE departement = ? ORDER BY id DESC", conn, params=(nom_departement,))
        conn.close()

        if not df_demandes.empty:
            for idx, row in df_demandes.iterrows():
                with str_app.expander(f"📌 #{row['id']} - {row['titre']} ({row['montant']} €)"):
                    str_app.write(f"**Statut actuel :** {row['statut']}")
                    str_app.write(f"**Description :** {row['cahier_charges']}")
                    str_app.write(f"**Avis Achats :** {row['avis_achats']} | **Avis Finance :** {row['avis_finance']}")
                    if row['motif_refus']:
                        str_app.error(f"Motif du refus : {row['motif_refus']}")
        else:
            str_app.info("Aucune demande d'achat enregistrée pour votre département.")

    # 3. ESPACE DE VALIDATION (ACHATS / FINANCE / FONDATEUR)
    with tab_validation:
        conn = get_db_connection()
        cursor = conn.cursor()

        if type_profil == "achats":
            str_app.markdown("### 🛒 Validations requises — Service Achats")
            cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'achats'")
            demandes_achats = cursor.fetchall()

            if demandes_achats:
                for d in demandes_achats:
                    d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich = d
                    with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        str_app.write(f"**Cahier des charges :** {d_cc}")
                        str_app.write(f"**Fournisseur proposé :** {d_fourn}")
                        
                        col1, col2 = str_app.columns(2)
                        with col1:
                            if str_app.button(f"✅ Approuver (Achats) #{d_id}"):
                                cursor.execute("UPDATE demandes SET avis_achats='Favorable', etape_actuelle='finance', statut='En attente validation Finance' WHERE id=?", (d_id,))
                                conn.commit()
                                str_app.success("Transmis à la Finance !")
                                str_app.rerun()
                        with col2:
                            motif = str_app.text_input(f"Motif refus #{d_id}")
                            if str_app.button(f"❌ Refuser #{d_id}"):
                                cursor.execute("UPDATE demandes SET statut='Refusé par Achats', avis_achats='Défavorable', motif_refus=? WHERE id=?", (motif, d_id))
                                conn.commit()
                                str_app.rerun()
            else:
                str_app.info("Aucune demande d'achat en attente d'évaluation.")

        elif type_profil == "finance":
            str_app.markdown("### 💶 Validations requises — Service Finance")
            cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'finance'")
            demandes_fin = cursor.fetchall()

            if demandes_fin:
                for d in demandes_fin:
                    d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich = d
                    with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        if str_app.button(f"✅ Valider le financement #{d_id}"):
                            cursor.execute("UPDATE demandes SET avis_finance='Favorable', etape_actuelle='fondateur', statut='En attente arbitrage Direction' WHERE id=?", (d_id,))
                            conn.commit()
                            str_app.success("Transmis à la Direction Générale !")
                            str_app.rerun()
            else:
                str_app.info("Aucune validation financière en attente.")

        elif type_profil == "fondateur":
            str_app.markdown("### 👑 Arbitrage Stratégique — Direction Générale")
            cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'fondateur'")
            demandes_dg = cursor.fetchall()

            if demandes_dg:
                for d in demandes_dg:
                    d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich = d
                    with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        if str_app.button(f"🎉 APPROUVER DÉFINITIVEMENT #{d_id}"):
                            solde = get_valeur_globale("solde_restant")
                            set_valeur_globale("solde_restant", solde - d_montant)
                            cursor.execute("UPDATE demandes SET statut='Validé & Financé', etape_actuelle='termine' WHERE id=?", (d_id,))
                            conn.commit()
                            str_app.success("Demande approuvée et budget imputé !")
                            str_app.rerun()
            else:
                str_app.info("Aucun arbitrage requis pour le moment.")
        else:
            str_app.info("Les validations sont réservées aux services Achats, Finance et à la Direction Générale.")
        
        conn.close()

# (Conserve ici les modules Messagerie, Cahiers des charges et Études présentés dans les étapes précédentes...)
