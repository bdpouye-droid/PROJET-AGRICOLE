import sqlite3
import json
import os
from datetime import datetime
import pandas as pd
import streamlit as str_app
from streamlit_autorefresh import st_autorefresh

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

# --- STYLE CSS DESIGN CORPORATE & TEAMS ---
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
    .badge-notification { background-color: #f85149; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
    
    /* TEAMS CHAT DESIGN STYLES */
    .chat-bubble-me {
        background-color: #5b5fc7; color: #ffffff; padding: 10px 14px; border-radius: 12px 12px 2px 12px; margin-bottom: 6px; max-width: 80%; display: inline-block;
    }
    .chat-bubble-other {
        background-color: #292d3e; color: #e6edf3; padding: 10px 14px; border-radius: 12px 12px 12px 2px; margin-bottom: 6px; max-width: 80%; border: 1px solid #3b4252; display: inline-block;
    }
    .chat-avatar {
        width: 32px; height: 32px; border-radius: 50%; background-color: #464b5d; color: white; text-align: center; line-height: 32px; font-weight: bold; margin-right: 8px; display: inline-block; font-size: 0.85rem;
    }
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
        avis_finance TEXT, motif_refus TEXT, date TEXT, fichier_devis TEXT, retour_remarque TEXT
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages_directs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, expediteur TEXT, destinataire TEXT, texte TEXT, date TEXT, type_envoi TEXT DEFAULT 'direct'
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

# --- BARRE LATÉRALE ---
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
            cursor.execute("DELETE FROM messages_directs")
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

# --- NOTIFICATIONS GLOBALES ---
def compter_notifications_actives(dept_nom, type_profil):
    conn = get_db_connection()
    cursor = conn.cursor()
    total_notifs = 0
    
    cursor.execute("SELECT COUNT(*) FROM messages_directs WHERE destinataire = ?", (dept_nom,))
    res_msg = cursor.fetchone()
    if res_msg: total_notifs += res_msg[0]
        
    if type_profil == "achats":
        cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'achats'")
        res_ach = cursor.fetchone()
        if res_ach: total_notifs += res_ach[0]
    elif type_profil == "finance":
        cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'finance'")
        res_fin = cursor.fetchone()
        if res_fin: total_notifs += res_fin[0]
    elif type_profil == "fondateur":
        cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'fondateur'")
        res_dg = cursor.fetchone()
        if res_dg: total_notifs += res_dg[0]

    # Notifications pour les retours/modifications adressés au département émetteur
    cursor.execute("SELECT COUNT(*) FROM demandes WHERE departement = ? AND (etape_actuelle = 'emetteur_retour' OR etape_actuelle = 'achats_retour')", (dept_nom,))
    res_retours = cursor.fetchone()
    if res_retours: total_notifs += res_retours[0]

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

if profil["type"] in ["finance", "fondateur"]:
    b_total = get_valeur_globale("budget_global")
    b_solde = get_valeur_globale("solde_restant")
    col_b1, col_b2 = str_app.columns(2)
    col_b1.metric("Budget Global Allocation", f"{b_total:,.2f} €")
    col_b2.metric("Solde Disponible", f"{b_solde:,.2f} €")

str_app.markdown("---")

# ==========================================
# 1. MODULE INGÉNIERIE & ÉTUDES MÉTIER
# ==========================================
def afficher_module_specifique_metier(nom_departement, type_profil):
    str_app.subheader(f"⚙️ Centre d'Ingénierie & Traçabilité des Études — {nom_departement}")
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    tab_creer, tab_consulter, tab_historique = str_app.tabs([
        "1. Nouvelle Étude & Partage", 
        "2. Études Reçues des Autres Départements",
        "3. 📜 Traçabilité & Historique de vos Études"
    ])
    
    with tab_creer:
        with str_app.form(f"form_etude_{nom_departement}", clear_on_submit=True):
            titre_etude = str_app.text_input("Intitulé de l'étude / Projet technique")
            champs_specifiques = {}
            if nom_departement == "Agriculture":
                champs_specifiques["culture"] = str_app.text_input("Type de culture / Spéculation")
                champs_specifiques["surface"] = str_app.number_input("Surface prévisionnelle (ha)", min_value=0.0, step=10.0)
                champs_specifiques["details"] = str_app.text_area("Paramètres pédologiques et contraintes climatiques")
            else:
                champs_specifiques["details"] = str_app.text_area("Spécifications et notes d'ingénierie générale")

            fich_etude = str_app.file_uploader("📥 Importer un fichier technique (PDF, Excel, CAO, Image)", type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "csv", "dwg"])
            destinataires_partage = str_app.multiselect("🤝 Partager cette étude avec :", tous_les_depts)
            
            submit_etude = str_app.form_submit_button("Enregistrer et diffuser l'étude")
            
            if submit_etude and titre_etude:
                nom_fich_sauve = ""
                if fich_etude is not None:
                    nom_fich_sauve = f"etude_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fich_etude.name}"
                    with open(os.path.join(DOSSIER_ETUDES, nom_fich_sauve), "wb") as f:
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
                ajouter_log("Étude Métier", nom_departement, f"Création étude: {titre_etude}")
                str_app.success("Étude enregistrée et diffusée avec succès !")
                str_app.rerun()

    with tab_consulter:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier WHERE departement != ? ORDER BY id DESC", (nom_departement,))
        toutes_etudes = cursor.fetchall()
        conn.close()
        
        etudes_recues = [e for e in toutes_etudes if nom_departement in (json.loads(e[5]) if e[5] else []) or type_profil == "fondateur"]

        if etudes_recues:
            for e in etudes_recues:
                e_id, e_dept, e_titre, e_json, e_fich, _, e_date = e
                data_dict = json.loads(e_json) if e_json else {}
                
                with str_app.expander(f"📁 [{e_dept}] {e_titre} ({e_date})"):
                    for k, v in data_dict.items():
                        str_app.write(f"**{k.capitalize()} :** {v}")
                    if e_fich:
                        chemin_f = os.path.join(DOSSIER_ETUDES, e_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Télécharger le fichier technique joint", data=file_download, file_name=e_fich, key=f"dl_etude_recu_{e_id}")
        else:
            str_app.info("Aucune étude partagée directement avec votre département.")

    with tab_historique:
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier WHERE departement = ? ORDER BY id DESC", (nom_departement,))
        mes_etudes = cursor.fetchall()
        conn.close()

        if mes_etudes:
            for e in mes_etudes:
                e_id, e_dept, e_titre, e_json, e_fich, e_dest, e_date = e
                data_dict = json.loads(e_json) if e_json else {}
                dests_list = json.loads(e_dest) if e_dest else []
                prefixe_dept = f"[{e_dept}] " if type_profil == "fondateur" else ""

                with str_app.expander(f"📜 {prefixe_dept}{e_titre} — Déposé le {e_date}"):
                    str_app.markdown(f"**Partagé avec :** {', '.join(dests_list) if dests_list else 'Aucun'}")
                    for k, v in data_dict.items():
                        str_app.write(f"• **{k.capitalize()} :** {v}")
                    if e_fich:
                        chemin_f = os.path.join(DOSSIER_ETUDES, e_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Télécharger le fichier original joint", data=file_download, file_name=e_fich, key=f"dl_etude_hist_{e_id}")
        else:
            str_app.info("Aucune étude enregistrée dans l'historique.")

# ==========================================
# 2. MODULE CAHIERS DES CHARGES
# ==========================================
def afficher_module_cahiers_charges(nom_departement, type_profil):
    str_app.subheader("📋 Cahiers des Charges & Documents Partagés")
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    tab_nouveau, tab_consultation, tab_historique_cdc = str_app.tabs([
        "1. Créer / Déposer un Cahier des Charges", 
        "2. Documents reçus des autres pôles",
        "3. 📜 Traçabilité des Cahiers des Charges Émis"
    ])

    with tab_nouveau:
        with str_app.form(f"form_cdc_{nom_departement}", clear_on_submit=True):
            titre_cdc = str_app.text_input("Intitulé du document / Cahier des charges")
            contenu_cdc = str_app.text_area("Contenu détaillé", height=120)
            fichier_cdc = str_app.file_uploader("📎 Joindre devis ou CDC (PDF, Excel, Word)", type=["pdf", "xlsx", "xls", "docx", "png", "jpg"])
            destinataires_avis = str_app.multiselect("Partager avec pour avis :", tous_les_depts)
            
            if str_app.form_submit_button("Enregistrer et diffuser") and titre_cdc:
                nom_fich_cdc = ""
                if fichier_cdc is not None:
                    nom_fich_cdc = f"cdc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fichier_cdc.name}"
                    with open(os.path.join(DOSSIER_UPLOADS, nom_fich_cdc), "wb") as f:
                        f.write(fichier_cdc.getbuffer())

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    nom_departement, f"{titre_cdc}||{nom_fich_cdc}", contenu_cdc, 
                    datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(destinataires_avis)
                ))
                conn.commit()
                conn.close()
                ajouter_log("Cahier des Charges", nom_departement, f"CDC créé : {titre_cdc}")
                str_app.success("Document enregistré et diffusé !")
                str_app.rerun()

    with tab_consultation:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement != ?", (nom_departement,))
        tous_cdc = cursor.fetchall()
        conn.close()

        cdc_recus = [c for c in tous_cdc if nom_departement in (json.loads(c[5]) if c[5] else []) or type_profil == "fondateur"]

        if cdc_recus:
            for c in cdc_recus:
                c_id, c_dept, c_titre_complet, c_txt, c_date, _ = c
                parts = c_titre_complet.split("||")
                vrai_titre = parts[0]
                fichier_joint = parts[1] if len(parts) > 1 else ""

                with str_app.expander(f"📄 [{c_dept}] {vrai_titre} ({c_date})"):
                    str_app.write(c_txt)
                    if fichier_joint:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, fichier_joint)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as fj:
                                str_app.download_button("📥 Télécharger la pièce jointe / devis", data=fj, file_name=fichier_joint, key=f"dl_cdc_recu_{c_id}")
        else:
            str_app.info("Aucun cahier des charges partagé avec votre département.")

    with tab_historique_cdc:
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement = ? ORDER BY id DESC", (nom_departement,))
        mes_cdc = cursor.fetchall()
        conn.close()

        if mes_cdc:
            for c in mes_cdc:
                c_id, c_dept, c_titre_complet, c_txt, c_date, c_dest = c
                parts = c_titre_complet.split("||")
                vrai_titre = parts[0]
                fichier_joint = parts[1] if len(parts) > 1 else ""
                dests_list = json.loads(c_dest) if c_dest else []
                prefixe = f"[{c_dept}] " if type_profil == "fondateur" else ""

                with str_app.expander(f"📜 {prefixe}{vrai_titre} — Diffusé le {c_date}"):
                    str_app.markdown(f"**Envoyé à :** {', '.join(dests_list) if dests_list else 'Aucun'}")
                    str_app.markdown("##### 📌 Contenu du document :")
                    str_app.write(c_txt)
                    if fichier_joint:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, fichier_joint)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as fj:
                                str_app.download_button("📥 Télécharger le fichier joint original", data=fj, file_name=fichier_joint, key=f"dl_cdc_hist_{c_id}")
        else:
            str_app.info("Aucun cahier des charges émis pour le moment.")

# ==========================================
# 3. MODULE BESOINS & SUIVI (AVEC WORKFLOW COMPLET & RENVOI POUR MODIFICATION)
# ==========================================
def afficher_module_besoins_et_suivi(nom_departement, type_profil):
    str_app.subheader("🛒 Gestion des Demandes d'Achat")

    if type_profil in ["achats", "finance", "fondateur"]:
        tab_creer, tab_suivi, tab_validation = str_app.tabs([
            "1. Émettre une Demande d'Achat", 
            "2. Suivi de vos Demandes", 
            "3. Espace de Validation"
        ])
    else:
        tab_creer, tab_suivi = str_app.tabs([
            "1. Émettre une Demande d'Achat", 
            "2. Suivi de vos Demandes"
        ])
        tab_validation = None

    # 1. ÉMETTRE OU MODIFIER UNE DEMANDE
    with tab_creer:
        # Traitement spécial si des demandes sont renvoyées pour correction à cet émetteur ou aux achats
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if type_profil == "achats":
            cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'achats_retour'")
        else:
            cursor.execute("SELECT * FROM demandes WHERE departement = ? AND etape_actuelle = 'emetteur_retour'", (nom_departement,))
        demandes_a_corriger = cursor.fetchall()
        conn.close()

        if demandes_a_corriger:
            str_app.warning("⚠️ Vous avez des demandes nécessitant une correction ou un ajustement suite à un retour de la Finance / DG !")
            for d in demandes_a_corriger:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_ach, d_fin, d_refus, d_date, d_fich, d_retour = d
                with str_app.expander(f"🔴 Action Requise sur Demande #{d_id} : {d_titre}", expanded=True):
                    str_app.error(f"💬 Remarques du pôle de contrôle : {d_retour}")
                    
                    with str_app.form(f"form_corriger_{d_id}"):
                        nouveau_titre = str_app.text_input("Titre", value=d_titre)
                        nouveau_cc = str_app.text_area("Contenu révisé", value=d_cc)
                        nouveau_montant = str_app.number_input("Montant ajusté (€)", value=float(d_montant))
                        nouveau_fourn = str_app.text_input("Fournisseur", value=d_fourn if d_fourn else "")
                        nouveau_devis = str_app.file_uploader("Nouveau Devis (Optionnel)", type=["pdf", "png", "jpg", "xlsx"])

                        if str_app.form_submit_button("🔄 Renvoyer la demande corrigée"):
                            nom_d_fich = d_fich
                            if nouveau_devis is not None:
                                nom_d_fich = f"devis_rev_{datetime.now().strftime('%Y%m%d%H%M%S')}_{nouveau_devis.name}"
                                with open(os.path.join(DOSSIER_UPLOADS, nom_d_fich), "wb") as f:
                                    f.write(nouveau_devis.getbuffer())

                            conn_u = get_db_connection()
                            cur_u = conn_u.cursor()
                            
                            # Si c'est renvoyé par l'émetteur -> repart chez Achats (ou directement Finance si émis par Achats)
                            prochaine_etape = "finance" if type_profil == "achats" else "achats"
                            nouveau_statut = "En attente validation Finance (Corrigé)" if type_profil == "achats" else "En attente validation Achats (Corrigé)"

                            cur_u.execute("""
                                UPDATE demandes SET titre=?, cahier_charges=?, montant=?, fournisseur=?, fichier_devis=?, etape_actuelle=?, statut=? WHERE id=?
                            """, (nouveau_titre, nouveau_cc, nouveau_montant, nouveau_fourn, nom_d_fich, prochaine_etape, nouveau_statut, d_id))
                            conn_u.commit()
                            conn_u.close()
                            
                            ajouter_log("Correction Demande", nom_departement, f"Demande #{d_id} corrigée et renvoyée")
                            str_app.success("Demande révisée et remise dans le circuit de validation !")
                            str_app.rerun()

            str_app.markdown("---")

        str_app.markdown("### Émettre une nouvelle Demande d'Achat")
        with str_app.form(f"form_demande_{nom_departement}", clear_on_submit=True):
            titre = str_app.text_input("Intitulé du besoin / équipement")
            cahier_charges = str_app.text_area("Description synthétique / Contenu de la demande")
            montant = str_app.number_input("Montant estimé ou devis (€)", min_value=0.0, step=100.0)
            fournisseur = str_app.text_input("Fournisseur pressenti (Optionnel)")
            fichier_devis = str_app.file_uploader("📎 Devis officiel joint (PDF/Image/Excel)", type=["pdf", "png", "jpg", "jpeg", "xlsx"])

            if str_app.form_submit_button("🚀 Soumettre la demande d'achat") and titre and montant > 0:
                nom_devis = ""
                if fichier_devis is not None:
                    nom_devis = f"devis_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fichier_devis.name}"
                    with open(os.path.join(DOSSIER_UPLOADS, nom_devis), "wb") as f:
                        f.write(fichier_devis.getbuffer())

                if type_profil == "achats":
                    etape_initiale = "finance"
                    statut_initial = "En attente validation Finance"
                    avis_achats_init = "Auto-validé (Émis par Achats)"
                else:
                    etape_initiale = "achats"
                    statut_initial = "En attente validation Achats"
                    avis_achats_init = "En attente"

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nom_departement, titre, cahier_charges, montant, fournisseur,
                    statut_initial, etape_initiale, avis_achats_init, "En attente", "",
                    datetime.now().strftime("%Y-%m-%d %H:%M"), nom_devis, ""
                ))
                conn.commit()
                conn.close()

                ajouter_log("Demande Achat", nom_departement, f"Demande créée : {titre} - {montant}€")
                str_app.success("Demande soumise avec succès !")
                str_app.rerun()

    # 2. SUIVI DES DEMANDES
    with tab_suivi:
        conn = get_db_connection()
        df_demandes = pd.read_sql_query("SELECT * FROM demandes WHERE departement = ? ORDER BY id DESC", conn, params=(nom_departement,))
        conn.close()

        if not df_demandes.empty:
            for _, row in df_demandes.iterrows():
                with str_app.expander(f"📌 #{row['id']} - {row['titre']} ({row['montant']} €)"):
                    str_app.write(f"**Statut actuel :** {row['statut']}")
                    str_app.write(f"**Contenu / Description :** {row['cahier_charges']}")
                    str_app.write(f"**Fournisseur :** {row['fournisseur']}")
                    str_app.write(f"**Avis Achats :** {row['avis_achats']} | **Avis Finance :** {row['avis_finance']}")
                    if row['fichier_devis']:
                        chemin_d = os.path.join(DOSSIER_UPLOADS, row['fichier_devis'])
                        if os.path.exists(chemin_d):
                            with open(chemin_d, "rb") as fd:
                                str_app.download_button("📥 Consulter le devis joint", data=fd, file_name=row['fichier_devis'], key=f"dl_suivi_{row['id']}")
                    if row['retour_remarque']:
                        str_app.warning(f"💬 Demande de modification reçue : {row['retour_remarque']}")
                    if row['motif_refus']:
                        str_app.error(f"Motif du refus définitif : {row['motif_refus']}")
        else:
            str_app.info("Aucune demande d'achat enregistrée pour votre département.")

    # 3. ESPACE DE VALIDATION (AVEC OPTION DE RENVOI / DEMANDE DE MODIFICATION)
    if tab_validation is not None:
        with tab_validation:
            conn = get_db_connection()
            cursor = conn.cursor()

            def afficher_details_demande_et_devis(d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich):
                str_app.markdown(f"#### 📄 Demande #{d_id} : {d_titre} — Montant : **{d_montant:,.2f} €**")
                str_app.markdown(f"• **Département Émetteur :** {d_dept}")
                str_app.markdown(f"• **Fournisseur pressenti :** {d_fourn if d_fourn else 'Non spécifié'}")
                str_app.markdown("##### 📝 Contenu détaillé du besoin :")
                str_app.info(d_cc if d_cc else "Aucune description complémentaire fournie.")
                
                if d_fich:
                    chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                    if os.path.exists(chemin_f):
                        with open(chemin_f, "rb") as fd:
                            str_app.download_button("📥 Télécharger / Consulter le Devis", data=fd, file_name=d_fich, key=f"dl_val_{d_id}")

            # VALIDATION ACHATS
            if type_profil == "achats":
                str_app.markdown("### 🛒 Validations Achats")
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'achats'")
                demandes_achats = cursor.fetchall()

                if demandes_achats:
                    for d in demandes_achats:
                        d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich, d_retour = d
                        with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant:,.2f} €)"):
                            afficher_details_demande_et_devis(d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich)
                            str_app.markdown("---")
                            c1, c2, c3 = str_app.columns(3)
                            with c1:
                                if str_app.button(f"✅ Valider & Transmettre Finance #{d_id}"):
                                    cursor.execute("UPDATE demandes SET avis_achats='Favorable', etape_actuelle='finance', statut='En attente validation Finance' WHERE id=?", (d_id,))
                                    conn.commit()
                                    str_app.rerun()
                            with c2:
                                note_retour = str_app.text_input(f"Remarque modification #{d_id}", key=f"note_ach_{d_id}")
                                if str_app.button(f"↩️ Renvoyer à l'émetteur #{d_id}"):
                                    cursor.execute("UPDATE demandes SET statut='Demande modification (Achats)', etape_actuelle='emetteur_retour', retour_remarque=? WHERE id=?", (note_retour, d_id))
                                    conn.commit()
                                    str_app.rerun()
                            with c3:
                                motif = str_app.text_input(f"Motif refus #{d_id}", key=f"refus_ach_{d_id}")
                                if str_app.button(f"❌ Refuser définitivement #{d_id}"):
                                    cursor.execute("UPDATE demandes SET statut='Refusé par Achats', avis_achats='Défavorable', motif_refus=? WHERE id=?", (motif, d_id))
                                    conn.commit()
                                    str_app.rerun()
                else:
                    str_app.info("Aucune demande en attente côté Achats.")

            # VALIDATION FINANCE
            elif type_profil == "finance":
                str_app.markdown("### 💶 Validations Finance")
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'finance'")
                demandes_fin = cursor.fetchall()

                if demandes_fin:
                    for d in demandes_fin:
                        d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich, d_retour = d
                        with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant:,.2f} €)"):
                            afficher_details_demande_et_devis(d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich)
                            str_app.markdown(f"**Avis Achats :** `{d_achats}`")
                            str_app.markdown("---")
                            
                            col_f1, col_f2, col_f3 = str_app.columns(3)
                            with col_f1:
                                if str_app.button(f"✅ Approuver Financement #{d_id}"):
                                    cursor.execute("UPDATE demandes SET avis_finance='Favorable', etape_actuelle='fondateur', statut='En attente arbitrage Direction' WHERE id=?", (d_id,))
                                    conn.commit()
                                    str_app.rerun()
                            with col_f2:
                                dest_renvoi = str_app.radio(f"Renvoi pour modification #{d_id} à :", ["Émetteur", "Achats"], key=f"rad_fin_{d_id}")
                                note_fin = str_app.text_input(f"Instructions de correction #{d_id}", key=f"note_fin_{d_id}")
                                if str_app.button(f"↩️ Renvoyer pour correction #{d_id}"):
                                    target_etape = "emetteur_retour" if dest_renvoi == "Émetteur" else "achats_retour"
                                    cursor.execute("UPDATE demandes SET statut=?, etape_actuelle=?, retour_remarque=? WHERE id=?", (f"Demande modification par Finance ({dest_renvoi})", target_etape, note_fin, d_id))
                                    conn.commit()
                                    str_app.rerun()
                            with col_f3:
                                motif_f = str_app.text_input(f"Motif refus #{d_id}", key=f"refus_fin_{d_id}")
                                if str_app.button(f"❌ Refuser #{d_id}"):
                                    cursor.execute("UPDATE demandes SET statut='Refusé par Finance', avis_finance='Défavorable', motif_refus=? WHERE id=?", (motif_f, d_id))
                                    conn.commit()
                                    str_app.rerun()
                else:
                    str_app.info("Aucune demande en attente côté Finance.")

            # VALIDATION DIRECTION GÉNÉRALE
            elif type_profil == "fondateur":
                str_app.markdown("### 👑 Validations Stratégiques Direction Générale")
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'fondateur'")
                demandes_dg = cursor.fetchall()

                if demandes_dg:
                    for d in demandes_dg:
                        d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich, d_retour = d
                        with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant:,.2f} €)"):
                            afficher_details_demande_et_devis(d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich)
                            str_app.markdown(f"**Avis Achats :** `{d_achats}` | **Avis Finance :** `{d_fin}`")
                            str_app.markdown("---")
                            
                            col_d1, col_d2 = str_app.columns(2)
                            with col_d1:
                                if str_app.button(f"🎉 APPROUVER ET LIBÉRER FONDS #{d_id}"):
                                    solde = get_valeur_globale("solde_restant")
                                    set_valeur_globale("solde_restant", solde - d_montant)
                                    cursor.execute("UPDATE demandes SET statut='Validé & Financé', etape_actuelle='termine' WHERE id=?", (d_id,))
                                    conn.commit()
                                    ajouter_log("Validation DG", "Direction Générale", f"Validation finale demande #{d_id}")
                                    str_app.rerun()
                            with col_d2:
                                dest_dg = str_app.radio(f"Renvoir DG #{d_id} à :", ["Émetteur", "Achats"], key=f"rad_dg_{d_id}")
                                note_dg = str_app.text_input(f"Instructions DG #{d_id}", key=f"note_dg_{d_id}")
                                if str_app.button(f"↩️ Renvoyer dossier #{d_id}"):
                                    target_etape = "emetteur_retour" if dest_dg == "Émetteur" else "achats_retour"
                                    cursor.execute("UPDATE demandes SET statut=?, etape_actuelle=?, retour_remarque=? WHERE id=?", (f"Arbitrage DG : Correction requise ({dest_dg})", target_etape, note_dg, d_id))
                                    conn.commit()
                                    str_app.rerun()
                else:
                    str_app.info("Aucun arbitrage requis au niveau Direction.")
            
            conn.close()

# ==========================================
# 4. MODULE MESSAGERIE & CHAT (INTERFACE STYLE TEAMS + TRAÇABILITÉ MULTI-DESTINATAIRES)
# ==========================================
def afficher_module_messagerie_directe(nom_departement):
    str_app.subheader("💬 Hub de Communication & Discussions (Style Microsoft Teams)")
    
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    tab_teams, tab_multi_tracabilite = str_app.tabs([
        "💬 Salon de Chat & Canaux Privés",
        "📢 Diffusion Multi-Destinataires & Historique"
    ])

    # 1. INTERFACE DE CHAT STYLE TEAMS
    with tab_teams:
        col_sidebar_chat, col_canvas_chat = str_app.columns([1, 2.3])

        with col_sidebar_chat:
            str_app.markdown("#### 🗂️ Contacts & Canaux")
            dept_selectionne = str_app.radio(
                "Sélectionner une discussion :",
                tous_les_depts,
                key="teams_chat_dept_select"
            )

        with col_canvas_chat:
            if dept_selectionne:
                # Header du Chat Teams
                str_app.markdown(f"""
                <div style="background-color: #1f2430; padding: 12px 16px; border-radius: 8px; margin-bottom: 15px; border-bottom: 2px solid #5b5fc7;">
                    <span style="font-size: 1.2rem;">💬</span> <b style="font-size: 1.1rem; color: #ffffff;">{dept_selectionne}</b>
                    <small style="color: #8b949e; margin-left: 10px;">• Discussion directe sécurisée</small>
                </div>
                """, unsafe_allow_html=True)

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT expediteur, destinataire, texte, date 
                    FROM messages_directs 
                    WHERE ((expediteur = ? AND destinataire = ?) OR (expediteur = ? AND destinataire = ?))
                    AND type_envoi = 'direct'
                    ORDER BY id ASC
                """, (nom_departement, dept_selectionne, dept_selectionne, nom_departement))
                chat_messages = cursor.fetchall()
                conn.close()

                # Conteneur des messages de chat
                chat_container = str_app.container(height=380)
                with chat_container:
                    if chat_messages:
                        for msg in chat_messages:
                            exp, _, txt, dt = msg
                            is_me = (exp == nom_departement)
                            initiales = exp[:2].upper()

                            if is_me:
                                str_app.markdown(f"""
                                <div style="display: flex; justify-content: flex-end; align-items: flex-end; margin-bottom: 10px;">
                                    <div class="chat-bubble-me">
                                        <div style="font-size: 0.75rem; opacity: 0.8; margin-bottom: 4px;"><b>Vous</b> • {dt}</div>
                                        <div>{txt}</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                str_app.markdown(f"""
                                <div style="display: flex; justify-content: flex-start; align-items: flex-start; margin-bottom: 10px;">
                                    <div class="chat-avatar">{initiales}</div>
                                    <div class="chat-bubble-other">
                                        <div style="font-size: 0.75rem; color: #8b949e; margin-bottom: 4px;"><b>{exp}</b> • {dt}</div>
                                        <div>{txt}</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        str_app.info(f"Aucun message échangé pour le moment avec {dept_selectionne}.")

                # Zone de saisie moderne
                with str_app.form(f"form_send_teams_{dept_selectionne}", clear_on_submit=True):
                    c_txt, c_btn = str_app.columns([4, 1])
                    with c_txt:
                        msg_saisi = str_app.text_input("Tapez un message...", placeholder=f"Écrire à {dept_selectionne}...", label_visibility="collapsed")
                    with c_btn:
                        envoyer_msg = str_app.form_submit_button("Envoyer ✈️")

                    if envoyer_msg and msg_saisi:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO messages_directs (expediteur, destinataire, texte, date, type_envoi) VALUES (?, ?, ?, ?, 'direct')",
                            (nom_departement, dept_selectionne, msg_saisi, datetime.now().strftime("%Y-%m-%d %H:%M"))
                        )
                        conn.commit()
                        conn.close()
                        str_app.rerun()

    # 2. DIFFUSION MULTI-DESTINATAIRES & HISTORIQUE/TRAÇABILITÉ
    with tab_multi_tracabilite:
        col_m_send, col_m_hist = str_app.columns([1, 1.2])

        with col_m_send:
            str_app.markdown("### 📢 Nouvelle Diffusion Multi-Destinataires")
            with str_app.form(f"form_multi_send_{nom_departement}", clear_on_submit=True):
                depts_cibles = str_app.multiselect("Sélectionner les départements destinataires :", tous_les_depts)
                objet_comm = str_app.text_input("Objet / Contenu de la communication")
                
                if str_app.form_submit_button("🚀 Publier la diffusion") and objet_comm and depts_cibles:
                    target_str = ",".join(depts_cibles)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    # On enregistre une entrée globale de diffusion avec le tag multi
                    for dest in depts_cibles:
                        cursor.execute(
                            "INSERT INTO messages_directs (expediteur, destinataire, texte, date, type_envoi) VALUES (?, ?, ?, ?, ?)",
                            (nom_departement, dest, objet_comm, datetime.now().strftime("%Y-%m-%d %H:%M"), f"multi:{target_str}")
                        )
                    conn.commit()
                    conn.close()
                    ajouter_log("Diffusion Multi", nom_departement, f"Message envoyé à : {target_str}")
                    str_app.success(f"Diffusion transmise à {len(depts_cibles)} département(s) !")
                    str_app.rerun()

        with col_m_hist:
            str_app.markdown("### 📜 Registre & Traçabilité des Envois Groupés")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT texte, date, type_envoi 
                FROM messages_directs 
                WHERE expediteur = ? AND type_envoi LIKE 'multi:%'
                ORDER BY id DESC
            """, (nom_departement,))
            envois_groupes = cursor.fetchall()
            conn.close()

            if envois_groupes:
                for eg in envois_groupes:
                    txt, dt, t_envoi = eg
                    dests_recup = t_envoi.replace("multi:", "").split(",")
                    with str_app.expander(f"📢 Communication du {dt}"):
                        str_app.markdown(f"**Destinataires cibles :** {', '.join(dests_recup)}")
                        str_app.markdown("##### 📝 Message transmis :")
                        str_app.info(txt)
            else:
                str_app.info("Aucun envoi multi-destinataires effectué par votre département.")

# ==========================================
# AGENCEMENT FINAL DES 4 ONGLETS PRINCIPAUX
# ==========================================
tabs_navigation = str_app.tabs([
    "1. Études & Ingénierie Métier", 
    "2. Cahiers des Charges", 
    "3. Besoins & Suivi (Achats)", 
    "4. Messagerie & Coordination"
])

with tabs_navigation[0]:
    afficher_module_specifique_metier(nom_dept, profil["type"])

with tabs_navigation[1]:
    afficher_module_cahiers_charges(nom_dept, profil["type"])

with tabs_navigation[2]:
    afficher_module_besoins_et_suivi(nom_dept, profil["type"])

with tabs_navigation[3]:
    afficher_module_messagerie_directe(nom_dept)
