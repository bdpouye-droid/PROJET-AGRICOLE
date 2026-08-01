import streamlit as str_app
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from io import BytesIO
from fpdf import FPDF
import sqlite3
import json
import os

# --- CONFIGURATION DE LA PAGE ---
str_app.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

# --- DOSSIERS POUR LES FICHIERS ET LE LOGO ---
DOSSIER_UPLOADS = "uploads_devis"
DOSSIER_ETUDES = "uploads_etudes"
if not os.path.exists(DOSSIER_UPLOADS):
    os.makedirs(DOSSIER_UPLOADS)
if not os.path.exists(DOSSIER_ETUDES):
    os.makedirs(DOSSIER_ETUDES)

CHEMIN_LOGO = "logo.png"

# --- STYLE CSS DESIGN & CORPORATE (SaaS Look + Badges) ---
str_app.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 150, 255, 0.2);
        border-color: #1f6feb;
    }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 6px;
        border: 1px solid #30363d;
        background-color: #161b22;
        color: #c9d1d9;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
    }
    .badge-vert {
        background-color: #238636; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;
    }
    .badge-orange {
        background-color: #9e6a03; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;
    }
    .badge-rouge {
        background-color: #da3633; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- ACTUALISATION AUTOMATIQUE ---
st_autorefresh(interval=5000, key="datarefreshcounter")

# --- INITIALISATION DE LA BASE DE DONNÉES SQLITE ---
def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_store (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS demandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            cahier_charges TEXT,
            montant REAL,
            fournisseur TEXT,
            statut TEXT,
            etape_actuelle TEXT,
            avis_achats TEXT,
            avis_finance TEXT,
            motif_refus TEXT,
            date TEXT,
            fichier_devis TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS etudes_metier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            donnees_json TEXT,
            fichier_etude TEXT,
            destinataires_partage TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cahiers_charges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            contenu TEXT,
            date TEXT,
            destinataires_avis TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages_coordination (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auteur TEXT,
            texte TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages_directs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expediteur TEXT,
            destinataire TEXT,
            texte TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journaux_bord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            texte TEXT,
            auteur TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            acteur TEXT,
            action TEXT,
            details TEXT
        )
    ''')
    
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

# --- DICTIONNAIRE DES UTILISATEURS & RÔLES (14 DÉPARTEMENTS + DIRECTION) ---
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

# --- GESTION DE LA CONNEXION ---
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
        with str_app.spinner("Vérification des accès..."):
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
            with str_app.spinner("Réinitialisation complète..."):
                budget_init = get_valeur_globale("budget_global")
                set_valeur_globale("solde_restant", budget_init)
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM demandes")
                cursor.execute("DELETE FROM etudes_metier")
                cursor.execute("DELETE FROM cahiers_charges")
                cursor.execute("DELETE FROM messages_coordination")
                cursor.execute("DELETE FROM messages_directs")
                cursor.execute("DELETE FROM journaux_bord")
                cursor.execute("DELETE FROM logs_audit")
                conn.commit()
                conn.close()
                
                ajouter_log("Réinitialisation", infos_user['nom'], "Base de données remise à zéro")
                str_app.success("Application réinitialisée à zéro !")
                str_app.rerun()
        str_app.sidebar.markdown("---")

    if str_app.sidebar.button("Se déconnecter"):
        with str_app.spinner("Déconnexion sécurisée..."):
            ajouter_log("Déconnexion", infos_user['nom'], "Déconnexion de l'utilisateur")
            str_app.session_state.user_connecte = None
            str_app.rerun()

user_key = str_app.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

str_app.title(f"Tableau de Bord - {profil['nom']}")

# --- FONCTION UTILITAIRE POUR LES BADGES DE STATUT ---
def formater_badge_statut(statut):
    statut_lower = statut.lower()
    if "validé" in statut_lower or "approuvé" in statut_lower:
        return f'<span class="badge-vert">🟢 {statut}</span>'
    elif "refusé" in statut_lower or "annulé" in statut_lower:
        return f'<span class="badge-rouge">🔴 {statut}</span>'
    else:
        return f'<span class="badge-orange">🟠 {statut}</span>'

# --- NOTIFICATIONS ---
conn_notif = get_db_connection()
cursor_notif = conn_notif.cursor()
if profil["type"] == "achats":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
    nb_pending = cursor_notif.fetchone()[0]
    if nb_pending > 0:
        str_app.warning(f"⚠️ Vous avez **{nb_pending}** demande(s) en attente de chiffrage et de sourcing.")
elif profil["type"] == "finance":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
    nb_pending = cursor_notif.fetchone()[0]
    if nb_pending > 0:
        str_app.warning(f"⚠️ Vous avez **{nb_pending}** dossier(s) en attente de contrôle budgétaire.")
elif profil["type"] == "fondateur":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'fondateur'")
    nb_pending = cursor_notif.fetchone()[0]
    if nb_pending > 0:
        str_app.warning(f"⚠️ Vous avez **{nb_pending}** dossier(s) en attente de signature exécutive.")
elif profil["type"] == "standard":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE departement = ? AND statut LIKE '%Refusé%'", (nom_dept,))
    nb_refus = cursor_notif.fetchone()[0]
    if nb_refus > 0:
        str_app.error(f"❌ Vous avez **{nb_refus}** demande(s) refusée(s) ou nécessitant une modification.")

cursor_notif.execute("SELECT COUNT(*) FROM messages_directs WHERE destinataire = ?", (nom_dept,))
nb_msg_recus = cursor_notif.fetchone()[0]
conn_notif.close()
if nb_msg_recus > 0:
    str_app.info(f"💬 Vous avez reçu des messages dans votre boîte de messagerie interdépartementale.")

str_app.markdown("---")

# --- FONCTION PDF ---
def generer_pdf(titre, texte_contenu, infos_complementaires=""):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(CHEMIN_LOGO):
        try:
            pdf.image(CHEMIN_LOGO, 10, 10, 25)
        except Exception:
            pass
            
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 10, txt="BUREAU D'ÉTUDES - DIRECTION GÉNÉRALE", ln=True, align="C")
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, txt="Document Officiel de Traçabilité", ln=True, align="C")
    pdf.ln(8)
    pdf.line(10, 32, 200, 32)
    pdf.ln(8)
    
    pdf.set_font("Arial", "B", 13)
    pdf.multi_cell(0, 8, txt=titre, align="L")
    pdf.ln(4)
    
    if infos_complementaires:
        pdf.set_font("Arial", "I", 10)
        pdf.multi_cell(0, 6, txt=infos_complementaires)
        pdf.ln(6)
        
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, txt=texte_contenu)
    
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin1', 'replace')
        
    return BytesIO(pdf_bytes)


# ==========================================
# MODULE MESSAGERIE DIRECTE INTERDÉPARTEMENTALE
# ==========================================
def afficher_module_messagerie_directe(nom_departement):
    str_app.subheader("📬 Messagerie Interdépartementale Directe")
    str_app.write("Envoyez et consultez des messages ciblés et sécurisés vers n'importe quel autre département du bureau d'études.")
    
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    col_m1, col_m2 = str_app.columns([1, 1])
    
    with col_m1:
        str_app.markdown("### ✉️ Envoyer un message direct")
        with str_app.form(f"form_msg_direct_{nom_departement}", clear_on_submit=True):
            destinataire_choisi = str_app.selectbox("Sélectionner le département destinataire", tous_les_depts)
            texte_message = str_app.text_area("Contenu du message / Note technique")
            submit_direct = str_app.form_submit_button("Envoyer le message")
            
            if submit_direct and texte_message:
                with str_app.spinner("Envoi en cours..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO messages_directs (expediteur, destinataire, texte, date) VALUES (?, ?, ?, ?)",
                        (nom_departement, destinataire_choisi, texte_message, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    str_app.success(f"Message transmis avec succès à [{destinataire_choisi}] !")
                    str_app.rerun()
            elif submit_direct:
                str_app.error("Veuillez saisir le contenu du message.")

    with col_m2:
        str_app.markdown("### 📥 Boîte de réception & Historique")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, expediteur, destinataire, texte, date FROM messages_directs WHERE destinataire = ? OR expediteur = ? ORDER BY id DESC", (nom_departement, nom_departement))
        messages_tous = cursor.fetchall()
        conn.close()
        
        if messages_tous:
            for m in messages_tous:
                m_id, m_exp, m_dest, m_texte, m_date = m
                if m_dest == nom_departement:
                    badge_sens = f"📬 Reçu de **{m_exp}**"
                    couleur_fond = "#161b22"
                else:
                    badge_sens = f"📤 Envoyé à **{m_dest}**"
                    couleur_fond = "#0d1117"
                
                str_app.markdown(f"""
                <div style="background-color: {couleur_fond}; padding: 10px; border-radius: 6px; border: 1px solid #30363d; margin-bottom: 8px;">
                    <small style="color: #8b949e;">{badge_sens} — {m_date}</small><br>
                    <span style="color: #c9d1d9; font-size: 0.9rem;">{m_texte}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            str_app.info("Aucun message direct pour le moment.")


# ==========================================
# MODULE COLLABORATIF : ESPACE TEAMS & JOURNAL
# ==========================================
def afficher_espace_coordination_et_journal(nom_departement):
    with str_app.expander("💬 **Espace de Coordination Global (Fil Partagé)**"):
        str_app.markdown("Canal de discussion et de notes transversales ouvert à l'ensemble des départements.")
        with str_app.form(f"form_coord_{nom_departement}", clear_on_submit=True):
            texte_msg = str_app.text_input("Publier une note ou un compte-rendu dans le fil global")
            submit_msg = str_app.form_submit_button("Envoyer dans le fil")
            if submit_msg and texte_msg:
                with str_app.spinner("Publication..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO messages_coordination (auteur, texte, date) VALUES (?, ?, ?)",
                        (nom_departement, texte_msg, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    str_app.success("Message publié avec succès !")
                    str_app.rerun()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT auteur, texte, date FROM messages_coordination ORDER BY id DESC")
        messages = cursor.fetchall()
        conn.close()
        
        if messages:
            for m in messages:
                str_app.markdown(f"""
                <div style="background-color: #161b22; padding: 12px; border-radius: 6px; border-left: 3px solid #1f6feb; margin-bottom: 10px;">
                    <small style="color: #8b949e;"><b>{m[0]}</b> — {m[2]}</small><br>
                    <span style="color: #c9d1d9; font-size: 0.95rem;">{m[1]}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            str_app.info("Aucun message dans le fil partagé pour le moment.")

    with str_app.expander(f"📔 **Journal de Bord Personnel ({nom_departement})**"):
        str_app.write("Vos notes internes et suivis quotidiens privés.")
        with str_app.form(f"form_journal_{nom_departement}", clear_on_submit=True):
            titre_j = str_app.text_input("Titre de l'entrée")
            texte_j = str_app.text_area("Notes et avancements")
            submit_j = str_app.form_submit_button("Ajouter au journal")
            
            if submit_j and titre_j and texte_j:
                with str_app.spinner("Enregistrement..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO journaux_bord (departement, titre, texte, auteur, date) VALUES (?, ?, ?, ?, ?)",
                        (nom_departement, titre_j, texte_j, nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    str_app.success("Entrée enregistrée avec succès !")
                    str_app.rerun()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT titre, texte, date FROM journaux_bord WHERE departement = ? ORDER BY id DESC", (nom_departement,))
        journaux = cursor.fetchall()
        conn.close()
        
        if journaux:
            for entree in journaux:
                str_app.markdown(f"**[{entree[2]}] {entree[0]}**\n\n{entree[1]}\n\n---")
        else:
            str_app.info("Aucune entrée dans votre journal de bord.")


# ==========================================
# MODULES SPÉCIFIQUES DÉDIÉS AUX 14 DÉPARTEMENTS
# AVEC IMPORT DE FICHIERS ET PARTAGE CIBLÉ INTERDÉPARTEMENTAL
# ==========================================
def afficher_module_specifique_metier(nom_departement):
    str_app.subheader(f"⚙️ Centre d'Ingénierie & Études Métier — {nom_departement}")
    str_app.write("Créez vos études amont, importez vos fichiers techniques (SIG, plans, PDF, Excel) et partagez-les avec les départements concernés.")
    
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    tab_creer, tab_consulter = str_app.tabs(["1. Nouvelle Étude & Partage", "2. Études & Fichiers Partagés Reçus"])
    
    with tab_creer:
        with str_app.form(f"form_etude_{nom_departement}", clear_on_submit=True):
            titre_etude = str_app.text_input("Intitulé de l'étude / Projet technique")
            
            # Saisie spécifique selon le département
            champs_specifiques = {}
            if nom_departement == "Agriculture":
                champs_specifiques["culture"] = str_app.text_input("Type de culture / Spéculation")
                champs_specifiques["surface"] = str_app.number_input("Surface prévisionnelle", min_value=0.0, step=10.0)
                champs_specifiques["details"] = str_app.text_area("Paramètres pédologiques et contraintes climatiques")
            elif nom_departement == "Élevage & Halieutique":
                champs_specifiques["filiere"] = str_app.selectbox("Filière", ["Bovins", "Petits Ruminants", "Aviculture", "Aquaculture / Halieutique"])
                champs_specifiques["effectif"] = str_app.number_input("Effectif cible / Volume", min_value=1, step=10)
                champs_specifiques["details"] = str_app.text_area("Spécifications nutritionnelles et infrastructures")
            elif nom_departement == "Industrie & Transformation":
                champs_specifiques["chaine"] = str_app.text_input("Intitulé de la chaîne de transformation")
                champs_specifiques["capacite"] = str_app.number_input("Capacité nominale horaire", min_value=0.0, step=1.0)
                champs_specifiques["details"] = str_app.text_area("Bilan de masso-efficience et layout process")
            elif nom_departement == "Ressources Hydriques":
                champs_specifiques["ouvrage"] = str_app.text_input("Type d'ouvrage (Forage, Station, Barrage)")
                champs_specifiques["debit"] = str_app.number_input("Débit prévisionnel (m³/h)", min_value=0.0, step=5.0)
                champs_specifiques["details"] = str_app.text_area("Paramètres hydrogéologiques")
            elif nom_departement == "Énergie & Maintenance":
                champs_specifiques["puissance"] = str_app.number_input("Charge électrique / Puissance requise (kWh)", min_value=0.0, step=50.0)
                champs_specifiques["source"] = str_app.selectbox("Source principale", ["Solaire PV", "Biomasse", "Réseau", "Hybride"])
                champs_specifiques["details"] = str_app.text_area("Plan de maintenance préventive")
            elif nom_departement == "Recherche & Développement":
                champs_specifiques["projet"] = str_app.text_input("Nom du prototype / Projet R&D")
                champs_specifiques["trl"] = str_app.slider("Niveau de maturité (TRL 1 à 9)", 1, 9, 3)
                champs_specifiques["details"] = str_app.text_area("Résultats de laboratoire et protocoles")
            elif nom_departement == "Sécurité & HSE":
                champs_specifiques["zone"] = str_app.text_input("Zone concernée par l'analyse des risques")
                champs_specifiques["criticite"] = str_app.selectbox("Criticité", ["Faible", "Modéré", "Élevé", "Critique"])
                champs_specifiques["details"] = str_app.text_area("Mesures de prévention et procédures HSE")
            elif nom_departement == "Ressources Humaines & RSE":
                champs_specifiques["poste"] = str_app.text_input("Profils et compétences recherchés")
                champs_specifiques["etp"] = str_app.number_input("Nombre d'ETP prévisionnels", min_value=1, step=1)
                champs_specifiques["details"] = str_app.text_area("Plan d'intégration locale et critères RSE")
            elif nom_departement == "Commercial & Marketing":
                champs_specifiques["marche"] = str_app.text_input("Segment de marché ou secteur visé")
                champs_specifiques["volume"] = str_app.number_input("Volume potentiel estimé (€)", min_value=0.0, step=10000.0)
                champs_specifiques["details"] = str_app.text_area("Positionnement stratégique et offre")
            elif nom_departement == "IT & Data":
                champs_specifiques["archi"] = str_app.text_input("Composant infrastructure / Logiciel")
                champs_specifiques["stack"] = str_app.text_input("Technologies (ex: SIG, Cloud, API)")
                champs_specifiques["details"] = str_app.text_area("Politique de sécurité et gouvernance BIM")
            elif nom_departement == "Logistique":
                champs_specifiques["corridor"] = str_app.text_input("Intitulé du corridor logistique / Chaîne")
                champs_specifiques["stockage"] = str_app.number_input("Capacité de stockage requise", min_value=0.0, step=50.0)
                champs_specifiques["details"] = str_app.text_area("Spécifications transport et manutention lourde")
            else:
                champs_specifiques["details"] = str_app.text_area("Spécifications et notes d'ingénierie")

            fich_etude = str_app.file_uploader("📥 Importer un fichier technique (SIG, CAO, PDF, Excel, Image)", type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "csv", "dwg"])
            destinataires_partage = str_app.multiselect("🤝 Partager cette étude avec d'autres départements :", tous_les_depts)
            
            submit_etude = str_app.form_submit_button("Enregistrer et diffuser l'étude")
            
            if submit_etude and titre_etude:
                nom_fich_sauve = ""
                if fich_etude is not None:
                    nom_fich_sauve = f"etude_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fich_etude.name}"
                    chemin_complet = os.path.join(DOSSIER_ETUDES, nom_fich_sauve)
                    with open(chemin_complet, "wb") as f:
                        f.write(fich_etude.getbuffer())
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO etudes_metier (departement, titre, donnees_json, fichier_etude, destinataires_partage, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    nom_departement, titre_etude, json.dumps(champs_specifiques), nom_fich_sauve,
                    json.dumps(destinataires_partage), datetime.now().strftime("%Y-%m-%d %H:%M")
                ))
                conn.commit()
                conn.close()
                ajouter_log("Étude Métier", nom_departement, f"Création et partage: {titre_etude}")
                str_app.success("Étude enregistrée et partagée avec succès !")
                str_app.rerun()
            elif submit_etude:
                str_app.error("Veuillez renseigner au moins l'intitulé de l'étude.")

    with tab_consulter:
        str_app.markdown("### 📥 Études partagées par les autres départements")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier WHERE departement != ?", (nom_departement,))
        toutes_etudes = cursor.fetchall()
        conn.close()
        
        etudes_recues = []
        for e in toutes_etudes:
            e_id, e_dept, e_titre, e_json, e_fich, e_dest_json, e_date = e
            destinataires = json.loads(e_dest_json) if e_dest_json else []
            if nom_departement in destinataires:
                etudes_recues.append(e)

        if etudes_recues:
            for e in etudes_recues:
                e_id, e_dept, e_titre, e_json, e_fich, e_dest_json, e_date = e
                data_dict = json.loads(e_json) if e_json else {}
                
                with str_app.expander(f"📁 [{e_dept}] {e_titre} (Reçue le {e_date})"):
                    for k, v in data_dict.items():
                        str_app.write(f"**{k.capitalize()} :** {v}")
                    
                    if e_fich:
                        chemin_f = os.path.join(DOSSIER_ETUDES, e_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Télécharger le fichier technique joint", data=file_download, file_name=e_fich, key=f"dl_etude_{e_id}")
        else:
            str_app.info("Aucune étude partagée avec vous pour le moment.")


# ==========================================
# MODULE CAHIERS DES CHARGES (UNIVERSEL)
# ==========================================
def afficher_module_cahiers_charges(nom_departement):
    str_app.subheader("Cahiers des Charges & Documents Partagés")
    liste_tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    with str_app.form(f"form_cc_{nom_departement}", clear_on_submit=True):
        titre_doc = str_app.text_input("Intitulé du document")
        contenu_doc = str_app.text_area("Contenu détaillé")
        destinataires_avis = str_app.multiselect("Partager avec pour avis :", liste_tous_depts)
        
        if str_app.form_submit_button("Enregistrer et diffuser"):
            if titre_doc and contenu_doc:
                with str_app.spinner("Enregistrement..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis) VALUES (?, ?, ?, ?, ?)",
                        (nom_departement, titre_doc, contenu_doc, datetime.now().strftime("%Y-%m-%d"), json.dumps(destinataires_avis))
                    )
                    conn.commit()
                    conn.close()
                    ajouter_log("Cahier des Charges", nom_departement, f"Création: {titre_doc}")
                    str_app.success("Document enregistré avec succès !")
                    str_app.rerun()
            else:
                str_app.error("Veuillez renseigner le titre et le contenu du document.")
    
    str_app.markdown("### 📁 Mes documents")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement = ?", (nom_departement,))
    mes_docs = cursor.fetchall()
    conn.close()
    
    if mes_docs:
        for doc in mes_docs:
            doc_id, doc_titre, doc_contenu, doc_date, doc_dest_json = doc
            destinataires = json.loads(doc_dest_json) if doc_dest_json else []
            partages = ", ".join(destinataires) if destinataires else "Interne"
            
            with str_app.expander(f"Doc #{doc_id} : {doc_titre} (Partagé avec : {partages})"):
                str_app.write(doc_contenu)
                pdf_io = generer_pdf(f"Cahier des Charges\n{doc_titre}", doc_contenu, f"Émetteur: {nom_departement}\nDate: {doc_date}")
                colA, colB = str_app.columns([1,1])
                colA.download_button("📥 Télécharger PDF", data=pdf_io, file_name=f"cc_{doc_id}.pdf", mime="application/pdf", key=f"pdf_{nom_departement}_{doc_id}")
                if colB.button("🗑️ Supprimer", key=f"del_cc_{nom_departement}_{doc_id}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cahiers_charges WHERE id = ?", (doc_id,))
                    conn.commit()
                    conn.close()
                    str_app.success("Document supprimé.")
                    str_app.rerun()

    str_app.markdown("### 📥 Documents reçus")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement != ?", (nom_departement,))
    autres_docs = cursor.fetchall()
    conn.close()
    
    for doc in autres_docs:
        doc_id, d_nom, doc_titre, doc_contenu, doc_date, doc_dest_json = doc
        destinataires = json.loads(doc_dest_json) if doc_dest_json else []
        if nom_departement in destinataires:
            with str_app.expander(f"📬 De [{d_nom}] : {doc_titre}"):
                str_app.write(doc_contenu)
                pdf_recu = generer_pdf(f"{doc_titre}", doc_contenu, f"Émetteur: {d_nom}")
                str_app.download_button("📥 Télécharger PDF", data=pdf_recu, file_name=f"recu_{doc_id}.pdf", mime="application/pdf", key=f"recu_{d_nom}_{doc_id}")


# ==========================================
# MODULE EXPRESSION DE BESOINS & SUIVI (AVEC FILTRES ET RECHERCHE)
# ==========================================
def afficher_module_expression_et_suivi(nom_departement):
    tab_besoin, tab_suivi = str_app.tabs(["1. Exprimer un Besoin", "2. Suivi de mes Demandes"])
    
    with tab_besoin:
        str_app.subheader("Nouvelle Expression de Besoin")
        with str_app.form("form_expr_besoin", clear_on_submit=True):
            titre_besoin = str_app.text_input("Intitulé de la demande")
            desc_besoin = str_app.text_area("Spécifications techniques / Justificatif")
            fournisseur_suggere = str_app.text_input("Fournisseur pressenti (optionnel)")
            fich_devis = str_app.file_uploader("📥 Joindre un devis/justificatif (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
            
            if str_app.form_submit_button("Transmettre aux Achats"):
                if titre_besoin and desc_besoin:
                    nom_fichier_sauve = ""
                    if fich_devis is not None:
                        nom_fichier_sauve = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{fich_devis.name}"
                        chemin_complet = os.path.join(DOSSIER_UPLOADS, nom_fichier_sauve)
                        with open(chemin_complet, "wb") as f:
                            f.write(fich_devis.getbuffer())
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        nom_departement, titre_besoin, desc_besoin, 0.0,
                        fournisseur_suggere if fournisseur_suggere else "À sourcer",
                        "En attente Achats", "achats", "En attente", "En attente", "",
                        datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_sauve
                    ))
                    conn.commit()
                    conn.close()
                    ajouter_log("Demande", nom_departement, f"Création: {titre_besoin}")
                    str_app.success("Besoin transmis avec succès !")
                else:
                    str_app.error("Veuillez remplir l'intitulé et les spécifications obligatoires.")

    with tab_suivi:
        str_app.subheader("Suivi et Gestion de mes Demandes")
        
        col_f1, col_f2 = str_app.columns(2)
        recherche_texte = col_f1.text_input("🔍 Rechercher dans mes demandes", "")
        filtre_statut = col_f2.selectbox("Filtrer par statut", ["Tous", "En attente", "Validé", "Refusé/Modifié"])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titre, cahier_charges, fournisseur, statut, motif_refus, fichier_devis FROM demandes WHERE departement = ?", (nom_departement,))
        mes_demandes = cursor.fetchall()
        conn.close()
        
        demandes_filtrees = []
        for d in mes_demandes:
            d_id, d_titre, d_cc, d_fourn, d_statut, d_motif, d_fich = d
            if recherche_texte.lower() not in d_titre.lower() and recherche_texte.lower() not in d_cc.lower():
                continue
            if filtre_statut == "En attente" and "attente" not in d_statut.lower():
                continue
            if filtre_statut == "Validé" and "validé" not in d_statut.lower() and "approuvé" not in d_statut.lower():
                continue
            if filtre_statut == "Refusé/Modifié" and "refus" not in d_statut.lower() and "modification" not in d_statut.lower():
                continue
            demandes_filtrees.append(d)

        if demandes_filtrees:
            for d in demandes_filtrees:
                d_id, d_titre, d_cc, d_fourn, d_statut, d_motif, d_fich = d
                badge_html = formater_badge_statut(d_statut)
                
                with str_app.expander(f"Demande #{d_id} : {d_titre} — {badge_html}", expanded=False):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.write(f"**Fournisseur :** {d_fourn}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Télécharger le document joint", data=file_download, file_name=d_fich, key=f"dl_fich_{d_id}")
                    
                    if d_motif:
                        str_app.error(f"❌ **Motif du retour / refus :** {d_motif}")
                    
                    if d_statut not in ["Approuvé et Signé", "Annulé par le département"]:
                        if str_app.button(f"🚫 Annuler cette demande #{d_id}", key=f"btn_annuler_{d_id}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE demandes SET statut = 'Annulé par le département', etape_actuelle = 'annule' WHERE id = ?", (d_id,))
                            conn.commit()
                            conn.close()
                            str_app.success("Demande annulée.")
                            str_app.rerun()

                    if "modification" in d_statut.lower():
                        str_app.info("Modifiez votre demande ci-dessous pour la soumettre à nouveau.")
                        with str_app.form(f"form_modif_{d_id}"):
                            nouveau_titre = str_app.text_input("Modifier l'intitulé", value=d_titre)
                            nouvelles_specs = str_app.text_area("Modifier les spécifications", value=d_cc)
                            nouveau_fournisseur = str_app.text_input("Modifier le fournisseur", value=d_fourn)
                            
                            if str_app.form_submit_button("Resoumettre aux Achats"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET titre = ?, cahier_charges = ?, fournisseur = ?, etape_actuelle = 'achats', avis_achats = 'En attente', statut = 'En attente Achats (Modifié)', motif_refus = ''
                                    WHERE id = ?
                                ''', (nouveau_titre, nouvelles_specs, nouveau_fournisseur, d_id))
                                conn.commit()
                                conn.close()
                                str_app.success("Demande mise à jour et relancée avec succès !")
                                str_app.rerun()
        else:
            str_app.info("Aucune demande ne correspond à vos critères.")


# ==========================================
# TABLEAU DE SUIVI GLOBAL (AVEC FILTRES)
# ==========================================
def afficher_suivi_global():
    if profil["type"] in ["achats", "finance", "fondateur"]:
        str_app.markdown("---")
        with str_app.expander("📊 **Tableau de Suivi Global de TOUTES les Demandes**"):
            conn = get_db_connection()
            df_global = pd.read_sql_query("SELECT id, departement, titre, montant, fournisseur, statut, date FROM demandes", conn)
            conn.close()
            
            if not df_global.empty:
                col_sg1, col_sg2 = str_app.columns(2)
                dept_filtre = col_sg1.selectbox("Filtrer par département", ["Tous"] + list(df_global["departement"].unique()))
                statut_filtre = col_sg2.selectbox("Filtrer par statut global", ["Tous"] + list(df_global["statut"].unique()))
                
                if dept_filtre != "Tous":
                    df_global = df_global[df_global["departement"] == dept_filtre]
                if statut_filtre != "Tous":
                    df_global = df_global[df_global["statut"] == statut_filtre]
                
                str_app.dataframe(df_global, use_container_width=True)
            else:
                str_app.info("Aucune demande enregistrée.")


# ==========================================
# ROUTAGE DES INTERFACES SELON LE RÔLE
# ==========================================

budget_global = get_valeur_globale("budget_global")
solde_restant = get_valeur_globale("solde_restant")

# 1. Départements Standards (DEP1 à DEP11)
if profil["type"] == "standard":
    tab1, tab2, tab3, tab4 = str_app.tabs(["1. Études & Ingénierie Métier", "2. Cahiers des Charges", "3. Besoins & Suivi", "4. Messagerie & Coordination"])
    with tab1:
        afficher_module_specifique_metier(nom_dept)
    with tab2:
        afficher_module_cahiers_charges(nom_dept)
    with tab3:
        afficher_module_expression_et_suivi(nom_dept)
    with tab4:
        afficher_module_messagerie_directe(nom_dept)
        str_app.markdown("---")
        afficher_espace_coordination_et_journal(nom_dept)

# 2. Département Achats (DEP12)
elif profil["type"] == "achats":
    tab_ach1, tab_ach2, tab_ach3, tab_ach4 = str_app.tabs(["1. Chiffrage & Sourcing", "2. Cahiers des Charges", "3. Messagerie Directe", "4. Coordination"])
    
    with tab_ach1:
        str_app.subheader("File d'attente - Achats & Approvisionnements")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, fournisseur, fichier_devis FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
        demandes_achats = cursor.fetchall()
        conn.close()
        
        if demandes_achats:
            for d in demandes_achats:
                d_id, d_dept, d_titre, d_cc, d_fourn, d_fich = d
                with str_app.expander(f"Besoin #{d_id} - {d_titre} (Émetteur : {d_dept})"):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.info(f"💡 **Fournisseur suggéré :** {d_fourn}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Consulter le devis joint", data=file_download, file_name=d_fich, key=f"dl_ach_{d_id}")
                    
                    with str_app.form(f"form_achats_{d_id}"):
                        fournisseur_choisi = str_app.text_input("Fournisseur retenu", value=d_fourn if d_fourn != "À sourcer" else "")
                        montant_chiffre = str_app.number_input("Montant exact (€)", min_value=0.0, step=100.0)
                        action_achats = str_app.radio("Décision", ["Valider & Transmettre Finance", "Refus définitif (Bloqué)", "Refusé avec demande de modification (vers Émetteur)"], key=f"a_achats_{d_id}")
                        motif = str_app.text_input("Motif obligatoire en cas de refus / modification")
                        
                        if str_app.form_submit_button("Valider la décision"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if "Valider" in action_achats and montant_chiffre > 0:
                                cursor.execute("UPDATE demandes SET fournisseur = ?, montant = ?, avis_achats = 'Validé', etape_actuelle = 'finance', statut = 'En attente Finance' WHERE id = ?", (fournisseur_choisi, montant_chiffre, d_id))
                                conn.commit()
                                conn.close()
                                str_app.success("Décision validée et transmise à la Finance !")
                                str_app.rerun()
                            else:
                                if not motif:
                                    str_app.error("Veuillez saisir un motif obligatoire pour valider ce choix.")
                                    conn.close()
                                else:
                                    etape_suivante = "bloque" if "définitif" in action_achats else "modification"
                                    statut_suivi = "Refusé par les Achats" if "définitif" in action_achats else "Refusé avec demande de modification"
                                    cursor.execute("UPDATE demandes SET avis_achats = 'Refusé', motif_refus = ?, etape_actuelle = ?, statut = ? WHERE id = ?", (motif, etape_suivante, statut_suivi, d_id))
                                    conn.commit()
                                    conn.close()
                                    str_app.success("Décision enregistrée.")
                                    str_app.rerun()
        else:
            str_app.info("Aucune demande en attente pour les Achats.")
            
    with tab_ach2:
        afficher_module_cahiers_charges(nom_dept)
    with tab_ach3:
        afficher_module_messagerie_directe(nom_dept)
    with tab_ach4:
        afficher_espace_coordination_et_journal(nom_dept)

    afficher_suivi_global()

# 3. Département Finance & Comptabilité (DEP13)
elif profil["type"] == "finance":
    str_app.subheader("Contrôle Budgétaire & Comptabilité")
    
    with str_app.expander("🔒 Afficher les indicateurs budgétaires (Confidentiel)"):
        col1, col2 = str_app.columns(2)
        col1.metric("Budget Global", f"{budget_global:,.2f} €")
        col2.metric("Solde Restant", f"{solde_restant:,.2f} €")
    
    tab_fin1, tab_fin2, tab_fin3, tab_fin4 = str_app.tabs(["1. Contrôle Budgétaire", "2. Cahiers des Charges", "3. Messagerie Directe", "4. Coordination"])
    
    with tab_fin1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, fichier_devis FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
        demandes_finance = cursor.fetchall()
        conn.close()
        
        if demandes_finance:
            for d in demandes_finance:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich = d
                with str_app.expander(f"Dossier #{d_id} - {d_titre} | Montant : {d_montant:,.2f} € (Émetteur : {d_dept})"):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.write(f"**Fournisseur validé :** {d_fourn}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Consulter le devis joint", data=file_download, file_name=d_fich, key=f"dl_fin_{d_id}")
                    
                    with str_app.form(f"form_finance_{d_id}"):
                        action_fin = str_app.radio("Décision budgétaire", [
                            "Valider & Transmettre Direction", 
                            "Refus définitif (Bloqué)", 
                            "Refusé avec demande de modification (vers Émetteur)"
                        ], key=f"a_fin_{d_id}")
                        motif_fin = str_app.text_input("Motif obligatoire en cas de refus / modification")
                        
                        if str_app.form_submit_button("Valider le contrôle budgétaire"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if "Valider" in action_fin:
                                if solde_restant >= d_montant:
                                    nouveau_solde = solde_restant - d_montant
                                    set_valeur_globale("solde_restant", nouveau_solde)
                                    cursor.execute("UPDATE demandes SET avis_finance = 'Validé', etape_actuelle = 'fondateur', statut = 'En attente Signature DG' WHERE id = ?", (d_id,))
                                    conn.commit()
                                    conn.close()
                                    str_app.success("Contrôle validé ! Transmis à la Direction Générale.")
                                    str_app.rerun()
                                else:
                                    str_app.error("Erreur : Solde budgétaire insuffisant pour couvrir cette demande !")
                                    conn.close()
                            else:
                                if not motif_fin:
                                    str_app.error("Veuillez saisir un motif.")
                                    conn.close()
                                else:
                                    etape_suivante = "bloque" if "définitif" in action_fin else "modification"
                                    statut_suivi = "Refusé par la Finance" if "définitif" in action_fin else "Refusé avec demande de modification"
                                    cursor.execute("UPDATE demandes SET avis_finance = 'Refusé', motif_refus = ?, etape_actuelle = ?, statut = ? WHERE id = ?", (motif_fin, etape_suivante, statut_suivi, d_id))
                                    conn.commit()
                                    conn.close()
                                    str_app.success("Décision enregistrée.")
                                    str_app.rerun()
        else:
            str_app.info("Aucun dossier en attente de contrôle budgétaire.")

    with tab_fin2:
        afficher_module_cahiers_charges(nom_dept)
    with tab_fin3:
        afficher_module_messagerie_directe(nom_dept)
    with tab_fin4:
        afficher_espace_coordination_et_journal(nom_dept)

    afficher_suivi_global()

# 4. Direction Générale (Fondateur)
elif profil["type"] == "fondateur":
    str_app.subheader("Pilotage Stratégique & Signature Exécutive")
    
    with str_app.expander("🔒 Afficher les indicateurs budgétaires (Confidentiel)"):
        col1, col2 = str_app.columns(2)
        col1.metric("Budget Global", f"{budget_global:,.2f} €")
        col2.metric("Solde Restant", f"{solde_restant:,.2f} €")
    
    tab_dg1, tab_dg2, tab_dg3 = str_app.tabs(["1. Signatures & Arbitrages", "2. Messagerie Directe", "3. Coordination"])
    
    with tab_dg1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, fichier_devis FROM demandes WHERE etape_actuelle = 'fondateur'")
        demandes_dg = cursor.fetchall()
        conn.close()
        
        if demandes_dg:
            str_app.markdown("### ✍️ Dossiers en attente de signature finale")
            for d in demandes_dg:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich = d
                with str_app.expander(f"Dossier DG #{d_id} - {d_titre} | Montant : {d_montant:,.2f} € (Émetteur : {d_dept})"):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.write(f"**Fournisseur :** {d_fourn}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Consulter le devis joint", data=file_download, file_name=d_fich, key=f"dl_dg_{d_id}")
                    
                    with str_app.form(f"form_dg_{d_id}"):
                        action_dg = str_app.radio("Décision de la Direction", ["Approuver et Signer", "Refuser le dossier"], key=f"a_dg_{d_id}")
                        motif_dg = str_app.text_input("Motif en cas de refus")
                        
                        if str_app.form_submit_button("Valider la décision de la Direction"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if "Approuver" in action_dg:
                                cursor.execute("UPDATE demandes SET statut = 'Approuvé et Signé', etape_actuelle = 'cloture' WHERE id = ?", (d_id,))
                                conn.commit()
                                conn.close()
                                str_app.success("Dossier approuvé et signé avec succès !")
                                str_app.rerun()
                            else:
                                if not motif_dg:
                                    str_app.error("Veuillez saisir un motif de refus.")
                                    conn.close()
                                else:
                                    nouveau_solde = solde_restant + d_montant
                                    set_valeur_globale("solde_restant", nouveau_solde)
                                    cursor.execute("UPDATE demandes SET statut = 'Refusé par la Direction', etape_actuelle = 'bloque', motif_refus = ? WHERE id = ?", (motif_dg, d_id))
                                    conn.commit()
                                    conn.close()
                                    str_app.success("Refus enregistré et budget restitué.")
                                    str_app.rerun()
        else:
            str_app.info("Aucun dossier en attente de signature exécutive.")

        afficher_suivi_global()

    with tab_dg2:
        afficher_module_messagerie_directe(nom_dept)
    with tab_dg3:
        afficher_espace_coordination_et_journal(nom_dept)
