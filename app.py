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

# --- STYLE CSS DESIGN & CORPORATE (SaaS Look + Badges & Textareas) ---
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
    .badge-notification {
        background-color: #f85149; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold;
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

# --- SYSTÈME DE CLOCHE DE NOTIFICATION GLOBALE ---
def compter_notifications_actives(dept_nom, type_profil):
    conn = get_db_connection()
    cursor = conn.cursor()
    total_notifs = 0
    
    cursor.execute("SELECT COUNT(*) FROM messages_directs WHERE destinataire = ?", (dept_nom,))
    res_msg = cursor.fetchone()
    if res_msg:
        total_notifs += res_msg[0]
        
    cursor.execute("SELECT destinataires_partage FROM etudes_metier WHERE departement != ?", (dept_nom,))
    toutes_etudes = cursor.fetchall()
    for e in toutes_etudes:
        dest_json = e[0]
        if dest_json:
            liste_dest = json.loads(dest_json)
            if dept_nom in liste_dest:
                total_notifs += 1

    if type_profil == "achats":
        cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
        res_ach = cursor.fetchone()
        if res_ach: total_notifs += res_ach[0]
    elif type_profil == "finance":
        cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
        res_fin = cursor.fetchone()
        if res_fin: total_notifs += res_fin[0]
    elif type_profil == "fondateur":
        cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'fondateur'")
        res_dg = cursor.fetchone()
        if res_dg: total_notifs += res_dg[0]
        
    conn.close()
    return total_notifs

nb_notifs = compter_notifications_actives(nom_dept, profil["type"])

if nb_notifs > 0:
    str_app.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #f85149; text-align: center; margin-bottom: 15px;">
        <span style="font-size: 1.2rem;">🔔</span> <b style="color: #f85149;">Centre de Notifications</b><br>
        <span class="badge-notification">{nb_notifs} élément(s) en attente</span>
    </div>
    """, unsafe_allow_html=True)
else:
    str_app.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #30363d; text-align: center; margin-bottom: 15px;">
        <span style="font-size: 1.2rem;">🔔</span> <span style="color: #8b949e; font-size: 0.9rem;">Aucune nouvelle notification</span>
    </div>
    """, unsafe_allow_html=True)

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
# MODULE MESSAGERIE DIRECTE MULTI-CIBLE & CHAT TEAMS
# ==========================================
def afficher_module_messagerie_directe(nom_departement):
    str_app.subheader("📬 Messagerie Interdépartementale Directe")
    str_app.write("Échangez en temps réel avec un ou plusieurs départements dans un format de discussion fluide (Style Teams).")

    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    col_m1, col_m2 = str_app.columns([1, 1.2])

    with col_m1:
        str_app.markdown("### ✉️ Diffuser un message ciblé")
        with str_app.form(f"form_msg_direct_{nom_departement}", clear_on_submit=True):
            depts_choisis = str_app.multiselect(
                "Sélectionner les départements destinataires :", 
                tous_les_depts,
                help="Vous pouvez choisir plusieurs départements concernés par ce message."
            )
            texte_message = str_app.text_area("Contenu du message / Note technique", height=120)
            submit_direct = str_app.form_submit_button("🚀 Envoyer aux départements sélectionnés")

            if submit_direct and texte_message and depts_choisis:
                with str_app.spinner("Envoi en cours..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    for dest in depts_choisis:
                        cursor.execute(
                            "INSERT INTO messages_directs (expediteur, destinataire, texte, date) VALUES (?, ?, ?, ?)",
                            (nom_departement, dest, texte_message, datetime.now().strftime("%Y-%m-%d %H:%M"))
                        )
                    conn.commit()
                    conn.close()
                    
                    str_app.success(f"Message transmis avec succès à : {', '.join(depts_choisis)} !")
                    str_app.rerun()
            elif submit_direct:
                str_app.error("Veuillez choisir au moins un destinataire et saisir un message.")

    with col_m2:
        str_app.markdown("### 💬 Salon de Chat & Historique Privé")
        
        dept_chat_selectionne = str_app.selectbox(
            "Ouvrir une discussion avec :", 
            tous_les_depts, 
            key="select_chat_private"
        )

        if dept_chat_selectionne:
            str_app.markdown(f"#### 🗨️ Discussion avec **{dept_chat_selectionne}**")
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT expediteur, destinataire, texte, date 
                FROM messages_directs 
                WHERE (expediteur = ? AND destinataire = ?) 
                   OR (expediteur = ? AND destinataire = ?)
                ORDER BY id ASC
            """, (nom_departement, dept_chat_selectionne, dept_chat_selectionne, nom_departement))
            
            chat_messages = cursor.fetchall()
            conn.close()

            chat_box = str_app.container(height=350)
            with chat_box:
                if chat_messages:
                    for msg in chat_messages:
                        exp, dest, txt, dt = msg
                        is_me = (exp == nom_departement)
                        
                        alignement = "flex-end" if is_me else "flex-start"
                        couleur_bulle = "#1f6feb" if is_me else "#21262d"
                        couleur_texte = "#ffffff" if is_me else "#c9d1d9"
                        auteur_nom = "Vous" if is_me else exp

                        str_app.markdown(f"""
                        <div style="display: flex; justify-content: {alignement}; margin-bottom: 10px;">
                            <div style="background-color: {couleur_bulle}; padding: 10px 14px; border-radius: 12px; max-width: 80%; border: 1px solid rgba(255,255,255,0.1);">
                                <small style="color: #8b949e; font-size: 0.75rem;"><b>{auteur_nom}</b> • {dt}</small><br>
                                <span style="color: {couleur_texte}; font-size: 0.92rem; white-space: pre-wrap;">{txt}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    str_app.info(f"Aucun message échangé pour l'instant avec {dept_chat_selectionne}. Lancez la discussion !")

            with str_app.form(f"chat_reply_{dept_chat_selectionne}", clear_on_submit=True):
                reponse_rapide = str_app.text_input("Écrire un message direct...", placeholder="Tapez votre réponse ici...")
                btn_repondre = str_app.form_submit_button("Envoyer")

                if btn_repondre and reponse_rapide:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO messages_directs (expediteur, destinataire, texte, date) VALUES (?, ?, ?, ?)",
                        (nom_departement, dept_chat_selectionne, reponse_rapide, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    str_app.rerun()


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
                    <span style="color: #c9d1d9; font-size: 0.95rem; white-space: pre-wrap;">{m[1]}</span>
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
# MODULE CAHIERS DES CHARGES & DOCUMENTS
# ==========================================
def afficher_module_cahiers_charges(nom_departement):
    str_app.subheader("📋 Cahiers des Charges & Documents Partagés")
    str_app.write("Rédigez et déposez vos cahiers des charges avec pièces justificatives (devis, CDC PDF) et partagez-les pour avis.")

    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    tab_nouveau, tab_consultation = str_app.tabs(["1. Créer / Déposer un Cahier des Charges", "2. Documents reçus pour avis"])

    with tab_nouveau:
        with str_app.form(f"form_cdc_{nom_departement}", clear_on_submit=True):
            titre_cdc = str_app.text_input("Intitulé du document / Cahier des charges")
            contenu_cdc = str_app.text_area("Contenu détaillé / Spécifications requises", height=150)
            
            fichier_cdc = str_app.file_uploader(
                "📎 Joindre un devis justificatif ou document (PDF, Excel, Word, Image)", 
                type=["pdf", "xlsx", "xls", "docx", "png", "jpg", "jpeg"]
            )
            
            destinataires_avis = str_app.multiselect("Partager avec pour avis :", tous_les_depts)
            
            submit_cdc = str_app.form_submit_button("Enregistrer et diffuser")

            if submit_cdc and titre_cdc:
                nom_fich_cdc = ""
                if fichier_cdc is not None:
                    nom_fich_cdc = f"cdc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fichier_cdc.name}"
                    chemin_fich = os.path.join(DOSSIER_UPLOADS, nom_fich_cdc)
                    with open(chemin_fich, "wb") as f:
                        f.write(fichier_cdc.getbuffer())

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    nom_departement, 
                    f"{titre_cdc}||{nom_fich_cdc}",
                    contenu_cdc, 
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    json.dumps(destinataires_avis)
                ))
                conn.commit()
                conn.close()

                ajouter_log("Cahier des Charges", nom_departement, f"Publication : {titre_cdc}")
                str_app.success("Cahier des charges et pièces jointes enregistrés avec succès !")
                str_app.rerun()

    with tab_consultation:
        str_app.markdown("### 📬 Documents partagés avec vous")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement != ?", (nom_departement,))
        tous_cdc = cursor.fetchall()
        conn.close()

        cdc_recus = []
        for c in tous_cdc:
            c_id, c_dept, c_titre_complet, c_txt, c_date, c_dest_json = c
            dest_list = json.loads(c_dest_json) if c_dest_json else []
            if nom_departement in dest_list:
                cdc_recus.append(c)

        if cdc_recus:
            for c in cdc_recus:
                c_id, c_dept, c_titre_complet, c_txt, c_date, c_dest_json = c
                
                parts = c_titre_complet.split("||")
                vrai_titre = parts[0]
                fichier_joint = parts[1] if len(parts) > 1 else ""

                with str_app.expander(f"📄 [{c_dept}] {vrai_titre} ({c_date})"):
                    str_app.write(c_txt)
                    
                    if fichier_joint:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, fichier_joint)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as fj:
                                str_app.download_button(
                                    "📥 Télécharger le devis / document justificatif joint", 
                                    data=fj, 
                                    file_name=fichier_joint, 
                                    key=f"dl_cdc_{c_id}"
                                )
        else:
            str_app.info("Aucun cahier des charges partagé avec votre département pour le moment.")


# ==========================================
# MODULES SPÉCIFIQUES DÉDIÉS AUX DÉPARTEMENTS
# ==========================================
def afficher_module_specifique_metier(nom_departement):
    str_app.subheader(f"⚙️ Centre d'Ingénierie & Études Métier — {nom_departement}")
    str_app.write("Créez vos études amont, importez vos fichiers techniques et partagez-les avec les départements concernés.")
    
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    tab_creer, tab_consulter = str_app.tabs(["1. Nouvelle Étude & Partage", "2. Études & Fichiers Partagés Reçus"])
    
    with tab_creer:
        with str_app.form(f"form_etude_{nom_departement}", clear_on_submit=True):
            titre_etude = str_app.text_input("Intitulé de l'étude / Projet technique")
            
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
                champs_specifiques["article"] = str_app.text_input("Référence article / Intitulé du stock ou matériel")
                champs_specifiques["stock_actuel"] = str_app.number_input("Capacité / Stock initial disponible", min_value=0.0, step=10.0)
                champs_specifiques["details"] = str_app.text_area("Spécifications d'entreposage, flux de manutention et gestion des stocks")
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
                    
                    str_app.markdown("---")
                    str_app.markdown("#### 💬 Avis techniques et commentaires")
                    
                    conn_c = get_db_connection()
                    cursor_c = conn_c.cursor()
                    cursor_c.execute("SELECT auteur, commentaire, date FROM commentaires_etudes WHERE etude_id = ? ORDER BY id ASC", (e_id,))
                    commentaires_liste = cursor_c.fetchall()
                    conn_c.close()
                    
                    if commentaires_liste:
                        for comm in commentaires_liste:
                            c_auteur, c_texte, c_date = comm
                            str_app.markdown(f"""
                            <div style="background-color: #161b22; padding: 10px; border-radius: 6px; border: 1px solid #30363d; margin-bottom: 6px;">
                                <small style="color: #8b949e;"><b>{c_auteur}</b> — {c_date}</small><br>
                                <span style="color: #c9d1d9; font-size: 0.9rem; white-space: pre-wrap;">{c_texte}</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        str_app.info("Aucun commentaire pour le moment.")
                    
                    with str_app.form(f"form_comm_{e_id}_{nom_departement}", clear_on_submit=True):
                        nouveau_comm = str_app.text_input("Ajouter une observation / avis technique")
                        submit_comm = str_app.form_submit_button("Publier l'avis")
                        if submit_comm and nouveau_comm:
                            conn_in = get_db_connection()
                            cursor_in = conn_in.cursor()
                            cursor_in.execute(
                                "INSERT INTO commentaires_etudes (etude_id, auteur, commentaire, date) VALUES (?, ?, ?, ?)",
                                (e_id, nom_departement, nouveau_comm, datetime.now().strftime("%Y-%m-%d %H:%M"))
                            )
                            conn_in.commit()
                            conn_in.close()
                            str_app.success("Commentaire ajouté !")
                            str_app.rerun()
        else:
            str_app.info("Aucune étude partagée directement avec votre département pour le moment.")


# ==========================================
# GESTION PRINCIPALE DE L'INTERFACE (ONGLETS)
# ==========================================
tabs_nav = str_app.tabs([
    "1. Études & Ingénierie Métier", 
    "2. Cahiers des Charges", 
    "3. Messagerie & Coordination"
])

with tabs_nav[0]:
    afficher_module_specifique_metier(nom_dept)

with tabs_nav[1]:
    afficher_module_cahiers_charges(nom_dept)

with tabs_nav[2]:
    afficher_module_messagerie_directe(nom_dept)
    str_app.markdown("---")
    afficher_espace_coordination_et_journal(nom_dept)
