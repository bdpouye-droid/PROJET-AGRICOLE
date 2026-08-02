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

# --- STYLE CSS PERSONNALISÉ & DESIGN MODERNE DES ONGLETS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    
    /* Boutons généraux */
    .stButton>button {
        border-radius: 8px; font-weight: 600; transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stButton>button:hover {
        transform: translateY(-1px); border-color: #1f6feb;
    }
    
    .badge-notification { background-color: #f85149; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
    .channel-header {
        background-color: #161b22; padding: 12px 18px; border-radius: 8px; 
        border-left: 4px solid #5b5fc7; margin-bottom: 15px;
    }
    
    /* Journal de Bord */
    .note-card {
        background-color: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 14px; margin-bottom: 12px; border-left: 4px solid #238636;
    }
    .note-date { color: #8b949e; font-size: 0.85rem; font-weight: 600; }
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS journal_bord (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, auteur TEXT, note TEXT, date_note TEXT, heure_note TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS corbeille_archives (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement_auteur TEXT, type_element TEXT, resume TEXT, details_json TEXT, date_suppression TEXT
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

# --- UTILS DATABASE ---
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

def archiver_dans_corbeille(departement_auteur, type_element, resume, details_dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO corbeille_archives (departement_auteur, type_element, resume, details_json, date_suppression) VALUES (?, ?, ?, ?, ?)",
        (departement_auteur, type_element, resume, json.dumps(details_dict), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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

# --- CALCUL DES NOTIFICATIONS MESSAGERIE ---
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
                st.session_state.tab_actif = "4. Messagerie & Chat"
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
    c_b1.metric("Budget Global Allocation", f"{b_total:,.2f} €")
    c_b2.metric("Solde Restant Disponible", f"{b_solde:,.2f} €")

st.markdown("---")

# --- NAVIGATION PAR ONGLETS PRINCIPAUX ---
onglets = [
    "1. Études & Ingénierie",
    "2. Cahiers des Charges",
    "3. Achats & Devis",
    "4. Messagerie & Chat",
    "5. Journal de Bord",
    "6. Corbeille & Archives",
    "7. Logs & Audit"
]

# Si l'utilisateur est fondateur ou finance, on peut ajouter des vues globales
if profil["type"] in ["fondateur", "finance"]:
    onglets.append("8. Administration & Budget")

choix_tab = st.radio("Navigation Bureau d'Études", onglets, horizontal=True, key="radio_navigation_principale")

st.markdown("---")

# --- SECTION 1 : ÉTUDES & INGÉNIERIE ---
if choix_tab == "1. Études & Ingénierie":
    st.subheader("📑 Gestion des Études Métier & Ingénierie")
    
    with st.expander("➕ Soumettre une nouvelle étude technique", expanded=False):
        with st.form("form_nouvelle_etude"):
            titre_etude = st.text_input("Titre de l'étude")
            donnees_texte = st.text_area("Données techniques / Paramètres / Description")
            fichier_etude = st.file_uploader("Joindre un fichier technique (PDF, DWG, XLSX, etc.)", type=["pdf", "xlsx", "docx", "dwg", "png", "jpg"])
            
            # Liste des départements pour partage
            tous_les_deps = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_dept]
            destinataires_choisis = st.multiselect("Partager cette étude avec d'autres départements", tous_les_deps)
            
            submit_etude = st.form_submit_button("Enregistrer et diffuser l'étude")
            
            if submit_etude:
                if titre_etude.strip():
                    nom_fic_etude = enregistrer_fichier_securise(DOSSIER_ETUDES, fichier_etude)
                    conn_e = get_db_connection()
                    cursor_e = conn_e.cursor()
                    cursor_e.execute(
                        "INSERT INTO etudes_metier (departement, titre, donnees_json, fichier_etude, destinataires_partage, date) VALUES (?, ?, ?, ?, ?, ?)",
                        (nom_dept, titre_etude, json.dumps({"description": donnees_texte}), nom_fic_etude, json.dumps(destinataires_choisis), datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn_e.commit()
                    conn_e.close()
                    ajouter_log("Création Étude", profil["nom"], f"Étude '{titre_etude}' créée.")
                    st.success("Étude enregistrée avec succès !")
                    st.rerun()
                else:
                    st.error("Veuillez renseigner au moins un titre.")

    st.markdown("### 📂 Études disponibles pour votre département")
    conn_e = get_db_connection()
    cursor_e = conn_e.cursor()
    cursor_e.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier")
    toutes_etudes = cursor_e.fetchall()
    conn_e.close()

    etudes_visibles = []
    for e in toutes_etudes:
        e_id, e_dept, e_titre, e_json, e_fic, e_partage_json, e_date = e
        partages = json.loads(e_partage_json) if e_partage_json else []
        if e_dept == nom_dept or nom_dept in partages or profil["type"] in ["fondateur", "finance"]:
            etudes_visibles.append(e)

    if not etudes_visibles:
        st.info("Aucune étude disponible pour le moment.")
    else:
        for ev in etudes_visibles:
            ev_id, ev_dept, ev_titre, ev_json, ev_fic, ev_partage_json, ev_date = ev
            with st.container():
                st.markdown(f"""
                <div style="background-color: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 10px;">
                    <b>{ev_titre}</b> <span style="color: #8b949e; font-size: 0.85rem;">(Créé par : {ev_dept} le {ev_date})</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Affichage des détails et du fichier attaché si présent
                data_d = json.loads(ev_json)
                st.write(data_d.get("description", ""))
                if ev_fic:
                    chemin_f = os.path.join(DOSSIER_ETUDES, ev_fic)
                    if os.path.exists(chemin_f):
                        with open(chemin_f, "rb") as f_dl:
                            st.download_button("📥 Télécharger le document technique", f_dl, file_name=ev_fic, key=f"dl_etude_{ev_id}")

# --- SECTION 2 : CAHIERS DES CHARGES ---
elif choix_tab == "2. Cahiers des Charges":
    st.subheader("📋 Rédaction & Consultation des Cahiers des Charges")
    
    with st.expander("➕ Rédiger un nouveau Cahier des Charges", expanded=False):
        with st.form("form_cdc"):
            titre_cdc = st.text_input("Titre du Cahier des Charges")
            contenu_cdc = st.text_area("Contenu détaillé du cahier des charges")
            
            tous_les_deps = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_dept]
            dest_avis = st.multiselect("Demander l'avis d'autres départements", tous_les_deps)
            
            submit_cdc = st.form_submit_button("Publier le Cahier des Charges")
            if submit_cdc:
                if titre_cdc.strip() and contenu_cdc.strip():
                    conn_c = get_db_connection()
                    cursor_c = conn_c.cursor()
                    cursor_c.execute(
                        "INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis) VALUES (?, ?, ?, ?, ?)",
                        (nom_dept, titre_cdc, contenu_cdc, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(dest_avis))
                    )
                    conn_c.commit()
                    conn_c.close()
                    ajouter_log("Création CDC", profil["nom"], f"Cahier des charges '{titre_cdc}' créé.")
                    st.success("Cahier des charges publié avec succès !")
                    st.rerun()
                else:
                    st.error("Veuillez remplir le titre et le contenu.")

    st.markdown("### 📄 Liste des Cahiers des Charges")
    conn_c = get_db_connection()
    cursor_c = conn_c.cursor()
    cursor_c.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges")
    les_cdc = cursor_c.fetchall()
    conn_c.close()

    if not les_cdc:
        st.info("Aucun cahier des charges enregistré.")
    else:
        for cdc in les_cdc:
            c_id, c_dept, c_titre, c_contenu, c_date, c_dest_json = cdc
            with st.expander(f"📌 {c_titre} (Auteur : {c_dept} - {c_date})"):
                st.write(c_contenu)

# --- SECTION 3 : ACHATS & DEVIS ---
elif choix_tab == "3. Achats & Devis":
    st.subheader("🛒 Gestion des Achats, Soumission de Devis & Validations")
    
    with st.expander("➕ Soumettre une nouvelle demande d'achat / devis", expanded=False):
        with st.form("form_devis"):
            titre_dem = st.text_input("Objet de la demande d'achat")
            cahier_charges_ref = st.text_area("Description / Référence au cahier des charges")
            montant_dem = st.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
            fournisseur_dem = st.text_input("Fournisseur / Prestataire suggéré")
            fichier_devis = st.file_uploader("Joindre le devis (PDF / Image)", type=["pdf", "png", "jpg", "xlsx"])
            
            submit_dem = st.form_submit_button("Soumettre la demande")
            if submit_dem:
                if titre_dem.strip() and montant_dem > 0:
                    nom_fic_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                    conn_d = get_db_connection()
                    cursor_d = conn_d.cursor()
                    cursor_d.execute(
                        """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (nom_dept, titre_dem, cahier_charges_ref, montant_dem, fournisseur_dem, "En cours", "Validation Achats", "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fic_devis, "")
                    )
                    conn_d.commit()
                    conn_d.close()
                    ajouter_log("Demande Achat", profil["nom"], f"Demande '{titre_dem}' pour {montant_dem}€ soumise.")
                    st.success("Demande soumise avec succès au pôle Achats !")
                    st.rerun()
                else:
                    st.error("Veuillez renseigner un titre valide et un montant supérieur à 0.")

    st.markdown("### 📋 Suivi de vos demandes et validations")
    conn_d = get_db_connection()
    cursor_d = conn_d.cursor()
    if profil["type"] in ["fondateur", "finance"]:
        cursor_d.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque FROM demandes")
    elif profil["type"] == "achats":
        cursor_d.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque FROM demandes")
    else:
        cursor_d.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque FROM demandes WHERE departement = ?", (nom_dept,))
    
    demandes_list = cursor_d.fetchall()
    conn_d.close()

    if not demandes_list:
        st.info("Aucune demande enregistrée.")
    else:
        for dem in demandes_list:
            d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fic, d_remarque = dem
            
            with st.container():
                st.markdown(f"""
                <div style="background-color: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 10px;">
                    <b>[{d_dept}] {d_titre}</b> - Montant : <b>{d_montant:,.2f} €</b> | Statut : <b style='color: #58a6ff;'>{d_statut}</b> (Étape : {d_etape})
                </div>
                """, unsafe_allow_html=True)
                
                # Actions spécifiques selon rôle (Achats ou Finance)
                col_act1, col_act2 = st.columns(2)
                if profil["type"] == "achats" and d_etape == "Validation Achats":
                    with col_act1:
                        if st.button("✅ Valider (Transférer Finance)", key=f"val_achats_{d_id}"):
                            conn_up = get_db_connection()
                            cursor_up = conn_up.cursor()
                            cursor_up.execute("UPDATE demandes SET avis_achats = 'Validé', etape_actuelle = 'Validation Finance' WHERE id = ?", (d_id,))
                            conn_up.commit()
                            conn_up.close()
                            st.success("Demande validée et transmise à la Finance !")
                            st.rerun()
                    with col_act2:
                        motif_rej = st.text_input("Motif du rejet (si refus)", key=f"motif_rej_a_{d_id}")
                        if st.button("❌ Refuser", key=f"ref_achats_{d_id}"):
                            conn_up = get_db_connection()
                            cursor_up = conn_up.cursor()
                            cursor_up.execute("UPDATE demandes SET statut = 'Refusé', avis_achats = 'Refusé', motif_refus = ? WHERE id = ?", (motif_rej, d_id))
                            conn_up.commit()
                            conn_up.close()
                            st.error("Demande refusée.")
                            st.rerun()
                            
                elif profil["type"] == "finance" and d_etape == "Validation Finance":
                    with col_act1:
                        if st.button("💰 Valider & Décaisser (Approuver)", key=f"val_fin_{d_id}"):
                            b_solde_actuel = get_valeur_globale("solde_restant")
                            if b_solde_actuel >= d_montant:
                                set_valeur_globale("solde_restant", b_solde_actuel - d_montant)
                                conn_up = get_db_connection()
                                cursor_up = conn_up.cursor()
                                cursor_up.execute("UPDATE demandes SET statut = 'Approuvé & Financé', avis_finance = 'Validé', etape_actuelle = 'Clôturé' WHERE id = ?", (d_id,))
                                conn_up.commit()
                                conn_up.close()
                                st.success("Demande approuvée et budget mis à jour !")
                                st.rerun()
                            else:
                                st.error("Solde budgétaire insuffisant pour approuver cette dépense !")
                    with col_act2:
                        motif_rej_f = st.text_input("Motif du rejet finance", key=f"motif_rej_f_{d_id}")
                        if st.button("❌ Refuser par la Finance", key=f"ref_fin_{d_id}"):
                            conn_up = get_db_connection()
                            cursor_up = conn_up.cursor()
                            cursor_up.execute("UPDATE demandes SET statut = 'Refusé', avis_finance = 'Refusé', motif_refus = ? WHERE id = ?", (motif_rej_f, d_id))
                            conn_up.commit()
                            conn_up.close()
                            st.error("Demande refusée par la finance.")
                            st.rerun()

# --- SECTION 4 : MESSAGERIE & CHAT ---
elif choix_tab == "4. Messagerie & Chat":
    st.subheader("💬 Canaux de Discussion & Messagerie Inter-Départements")
    
    conn_m = get_db_connection()
    cursor_m = conn_m.cursor()
    cursor_m.execute("SELECT id, nom_groupe, membres_json, createur FROM discussions")
    toutes_discs = cursor_m.fetchall()
    conn_m.close()

    # Création d'un groupe de discussion
    with st.expander("➕ Créer un nouveau canal de discussion", expanded=False):
        with st.form("form_creer_groupe"):
            nom_g = st.text_input("Nom du canal / groupe")
            tous_les_deps = [u["dept"] for u in UTILISATEURS.values()]
            membres_g = st.multiselect("Sélectionner les départements participants", tous_les_deps, default=[nom_dept])
            submit_g = st.form_submit_button("Créer le canal")
            if submit_g:
                if nom_g.strip() and membres_g:
                    conn_cg = get_db_connection()
                    cursor_cg = conn_cg.cursor()
                    cursor_cg.execute(
                        "INSERT INTO discussions (nom_groupe, membres_json, createur, date_creation) VALUES (?, ?, ?, ?)",
                        (nom_g, json.dumps(membres_g), nom_dept, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn_cg.commit()
                    conn_cg.close()
                    st.success("Canal créé avec succès !")
                    st.rerun()

    # Filtrer les discussions où l'utilisateur est membre
    mes_discs = []
    for d in toutes_discs:
        d_id, d_nom, d_membres_j, d_crea = d
        membres = json.loads(d_membres_j)
        if nom_dept in membres or profil["type"] == "fondateur":
            mes_discs.append(d)

    if not mes_discs:
        st.info("Vous ne participez à aucun canal de discussion pour le moment.")
    else:
        options_canaux = {d[1]: d[0] for d in mes_discs}
        
        # Gestion de la téléportation par notification
        index_defaut = 0
        if st.session_state.discussion_active_id is not None:
            for idx, (nom_c, id_c) in enumerate(options_canaux.items()):
                if id_c == st.session_state.discussion_active_id:
                    index_defaut = idx
                    break

        choix_canal_nom = st.selectbox("Sélectionner un canal", list(options_canaux.keys()), index=index_defaut)
        id_canal_actif = options_canaux[choix_canal_nom]
        st.session_state.discussion_active_id = id_canal_actif

        st.markdown(f"<div class='channel-header'><b>Canal actif :</b> {choix_canal_nom}</div>", unsafe_allow_html=True)

        # Récupération des messages
        conn_msg = get_db_connection()
        cursor_msg = conn_msg.cursor()
        cursor_msg.execute("SELECT id, expediteur, texte, date, lus_json FROM messages_chat WHERE discussion_id = ? ORDER BY id ASC", (id_canal_actif,))
        messages = cursor_msg.fetchall()

        # Marquer les messages comme lus
        for m_id, m_exp, m_txt, m_date, m_lus_j in messages:
            lus = json.loads(m_lus_j) if m_lus_j else []
            if m_exp != nom_dept and nom_dept not in lus:
                lus.append(nom_dept)
                cursor_msg.execute("UPDATE messages_chat SET lus_json = ? WHERE id = ?", (json.dumps(lus), m_id))
        conn_msg.commit()

        for m_id, m_exp, m_txt, m_date, m_lus_j in messages:
            align = "right" if m_exp == nom_dept else "left"
            bg_col = "#1f6feb" if m_exp == nom_dept else "#21262d"
            st.markdown(f"""
            <div style="text-align: {align}; margin-bottom: 8px;">
                <div style="display: inline-block; background-color: {bg_col}; padding: 10px 14px; border-radius: 10px; max-width: 75%; text-align: left; border: 1px solid #30363d;">
                    <span style="font-size: 0.75rem; color: #8b949e;"><b>{m_exp}</b> - {m_date}</span><br>
                    <span>{m_txt}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        conn_msg.close()

        # Formulaire d'envoi de message
        with st.form(key=f"form_chat_{id_canal_actif}", clear_on_submit=True):
            nouveau_texte = st.text_input("Votre message...")
            envoyer = st.form_submit_button("Envoyer")
            if envoyer and nouveau_texte.strip():
                conn_ins = get_db_connection()
                cursor_ins = conn_ins.cursor()
                cursor_ins.execute(
                    "INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json) VALUES (?, ?, ?, ?, ?)",
                    (id_canal_actif, nom_dept, nouveau_texte, datetime.now().strftime("%H:%M"), json.dumps([nom_dept]))
                )
                conn_ins.commit()
                conn_ins.close()
                st.rerun()

# --- SECTION 5 : JOURNAL DE BORD ---
elif choix_tab == "5. Journal de Bord":
    st.subheader("📓 Journal de Bord & Notes du Département")
    
    with st.form("form_journal"):
        note_txt = st.text_area("Ajouter une note ou un compte-rendu d'activité")
        submit_note = st.form_submit_button("Publier dans le journal")
        if submit_note and note_txt.strip():
            conn_j = get_db_connection()
            cursor_j = conn_j.cursor()
            cursor_j.execute(
                "INSERT INTO journal_bord (departement, auteur, note, date_note, heure_note) VALUES (?, ?, ?, ?, ?)",
                (nom_dept, profil["nom"], note_txt, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"))
            )
            conn_j.commit()
            conn_j.close()
            st.success("Note ajoutée au journal de bord !")
            st.rerun()

    conn_j = get_db_connection()
    cursor_j = conn_j.cursor()
    if profil["type"] in ["fondateur", "finance"]:
        cursor_j.execute("SELECT departement, auteur, note, date_note, heure_note FROM journal_bord ORDER BY id DESC")
    else:
        cursor_j.execute("SELECT departement, auteur, note, date_note, heure_note FROM journal_bord WHERE departement = ? ORDER BY id DESC", (nom_dept,))
    notes = cursor_j.fetchall()
    conn_j.close()

    if not notes:
        st.info("Aucune note dans le journal de bord.")
    else:
        for n_dept, n_auteur, n_txt, n_date, n_heure in notes:
            st.markdown(f"""
            <div class="note-card">
                <div class="note-date">[{n_dept}] {n_auteur} - {n_date} à {n_heure}</div>
                <div style="margin-top: 6px;">{n_txt}</div>
            </div>
            """, unsafe_allow_html=True)

# --- SECTION 6 : CORBEILLE & ARCHIVES ---
elif choix_tab == "6. Corbeille & Archives":
    st.subheader("🗑️ Corbeille & Éléments Archivés")
    conn_arc = get_db_connection()
    cursor_arc = conn_arc.cursor()
    cursor_arc.execute("SELECT departement_auteur, type_element, resume, date_suppression FROM corbeille_archives")
    archives = cursor_arc.fetchall()
    conn_arc.close()

    if not archives:
        st.info("La corbeille est vide.")
    else:
        for arc in archives:
            a_dept, a_type, a_res, a_date = arc
            st.write(f"- **[{a_date}]** ({a_type}) par {a_dept} : {a_res}")

# --- SECTION 7 : LOGS & AUDIT ---
elif choix_tab == "7. Logs & Audit":
    st.subheader("📊 Journal d'Audit & Traçabilité des Actions")
    conn_l = get_db_connection()
    cursor_l = conn_l.cursor()
    cursor_l.execute("SELECT date, acteur, action, details FROM logs_audit ORDER BY id DESC LIMIT 100")
    logs = cursor_l.fetchall()
    conn_l.close()

    if not logs:
        st.info("Aucun log enregistré.")
    else:
        df_logs = pd.DataFrame(logs, columns=["Date", "Acteur", "Action", "Détails"])
        st.dataframe(df_logs, use_container_width=True)

# --- SECTION 8 : ADMINISTRATION & BUDGET ---
elif choix_tab == "8. Administration & Budget":
    if profil["type"] not in ["fondateur", "finance"]:
        st.error("Accès réservé à la Direction et au pôle Finance.")
    else:
        st.subheader("⚙️ Administration Générale & Pilotage Budgétaire")
        nouveau_budget = st.number_input("Modifier le Budget Global (€)", value=get_valeur_globale("budget_global"), step=50000.0)
        if st.button("Mettre à jour le budget global"):
            set_valeur_globale("budget_global", nouveau_budget)
            st.success("Budget global mis à jour avec succès !")
            st.rerun()
