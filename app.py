import sqlite3
import json
import os
import uuid
from datetime import datetime
import pandas as pd
import streamlit as st

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

# --- DOSSIERS DE STOCKAGE ---
DOSSIER_UPLOADS = "uploads_devis"
DOSSIER_ETUDES = "uploads_etudes"
os.makedirs(DOSSIER_UPLOADS, exist_ok=True)
os.makedirs(DOSSIER_ETUDES, exist_ok=True)

CHEMIN_LOGO = "logo.png"

# --- STYLE CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .stButton>button {
        border-radius: 8px; font-weight: 600; transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stButton>button:hover {
        transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 150, 255, 0.2); border-color: #1f6feb;
    }
    .badge-notification { background-color: #f85149; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
    
    .channel-header {
        background-color: #161b22; padding: 12px 18px; border-radius: 8px; 
        border-left: 4px solid #5b5fc7; margin-bottom: 15px;
    }
    .notif-card {
        background-color: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 10px; margin-bottom: 8px; cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)

# --- INITIALISATION ET MIGRATION SQLITE ---
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS cahiers_charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, contenu TEXT, date TEXT, destinataires_avis TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS discussions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nom_groupe TEXT, membres_json TEXT, createur TEXT, date_creation TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT, discussion_id INTEGER, expediteur TEXT, texte TEXT, date TEXT, lus_json TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, acteur TEXT, action TEXT, details TEXT
    )''')
    
    # Check migrations
    cursor.execute("PRAGMA table_info(demandes)")
    cols = [column[1] for column in cursor.fetchall()]
    if "retour_remarque" not in cols:
        cursor.execute("ALTER TABLE demandes ADD COLUMN retour_remarque TEXT DEFAULT ''")
    
    cursor.execute("SELECT value FROM global_store WHERE key = 'budget_global'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('budget_global', ?)", (str(10000000.0),))
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('solde_restant', ?)", (str(10000000.0),))
    
    conn.commit()
    conn.close()

init_db()

# --- UTILS DB & FICHIERS ---
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

def enregistrer_fichier_securise(dossier, fichier):
    if fichier is not None:
        ext = os.path.splitext(fichier.name)[1]
        nom_unique = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        chemin_complet = os.path.join(dossier, nom_unique)
        with open(chemin_complet, "wb") as f:
            f.write(fichier.getbuffer())
        return nom_unique
    return ""

# --- ROLES ET UTILISATEURS ---
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

# --- GESTION DE LA SESSION ---
if 'user_connecte' not in st.session_state:
    st.session_state.user_connecte = None
if 'tab_actif' not in st.session_state:
    st.session_state.tab_actif = 0
if 'discussion_active_id' not in st.session_state:
    st.session_state.discussion_active_id = None

# --- AUTHENTIFICATION ---
if os.path.exists(CHEMIN_LOGO):
    st.sidebar.image(CHEMIN_LOGO, use_column_width=True)
else:
    st.sidebar.markdown("## 🏢 Bureau d'Études")

st.sidebar.markdown("---")

if st.session_state.user_connecte is None:
    st.sidebar.subheader("Connexion Collaborateur")
    username = st.sidebar.text_input("Identifiant")
    password = st.sidebar.text_input("Mot de passe", type="password")
    
    if st.sidebar.button("Se connecter"):
        if username in UTILISATEURS and UTILISATEURS[username]["mdp"] == password:
            st.session_state.user_connecte = username
            ajouter_log("Connexion", UTILISATEURS[username]["nom"], "Connexion réussie")
            st.rerun()
        else:
            st.sidebar.error("Identifiant ou mot de passe incorrect.")
    st.stop()

user_key = st.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

st.sidebar.success(f"Connecté : **{profil['nom']}**")
st.sidebar.markdown("---")

if st.session_state.user_connecte == "fondateur":
    if st.sidebar.button("🔄 Reset Global de l'application"):
        budget_init = get_valeur_globale("budget_global")
        set_valeur_globale("solde_restant", budget_init)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM demandes")
        cursor.execute("DELETE FROM etudes_metier")
        cursor.execute("DELETE FROM cahiers_charges")
        cursor.execute("DELETE FROM discussions")
        cursor.execute("DELETE FROM messages_chat")
        cursor.execute("DELETE FROM logs_audit")
        conn.commit()
        conn.close()
        st.success("Réinitialisation terminée.")
        st.rerun()
    st.sidebar.markdown("---")

if st.sidebar.button("Se déconnecter"):
    st.session_state.user_connecte = None
    st.session_state.discussion_active_id = None
    st.rerun()

# --- CALCUL DES NOTIFICATIONS DE MESSAGERIE & DE DEMANDES ---
def obtenir_notifications_chat(dept_nom):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom_groupe, membres_json FROM discussions")
    discs = cursor.fetchall()
    
    notifs_chat = []
    for d_id, nom_g, membres_j in discs:
        membres = json.loads(membres_j)
        if dept_nom in membres:
            cursor.execute("SELECT expediteur, lus_json FROM messages_chat WHERE discussion_id = ?", (d_id,))
            msgs = cursor.fetchall()
            non_lus = 0
            for exp, lus_j in msgs:
                lus = json.loads(lus_j) if lus_j else []
                if exp != dept_nom and dept_nom not in lus:
                    non_lus += 1
            if non_lus > 0:
                notifs_chat.append({"disc_id": d_id, "nom": nom_g, "count": non_lus})
    conn.close()
    return notifs_chat

notifs_chat_list = obtenir_notifications_chat(nom_dept)
total_chat_notifs = sum(item["count"] for item in notifs_chat_list)

# Affichage Centre de Notification & Téléportation dans Sidebar
if total_chat_notifs > 0:
    st.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #f85149; text-align: center; margin-bottom: 10px;">
        <span style="font-size: 1.1rem;">🔔</span> <b style="color: #f85149;">Centre de Notifications</b><br>
        <span class="badge-notification">{total_chat_notifs} nouveau(x) message(s)</span>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar.expander("💬 Téléportation vers Discussion", expanded=True):
        for notif in notifs_chat_list:
            if st.button(f"👉 {notif['nom']} ({notif['count']} non lu(s))", key=f"notif_btn_{notif['disc_id']}"):
                st.session_state.discussion_active_id = notif['disc_id']
                st.session_state.tab_actif = 3  # Téléportation automatique vers l'onglet 4 (Messagerie)
                st.rerun()

st.title(f"Tableau de Bord - {profil['nom']}")

if profil["type"] in ["finance", "fondateur"]:
    b_total = get_valeur_globale("budget_global")
    b_solde = get_valeur_globale("solde_restant")
    c_b1, c_b2 = st.columns(2)
    c_b1.metric("Budget Global Allocated", f"{b_total:,.2f} €")
    c_b2.metric("Solde Restant Disponible", f"{b_solde:,.2f} €")

st.markdown("---")

# ==========================================
# 1. MODULE INGÉNIERIE & ÉTUDES MÉTIER
# ==========================================
def afficher_module_etudes(nom_departement, type_profil):
    st.subheader(f"⚙️ Centre d'Ingénierie & Traçabilité des Études — {nom_departement}")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    t1, t2, t3 = st.tabs(["1. Nouvelle Étude & Partage", "2. Études Reçues", "3. 📜 Historique"])
    
    with t1:
        with st.form(f"form_etude_{nom_departement}", clear_on_submit=True):
            titre = st.text_input("Intitulé de l'étude / Projet technique")
            details = st.text_area("Spécifications et notes d'ingénierie")
            fich = st.file_uploader("📥 Importer fichier technique", type=["pdf", "png", "jpg", "xlsx", "dwg"])
            destinataires = st.multiselect("🤝 Partager avec :", tous_depts)
            
            if st.form_submit_button("Enregistrer et diffuser") and titre:
                nom_f = enregistrer_fichier_securise(DOSSIER_ETUDES, fich)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO etudes_metier (departement, titre, donnees_json, fichier_etude, destinataires_partage, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nom_departement, titre, json.dumps({"details": details}), nom_f, json.dumps(destinataires), datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                conn.close()
                ajouter_log("Étude Métier", nom_departement, f"Étude créée: {titre}")
                st.success("Étude diffusée !")
                st.rerun()

    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier WHERE departement != ? ORDER BY id DESC", (nom_departement,))
        etudes = cursor.fetchall()
        conn.close()
        recus = [e for e in etudes if nom_departement in (json.loads(e[5]) if e[5] else []) or type_profil == "fondateur"]

        if recus:
            for e in recus:
                e_id, e_dept, e_titre, e_json, e_fich, _, e_date = e
                with st.expander(f"📁 [{e_dept}] {e_titre} ({e_date})"):
                    data = json.loads(e_json) if e_json else {}
                    st.write(f"**Description :** {data.get('details', '')}")
                    if e_fich:
                        chemin = os.path.join(DOSSIER_ETUDES, e_fich)
                        if os.path.exists(chemin):
                            with open(chemin, "rb") as f:
                                st.download_button("📥 Télécharger Fichier Joint", f, file_name=e_fich, key=f"dl_et_{e_id}")
        else:
            st.info("Aucune étude reçue.")

    with t3:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT id, departement, titre, date FROM etudes_metier ORDER BY id DESC" if type_profil == "fondateur" else "SELECT id, departement, titre, date FROM etudes_metier WHERE departement = ? ORDER BY id DESC"
        cursor.execute(query, () if type_profil == "fondateur" else (nom_departement,))
        mes_e = cursor.fetchall()
        conn.close()
        for me in mes_e:
            st.write(f"📜 **[{me[1]}] {me[2]}** — {me[3]}")

# ==========================================
# 2. MODULE CAHIERS DES CHARGES
# ==========================================
def afficher_module_cdc(nom_departement, type_profil):
    st.subheader("📋 Cahiers des Charges & Documents Partagés")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    t1, t2 = st.tabs(["1. Publier un Cahier des Charges", "2. Documents Reçus & Suivi"])
    with t1:
        with st.form("form_cdc"):
            titre = st.text_input("Intitulé du document")
            contenu = st.text_area("Contenu détaillé")
            fich = st.file_uploader("📎 Pièce jointe", type=["pdf", "xlsx", "docx"])
            dest = st.multiselect("Partager pour consultation :", tous_depts)
            if st.form_submit_button("Diffuser Document") and titre:
                f_name = enregistrer_fichier_securise(DOSSIER_UPLOADS, fich)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis) VALUES (?, ?, ?, ?, ?)",
                               (nom_departement, f"{titre}||{f_name}", contenu, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(dest)))
                conn.commit()
                conn.close()
                st.success("Document diffusé avec succès.")
                st.rerun()

    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges ORDER BY id DESC")
        cdcs = cursor.fetchall()
        conn.close()
        for c in cdcs:
            c_id, c_dept, c_titre_raw, c_txt, c_date, c_dest_raw = c
            dests = json.loads(c_dest_raw) if c_dest_raw else []
            if nom_departement in dests or c_dept == nom_departement or type_profil == "fondateur":
                parts = c_titre_raw.split("||")
                t_titre = parts[0]
                t_fich = parts[1] if len(parts) > 1 else ""
                with st.expander(f"📄 [{c_dept}] {t_titre} ({c_date})"):
                    st.write(c_txt)
                    if t_fich:
                        ch = os.path.join(DOSSIER_UPLOADS, t_fich)
                        if os.path.exists(ch):
                            with open(ch, "rb") as f:
                                st.download_button("📥 Télécharger pièce jointe", f, file_name=t_fich, key=f"dl_cdc_{c_id}")

# ==========================================
# 3. MODULE BESOINS & ACHATS
# ==========================================
def afficher_module_achats(nom_departement, type_profil):
    st.subheader("🛒 Gestion des Demandes d'Achat")
    t1, t2 = st.tabs(["1. Émettre / Corriger une Demande", "2. Suivi de mes demandes"])
    
    with t1:
        with st.form("form_demande_achat"):
            titre = st.text_input("Intitulé du besoin")
            desc = st.text_area("Description du besoin / Spécifications")
            montant = st.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
            fournisseur = st.text_input("Fournisseur proposé (Facultatif)")
            devis = st.file_uploader("📎 Importer devis", type=["pdf", "png", "jpg", "xlsx"])
            
            if st.form_submit_button("Soumettre la Demande") and titre and montant > 0:
                f_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, devis)
                etape = "finance" if type_profil == "achats" else "achats"
                statut = "En attente validation Finance" if type_profil == "achats" else "En attente validation Achats"
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nom_departement, titre, desc, montant, fournisseur, statut, etape, "Auto-validé" if type_profil == "achats" else "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), f_devis, ""))
                conn.commit()
                conn.close()
                st.success("Demande enregistrée dans le circuit de validation.")
                st.rerun()

    with t2:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM demandes WHERE departement = ? ORDER BY id DESC", conn, params=(nom_departement,))
        conn.close()
        if not df.empty:
            for _, r in df.iterrows():
                with st.expander(f"📌 #{r['id']} - {r['titre']} ({r['montant']} €) - Statut: {r['statut']}"):
                    st.write(f"**Description :** {r['cahier_charges']}")
                    if r.get('retour_remarque'):
                        st.warning(f"💬 Remarque de révision : {r['retour_remarque']}")
        else:
            st.info("Aucune demande émise.")

# ==========================================
# 4. MODULE MESSAGERIE & CHAT UNIFIÉ (AVEC GROUPES & NOTIFS)
# ==========================================
def afficher_module_messagerie_unifiee(nom_departement):
    st.subheader("💬 Hub de Discussion & Communication Directe")
    
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    col_groupes, col_chat = st.columns([1.1, 2.2])

    # 1. Sélection ou création des salons de discussion
    with col_groupes:
        st.markdown("#### 💬 Salons & Conversations")
        
        # Modal/Formulaire de création de nouveau groupe
        with st.expander("➕ Créer une nouvelle discussion", expanded=False):
            with st.form("form_nouveau_groupe"):
                membres_selectionnes = st.multiselect("Sélectionner les participants :", tous_depts)
                nom_groupe_custom = st.text_input("Nom du groupe (Facultatif)")
                
                if st.form_submit_button("Démarrer la discussion") and membres_selectionnes:
                    tous_membres = list(set(membres_selectionnes + [nom_departement]))
                    if not nom_groupe_custom:
                        nom_groupe_custom = ", ".join(membres_selectionnes[:2]) + ("..." if len(membres_selectionnes) > 2 else "")
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO discussions (nom_groupe, membres_json, createur, date_creation) VALUES (?, ?, ?, ?)",
                        (nom_groupe_custom, json.dumps(tous_membres), nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    nouveau_id = cursor.lastrowid
                    conn.commit()
                    conn.close()
                    st.session_state.discussion_active_id = nouveau_id
                    st.rerun()

        st.markdown("---")
        
        # Récupération de toutes les discussions de l'utilisateur avec badges de non-lus 🔴
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom_groupe, membres_json FROM discussions ORDER BY id DESC")
        toutes_discs = cursor.fetchall()
        
        discussions_utilisateur = []
        for d_id, nom_g, membres_j in toutes_discs:
            membres = json.loads(membres_j)
            if nom_departement in membres:
                # Compter les non lus
                cursor.execute("SELECT expediteur, lus_json FROM messages_chat WHERE discussion_id = ?", (d_id,))
                msgs = cursor.fetchall()
                nb_non_lus = 0
                for exp, lus_j in msgs:
                    lus = json.loads(lus_j) if lus_j else []
                    if exp != nom_departement and nom_departement not in lus:
                        nb_non_lus += 1
                
                label = f"{'🔴 ' + str(nb_non_lus) + ' ' if nb_non_lus > 0 else ''}{nom_g}"
                discussions_utilisateur.append((d_id, label, nom_g, nb_non_lus))

        conn.close()

        if discussions_utilisateur:
            if st.session_state.discussion_active_id is None:
                st.session_state.discussion_active_id = discussions_utilisateur[0][0]

            for d_id, label, nom_g, count in discussions_utilisateur:
                type_button = "primary" if st.session_state.discussion_active_id == d_id else "secondary"
                if st.button(label, key=f"btn_disc_{d_id}", use_container_width=True, type=type_button):
                    st.session_state.discussion_active_id = d_id
                    st.rerun()
        else:
            st.info("Aucune discussion active. Créez-en une ci-dessus !")

    # 2. Zone d'affichage du Chat
    with col_chat:
        if st.session_state.discussion_active_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT nom_groupe, membres_json FROM discussions WHERE id = ?", (st.session_state.discussion_active_id,))
            disc_info = cursor.fetchone()

            if disc_info:
                nom_g, membres_j = disc_info
                membres = json.loads(membres_j)

                # Header de conversation
                st.markdown(f"""
                <div class="channel-header">
                    <b style="font-size: 1.1rem; color: #ffffff;">👥 {nom_g}</b><br>
                    <small style="color: #8b949e;">Membres : {', '.join(membres)}</small>
                </div>
                """, unsafe_allow_html=True)

                # Marquer les messages comme LUS automatiquement lors de l'ouverture
                cursor.execute("SELECT id, expediteur, texte, date, lus_json FROM messages_chat WHERE discussion_id = ?", (st.session_state.discussion_active_id,))
                messages = cursor.fetchall()
                
                for m_id, exp, txt, dt, lus_j in messages:
                    lus = json.loads(lus_j) if lus_j else []
                    if nom_departement not in lus:
                        lus.append(nom_departement)
                        cursor.execute("UPDATE messages_chat SET lus_json = ? WHERE id = ?", (json.dumps(lus), m_id))
                conn.commit()

                # Conteneur des messages avec bulles native Streamlit
                chat_box = st.container(height=400)
                with chat_box:
                    if messages:
                        for m_id, exp, txt, dt, _ in messages:
                            is_me = (exp == nom_departement)
                            role = "user" if is_me else "assistant"
                            avatar = "👤" if is_me else "🏢"
                            
                            with st.chat_message(role, avatar=avatar):
                                st.markdown(f"**{exp}** <small style='color: #8b949e;'>({dt})</small>", unsafe_allow_html=True)
                                st.write(txt)
                    else:
                        st.info("Discussion démarrée. Envoyez le premier message !")

                # Zone de Saisie du Message
                prompt = st.chat_input("Votre message...")
                if prompt:
                    cursor.execute(
                        "INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json) VALUES (?, ?, ?, ?, ?)",
                        (st.session_state.discussion_active_id, nom_departement, prompt, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps([nom_departement]))
                    )
                    conn.commit()
                    conn.close()
                    st.rerun()
            conn.close()

# ==========================================
# 5. NOSTE MODULE : SUIVI GLOBAL POUR PÔLES DE CONTRÔLE
# ==========================================
def afficher_module_suivi_global_controle():
    st.subheader("📊 Pôle de Contrôle & Supervision Globale")
    
    conn = get_db_connection()
    df_demandes = pd.read_sql_query("SELECT * FROM demandes ORDER BY id DESC", conn)
    conn.close()

    if df_demandes.empty:
        st.info("Aucune donnée disponible dans le système pour le moment.")
        return

    # Indicateurs clés KPI (Haut de page)
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric("Total Demandes Émises", len(df_demandes))
    col_kpi2.metric("En Cours de Validation", len(df_demandes[df_demandes['statut'].str.contains("attente|Demande", case=False, na=False)]))
    col_kpi3.metric("Validées & Financées", len(df_demandes[df_demandes['statut'] == "Validé & Financé"]))
    col_kpi4.metric("Volume Cumulé (€)", f"{df_demandes['montant'].sum():,.2f} €")

    st.markdown("---")
    st.markdown("### 🔍 Filtres de Contrôle Détaillés")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        depts_dispos = ["Tous"] + list(df_demandes['departement'].unique())
        dept_filtre = st.selectbox("Filtrer par Département Émetteur :", depts_dispos)
    with col_f2:
        statuts_dispos = ["Tous"] + list(df_demandes['statut'].unique())
        statut_filtre = st.selectbox("Filtrer par Statut de validation :", statuts_dispos)

    # Filtrage dynamique
    df_filtré = df_demandes.copy()
    if dept_filtre != "Tous":
        df_filtré = df_filtré[df_filtré['departement'] == dept_filtre]
    if statut_filtre != "Tous":
        df_filtré = df_filtré[df_filtré['statut'] == statut_filtre]

    # Tableau interactif des demandes
    st.markdown("##### 📋 Table de Supervision Consolidée")
    st.dataframe(
        df_filtré[['id', 'date', 'departement', 'titre', 'montant', 'fournisseur', 'statut', 'etape_actuelle', 'avis_achats', 'avis_finance']],
        use_container_width=True,
        hide_index=True
    )

    # Détail d'une demande sélectionnée
    st.markdown("---")
    st.markdown("##### 🕵️ Inspection Approfondie d'un Dossier")
    demande_ids = df_filtré['id'].tolist()
    if demande_ids:
        selected_id = st.selectbox("Sélectionner l'ID de la demande à inspecter :", demande_ids)
        row_selected = df_filtré[df_filtré['id'] == selected_id].iloc[0]
        
        c_det1, c_det2 = st.columns(2)
        with c_det1:
            st.write(f"**Émetteur :** {row_selected['departement']}")
            st.write(f"**Montant :** {row_selected['montant']:,.2f} €")
            st.write(f"**Fournisseur :** {row_selected['fournisseur']}")
            st.write(f"**Date d'émission :** {row_selected['date']}")
        with c_det2:
            st.write(f"**Statut Actuel :** {row_selected['statut']}")
            st.write(f"**Avis Achats :** {row_selected['avis_achats']}")
            st.write(f"**Avis Finance :** {row_selected['avis_finance']}")
            if row_selected.get('retour_remarque'):
                st.warning(f"Note de révision : {row_selected['retour_remarque']}")

        st.info(f"**Description du Besoin :**\n{row_selected['cahier_charges']}")
        
        if row_selected.get('fichier_devis'):
            chemin = os.path.join(DOSSIER_UPLOADS, row_selected['fichier_devis'])
            if os.path.exists(chemin):
                with open(chemin, "rb") as f:
                    st.download_button("📥 Télécharger le Devis de Contrôle", f, file_name=row_selected['fichier_devis'], key=f"dl_ctrl_{selected_id}")

# ==========================================
# AGENCEMENT PRINCIPAL AVEC NAVIGATION DYNAMIQUE
# ==========================================
# Construction des onglets selon le rôle de l'utilisateur connecté
onglets_titres = [
    "1. Études & Ingénierie", 
    "2. Cahiers des Charges", 
    "3. Besoins & Achats", 
    "4. Messagerie & Chat"
]

# Les rôles de supervision bénéficient de l'onglet 5 de Suivi Global
if profil["type"] in ["achats", "finance", "fondateur"]:
    onglets_titres.append("📊 Pôle de Contrôle (Suivi Global)")

tabs_navigation = st.tabs(onglets_titres)

with tabs_navigation[0]:
    afficher_module_etudes(nom_dept, profil["type"])

with tabs_navigation[1]:
    afficher_module_cdc(nom_dept, profil["type"])

with tabs_navigation[2]:
    afficher_module_achats(nom_dept, profil["type"])

with tabs_navigation[3]:
    afficher_module_messagerie_unifiee(nom_dept)

if profil["type"] in ["achats", "finance", "fondateur"]:
    with tabs_navigation[4]:
        afficher_module_suivi_global_controle()
