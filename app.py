import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="ERP - Bureau d'Études Natika",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INJECTION CSS POUR DESIGN SAAS HAUT DE GAMME ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Masquer les éléments Streamlit par défaut */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Style des cartes KPI */
    .kpi-card {
        background: linear-gradient(135deg, #161b22 0%, #1f242c 100%);
        border: 1px solid #30363d;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        color: #ffffff;
    }

    /* Badges de statut */
    .badge-attente { background-color: #d97706; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
    .badge-valide { background-color: #059669; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
    .badge-refuse { background-color: #dc2626; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Dossier pour les uploads GED
DOSSIER_UPLOADS = "uploads_ged"
if not os.path.exists(DOSSIER_UPLOADS):
    os.makedirs(DOSSIER_UPLOADS)

# --- INITIALISATION DE LA BASE DE DONNÉES ---
def get_db_connection():
    conn = sqlite3.connect("database_be.db", check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table Utilisateurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifiant TEXT UNIQUE,
            mot_de_passe TEXT,
            nom TEXT,
            departement TEXT,
            role TEXT
        )
    ''')
    
    # Table Projets / Affaires
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_projet TEXT UNIQUE,
            nom_projet TEXT,
            client TEXT,
            budget_alloue REAL,
            statut TEXT,
            date_creation TEXT
        )
    ''')

    # Table Demandes d'Achats (liées aux projets)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS demandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_projet TEXT,
            titre TEXT,
            montant REAL,
            departement TEXT,
            demandeur TEXT,
            statut TEXT,
            date TEXT
        )
    ''')

    # Table Suivi des Temps (Timesheets)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suivi_temps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_projet TEXT,
            collaborateur TEXT,
            departement TEXT,
            heures REAL,
            tache TEXT,
            date TEXT
        )
    ''')

    # Table GED Technique
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ged_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_projet TEXT,
            titre TEXT,
            version TEXT,
            type_doc TEXT,
            nom_fichier TEXT,
            auteur TEXT,
            date TEXT
        )
    ''')

    # Créer un compte admin par défaut si la table est vide
    cursor.execute("SELECT COUNT(*) FROM utilisateurs")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO utilisateurs (identifiant, mot_de_passe, nom, departement, role) VALUES (?, ?, ?, ?, ?)",
                       ("admin", "admin123", "Directeur BE", "Direction", "Admin"))
        cursor.execute("INSERT INTO projets (code_projet, nom_projet, client, budget_alloue, statut, date_creation) VALUES (?, ?, ?, ?, ?, ?)",
                       ("PRJ-2026-001", "Ferme Solaire Régionale", "GreenEnergy Corp", 45000.0, "En cours", "2026-01-10"))

    conn.commit()
    conn.close()

init_db()

# --- GESTION DE LA SESSION UTILISATEUR ---
if 'connecte' not in st.session_state:
    st.session_state['connecte'] = False
    st.session_state['user'] = None

if not st.session_state['connecte']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🏗️ Connexion Collaborateur - Natika Group")
        with st.form("login_form"):
            identifiant = st.text_input("Identifiant")
            mot_de_passe = st.text_input("Mot de passe", type="password")
            submit = st.form_submit_button("Se connecter")
            
            if submit:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, nom, departement, role FROM utilisateurs WHERE identifiant = ? AND mot_de_passe = ?", (identifiant, mot_de_passe))
                user_data = cursor.fetchone()
                conn.close()
                
                if user_data:
                    st.session_state['connecte'] = True
                    st.session_state['user'] = {
                        "id": user_data[0],
                        "nom": user_data[1],
                        "departement": user_data[2],
                        "role": user_data[3]
                    }
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
    st.stop()

# Utilisateur connecté
profil = st.session_state['user']

# --- NAVIGATION DANS LA SIDEBAR ---
st.sidebar.markdown(f"👤 **{profil['nom']}**")
st.sidebar.markdown(f"🏢 Dept: *{profil['departement']}*")
st.sidebar.markdown(f"🔑 Rôle: *{profil['role']}*")
st.sidebar.divider()

menu = st.sidebar.radio("Navigation", [
    "📊 Tableau de bord (BI)",
    "📁 Gestion des Projets",
    "⏱️ Saisie des Temps (Timesheets)",
    "📂 GED Technique (Plans & Notes)",
    "🛒 Achats & Validations",
    "⚙️ Administration"
])

if st.sidebar.button("Déconnexion"):
    st.session_state['connecte'] = False
    st.session_state['user'] = None
    st.rerun()

conn = get_db_connection()

# --- 1. TABLEAU DE BORD DE PILOTAGE (BI) ---
if menu == "📊 Tableau de bord (BI)":
    st.title("📊 Tableau de bord de pilotage - Bureau d'Études")
    
    # Récupération des données
    df_projets = pd.read_sql_query("SELECT * FROM projets", conn)
    df_demandes = pd.read_sql_query("SELECT * FROM demandes", conn)
    df_temps = pd.read_sql_query("SELECT * FROM suivi_temps", conn)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total_budget = df_projets["budget_alloue"].sum() if not df_projets.empty else 0
        st.metric("Budget Global Alloué", f"{total_budget:,.2f} €")
    with col2:
        total_heures = df_temps["heures"].sum() if not df_temps.empty else 0
        st.metric("Total Heures Travaillées", f"{total_heures} h")
    with col3:
        nb_projets_actifs = len(df_projets[df_projets["statut"] == "En cours"])
        st.metric("Projets Actifs", nb_projets_actifs)
        
    st.divider()
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Consommation des Achats par Département")
        if not df_demandes.empty:
            fig_achats = px.bar(df_demandes, x="departement", y="montant", color="statut", title="Montant des demandes par département")
            st.plotly_chart(fig_achats, use_container_width=True)
        else:
            st.info("Aucune donnée d'achat enregistrée.")
            
    with col_g2:
        st.subheader("Charge de travail (Heures par Ingénieur / Collaborateur)")
        if not df_temps.empty:
            fig_temps = px.pie(df_temps, names="collaborateur", values="heures", title="Répartition du temps de travail")
            st.plotly_chart(fig_temps, use_container_width=True)
        else:
            st.info("Aucune saisie de temps enregistrée.")

# --- 2. GESTION DES PROJETS & AFFAIRES ---
elif menu == "📁 Gestion des Projets":
    st.title("📁 Gestion des Projets & Affaires")
    
    with st.expander("➕ Créer une nouvelle Affaire / Projet"):
        with st.form("form_projet"):
            c_code = st.text_input("Code Projet (ex: PRJ-2026-002)")
            c_nom = st.text_input("Nom du Projet")
            c_client = st.text_input("Client")
            c_budget = st.number_input("Budget Alloué (€)", min_value=0.0, step=1000.0)
            c_statut = st.selectbox("Statut", ["En cours", "Clôturé", "En attente"])
            
            if st.form_submit_button("Enregistrer le projet"):
                if c_code and c_nom:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO projets (code_projet, nom_projet, client, budget_alloue, statut, date_creation) VALUES (?, ?, ?, ?, ?, ?)",
                                       (c_code, c_nom, c_client, c_budget, c_statut, datetime.now().strftime("%Y-%m-%d")))
                        conn.commit()
                        st.success("Projet créé avec succès !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur (Code projet probablement déjà existant) : {e}")
                        
    st.subheader("Liste des Projets en cours")
    df_p = pd.read_sql_query("SELECT * FROM projets", conn)
    st.dataframe(df_p, use_container_width=True)

# --- 3. SAISIE DES TEMPS (TIMESHEETS) ---
elif menu == "⏱️ Saisie des Temps (Timesheets)":
    st.title("⏱️ Suivi des Temps de Travail")
    
    df_projets = pd.read_sql_query("SELECT code_projet, nom_projet FROM projets WHERE statut = 'En cours'", conn)
    
    with st.form("form_timesheet", clear_on_submit=True):
        choix_projet = st.selectbox("Projet rattaché", df_projets["code_projet"] + " - " + df_projets["nom_projet"] if not df_projets.empty else ["Aucun projet disponible"])
        nb_heures = st.number_input("Nombre d'heures", min_value=0.5, step=0.5)
        tache_desc = st.text_area("Description de la tâche (ex: Modélisation 3D, Notes de calcul...)")
        
        if st.form_submit_button("Enregistrer mes heures"):
            if not df_projets.empty and nb_heures > 0:
                code_p = choix_projet.split(" - ")[0]
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suivi_temps (code_projet, collaborateur, departement, heures, tache, date) VALUES (?, ?, ?, ?, ?, ?)",
                               (code_p, profil['nom'], profil['departement'], nb_heures, tache_desc, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Heures enregistrées avec succès !")
                st.rerun()
                
    st.subheader("Historique de vos saisies")
    df_t = pd.read_sql_query(f"SELECT * FROM suivi_temps WHERE collaborateur = '{profil['nom']}'", conn)
    st.dataframe(df_t, use_container_width=True)

# --- 4. GED TECHNIQUE (PLANS & NOTES) ---
elif menu == "📂 GED Technique (Plans & Notes)":
    st.title("📂 GED Technique - Plans & Notes de Calcul")
    
    df_projets = pd.read_sql_query("SELECT code_projet FROM projets", conn)
    
    with st.form("form_ged", clear_on_submit=True):
        c_proj = st.selectbox("Projet", df_projets["code_projet"] if not df_projets.empty else [])
        titre_doc = st.text_input("Titre du document (ex: Plan de structure R+2)")
        version_doc = st.selectbox("Version", ["V1.0", "V1.1", "V2.0", "V3.0"])
        type_doc = st.selectbox("Type de fichier", ["Plan PDF", "Fichier DAO (DXF/DWG)", "Note de calcul", "Rapport"])
        fichier = st.file_uploader("Fichier technique", type=["pdf", "dxf", "dwg", "xlsx", "docx"])
        
        if st.form_submit_button("Archiver dans la GED"):
            if fichier and c_proj:
                nom_fich = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{version_doc}_{fichier.name}"
                chemin = os.path.join(DOSSIER_UPLOADS, nom_fich)
                with open(chemin, "wb") as f:
                    f.write(fichier.getbuffer())
                
                cursor = conn.cursor()
                cursor.execute("INSERT INTO ged_documents (code_projet, titre, version, type_doc, nom_fichier, auteur, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (c_proj, titre_doc, version_doc, type_doc, nom_fich, profil['nom'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Document versionné et archivé avec succès !")
                st.rerun()
                
    st.subheader("Documents techniques disponibles")
    df_ged = pd.read_sql_query("SELECT * FROM ged_documents", conn)
    st.dataframe(df_ged, use_container_width=True)

# --- 5. ACHATS & VALIDATIONS ---
elif menu == "🛒 Achats & Validations":
    st.title("🛒 Gestion des Achats & Demandes")
    
    df_projets = pd.read_sql_query("SELECT code_projet FROM projets", conn)
    
    with st.expander("Créer une nouvelle demande d'achat"):
        with st.form("form_achat", clear_on_submit=True):
            p_code = st.selectbox("Projet rattaché", df_projets["code_projet"] if not df_projets.empty else [])
            titre_demande = st.text_input("Intitulé de la demande (ex: Achat licence CAO)")
            montant = st.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
            
            if st.form_submit_button("Soumettre la demande"):
                if titre_demande and montant > 0:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO demandes (code_projet, titre, montant, departement, demandeur, statut, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (p_code, titre_demande, montant, profil['departement'], profil['nom'], "En attente", datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.success("Demande transmise avec succès !")
                    st.rerun()
                    
    st.subheader("Suivi des Demandes")
    df_dem = pd.read_sql_query("SELECT * FROM demandes", conn)
    st.dataframe(df_dem, use_container_width=True)

# --- 6. ADMINISTRATION ---
elif menu == "⚙️ Administration":
    if profil['role'] != "Admin":
        st.error("Accès réservé aux administrateurs.")
        st.stop()
        
    st.title("⚙️ Administration des Utilisateurs")
    
    with st.form("form_create_user"):
        st.subheader("Ajouter un nouveau collaborateur")
        new_id = st.text_input("Identifiant de connexion")
        new_pwd = st.text_input("Mot de passe temporaire")
        new_nom = st.text_input("Nom complet")
        new_dept = st.selectbox("Département", ["Direction", "Design Office", "Achats", "Finance", "Technique"])
        new_role = st.selectbox("Rôle", ["Collaborateur", "Valideur", "Admin"])
        
        if st.form_submit_button("Créer le compte"):
            if new_id and new_pwd:
                try:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO utilisateurs (identifiant, mot_de_passe, nom, departement, role) VALUES (?, ?, ?, ?, ?)",
                                   (new_id, new_pwd, new_nom, new_dept, new_role))
                    conn.commit()
                    st.success(f"Compte pour {new_nom} créé avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")
                    
    st.subheader("Liste des Utilisateurs")
    df_users = pd.read_sql_query("SELECT id, identifiant, nom, departement, role FROM utilisateurs", conn)
    st.dataframe(df_users, use_container_width=True)

conn.close()
