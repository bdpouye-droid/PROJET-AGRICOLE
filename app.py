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

# --- BARRE LATÉRALE DE CONNEXION ---
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

# Affichage des métriques budgétaires pour tous
b_total = get_valeur_globale("budget_global")
b_solde = get_valeur_globale("solde_restant")
col_b1, col_b2 = str_app.columns(2)
col_b1.metric("Budget Global Allocation", f"{b_total:,.2f} €")
col_b2.metric("Solde Disponible", f"{b_solde:,.2f} €")

str_app.markdown("---")

# ==========================================
# 1. MODULE INGÉNIERIE & ÉTUDES MÉTIER
# ==========================================
def afficher_module_specifique_metier(nom_departement):
    str_app.subheader(f"⚙️ Centre d'Ingénierie & Études Métier — {nom_departement}")
    
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    tab_creer, tab_consulter = str_app.tabs(["1. Nouvelle Étude & Partage", "2. Études & Fichiers Partagés Reçus"])
    
    with tab_creer:
        with str_app.form(f"form_etude_{nom_departement}", clear_on_submit=True):
            titre_etude = str_app.text_input("Intitulé de l'étude / Projet technique")
            
            champs_specifiques = {}
            if nom_departement == "Agriculture":
                champs_specifiques["culture"] = str_app.text_input("Type de culture / Spéculation")
                champs_specifiques["surface"] = str_app.number_input("Surface prévisionnelle (ha)", min_value=0.0, step=10.0)
                champs_specifiques["details"] = str_app.text_area("Paramètres pédologiques et contraintes climatiques")
            elif nom_departement == "Élevage & Halieutique":
                champs_specifiques["filiere"] = str_app.selectbox("Filière", ["Bovins", "Petits Ruminants", "Aviculture", "Aquaculture / Halieutique"])
                champs_specifiques["effectif"] = str_app.number_input("Effectif cible / Volume", min_value=1, step=10)
                champs_specifiques["details"] = str_app.text_area("Spécifications nutritionnelles et infrastructures")
            elif nom_departement == "Ressources Humaines & RSE":
                champs_specifiques["poste"] = str_app.text_input("Profils et compétences recherchés")
                champs_specifiques["etp"] = str_app.number_input("Nombre d'ETP prévisionnels", min_value=1, step=1)
                champs_specifiques["details"] = str_app.text_area("Plan d'intégration locale et critères RSE")
            elif nom_departement == "Logistique":
                champs_specifiques["article"] = str_app.text_input("Référence article / Stock ou matériel")
                champs_specifiques["stock_actuel"] = str_app.number_input("Capacité / Stock initial", min_value=0.0, step=10.0)
                champs_specifiques["details"] = str_app.text_area("Spécifications d'entreposage et flux")
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
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier WHERE departement != ?", (nom_departement,))
        toutes_etudes = cursor.fetchall()
        conn.close()
        
        etudes_recues = []
        for e in toutes_etudes:
            destinataires = json.loads(e[5]) if e[5] else []
            if nom_departement in destinataires:
                etudes_recues.append(e)

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
                            str_app.markdown(f"**{comm[0]}** ({comm[2]}) : {comm[1]}")
                    
                    with str_app.form(f"form_comm_{e_id}_{nom_departement}", clear_on_submit=True):
                        nouveau_comm = str_app.text_input("Ajouter une observation")
                        if str_app.form_submit_button("Publier l'avis") and nouveau_comm:
                            conn_in = get_db_connection()
                            cursor_in = conn_in.cursor()
                            cursor_in.execute(
                                "INSERT INTO commentaires_etudes (etude_id, auteur, commentaire, date) VALUES (?, ?, ?, ?)",
                                (e_id, nom_departement, nouveau_comm, datetime.now().strftime("%Y-%m-%d %H:%M"))
                            )
                            conn_in.commit()
                            conn_in.close()
                            str_app.rerun()
        else:
            str_app.info("Aucune étude partagée directement avec votre département.")

# ==========================================
# 2. MODULE CAHIERS DES CHARGES
# ==========================================
def afficher_module_cahiers_charges(nom_departement):
    str_app.subheader("📋 Cahiers des Charges & Documents Partagés")
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    tab_nouveau, tab_consultation = str_app.tabs(["1. Créer / Déposer un Cahier des Charges", "2. Documents reçus pour avis"])

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

        cdc_recus = [c for c in tous_cdc if nom_departement in (json.loads(c[5]) if c[5] else [])]

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
                                str_app.download_button("📥 Télécharger la pièce jointe / devis", data=fj, file_name=fichier_joint, key=f"dl_cdc_{c_id}")
        else:
            str_app.info("Aucun cahier des charges partagé avec votre département.")

# ==========================================
# 3. MODULE BESOINS & SUIVI (WORKFLOW ACHATS/FINANCE)
# ==========================================
def afficher_module_besoins_et_suivi(nom_departement, type_profil):
    str_app.subheader("🛒 Gestion des Demandes d'Achat & Validation Budgétaire")

    tab_creer, tab_suivi, tab_validation = str_app.tabs([
        "1. Émettre une Demande d'Achat", 
        "2. Suivi de vos Demandes", 
        "3. Espace de Validation (Achats / Finance / DG)"
    ])

    with tab_creer:
        with str_app.form(f"form_demande_{nom_departement}", clear_on_submit=True):
            titre = str_app.text_input("Intitulé du besoin / équipement")
            cahier_charges = str_app.text_area("Description synthétique de la demande")
            montant = str_app.number_input("Montant estimé ou devis (€)", min_value=0.0, step=100.0)
            fournisseur = str_app.text_input("Fournisseur pressenti (Optionnel)")
            fichier_devis = str_app.file_uploader("📎 Devis officiel joint (PDF/Image)", type=["pdf", "png", "jpg", "jpeg", "xlsx"])

            if str_app.form_submit_button("🚀 Soumettre la demande d'achat") and titre and montant > 0:
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
                str_app.success("Demande transmise au Service Achats !")
                str_app.rerun()

    with tab_suivi:
        conn = get_db_connection()
        df_demandes = pd.read_sql_query("SELECT * FROM demandes WHERE departement = ? ORDER BY id DESC", conn, params=(nom_departement,))
        conn.close()

        if not df_demandes.empty:
            for _, row in df_demandes.iterrows():
                with str_app.expander(f"📌 #{row['id']} - {row['titre']} ({row['montant']} €)"):
                    str_app.write(f"**Statut actuel :** {row['statut']}")
                    str_app.write(f"**Description :** {row['cahier_charges']}")
                    str_app.write(f"**Avis Achats :** {row['avis_achats']} | **Avis Finance :** {row['avis_finance']}")
                    if row['motif_refus']:
                        str_app.error(f"Motif du refus : {row['motif_refus']}")
        else:
            str_app.info("Aucune demande d'achat enregistrée pour votre département.")

    with tab_validation:
        conn = get_db_connection()
        cursor = conn.cursor()

        if type_profil == "achats":
            str_app.markdown("### 🛒 Validations Achats")
            cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'achats'")
            demandes_achats = cursor.fetchall()

            if demandes_achats:
                for d in demandes_achats:
                    d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich = d
                    with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        str_app.write(f"**Description :** {d_cc}")
                        c1, c2 = str_app.columns(2)
                        with c1:
                            if str_app.button(f"✅ Valider & transmettre Finance #{d_id}"):
                                cursor.execute("UPDATE demandes SET avis_achats='Favorable', etape_actuelle='finance', statut='En attente validation Finance' WHERE id=?", (d_id,))
                                conn.commit()
                                str_app.rerun()
                        with c2:
                            motif = str_app.text_input(f"Motif refus #{d_id}")
                            if str_app.button(f"❌ Refuser #{d_id}"):
                                cursor.execute("UPDATE demandes SET statut='Refusé par Achats', avis_achats='Défavorable', motif_refus=? WHERE id=?", (motif, d_id))
                                conn.commit()
                                str_app.rerun()
            else:
                str_app.info("Aucune demande en attente côté Achats.")

        elif type_profil == "finance":
            str_app.markdown("### 💶 Validations Finance")
            cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'finance'")
            demandes_fin = cursor.fetchall()

            if demandes_fin:
                for d in demandes_fin:
                    d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich = d
                    with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        if str_app.button(f"✅ Approuver Financement #{d_id}"):
                            cursor.execute("UPDATE demandes SET avis_finance='Favorable', etape_actuelle='fondateur', statut='En attente arbitrage Direction' WHERE id=?", (d_id,))
                            conn.commit()
                            str_app.rerun()
            else:
                str_app.info("Aucune demande en attente côté Finance.")

        elif type_profil == "fondateur":
            str_app.markdown("### 👑 Validations Stratégiques Direction Générale")
            cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'fondateur'")
            demandes_dg = cursor.fetchall()

            if demandes_dg:
                for d in demandes_dg:
                    d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_refus, d_date, d_fich = d
                    with str_app.expander(f"Demande #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        if str_app.button(f"🎉 APPROUVER ET LIBÉRER FONDS #{d_id}"):
                            solde = get_valeur_globale("solde_restant")
                            set_valeur_globale("solde_restant", solde - d_montant)
                            cursor.execute("UPDATE demandes SET statut='Validé & Financé', etape_actuelle='termine' WHERE id=?", (d_id,))
                            conn.commit()
                            ajouter_log("Validation DG", "Direction Générale", f"Validation finale demande #{d_id}")
                            str_app.rerun()
            else:
                str_app.info("Aucun arbitrage requis au niveau Direction.")
        else:
            str_app.info("Seuls les départements Achats, Finance et la Direction Générale gèrent cet espace.")
        
        conn.close()

# ==========================================
# 4. MODULE MESSAGERIE & CHAT TEAMS
# ==========================================
def afficher_module_messagerie_directe(nom_departement):
    str_app.subheader("📬 Messagerie Directe & Discussion Privée")
    tous_les_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    col_m1, col_m2 = str_app.columns([1, 1.2])

    with col_m1:
        str_app.markdown("### ✉️ Envoi Multi-Destinataires")
        with str_app.form(f"form_msg_direct_{nom_departement}", clear_on_submit=True):
            depts_choisis = str_app.multiselect("Sélectionner les départements cibles :", tous_les_depts)
            texte_message = str_app.text_area("Contenu du message", height=100)
            
            if str_app.form_submit_button("🚀 Envoyer aux départements") and texte_message and depts_choisis:
                conn = get_db_connection()
                cursor = conn.cursor()
                for dest in depts_choisis:
                    cursor.execute(
                        "INSERT INTO messages_directs (expediteur, destinataire, texte, date) VALUES (?, ?, ?, ?)",
                        (nom_departement, dest, texte_message, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                conn.commit()
                conn.close()
                str_app.success(f"Message transmis à : {', '.join(depts_choisis)}")
                str_app.rerun()

    with col_m2:
        str_app.markdown("### 💬 Salon de Discussion (Style Teams)")
        dept_chat = str_app.selectbox("Ouvrir le chat avec :", tous_les_depts, key="select_chat_private")

        if dept_chat:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT expediteur, destinataire, texte, date 
                FROM messages_directs 
                WHERE (expediteur = ? AND destinataire = ?) OR (expediteur = ? AND destinataire = ?)
                ORDER BY id ASC
            """, (nom_departement, dept_chat, dept_chat, nom_departement))
            chat_messages = cursor.fetchall()
            conn.close()

            chat_box = str_app.container(height=300)
            with chat_box:
                if chat_messages:
                    for msg in chat_messages:
                        exp, _, txt, dt = msg
                        is_me = (exp == nom_departement)
                        alignement = "flex-end" if is_me else "flex-start"
                        couleur_bulle = "#1f6feb" if is_me else "#21262d"
                        auteur_nom = "Vous" if is_me else exp

                        str_app.markdown(f"""
                        <div style="display: flex; justify-content: {alignement}; margin-bottom: 8px;">
                            <div style="background-color: {couleur_bulle}; padding: 8px 12px; border-radius: 10px; max-width: 80%;">
                                <small style="color: #8b949e;"><b>{auteur_nom}</b> • {dt}</small><br>
                                <span style="color: #ffffff; white-space: pre-wrap;">{txt}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    str_app.info(f"Aucune discussion encore entamée avec {dept_chat}.")

            with str_app.form(f"chat_reply_{dept_chat}", clear_on_submit=True):
                reponse = str_app.text_input("Écrire dans le chat...", placeholder="Votre message...")
                if str_app.form_submit_button("Envoyer") and reponse:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO messages_directs (expediteur, destinataire, texte, date) VALUES (?, ?, ?, ?)",
                        (nom_departement, dept_chat, reponse, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    str_app.rerun()

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
    afficher_module_specifique_metier(nom_dept)

with tabs_navigation[1]:
    afficher_module_cahiers_charges(nom_dept)

with tabs_navigation[2]:
    afficher_module_besoins_et_suivi(nom_dept, profil["type"])

with tabs_navigation[3]:
    afficher_module_messagerie_directe(nom_dept)
