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
    /* Masquer le sélecteur d'onglet natif pour forcer la téléportation synchrone */
    div[data-testid="stRadio"] > label { display: none; }
    div[data-testid="stRadio"] > div { flex-direction: row; justify-content: flex-start; gap: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- INITIALISATION BASE DE DONNÉES ---
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
    
    cursor.execute("SELECT value FROM global_store WHERE key = 'budget_global'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('budget_global', ?)", (str(10000000.0),))
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('solde_restant', ?)", (str(10000000.0),))
    
    conn.commit()
    conn.close()

init_db()

# --- UTILS DATABASE & FICHIERS ---
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
    st.session_state.tab_actif = "1. Études & Ingénierie"
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

# --- CALCUL DES NOTIFICATIONS MESSAGERIE ET TÉLÉPORTATION EFFECTIVE ---
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

if total_chat_notifs > 0:
    st.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #f85149; text-align: center; margin-bottom: 10px;">
        <span style="font-size: 1.1rem;">🔔</span> <b style="color: #f85149;">Centre de Notifications</b><br>
        <span class="badge-notification">{total_chat_notifs} message(s) non lu(s)</span>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar.expander("💬 Téléportation vers Discussion", expanded=True):
        for notif in notifs_chat_list:
            if st.button(f"👉 {notif['nom']} ({notif['count']} non lu(s))", key=f"notif_btn_{notif['disc_id']}"):
                st.session_state.discussion_active_id = notif['disc_id']
                st.session_state.tab_actif = "4. Messagerie & Chat"  # Redirection synchrone garantie
                st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("Se déconnecter"):
    st.session_state.user_connecte = None
    st.session_state.discussion_active_id = None
    st.rerun()

st.title(f"Tableau de Bord - {profil['nom']}")

if profil["type"] in ["finance", "fondateur"]:
    b_total = get_valeur_globale("budget_global")
    b_solde = get_valeur_globale("solde_restant")
    c_b1, c_b2 = st.columns(2)
    c_b1.metric("Budget Global Allocaté", f"{b_total:,.2f} €")
    c_b2.metric("Solde Restant Disponible", f"{b_solde:,.2f} €")

st.markdown("---")

# --- NAVIGATION PRINCIPALE SYNCHRONE ---
onglets_possibles = ["1. Études & Ingénierie", "2. Cahiers des Charges", "3. Besoins & Achats", "4. Messagerie & Chat"]
if profil["type"] in ["achats", "finance", "fondateur"]:
    onglets_possibles.append("📊 Pôle de Contrôle (Suivi Global)")

onglet_selectionne = st.radio(
    "Navigation", 
    onglets_possibles, 
    index=onglets_possibles.index(st.session_state.tab_actif) if st.session_state.tab_actif in onglets_possibles else 0,
    horizontal=True
)
st.session_state.tab_actif = onglet_selectionne

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
# 3. MODULE BESOINS & ACHATS (AVEC WORKFLOWS CROISÉS & RESSOUMISSION)
# ==========================================
def afficher_module_achats(nom_departement, type_profil):
    st.subheader("🛒 Gestion des Demandes d'Achat & Validations")
    
    t1, t2, t3 = st.tabs(["1. Émettre une Demande", "2. Suivi de mes Demandes & Corrections", "3. 🛡️ Espace de Validation"])
    
    # 1. ÉMISSION
    with t1:
        with st.form("form_demande_achat", clear_on_submit=True):
            titre = st.text_input("Intitulé du besoin")
            desc = st.text_area("Description du besoin / Spécifications")
            montant = st.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
            fournisseur = st.text_input("Fournisseur proposé (Facultatif)")
            devis = st.file_uploader("📎 Importer devis", type=["pdf", "png", "jpg", "xlsx"])
            
            if st.form_submit_button("Soumettre la Demande") and titre and montant > 0:
                f_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, devis)
                
                # Routage du circuit selon l'émetteur
                if type_profil == "finance":
                    etape = "achats"
                    statut = "En attente validation Achats"
                elif type_profil == "achats":
                    etape = "finance"
                    statut = "En attente validation Finance"
                else:
                    etape = "achats"
                    statut = "En attente validation Achats"

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nom_departement, titre, desc, montant, fournisseur, statut, etape, "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), f_devis, ""))
                conn.commit()
                conn.close()
                st.success("Demande enregistrée dans le circuit de validation.")
                st.rerun()

    # 2. SUIVI ET FORMULAIRE DE RESSOUMISSION / CORRECTION
    with t2:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM demandes WHERE departement = ? ORDER BY id DESC", conn, params=(nom_departement,))
        conn.close()
        
        if not df.empty:
            for _, r in df.iterrows():
                with st.expander(f"📌 #{r['id']} - {r['titre']} ({r['montant']} €) - Statut: {r['statut']}"):
                    st.write(f"**Description :** {r['cahier_charges']}")
                    
                    # Si demande de modification par le pôle de contrôle
                    if "Modification" in str(r['statut']):
                        st.warning(f"💬 Remarque du contrôleur : {r['retour_remarque']}")
                        st.markdown("##### ✏️ Soumettre la version corrigée")
                        
                        with st.form(f"form_corriger_{r['id']}"):
                            c_titre = st.text_input("Titre corrigé", value=r['titre'])
                            c_desc = st.text_area("Description corrigée", value=r['cahier_charges'])
                            c_montant = st.number_input("Nouveau montant (€)", value=float(r['montant']))
                            c_devis = st.file_uploader("Nouveau devis (laisser vide si inchangé)", type=["pdf", "png", "jpg", "xlsx"])
                            
                            if st.form_submit_button("Envoyer la correction"):
                                nom_f = r['fichier_devis']
                                if c_devis is not None:
                                    nom_f = enregistrer_fichier_securise(DOSSIER_UPLOADS, c_devis)
                                
                                # Ré-injection dans le circuit
                                nouv_etape = "achats" if type_profil != "achats" else "finance"
                                nouv_statut = f"En attente validation {nouv_etape.capitalize()} (Après correction)"
                                
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE demandes SET titre=?, cahier_charges=?, montant=?, fichier_devis=?, statut=?, etape_actuelle=?, retour_remarque='' WHERE id=?
                                """, (c_titre, c_desc, c_montant, nom_f, nouv_statut, nouv_etape, r['id']))
                                conn.commit()
                                conn.close()
                                st.success("Demande corrigée et renvoyée en validation !")
                                st.rerun()
        else:
            st.info("Aucune demande émise.")

    # 3. ESPACE DE VALIDATION (BOUTONS APPROUVER, MODIFIER, REFUSER)
    with t3:
        if type_profil not in ["achats", "finance", "fondateur"]:
            st.warning("Espace réservé aux pôles de validation (Achats, Finance, Direction).")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Filtre de la boîte de réception selon le rôle
            if type_profil == "achats":
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'achats' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
            elif type_profil == "finance":
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'finance' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
            else: # Direction générale
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'direction' OR statut LIKE 'En attente%'")
            
            demandes_a_traiter = cursor.fetchall()
            conn.close()

            if demandes_a_traiter:
                for d in demandes_a_traiter:
                    d_id, d_dept, d_titre, d_desc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_motif, d_date, d_fich, d_rem = d
                    
                    with st.expander(f"📥 Dossier #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        st.write(f"**Description :** {d_desc}")
                        st.write(f"**Fournisseur :** {d_fourn}")
                        
                        col_v1, col_v2, col_v3 = st.columns(3)
                        
                        # APPROUVER
                        with col_v1:
                            if st.button(f"🟢 Approuver #{d_id}", key=f"app_{d_id}"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                
                                # Circuit spécial Finance / Achats / Direction
                                if type_profil == "achats":
                                    prochaine = "direction" if d_dept == "Finance & Comptabilité" else "finance"
                                    st_msg = "En attente validation Direction" if prochaine == "direction" else "En attente validation Finance"
                                    cursor.execute("UPDATE demandes SET avis_achats='Approuvé', etape_actuelle=?, statut=? WHERE id=?", (prochaine, st_msg, d_id))
                                
                                elif type_profil == "finance":
                                    prochaine = "direction" if d_dept == "Achats & Approvisionnements" else "terminee"
                                    if prochaine == "terminee":
                                        cursor.execute("UPDATE demandes SET avis_finance='Approuvé', etape_actuelle='terminee', statut='Validé & Financé' WHERE id=?", (d_id,))
                                        solde = get_valeur_globale("solde_restant")
                                        set_valeur_globale("solde_restant", solde - d_montant)
                                    else:
                                        cursor.execute("UPDATE demandes SET avis_finance='Approuvé', etape_actuelle='direction', statut='En attente validation Direction' WHERE id=?", (d_id,))
                                
                                else: # Direction Générale
                                    cursor.execute("UPDATE demandes SET etape_actuelle='terminee', statut='Validé & Financé' WHERE id=?", (d_id,))
                                    solde = get_valeur_globale("solde_restant")
                                    set_valeur_globale("solde_restant", solde - d_montant)
                                
                                conn.commit()
                                conn.close()
                                st.success(f"Dossier #{d_id} approuvé !")
                                st.rerun()

                        # DEMANDER MODIFICATION
                        with col_v2:
                            remarque = st.text_input("Remarque d'ajustement", key=f"rem_{d_id}")
                            if st.button(f"🟡 Requis modification #{d_id}", key=f"mod_{d_id}") and remarque:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE demandes SET statut='Demande de Modification', etape_actuelle='emetteur', retour_remarque=? WHERE id=?", (remarque, d_id))
                                conn.commit()
                                conn.close()
                                st.warning("Demande renvoyée pour correction.")
                                st.rerun()

                        # REFUS DÉFINITIF
                        with col_v3:
                            motif = st.text_input("Motif du refus", key=f"mot_{d_id}")
                            if st.button(f"🔴 Refuser définitivement #{d_id}", key=f"ref_{d_id}") and motif:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE demandes SET statut='Refusé', etape_actuelle='terminee', motif_refus=? WHERE id=?", (motif, d_id))
                                conn.commit()
                                conn.close()
                                st.error("Dossier refusé.")
                                st.rerun()
            else:
                st.info("Aucune demande en attente de validation pour votre pôle.")

# ==========================================
# 4. MODULE MESSAGERIE & CHAT UNIFIÉ (AVEC PSEUDO TEMPS RÉEL PAR FRAGMENT)
# ==========================================
@st.fragment(run_every="3s")
def afficher_zone_messages(discussion_id, nom_dept):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, expediteur, texte, date, lus_json FROM messages_chat WHERE discussion_id = ?", (discussion_id,))
    messages = cursor.fetchall()
    
    # Marquer comme lu
    for m_id, exp, txt, dt, lus_j in messages:
        lus = json.loads(lus_j) if lus_j else []
        if nom_dept not in lus:
            lus.append(nom_dept)
            cursor.execute("UPDATE messages_chat SET lus_json = ? WHERE id = ?", (json.dumps(lus), m_id))
    conn.commit()

    chat_box = st.container(height=380)
    with chat_box:
        if messages:
            for m_id, exp, txt, dt, _ in messages:
                is_me = (exp == nom_dept)
                role = "user" if is_me else "assistant"
                avatar = "👤" if is_me else "🏢"
                with st.chat_message(role, avatar=avatar):
                    st.markdown(f"**{exp}** <small style='color: #8b949e;'>({dt})</small>", unsafe_allow_html=True)
                    st.write(txt)
        else:
            st.info("Discussion démarrée. Envoyez le premier message !")
    conn.close()

def afficher_module_messagerie_unifiee(nom_departement):
    st.subheader("💬 Hub de Discussion & Communication Directe")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    
    col_groupes, col_chat = st.columns([1.1, 2.2])

    with col_groupes:
        st.markdown("#### 💬 Salons & Conversations")
        
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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom_groupe, membres_json FROM discussions ORDER BY id DESC")
        toutes_discs = cursor.fetchall()
        
        discussions_utilisateur = []
        for d_id, nom_g, membres_j in toutes_discs:
            membres = json.loads(membres_j)
            if nom_departement in membres:
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
            st.info("Aucune discussion active.")

    with col_chat:
        if st.session_state.discussion_active_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT nom_groupe, membres_json FROM discussions WHERE id = ?", (st.session_state.discussion_active_id,))
            disc_info = cursor.fetchone()

            if disc_info:
                nom_g, membres_j = disc_info
                membres = json.loads(membres_j)

                st.markdown(f"""
                <div class="channel-header">
                    <b style="font-size: 1.1rem; color: #ffffff;">👥 {nom_g}</b><br>
                    <small style="color: #8b949e;">Membres : {', '.join(membres)}</small>
                </div>
                """, unsafe_allow_html=True)

                # Zone de messages isolée (Fragment temps réel)
                afficher_zone_messages(st.session_state.discussion_active_id, nom_departement)

                # Champ de frappe hors fragment pour éviter la perte de focus
                prompt = st.chat_input("Votre message...")
                if prompt:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json) VALUES (?, ?, ?, ?, ?)",
                        (st.session_state.discussion_active_id, nom_departement, prompt, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps([nom_departement]))
                    )
                    conn.commit()
                    conn.close()
                    st.rerun()
            conn.close()

# ==========================================
# 5. MODULE SUIVI GLOBAL POUR PÔLE DE CONTRÔLE
# ==========================================
def afficher_module_suivi_global_controle():
    st.subheader("📊 Pôle de Contrôle & Supervision Globale")
    
    conn = get_db_connection()
    df_demandes = pd.read_sql_query("SELECT * FROM demandes ORDER BY id DESC", conn)
    conn.close()

    if df_demandes.empty:
        st.info("Aucune donnée enregistrée.")
        return

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric("Total Demandes Émises", len(df_demandes))
    col_kpi2.metric("En Cours de Validation", len(df_demandes[df_demandes['statut'].str.contains("attente|Demande", case=False, na=False)]))
    col_kpi3.metric("Validées & Financées", len(df_demandes[df_demandes['statut'] == "Validé & Financé"]))
    col_kpi4.metric("Volume Cumulé (€)", f"{df_demandes['montant'].sum():,.2f} €")

    st.markdown("---")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        depts_dispos = ["Tous"] + list(df_demandes['departement'].unique())
        dept_filtre = st.selectbox("Filtrer par Département Émetteur :", depts_dispos)
    with col_f2:
        statuts_dispos = ["Tous"] + list(df_demandes['statut'].unique())
        statut_filtre = st.selectbox("Filtrer par Statut de validation :", statuts_dispos)

    df_filtré = df_demandes.copy()
    if dept_filtre != "Tous":
        df_filtré = df_filtré[df_filtré['departement'] == dept_filtre]
    if statut_filtre != "Tous":
        df_filtré = df_filtré[df_filtré['statut'] == statut_filtre]

    st.dataframe(
        df_filtré[['id', 'date', 'departement', 'titre', 'montant', 'fournisseur', 'statut', 'etape_actuelle', 'avis_achats', 'avis_finance']],
        use_container_width=True,
        hide_index=True
    )

# ==========================================
# ROUTAGE DYNAMIQUE DES VUES
# ==========================================
if st.session_state.tab_actif == "1. Études & Ingénierie":
    afficher_module_etudes(nom_dept, profil["type"])

elif st.session_state.tab_actif == "2. Cahiers des Charges":
    afficher_module_cdc(nom_dept, profil["type"])

elif st.session_state.tab_actif == "3. Besoins & Achats":
    afficher_module_achats(nom_dept, profil["type"])

elif st.session_state.tab_actif == "4. Messagerie & Chat":
    afficher_module_messagerie_unifiee(nom_dept)

elif st.session_state.tab_actif == "📊 Pôle de Contrôle (Suivi Global)":
    afficher_module_suivi_global_controle()
