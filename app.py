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

# --- STYLE CSS DESIGN & CORPORATE ---
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
        white-space: pre-wrap;
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
        CREATE TABLE IF NOT EXISTS commentaires_etudes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            etude_id INTEGER,
            auteur TEXT,
            commentaire TEXT,
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
            canal TEXT,
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
            lu INTEGER DEFAULT 0,
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
        CREATE TABLE IF NOT EXISTS structuration_cadrage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre_hypothese TEXT,
            contenu_hypothese TEXT,
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

# --- DICTIONNAIRE DES UTILISATEURS & RÔLES ---
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
                cursor.execute("DELETE FROM commentaires_etudes")
                cursor.execute("DELETE FROM cahiers_charges")
                cursor.execute("DELETE FROM messages_coordination")
                cursor.execute("DELETE FROM messages_directs")
                cursor.execute("DELETE FROM journaux_bord")
                cursor.execute("DELETE FROM structuration_cadrage")
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

def formater_badge_statut(statut):
    statut_lower = statut.lower()
    if "validé" in statut_lower or "approuvé" in statut_lower:
        return f'<span class="badge-vert">🟢 {statut}</span>'
    elif "refusé" in statut_lower or "annulé" in statut_lower:
        return f'<span class="badge-rouge">🔴 {statut}</span>'
    else:
        return f'<span class="badge-orange">🟠 {statut}</span>'

# --- NAVIGATION PAR NOTIFICATIONS ---
if 'nav_cible' not in str_app.session_state:
    str_app.session_state.nav_cible = None

def recuperer_elements_notifications(dept_nom, type_profil):
    conn = get_db_connection()
    cursor = conn.cursor()
    liste_notifs = []
    
    cursor.execute("SELECT id, expediteur, texte, date FROM messages_directs WHERE destinataire = ? AND lu = 0 ORDER BY id DESC", (dept_nom,))
    for m in cursor.fetchall():
        liste_notifs.append({
            "type": "message",
            "titre": f"Message de {m[1]}",
            "desc": m[2][:50] + "...",
            "action_cle": f"msg_{m[0]}"
        })
        
    cursor.execute("SELECT id, departement, titre, destinataires_partage, date FROM etudes_metier WHERE departement != ?", (dept_nom,))
    for e in cursor.fetchall():
        dest_json = e[3]
        if dest_json:
            liste_dest = json.loads(dest_json)
            if dept_nom in liste_dest:
                liste_notifs.append({
                    "type": "etude",
                    "titre": f"Étude reçue : {e[2]}",
                    "desc": f"Émise par {e[1]}",
                    "action_cle": f"etude_{e[0]}"
                })

    if type_profil == "achats":
        cursor.execute("SELECT id, departement, titre FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
        for d in cursor.fetchall():
            liste_notifs.append({
                "type": "demande_achats",
                "titre": f"Demande d'achat : {d[2]}",
                "desc": f"Émise par {d[1]}",
                "action_cle": f"demande_{d[0]}"
            })
    elif type_profil == "finance":
        cursor.execute("SELECT id, departement, titre FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
        for d in cursor.fetchall():
            liste_notifs.append({
                "type": "demande_finance",
                "titre": f"Dossier financier : {d[2]}",
                "desc": f"Émis par {d[1]}",
                "action_cle": f"demande_{d[0]}"
            })
    elif type_profil == "fondateur":
        cursor.execute("SELECT id, departement, titre FROM demandes WHERE etape_actuelle = 'fondateur'")
        for d in cursor.fetchall():
            liste_notifs.append({
                "type": "demande_dg",
                "titre": f"Signature exécutive : {d[2]}",
                "desc": f"Émis par {d[1]}",
                "action_cle": f"demande_{d[0]}"
            })
            
    conn.close()
    return liste_notifs

items_notifs = recuperer_elements_notifications(nom_dept, profil["type"])
nb_notifs = len(items_notifs)

with str_app.sidebar.expander(f"🔔 Centre de Notifications ({nb_notifs})", expanded=(nb_notifs > 0)):
    if nb_notifs > 0:
        for idx, notif in enumerate(items_notifs):
            str_app.markdown(f"**{notif['titre']}**<br><small style='color: #8b949e;'>{notif['desc']}</small>", unsafe_allow_html=True)
            if str_app.button(f"🔍 Téléporter", key=f"btn_notif_{idx}_{notif['action_cle']}"):
                str_app.session_state.nav_cible = notif['action_cle']
                if notif['action_cle'].startswith("msg_"):
                    msg_id_num = notif['action_cle'].split("_")[1]
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE messages_directs SET lu = 1 WHERE id = ?", (msg_id_num,))
                    conn.commit()
                    conn.close()
                str_app.rerun()
            str_app.markdown("---")
    else:
        str_app.info("Aucune notification en attente.")

str_app.sidebar.markdown("---")

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

# --- MODULE MESSAGERIE TYPE TEAMS ---
def afficher_module_messagerie_directe(nom_departement):
    str_app.subheader("📬 Messagerie Interdépartementale (Structure style Teams)")
    
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    col_m1, col_m2 = str_app.columns([1, 1])
    
    with col_m1:
        str_app.markdown("### ✉️ Envoyer un message")
        with str_app.form(f"form_msg_direct_{nom_departement}", clear_on_submit=True):
            destinataire_choisi = str_app.selectbox("Destinataire", tous_les_depts)
            texte_message = str_app.text_area("Contenu du message")
            submit_direct = str_app.form_submit_button("Envoyer")
            
            if submit_direct and destinataire_choisi and texte_message:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages_directs (expediteur, destinataire, texte, lu, date) VALUES (?, ?, ?, 0, ?)",
                    (nom_departement, destinataire_choisi, texte_message, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                conn.close()
                str_app.success("Message envoyé !")
                str_app.rerun()

    with col_m2:
        str_app.markdown("### 💬 Canaux de Discussion")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, expediteur, destinataire, texte, date FROM messages_directs WHERE destinataire = ? OR expediteur = ? ORDER BY id DESC", (nom_departement, nom_departement))
        messages_tous = cursor.fetchall()
        conn.close()
        
        if messages_tous:
            for m in messages_tous:
                m_id, m_exp, m_dest, m_texte, m_date = m
                is_target = (str_app.session_state.nav_cible == f"msg_{m_id}")
                
                if m_dest == nom_departement:
                    badge_sens = f"📬 Reçu de **{m_exp}**"
                else:
                    badge_sens = f"📤 Envoyé à **{m_dest}**"
                
                str_app.markdown(f"""
                <div style="background-color: {'#1f2937' if is_target else '#161b22'}; padding: 10px; border-radius: 6px; border: 1px solid {'#1f6feb' if is_target else '#30363d'}; margin-bottom: 8px;">
                    <small style="color: #8b949e;">{badge_sens} — {m_date}</small><br>
                    <span style="color: #c9d1d9; font-size: 0.9rem; white-space: pre-wrap;">{m_texte}</span>
                </div>
                """, unsafe_allow_html=True)
                
                if is_target and str_app.button("Effacer la surbrillance", key=f"clear_msg_{m_id}"):
                    str_app.session_state.nav_cible = None
                    str_app.rerun()
        else:
            str_app.info("Aucun message.")

def afficher_espace_coordination_et_journal(nom_departement):
    with str_app.expander("💬 **Espace de Coordination Global (Canal Général)**"):
        with str_app.form(f"form_coord_{nom_departement}", clear_on_submit=True):
            texte_msg = str_app.text_input("Publier dans le canal général")
            if str_app.form_submit_button("Envoyer") and texte_msg:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages_coordination (canal, auteur, texte, date) VALUES ('general', ?, ?, ?)",
                    (nom_departement, texte_msg, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                conn.close()
                str_app.rerun()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT auteur, texte, date FROM messages_coordination ORDER BY id DESC")
        messages = cursor.fetchall()
        conn.close()
        for m in messages:
            str_app.markdown(f"<small><b>{m[0]}</b> — {m[2]}</small><br>{m[1]}<hr style='margin:5px 0;'>", unsafe_allow_html=True)

# --- MODULES MÉTIER & STRUCTURATION ---
def afficher_module_structuration(nom_departement):
    str_app.subheader(f"📐 Phase de Structuration & Cadrage Initial — {nom_departement}")
    with str_app.form(f"form_struct_{nom_departement}", clear_on_submit=True):
        titre_hyp = str_app.text_input("Intitulé de l'hypothèse")
        contenu_hyp = str_app.text_area("Description détaillée")
        if str_app.form_submit_button("Enregistrer") and titre_hyp and contenu_hyp:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO structuration_cadrage (departement, titre_hypothese, contenu_hypothese, date) VALUES (?, ?, ?, ?)",
                (nom_departement, titre_hyp, contenu_hyp, datetime.now().strftime("%Y-%m-%d"))
            )
            conn.commit()
            conn.close()
            str_app.success("Enregistré !")
            str_app.rerun()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT titre_hypothese, contenu_hypothese, date FROM structuration_cadrage WHERE departement = ?", (nom_departement,))
    for h in cursor.fetchall():
        str_app.markdown(f"**[{h[2]}] {h[0]}**<br>{h[1]}<hr>", unsafe_allow_html=True)
    conn.close()

def afficher_module_specifique_metier(nom_departement):
    str_app.subheader(f"⚙️ Centre d'Ingénierie & Études Métier — {nom_departement}")
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    tab_creer, tab_consulter = str_app.tabs(["1. Nouvelle Étude", "2. Études Reçues"])
    with tab_creer:
        with str_app.form(f"form_etude_{nom_departement}", clear_on_submit=True):
            titre_etude = str_app.text_input("Intitulé de l'étude")
            details = str_app.text_area("Détails")
            destinataires_partage = str_app.multiselect("Partager avec :", tous_les_depts)
            if str_app.form_submit_button("Diffuser") and titre_etude:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO etudes_metier (departement, titre, donnees_json, fichier_etude, destinataires_partage, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (nom_departement, titre_etude, json.dumps({"details": details}), "", json.dumps(destinataires_partage), datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                conn.close()
                str_app.success("Diffusé !")
                str_app.rerun()

    with tab_consulter:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, donnees_json, destinataires_partage, date FROM etudes_metier WHERE departement != ?", (nom_departement,))
        for e in cursor.fetchall():
            if nom_departement in json.loads(e[4] or "[]"):
                is_target = (str_app.session_state.nav_cible == f"etude_{e[0]}")
                with str_app.expander(f"📁 [{e[1]}] {e[2]}", expanded=is_target):
                    if is_target and str_app.button("Effacer la surbrillance", key=f"clear_etude_{e[0]}"):
                        str_app.session_state.nav_cible = None
                        str_app.rerun()
                    str_app.write(json.loads(e[3]).get("details", ""))
        conn.close()

def afficher_module_cahiers_charges(nom_departement):
    str_app.subheader("Cahiers des Charges")
    with str_app.form(f"form_cc_{nom_departement}", clear_on_submit=True):
        titre = str_app.text_input("Titre")
        contenu = str_app.text_area("Contenu")
        if str_app.form_submit_button("Créer") and titre:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis) VALUES (?, ?, ?, ?, '[]')", (nom_departement, titre, contenu, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            conn.close()
            str_app.rerun()

def afficher_module_expression_et_suivi(nom_departement):
    tab_besoin, tab_suivi = str_app.tabs(["1. Exprimer un Besoin", "2. Suivi"])
    with tab_besoin:
        with str_app.form("form_besoin", clear_on_submit=True):
            titre = str_app.text_input("Titre du besoin / Achat")
            desc = str_app.text_area("Description")
            montant_estime = str_app.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
            if str_app.form_submit_button("Transmettre") and titre:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis)
                    VALUES (?, ?, ?, ?, 'À sourcer', 'En attente Achats', 'achats', 'En attente', 'En attente', '', ?, '')
                ''', (nom_departement, titre, desc, montant_estime, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                conn.close()
                str_app.success("Transmis aux Achats !")
                str_app.rerun()
    with tab_suivi:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titre, statut, motif_refus FROM demandes WHERE departement = ?", (nom_departement,))
        for d in cursor.fetchall():
            is_target = (str_app.session_state.nav_cible == f"demande_{d[0]}")
            with str_app.expander(f"Demande #{d[0]} : {d[1]} - {d[2]}", expanded=is_target):
                if is_target and str_app.button("Effacer la surbrillance", key=f"clear_dem_{d[0]}"):
                    str_app.session_state.nav_cible = None
                    str_app.rerun()
                if d[3]:
                    str_app.error(f"Motif : {d[3]}")
        conn.close()

def afficher_suivi_global():
    if profil["type"] in ["achats", "finance", "fondateur"]:
        with str_app.expander("📊 **Suivi Global**"):
            conn = get_db_connection()
            df = pd.read_sql_query("SELECT id, departement, titre, montant, statut FROM demandes", conn)
            conn.close()
            str_app.dataframe(df, use_container_width=True)

# --- ROUTAGE ---
budget_global = get_valeur_globale("budget_global")
solde_restant = get_valeur_globale("solde_restant")

if profil["type"] == "standard":
    t1, t2, t3, t4, t5 = str_app.tabs(["Études", "Structuration", "Cahiers des charges", "Besoins & Suivi", "Messagerie"])
    with t1: afficher_module_specifique_metier(nom_dept)
    with t2: afficher_module_structuration(nom_dept)
    with t3: afficher_module_cahiers_charges(nom_dept)
    with t4: afficher_module_expression_et_suivi(nom_dept)
    with t5: afficher_module_messagerie_directe(nom_dept)

elif profil["type"] == "achats":
    t1, t2, t3 = str_app.tabs(["File Achats", "Messagerie", "Suivi Global"])
    with t1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
        for d in cursor.fetchall():
            is_target = (str_app.session_state.nav_cible == f"demande_{d[0]}")
            with str_app.expander(f"Demande #{d[0]} - {d[2]} (Par {d[1]})", expanded=is_target):
                if is_target and str_app.button("Effacer la surbrillance", key=f"clear_ach_{d[0]}"):
                    str_app.session_state.nav_cible = None
                    str_app.rerun()
                str_app.write(d[3])
                with str_app.form(f"f_ach_{d[0]}"):
                    montant_valide = str_app.number_input("Montant validé (€)", value=d[4], min_value=0.0)
                    if str_app.form_submit_button("Valider & Transmettre Finance"):
                        cursor.execute("UPDATE demandes SET montant = ?, avis_achats = 'Validé', etape_actuelle = 'finance', statut = 'En attente Finance' WHERE id = ?", (montant_valide, d[0]))
                        conn.commit()
                        str_app.rerun()
        conn.close()
    with t2: afficher_module_messagerie_directe(nom_dept)
    with t3: afficher_suivi_global()

elif profil["type"] == "finance":
    t1, t2, t3 = str_app.tabs(["Contrôle Budgétaire", "Messagerie", "Suivi Global"])
    with t1:
        str_app.metric("Solde Restant", f"{solde_restant:,.2f} €")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, montant FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
        for d in cursor.fetchall():
            is_target = (str_app.session_state.nav_cible == f"demande_{d[0]}")
            with str_app.expander(f"Dossier #{d[0]} - {d[2]} | {d[3]:,.2f} €", expanded=is_target):
                if is_target and str_app.button("Effacer la surbrillance", key=f"clear_fin_{d[0]}"):
                    str_app.session_state.nav_cible = None
                    str_app.rerun()
                if str_app.button("Valider & Transmettre Direction", key=f"val_fin_{d[0]}"):
                    if solde_restant >= d[3]:
                        set_valeur_globale("solde_restant", solde_restant - d[3])
                        cursor.execute("UPDATE demandes SET avis_finance = 'Validé', etape_actuelle = 'fondateur', statut = 'En attente Signature DG' WHERE id = ?", (d[0],))
                        conn.commit()
                        str_app.rerun()
                    else:
                        str_app.error("Solde insuffisant !")
        conn.close()
    with t2: afficher_module_messagerie_directe(nom_dept)
    with t3: afficher_suivi_global()

elif profil["type"] == "fondateur":
    str_app.subheader("Pilotage Stratégique, Achats & Signature Exécutive")
    t1, t2, t3, t4 = str_app.tabs(["1. Émettre un Achat / Besoin", "2. Signatures & Arbitrages", "3. Messagerie", "4. Suivi Global"])
    with t1:
        afficher_module_expression_et_suivi(nom_dept)
    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, montant FROM demandes WHERE etape_actuelle = 'fondateur'")
        for d in cursor.fetchall():
            is_target = (str_app.session_state.nav_cible == f"demande_{d[0]}")
            with str_app.expander(f"Dossier DG #{d[0]} - {d[2]} | {d[3]:,.2f} €", expanded=is_target):
                if is_target and str_app.button("Effacer la surbrillance", key=f"clear_dg_{d[0]}"):
                    str_app.session_state.nav_cible = None
                    str_app.rerun()
                if str_app.button("Approuver et Signer", key=f"app_dg_{d[0]}"):
                    cursor.execute("UPDATE demandes SET statut = 'Approuvé et Signé', etape_actuelle = 'cloture' WHERE id = ?", (d[0],))
                    conn.commit()
                    str_app.rerun()
        conn.close()
    with t3: afficher_module_messagerie_directe(nom_dept)
    with t4: afficher_suivi_global()
