import sqlite3
import json
import os
import uuid
import io
from datetime import datetime, date
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==========================================
# CONFIGURATION DE LA PAGE & STYLE CSS
# ==========================================

st.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

DOSSIER_UPLOADS = "uploads_devis"
DOSSIER_ETUDES = "uploads_etudes"
os.makedirs(DOSSIER_UPLOADS, exist_ok=True)
os.makedirs(DOSSIER_ETUDES, exist_ok=True)
DB_PATH = "bureau_etudes.db"

st.markdown("""
<style>
    :root {
        --accent: #5b8def;
        --accent-2: #7c5cf5;
        --bg-card: #151a23;
        --bg-card-2: #11151c;
        --border: #262d3a;
        --text-muted: #8b96a5;
        --success: #2ea043;
        --warning: #d29922;
        --danger: #f85149;
    }
    
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    .solde-card {
        background: linear-gradient(135deg, #161b22 0%, #21262d 100%);
        padding: 18px 24px;
        border-radius: 12px;
        border: 1px solid #30363d;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    
    .status-badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    
    .badge-achats { background-color: #388bfd33; color: #58a6ff; border: 1px solid #388bfd66; }
    .badge-finance { background-color: #bb800933; color: #d29922; border: 1px solid #bb800966; }
    .badge-direction { background-color: #a371f733; color: #bc8cff; border: 1px solid #a371f766; }
    .badge-valide { background-color: #2ea04333; color: #3fb950; border: 1px solid #2ea04366; }
    .badge-refuse { background-color: #f8514933; color: #ff7b72; border: 1px solid #f8514966; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# BASE DE DONNÉES & MIGRATIONS
# ==========================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Table Paramètres Globaux (Solde)
    c.execute("""
    CREATE TABLE IF NOT EXISTS parametres_globaux (
        cle TEXT PRIMARY KEY,
        valeur TEXT
    )
    """)
    
    # Initialiser le solde global par défaut si inexistant
    c.execute("SELECT valeur FROM parametres_globaux WHERE cle = 'solde_global'")
    if not c.fetchone():
        c.execute("INSERT INTO parametres_globaux (cle, valeur) VALUES ('solde_global', '500000.00')")
        
    # Table Utilisateurs & Départements
    c.execute("""
    CREATE TABLE IF NOT EXISTS utilisateurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT UNIQUE NOT NULL,
        mot_de_passe TEXT NOT NULL,
        type_profil TEXT NOT NULL, -- STANDARD, ACHATS, FINANCE, DIRECTION
        budget_alloue REAL DEFAULT 0.0
    )
    """)
    
    # Table Demandes d'Achat
    c.execute("""
    CREATE TABLE IF NOT EXISTS demandes_achat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_emetteur TEXT NOT NULL,
        titre TEXT NOT NULL,
        description TEXT,
        categorie TEXT,
        prix_estimatif REAL DEFAULT 0.0,
        prix_final REAL DEFAULT 0.0,
        fournisseur TEXT DEFAULT '',
        statut TEXT DEFAULT 'En attente Achats',
        date_creation TEXT,
        motif_refus TEXT,
        date_validation_achats TEXT,
        date_validation_finance TEXT,
        date_validation_direction TEXT
    )
    """)
    
    # Migration douce : s'assurer des colonnes dans demandes_achat
    c.execute("PRAGMA table_info(demandes_achat)")
    cols = [col[1] for col in c.fetchall()]
    if 'prix_final' not in cols:
        c.execute("ALTER TABLE demandes_achat ADD COLUMN prix_final REAL DEFAULT 0.0")
    if 'fournisseur' not in cols:
        c.execute("ALTER TABLE demandes_achat ADD COLUMN fournisseur TEXT DEFAULT ''")
    if 'motif_refus' not in cols:
        c.execute("ALTER TABLE demandes_achat ADD COLUMN motif_refus TEXT")
        
    # Table Journal de bord / Chat
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expediteur TEXT NOT NULL,
        destinataire TEXT NOT NULL,
        message TEXT NOT NULL,
        horodatage TEXT NOT NULL
    )
    """)
    
    # Comptes par défaut
    comptes_defaut = [
        ("Département Génie Civil", "pass123", "STANDARD", 50000.0),
        ("Département Électricité", "pass123", "STANDARD", 45000.0),
        ("Service Achats & Sourcing", "achats123", "ACHATS", 0.0),
        ("Direction Financière", "finance123", "FINANCE", 0.0),
        ("Direction Générale", "admin123", "DIRECTION", 500000.0)
    ]
    for nom, mdp, typ, budg in comptes_defaut:
        c.execute("INSERT OR IGNORE INTO utilisateurs (nom, mot_de_passe, type_profil, budget_alloue) VALUES (?, ?, ?, ?)",
                  (nom, mdp, typ, budg))
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# UTILITAIRES SOLDE GLOBAL
# ==========================================

def obtenir_solde_global():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT valeur FROM parametres_globaux WHERE cle = 'solde_global'")
    res = c.fetchone()
    conn.close()
    return float(res['valeur']) if res else 0.0

def ajuster_solde_global(montant_deduit):
    solde_actuel = obtenir_solde_global()
    nouveau_solde = solde_actuel - montant_deduit
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE parametres_globaux SET valeur = ? WHERE cle = 'solde_global'", (str(nouveau_solde),))
    conn.commit()
    conn.close()

def afficher_carte_solde(profil_type):
    """Affiche le solde global. Masqué par défaut pour Finance et Direction Générale."""
    solde = obtenir_solde_global()
    
    if "montrer_solde" not in st.session_state:
        st.session_state.montrer_solde = False

    st.markdown('<div class="solde-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    
    with c1:
        st.caption("💳 **Trésorerie & Solde Global Entreprise**")
        if profil_type in ["FINANCE", "DIRECTION"]:
            if st.session_state.montrer_solde:
                st.subheader(f"{solde:,.2f} €".replace(",", " "))
            else:
                st.subheader("•••••• €  *(Masqué)*")
        else:
            st.subheader(f"{solde:,.2f} €".replace(",", " "))
            
    with c2:
        if profil_type in ["FINANCE", "DIRECTION"]:
            btn_txt = "🙈 Masquer" if st.session_state.montrer_solde else "👁️ Afficher le solde"
            if st.button(btn_txt, key="btn_toggle_solde_global"):
                st.session_state.montrer_solde = not st.session_state.montrer_solde
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# AUTHENTIFICATION & SESSION STATE
# ==========================================

if "connected" not in st.session_state:
    st.session_state.connected = False
if "user" not in st.session_state:
    st.session_state.user = None

def ecran_connexion():
    st.title("🏢 Plateforme de Pilotage - Bureau d'Études")
    st.subheader("Connexion à votre espace de travail")
    
    conn = get_db_connection()
    users = conn.execute("SELECT nom FROM utilisateurs").fetchall()
    conn.close()
    
    noms_users = [u['nom'] for u in users]
    
    with st.form("form_login"):
        user_select = st.selectbox("Sélectionnez votre Département / Profil", noms_users)
        pwd_input = st.text_input("Mot de passe", type="password")
        btn_submit = st.form_submit_button("Se connecter")
        
        if btn_submit:
            conn = get_db_connection()
            u = conn.execute("SELECT * FROM utilisateurs WHERE nom = ? AND mot_de_passe = ?", 
                             (user_select, pwd_input)).fetchone()
            conn.close()
            
            if u:
                st.session_state.connected = True
                st.session_state.user = dict(u)
                st.success(f"Bienvenue, {u['nom']} !")
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")

if not st.session_state.connected:
    ecran_connexion()
    st.stop()

# Utilisateur courant
current_user = st.session_state.user
nom_dept = current_user["nom"]
profil_type = current_user["type_profil"]

# Barre latérale - Profil & Déconnexion
with st.sidebar:
    st.title("🏢 Pilotage BE")
    st.write(f"👤 **Compte :** {nom_dept}")
    st.write(f"🏷️ **Rôle :** {profil_type}")
    
    if st.button("🚪 Déconnexion"):
        st.session_state.connected = False
        st.session_state.user = None
        st.rerun()
    st.divider()

# ==========================================
# MODULE BESOINS & ACHATS (WORKFLOW 4 NIVEAUX)
# ==========================================

def afficher_module_achats():
    st.header("🛒 Gestion des Besoins, Achats & Validation Budgétaire")
    afficher_carte_solde(profil_type)
    
    # Config des Onglets selon Profil
    if profil_type == "STANDARD":
        tabs = st.tabs(["➕ Soumettre une Demande", "📋 Mes Demandes & Suivi"])
    elif profil_type == "ACHATS":
        tabs = st.tabs(["🔎 Sourcing & Négociation Achats", "📊 Toutes les Demandes"])
    elif profil_type == "FINANCE":
        tabs = st.tabs(["💰 Contrôle Budgétaire Finance", "📊 Suivi Global Achats"])
    elif profil_type == "DIRECTION":
        tabs = st.tabs(["🏛️ Approbation Finale & Décaissement", "📊 Suivi Général"])

    # -------------------------------------------------------------
    # 1. SOUMISSION DE DEMANDE (DÉPARTEMENTS STANDARDS)
    # -------------------------------------------------------------
    if profil_type == "STANDARD":
        with tabs[0]:
            st.subheader("Créer une nouvelle demande d'achat")
            with st.form("form_creer_demande"):
                titre = st.text_input("Titre de la demande / Matériel")
                categorie = st.selectbox("Catégorie", ["Matériel Informatique", "Consommables", "Prestation d'Étude", "Logiciels & Licences", "Autre"])
                prix_est = st.number_input("Prix estimatif indicatif (€)", min_value=1.0, value=100.0, step=10.0)
                description = st.text_area("Description détaillée du besoin")
                
                if st.form_submit_button("📤 Soumettre aux Achats"):
                    if titre and description:
                        conn = get_db_connection()
                        conn.execute("""
                        INSERT INTO demandes_achat (dept_emetteur, titre, description, categorie, prix_estimatif, statut, date_creation)
                        VALUES (?, ?, ?, ?, ?, 'En attente Achats', ?)
                        """, (nom_dept, titre, description, categorie, prix_est, datetime.now().strftime("%Y-%m-%d %H:%M")))
                        conn.commit()
                        conn.close()
                        st.success("Demande soumise avec succès au département Achats !")
                        st.rerun()
                    else:
                        st.warning("Veuillez remplir le titre et la description.")

        with tabs[1]:
            st.subheader("Suivi de vos demandes")
            conn = get_db_connection()
            demandes = conn.execute("SELECT * FROM demandes_achat WHERE dept_emetteur = ? ORDER BY id DESC", (nom_dept,)).fetchall()
            conn.close()
            
            if demandes:
                df = pd.DataFrame([dict(d) for d in demandes])
                st.dataframe(df[['id', 'titre', 'categorie', 'prix_estimatif', 'prix_final', 'fournisseur', 'statut', 'date_creation']], use_container_width=True)
            else:
                st.info("Aucune demande soumise pour le moment.")

    # -------------------------------------------------------------
    # 2. SOURCING & NÉGOCIATION (DEPARTEMENT ACHATS)
    # -------------------------------------------------------------
    elif profil_type == "ACHATS":
        with tabs[0]:
            st.subheader("Demandes en attente de Sourcing Achats")
            conn = get_db_connection()
            demandes_achats = conn.execute("SELECT * FROM demandes_achat WHERE statut = 'En attente Achats' ORDER BY id ASC").fetchall()
            conn.close()
            
            if not demandes_achats:
                st.success("🎉 Aucune demande en attente de sourcing.")
            else:
                for d in demandes_achats:
                    with st.expander(f"📦 Demande #{d['id']} : {d['titre']} ({d['dept_emetteur']})"):
                        st.write(f"**Catégorie :** {d['categorie']} | **Prix Estimé :** {d['prix_estimatif']:,.2f} €")
                        st.write(f"**Description :** {d['description']}")
                        st.divider()
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            fournisseur_input = st.text_input("Fournisseur retenu", value=d['fournisseur'], key=f"fourn_{d['id']}")
                        with col_b:
                            prix_final_input = st.number_input("Prix Négocié / Final (€)", min_value=0.0, value=d['prix_estimatif'], key=f"pfinal_{d['id']}")
                            
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("✅ Transmettre à la Finance", key=f"val_ach_{d['id']}"):
                                if not fournisseur_input:
                                    st.warning("Veuillez renseigner le nom du fournisseur.")
                                else:
                                    conn = get_db_connection()
                                    conn.execute("""
                                    UPDATE demandes_achat 
                                    SET fournisseur = ?, prix_final = ?, statut = 'En attente Finance', date_validation_achats = ?
                                    WHERE id = ?
                                    """, (fournisseur_input, prix_final_input, datetime.now().strftime("%Y-%m-%d %H:%M"), d['id']))
                                    conn.commit()
                                    conn.close()
                                    st.success("Transmis à la Finance pour contrôle budgétaire !")
                                    st.rerun()
                        with btn_col2:
                            if st.button("❌ Refuser la demande", key=f"ref_ach_{d['id']}"):
                                conn = get_db_connection()
                                conn.execute("UPDATE demandes_achat SET statut = 'Refusé Achats' WHERE id = ?", (d['id'],))
                                conn.commit()
                                conn.close()
                                st.error("Demande refusée.")
                                st.rerun()

        with tabs[1]:
            st.subheader("Toutes les demandes enregistrées")
            conn = get_db_connection()
            demandes_all = conn.execute("SELECT * FROM demandes_achat ORDER BY id DESC").fetchall()
            conn.close()
            if demandes_all:
                st.dataframe(pd.DataFrame([dict(d) for d in demandes_all]), use_container_width=True)

    # -------------------------------------------------------------
    # 3. CONTRÔLE BUDGÉTAIRE (DEPARTEMENT FINANCE)
    # -------------------------------------------------------------
    elif profil_type == "FINANCE":
        with tabs[0]:
            st.subheader("Demandes pré-validées par les Achats (Contrôle Budgétaire)")
            conn = get_db_connection()
            demandes_finance = conn.execute("SELECT * FROM demandes_achat WHERE statut = 'En attente Finance' ORDER BY id ASC").fetchall()
            conn.close()
            
            if not demandes_finance:
                st.info("Aucune demande en attente de contrôle budgétaire.")
            else:
                for d in demandes_finance:
                    with st.expander(f"🔍 Contrôle #{d['id']} : {d['titre']} | Fournisseur : {d['fournisseur']} ({d['prix_final']:,.2f} €)"):
                        st.write(f"**Département Émetteur :** {d['dept_emetteur']}")
                        st.write(f"**Prix Estimatif Initiale :** {d['prix_estimatif']:,.2f} €")
                        st.write(f"**Prix Négocié par Achats :** :green[{d['prix_final']:,.2f} €]")
                        st.write(f"**Fournisseur Sourcing :** {d['fournisseur']}")
                        st.write(f"**Description :** {d['description']}")
                        st.info(" Note : La Finance valide l'enveloppe budgétaire sans modifier les prix ou fournisseurs fixés par les Achats.")
                        
                        btn_f1, btn_f2 = st.columns(2)
                        with btn_f1:
                            if st.button("✅ Valider le Budget & Transmettre à la Direction", key=f"val_fin_{d['id']}"):
                                conn = get_db_connection()
                                conn.execute("""
                                UPDATE demandes_achat 
                                SET statut = 'En attente Direction', date_validation_finance = ?
                                WHERE id = ?
                                """, (datetime.now().strftime("%Y-%m-%d %H:%M"), d['id']))
                                conn.commit()
                                conn.close()
                                st.success("Contrôle budgétaire OK. Transmis à la Direction Général !")
                                st.rerun()
                        with btn_f2:
                            if st.button("❌ Refuser (Budget Insuffisant)", key=f"ref_fin_{d['id']}"):
                                conn = get_db_connection()
                                conn.execute("UPDATE demandes_achat SET statut = 'Refusé Finance' WHERE id = ?", (d['id'],))
                                conn.commit()
                                conn.close()
                                st.error("Demande rejetée par la Finance.")
                                st.rerun()

        with tabs[1]:
            st.subheader("Historique et suivi global des demandes")
            conn = get_db_connection()
            demandes_all = conn.execute("SELECT * FROM demandes_achat ORDER BY id DESC").fetchall()
            conn.close()
            if demandes_all:
                st.dataframe(pd.DataFrame([dict(d) for d in demandes_all]), use_container_width=True)

    # -------------------------------------------------------------
    # 4. APPROBATION FINALE & DÉCAISSEMENT (DIRECTION GÉNÉRALE)
    # -------------------------------------------------------------
    elif profil_type == "DIRECTION":
        with tabs[0]:
            st.subheader("Demandes validées par Achats & Finance en attente de Décaissement")
            conn = get_db_connection()
            demandes_dir = conn.execute("SELECT * FROM demandes_achat WHERE statut = 'En attente Direction' ORDER BY id ASC").fetchall()
            conn.close()
            
            if not demandes_dir:
                st.success("🎉 Aucune demande en attente de décision finale.")
            else:
                for d in demandes_dir:
                    with st.expander(f"🏛️ Validation Finale #{d['id']} : {d['titre']} - {d['prix_final']:,.2f} €"):
                        st.write(f"**Département Demandeur :** {d['dept_emetteur']}")
                        st.write(f"**Fournisseur Retenu :** {d['fournisseur']}")
                        st.write(f"**Montant à Décaisser :** :green[{d['prix_final']:,.2f} €]")
                        st.write(f"**Avis Achats :** Validé le {d['date_validation_achats']}")
                        st.write(f"**Avis Finance :** Validé le {d['date_validation_finance']}")
                        
                        btn_d1, btn_d2 = st.columns(2)
                        with btn_d1:
                            if st.button("🚀 Approuver & Décaisser l'Argent", key=f"val_dir_{d['id']}"):
                                # Validation définitive + réduction du solde global
                                ajuster_solde_global(d['prix_final'])
                                
                                conn = get_db_connection()
                                conn.execute("""
                                UPDATE demandes_achat 
                                SET statut = 'Validé & Financé', date_validation_direction = ?
                                WHERE id = ?
                                """, (datetime.now().strftime("%Y-%m-%d %H:%M"), d['id']))
                                conn.commit()
                                conn.close()
                                st.balloons()
                                st.success(f"Demande approuvée ! Le montant de {d['prix_final']:,.2f} € a été déduit du solde global.")
                                st.rerun()
                        with btn_d2:
                            if st.button("❌ Refus Direction", key=f"ref_dir_{d['id']}"):
                                conn = get_db_connection()
                                conn.execute("UPDATE demandes_achat SET statut = 'Refusé Direction' WHERE id = ?", (d['id'],))
                                conn.commit()
                                conn.close()
                                st.error("Demande refusée par la Direction.")
                                st.rerun()

        with tabs[1]:
            st.subheader("Vision globale de toutes les opérations")
            conn = get_db_connection()
            demandes_all = conn.execute("SELECT * FROM demandes_achat ORDER BY id DESC").fetchall()
            conn.close()
            if demandes_all:
                st.dataframe(pd.DataFrame([dict(d) for d in demandes_all]), use_container_width=True)

# ==========================================
# ROUTAGE DYNAMIQUE DE L'APPLICATION
# ==========================================

st.sidebar.title("📌 Navigation")
choix_menu = st.sidebar.radio("Modules Disponibles", [
    "🛒 Besoins & Achats",
    "💬 Messagerie & Chat",
    "📊 Statistiques Globales"
])

if choix_menu == "🛒 Besoins & Achats":
    afficher_module_achats()

elif choix_menu == "💬 Messagerie & Chat":
    st.header("💬 Messagerie Unifiée Inter-Services")
    st.info("Cet espace permet d'échanger en direct entre les départements standards, les Achats, la Finance et la Direction.")
    
    conn = get_db_connection()
    users = [u['nom'] for u in conn.execute("SELECT nom FROM utilisateurs WHERE nom != ?", (nom_dept,)).fetchall()]
    conn.close()
    
    destinataire = st.selectbox("Envoyer un message à :", users)
    msg_input = st.text_area("Votre message...")
    if st.button("📤 Envoyer Message"):
        if msg_input:
            conn = get_db_connection()
            conn.execute("INSERT INTO messages_chat (expediteur, destinataire, message, horodatage) VALUES (?, ?, ?, ?)",
                         (nom_dept, destinataire, msg_input, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            conn.close()
            st.success("Message envoyé !")
            st.rerun()

    st.divider()
    st.subheader("📜 Fil de conversation")
    conn = get_db_connection()
    messages = conn.execute("""
    SELECT * FROM messages_chat 
    WHERE (expediteur = ? AND destinataire = ?) OR (expediteur = ? AND destinataire = ?)
    ORDER BY id DESC
    """, (nom_dept, destinataire, destinataire, nom_dept)).fetchall()
    conn.close()
    
    for m in messages:
        st.write(f"**[{m['horodatage']}] {m['expediteur']} :** {m['message']}")

elif choix_menu == "📊 Statistiques Globales":
    st.header("📈 Dashboard & Statistiques Budgétaires")
    afficher_carte_solde(profil_type)
    
    conn = get_db_connection()
    df_demandes = pd.read_sql_query("SELECT * FROM demandes_achat", conn)
    conn.close()
    
    if not df_demandes.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Demandes", len(df_demandes))
        c2.metric("En Cours de traitement", len(df_demandes[df_demandes['statut'].str.contains('En attente', na=False)]))
        c3.metric("Validées & Financées", len(df_demandes[df_demandes['statut'] == 'Validé & Financé']))
        
        st.subheader("Répartition des dépenses financées par Département")
        df_validees = df_demandes[df_demandes['statut'] == 'Validé & Financé']
        if not df_validees.empty:
            chart_data = df_validees.groupby('dept_emetteur')['prix_final'].sum()
            st.bar_chart(chart_data)
        else:
            st.info("Aucune dépense financée pour le moment.")
