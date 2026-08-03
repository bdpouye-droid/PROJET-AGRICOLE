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
from reportlab.lib.styles import getSampleStyleSheet

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

# --- STYLE CSS PERSONNALISÉ & DESIGN MODERNE ---
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
        background: radial-gradient(circle at 0% 0%, #12161f 0%, #0b0e14 55%, #0a0c11 100%);
    }

    h1, h2, h3 { letter-spacing: -0.01em; }

    /* Titre principal */
    h1 {
        background: linear-gradient(90deg, #ffffff 0%, #b9c6e8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    /* Boutons généraux */
    .stButton>button {
        border-radius: 10px; font-weight: 600; transition: all 0.15s ease;
        border: 1px solid var(--border); background-color: #171c26;
    }
    .stButton>button:hover {
        transform: translateY(-1px); border-color: var(--accent);
        box-shadow: 0 4px 14px rgba(91, 141, 239, 0.25);
    }
    .stButton>button[kind="primary"] {
        background: linear-gradient(90deg, var(--accent) 0%, var(--accent-2) 100%);
        border: none; color: white;
    }
    .stDownloadButton>button {
        border-radius: 10px; font-weight: 600; border: 1px solid var(--border);
        background-color: #14201a; color: #b7f0c2;
    }
    .stDownloadButton>button:hover { border-color: var(--success); transform: translateY(-1px); }

    .badge-notification {
        background: linear-gradient(90deg, #f85149, #d63b32);
        color: white; padding: 2px 9px; border-radius: 12px; font-size: 0.75rem; font-weight: 700;
    }
    .channel-header {
        background-color: var(--bg-card); padding: 12px 18px; border-radius: 10px;
        border-left: 4px solid var(--accent-2); margin-bottom: 15px;
    }

    /* Cartes génériques (journal, listes...) */
    .note-card {
        background-color: var(--bg-card); border: 1px solid var(--border); border-radius: 10px;
        padding: 14px; margin-bottom: 12px; border-left: 4px solid var(--success);
    }
    .note-date { color: var(--text-muted); font-size: 0.85rem; font-weight: 600; }

    /* Barre de filtres */
    .filter-bar {
        background-color: var(--bg-card-2); border: 1px solid var(--border); border-radius: 12px;
        padding: 14px 16px 4px 16px; margin-bottom: 16px;
    }
    .filter-bar-title { color: var(--text-muted); font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }

    /* Barre d'export */
    .export-bar { display: flex; gap: 8px; margin: 6px 0 14px 0; }

    /* KPI cards */
    div[data-testid="stMetric"] {
        background-color: var(--bg-card); border: 1px solid var(--border);
        border-radius: 12px; padding: 12px 16px;
    }

    /* Statut pills utilisés via markdown */
    .pill { display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }
    .pill-attente { background: rgba(210,153,34,0.15); color: #e3b341; border: 1px solid rgba(210,153,34,0.4); }
    .pill-valide { background: rgba(46,160,67,0.15); color: #56d364; border: 1px solid rgba(46,160,67,0.4); }
    .pill-refuse { background: rgba(248,81,73,0.15); color: #ff7b72; border: 1px solid rgba(248,81,73,0.4); }
    .pill-modif { background: rgba(91,141,239,0.15); color: #79b8ff; border: 1px solid rgba(91,141,239,0.4); }

    /* Onglets natifs st.tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0; background-color: var(--bg-card-2); padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] { background-color: var(--bg-card); border-bottom: 2px solid var(--accent); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# UTILITAIRES : EXPORT EXCEL / PDF
# ==========================================
def exporter_excel_bytes(df: pd.DataFrame, nom_feuille="Données"):
    """Retourne les bytes d'un fichier Excel généré à partir d'un DataFrame."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nom_feuille[:31] or "Données")
        worksheet = writer.sheets[nom_feuille[:31] or "Données"]
        for i, col in enumerate(df.columns):
            largeur = min(max(len(str(col)), df[col].astype(str).map(len).max() if len(df) else 10) + 2, 50)
            worksheet.column_dimensions[worksheet.cell(row=1, column=i + 1).column_letter].width = largeur
    return buffer.getvalue()

def exporter_pdf_bytes(df: pd.DataFrame, titre="Export", colonnes_max=8):
    """Retourne les bytes d'un PDF listant un DataFrame sous forme de tableau."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(titre, styles["Title"]), Spacer(1, 0.4*cm)]
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.5*cm))

    df_aff = df.copy()
    if len(df_aff.columns) > colonnes_max:
        df_aff = df_aff.iloc[:, :colonnes_max]

    df_aff = df_aff.astype(str)
    data = [list(df_aff.columns)] + df_aff.values.tolist()

    tableau = Table(data, repeatRows=1)
    tableau.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f7")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(tableau)
    doc.build(elements)
    return buffer.getvalue()

def afficher_boutons_export(df: pd.DataFrame, nom_base: str, titre_pdf: str = None, key_prefix: str = ""):
    """Affiche côte à côte un bouton d'export Excel et un bouton d'export PDF pour un DataFrame."""
    if df.empty:
        return
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📊 Exporter en Excel",
            data=exporter_excel_bytes(df, nom_base),
            file_name=f"{nom_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"xlsx_{key_prefix}", use_container_width=True
        )
    with c2:
        st.download_button(
            "📄 Exporter en PDF",
            data=exporter_pdf_bytes(df, titre_pdf or nom_base),
            file_name=f"{nom_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key=f"pdf_{key_prefix}", use_container_width=True
        )

def pill_statut(statut: str) -> str:
    """Retourne un badge HTML coloré selon le statut."""
    s = str(statut).lower()
    if "validé" in s or "financé" in s or "approuvé" in s:
        classe = "pill-valide"
    elif "refusé" in s:
        classe = "pill-refuse"
    elif "modification" in s:
        classe = "pill-modif"
    else:
        classe = "pill-attente"
    return f'<span class="pill {classe}">{statut}</span>'

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

def migrer_schema():
    """Ajoute les nouvelles colonnes nécessaires si elles n'existent pas déjà (compatible avec une base existante)."""
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    migrations = [
        ("discussions", "archives_par", "TEXT DEFAULT '[]'"),
        ("etudes_metier", "vus_json", "TEXT DEFAULT '[]'"),
        ("cahiers_charges", "vus_par_json", "TEXT DEFAULT '[]'"),
    ]
    for table, colonne, type_def in migrations:
        cursor.execute(f"PRAGMA table_info({table})")
        colonnes_existantes = [c[1] for c in cursor.fetchall()]
        if colonne not in colonnes_existantes:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {type_def}")
    conn.commit()
    conn.close()

init_db()
migrer_schema()

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
            st.session_state.heure_connexion = datetime.now()
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

def obtenir_notifications_chat(dept_nom):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom_groupe, membres_json, archives_par FROM discussions")
    discs = cursor.fetchall()

    notifs_chat = []
    for d_id, nom_g, membres_j, archives_j in discs:
        membres = json.loads(membres_j)
        archives = json.loads(archives_j) if archives_j else []
        if dept_nom in membres and dept_nom not in archives:
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

def obtenir_toutes_notifications(nom_dept, type_profil):
    """Centralise toutes les notifications actionnables pour le département connecté."""
    conn = get_db_connection()
    cursor = conn.cursor()
    notifs = []

    # --- Chat non lus (par discussion) ---
    for notif in notifs_chat_list:
        notifs.append({
            "icone": "💬", "label": f"{notif['nom']} ({notif['count']} message(s) non lu(s))",
            "cible_tab": "4. Messagerie & Chat", "cible_disc": notif["disc_id"], "key": f"chat_{notif['disc_id']}"
        })

    # --- Études reçues non consultées ---
    cursor.execute("SELECT id, departement, titre, destinataires_partage, vus_json FROM etudes_metier WHERE departement != ?", (nom_dept,))
    for e_id, e_dept, e_titre, dest_j, vus_j in cursor.fetchall():
        dests = json.loads(dest_j) if dest_j else []
        vus = json.loads(vus_j) if vus_j else []
        if nom_dept in dests and nom_dept not in vus:
            notifs.append({
                "icone": "⚙️", "label": f"Nouvelle étude de [{e_dept}] : {e_titre}",
                "cible_tab": "1. Études & Ingénierie", "cible_disc": None, "key": f"etude_{e_id}"
            })

    # --- Cahiers des charges reçus non consultés ---
    cursor.execute("SELECT id, departement, titre, destinataires_avis, vus_par_json FROM cahiers_charges WHERE departement != ?", (nom_dept,))
    for c_id, c_dept, c_titre_raw, dest_j, vus_j in cursor.fetchall():
        dests = json.loads(dest_j) if dest_j else []
        vus = json.loads(vus_j) if vus_j else []
        if nom_dept in dests and nom_dept not in vus:
            notifs.append({
                "icone": "📋", "label": f"Nouveau CDC de [{c_dept}] : {c_titre_raw.split('||')[0]}",
                "cible_tab": "2. Cahiers des Charges", "cible_disc": None, "key": f"cdc_{c_id}"
            })

    # --- Demandes en attente de validation pour ce pôle ---
    if type_profil in ["achats", "finance", "fondateur"]:
        if type_profil == "achats":
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'achats' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
        elif type_profil == "finance":
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'finance' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
        else:
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'direction' OR statut LIKE 'En attente%'")
        nb_a_valider = cursor.fetchone()[0]
        if nb_a_valider > 0:
            notifs.append({
                "icone": "🛡️", "label": f"{nb_a_valider} dossier(s) en attente de votre validation",
                "cible_tab": "3. Besoins & Achats", "cible_disc": None, "key": "valid_achats"
            })

    # --- Corrections demandées à l'émetteur ---
    cursor.execute("SELECT COUNT(*) FROM demandes WHERE departement = ? AND statut = 'Demande de Modification'", (nom_dept,))
    nb_corrections = cursor.fetchone()[0]
    if nb_corrections > 0:
        notifs.append({
            "icone": "✏️", "label": f"{nb_corrections} demande(s) à corriger suite à une remarque",
            "cible_tab": "3. Besoins & Achats", "cible_disc": None, "key": "correction_emetteur"
        })

    conn.close()
    return notifs

notifs_chat_list = obtenir_notifications_chat(nom_dept)
total_chat_notifs = sum(item["count"] for item in notifs_chat_list)
toutes_notifs = obtenir_toutes_notifications(nom_dept, profil["type"])

if toutes_notifs:
    st.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #f85149; text-align: center; margin-bottom: 10px;">
        <span style="font-size: 1.1rem;">🔔</span> <b style="color: #f85149;">Centre de Notifications</b><br>
        <span class="badge-notification">{len(toutes_notifs)} élément(s) à traiter</span>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar.expander("👉 Téléportation interactive", expanded=True):
        for notif in toutes_notifs:
            if st.button(f"{notif['icone']} {notif['label']}", key=f"notif_btn_{notif['key']}", use_container_width=True):
                if notif["cible_disc"] is not None:
                    st.session_state.discussion_active_id = notif["cible_disc"]
                st.session_state.tab_actif = notif["cible_tab"]
                st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("Se déconnecter"):
    duree = ""
    if "heure_connexion" in st.session_state:
        delta = datetime.now() - st.session_state.heure_connexion
        minutes = int(delta.total_seconds() // 60)
        duree = f"Durée de session : {minutes // 60}h{minutes % 60:02d}min"
    ajouter_log("Déconnexion", profil["nom"], duree or "Durée de session inconnue")
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

# --- NAVIGATION ONGLES PRINCIPAUX (AVEC MODULE DIRECTION CORBEILLE SI FONDATEUR) ---
onglets_possibles = ["1. Études & Ingénierie", "2. Cahiers des Charges", "3. Besoins & Achats", "4. Messagerie & Chat", "📖 Journal de Bord", "🔍 Recherche Globale"]
if profil["type"] in ["achats", "finance", "fondateur"]:
    onglets_possibles.append("📊 Pôle de Contrôle (Suivi Global)")
    onglets_possibles.append("📈 Statistiques")
if profil["type"] == "fondateur":
    onglets_possibles.append("🕵️ Audit & Traçabilité")
    onglets_possibles.append("🗑️ Corbeille & Historique Suppressions")

cols_tabs = st.columns(len(onglets_possibles))
for idx, tab_nom in enumerate(onglets_possibles):
    is_active = (st.session_state.tab_actif == tab_nom)
    btn_type = "primary" if is_active else "secondary"
    if cols_tabs[idx].button(tab_nom, key=f"main_nav_tab_{idx}", use_container_width=True, type=btn_type):
        st.session_state.tab_actif = tab_nom
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 1. MODULE INGÉNIERIE & ÉTUDES MÉTIER
# ==========================================
def afficher_module_etudes(nom_departement, type_profil):
    st.subheader(f"⚙️ Centre d'Ingénierie & Traçabilité des Études — {nom_departement}")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    t1, t2, t3 = st.tabs(["1. Nouvelle Étude & Partage", "2. Études Reçues", "3. 📜 Historique & Gestion"])
    
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
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date, vus_json FROM etudes_metier WHERE departement != ? ORDER BY id DESC", (nom_departement,))
        etudes = cursor.fetchall()
        recus = [e for e in etudes if nom_departement in (json.loads(e[5]) if e[5] else []) or type_profil == "fondateur"]

        # Marquer comme vues par ce département (pour désactiver la notification correspondante)
        for e in recus:
            vus = json.loads(e[7]) if e[7] else []
            if nom_departement not in vus:
                vus.append(nom_departement)
                cursor.execute("UPDATE etudes_metier SET vus_json = ? WHERE id = ?", (json.dumps(vus), e[0]))
        conn.commit()
        conn.close()

        if recus:
            depts_dispo = ["Tous"] + sorted(set(e[1] for e in recus))
            st.markdown('<div class="filter-bar"><div class="filter-bar-title">🔎 Filtrer</div>', unsafe_allow_html=True)
            c_f1, c_f2 = st.columns([2, 1])
            with c_f1:
                recherche = st.text_input("Rechercher (titre ou description)", key="recherche_etudes_recues")
            with c_f2:
                dept_choisi = st.selectbox("Département émetteur", depts_dispo, key="dept_etudes_recues")
            st.markdown('</div>', unsafe_allow_html=True)

            def _match(e):
                data = json.loads(e[3]) if e[3] else {}
                texte = f"{e[2]} {data.get('details', '')}".lower()
                ok_recherche = recherche.lower() in texte if recherche else True
                ok_dept = (dept_choisi == "Tous") or (e[1] == dept_choisi)
                return ok_recherche and ok_dept

            recus_filtres = [e for e in recus if _match(e)]

            df_export = pd.DataFrame([{
                "ID": e[0], "Département": e[1], "Titre": e[2],
                "Description": (json.loads(e[3]) if e[3] else {}).get("details", ""), "Date": e[6]
            } for e in recus_filtres])
            afficher_boutons_export(df_export, "etudes_recues", "Études Reçues", key_prefix="etudes_recues")

            if recus_filtres:
                for e in recus_filtres:
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
                st.info("Aucune étude ne correspond aux filtres.")
        else:
            st.info("Aucune étude reçue.")

    with t3:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT id, departement, titre, donnees_json, date FROM etudes_metier ORDER BY id DESC" if type_profil == "fondateur" else "SELECT id, departement, titre, donnees_json, date FROM etudes_metier WHERE departement = ? ORDER BY id DESC"
        cursor.execute(query, () if type_profil == "fondateur" else (nom_departement,))
        mes_e = cursor.fetchall()
        conn.close()
        
        if mes_e:
            recherche_h = st.text_input("🔎 Rechercher un titre", key="recherche_etudes_historique")
            mes_e_filtres = [me for me in mes_e if (recherche_h.lower() in me[2].lower()) or not recherche_h]

            df_export_h = pd.DataFrame([{
                "ID": me[0], "Département": me[1], "Titre": me[2], "Date": me[4]
            } for me in mes_e_filtres])
            afficher_boutons_export(df_export_h, "etudes_historique", "Historique des Études", key_prefix="etudes_hist")

            for me in mes_e_filtres:
                me_id, me_dept, me_titre, me_json, me_date = me
                c_info1, c_info2 = st.columns([4, 1])
                with c_info1:
                    st.write(f"📜 **[{me_dept}] {me_titre}** — {me_date}")
                with c_info2:
                    if st.button("🗑️ Supprimer", key=f"del_etude_{me_id}"):
                        archiver_dans_corbeille(me_dept, "Étude Technique", me_titre, {"details_json": me_json, "date": me_date})
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM etudes_metier WHERE id = ?", (me_id,))
                        conn.commit()
                        conn.close()
                        ajouter_log("Suppression Étude", me_dept, f"Étude supprimée : {me_titre}")
                        st.success("Étude supprimée et archivée.")
                        st.rerun()
        else:
            st.info("Aucune étude enregistrée.")

# ==========================================
# 2. MODULE CAHIERS DES CHARGES
# ==========================================
def afficher_module_cdc(nom_departement, type_profil):
    st.subheader("📋 Cahiers des Charges & Documents Partagés")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    t1, t2 = st.tabs(["1. Publier un Cahier des Charges", "2. Documents Reçus & Gestion"])
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
                ajouter_log("Cahier des Charges", nom_departement, f"CDC publié : {titre}")
                st.success("Document diffusé avec succès.")
                st.rerun()

    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis, vus_par_json FROM cahiers_charges ORDER BY id DESC")
        cdcs = cursor.fetchall()

        cdcs_visibles = []
        for c in cdcs:
            c_id, c_dept, c_titre_raw, c_txt, c_date, c_dest_raw, c_vus_raw = c
            dests = json.loads(c_dest_raw) if c_dest_raw else []
            if nom_departement in dests or c_dept == nom_departement or type_profil == "fondateur":
                cdcs_visibles.append(c)
                if c_dept != nom_departement:
                    vus = json.loads(c_vus_raw) if c_vus_raw else []
                    if nom_departement not in vus:
                        vus.append(nom_departement)
                        cursor.execute("UPDATE cahiers_charges SET vus_par_json = ? WHERE id = ?", (json.dumps(vus), c_id))
        conn.commit()
        conn.close()

        if cdcs_visibles:
            depts_dispo_cdc = ["Tous"] + sorted(set(c[1] for c in cdcs_visibles))
            st.markdown('<div class="filter-bar"><div class="filter-bar-title">🔎 Filtrer</div>', unsafe_allow_html=True)
            cf1, cf2 = st.columns([2, 1])
            with cf1:
                recherche_cdc = st.text_input("Rechercher (titre ou contenu)", key="recherche_cdc")
            with cf2:
                dept_cdc = st.selectbox("Département émetteur", depts_dispo_cdc, key="dept_cdc")
            st.markdown('</div>', unsafe_allow_html=True)

            def _match_cdc(c):
                titre_seul = c[2].split("||")[0]
                texte = f"{titre_seul} {c[3]}".lower()
                ok_recherche = recherche_cdc.lower() in texte if recherche_cdc else True
                ok_dept = (dept_cdc == "Tous") or (c[1] == dept_cdc)
                return ok_recherche and ok_dept

            cdcs_filtres = [c for c in cdcs_visibles if _match_cdc(c)]

            df_export_cdc = pd.DataFrame([{
                "ID": c[0], "Département": c[1], "Titre": c[2].split("||")[0],
                "Contenu": c[3], "Date": c[4]
            } for c in cdcs_filtres])
            afficher_boutons_export(df_export_cdc, "cahiers_des_charges", "Cahiers des Charges", key_prefix="cdc")
        else:
            cdcs_filtres = []

        for c in cdcs_filtres:
            c_id, c_dept, c_titre_raw, c_txt, c_date, c_dest_raw, c_vus_raw = c
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

                if c_dept == nom_departement or type_profil == "fondateur":
                    if st.button("🗑️ Supprimer ce Cahier des Charges", key=f"del_cdc_{c_id}"):
                        archiver_dans_corbeille(c_dept, "Cahier des Charges", t_titre, {"contenu": c_txt, "date": c_date})
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM cahiers_charges WHERE id = ?", (c_id,))
                        conn.commit()
                        conn.close()
                        ajouter_log("Suppression CDC", c_dept, f"CDC supprimé : {t_titre}")
                        st.success("Cahier des charges supprimé et archivé.")
                        st.rerun()

# ==========================================
# 3. MODULE BESOINS & ACHATS
# ==========================================
def afficher_module_achats(nom_departement, type_profil):
    st.subheader("🛒 Gestion des Demandes d'Achat & Validations")
    
    est_controleur = type_profil in ["achats", "finance", "fondateur"]
    titres_sous_tabs = ["1. Émettre une Demande", "2. Suivi de mes Demandes & Corrections"]
    if est_controleur:
        titres_sous_tabs.append("3. 🛡️ Espace de Validation")
        
    sub_tabs = st.tabs(titres_sous_tabs)
    
    # 1. ÉMISSION
    with sub_tabs[0]:
        with st.form("form_demande_achat", clear_on_submit=True):
            titre = st.text_input("Intitulé du besoin")
            desc = st.text_area("Description du besoin / Spécifications")
            montant = st.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
            fournisseur = st.text_input("Fournisseur proposé (Facultatif)")
            devis = st.file_uploader("📎 Importer devis", type=["pdf", "png", "jpg", "xlsx"])
            
            if st.form_submit_button("Soumettre la Demande") and titre and montant > 0:
                f_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, devis)
                
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
                ajouter_log("Demande d'Achat", nom_departement, f"Demande soumise : {titre} ({montant} €)")
                st.success("Demande enregistrée dans le circuit de validation.")
                st.rerun()

    # 2. SUIVI ET FORMULAIRE DE RESSOUMISSION
    with sub_tabs[1]:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM demandes WHERE departement = ? ORDER BY id DESC", conn, params=(nom_departement,))
        conn.close()
        
        if not df.empty:
            st.markdown('<div class="filter-bar"><div class="filter-bar-title">🔎 Filtrer mes demandes</div>', unsafe_allow_html=True)
            fc1, fc2, fc3 = st.columns([2, 1.2, 1.2])
            with fc1:
                recherche_dem = st.text_input("Rechercher (titre/description)", key="recherche_mes_demandes")
            with fc2:
                statuts_dispo_dem = ["Tous"] + sorted(df["statut"].unique().tolist())
                statut_dem_filtre = st.selectbox("Statut", statuts_dispo_dem, key="statut_mes_demandes")
            with fc3:
                montant_min = st.number_input("Montant minimum (€)", min_value=0.0, step=100.0, key="montant_min_mes_demandes")
            st.markdown('</div>', unsafe_allow_html=True)

            df_filtre_dem = df.copy()
            if recherche_dem:
                masque = df_filtre_dem["titre"].str.contains(recherche_dem, case=False, na=False) | df_filtre_dem["cahier_charges"].str.contains(recherche_dem, case=False, na=False)
                df_filtre_dem = df_filtre_dem[masque]
            if statut_dem_filtre != "Tous":
                df_filtre_dem = df_filtre_dem[df_filtre_dem["statut"] == statut_dem_filtre]
            if montant_min > 0:
                df_filtre_dem = df_filtre_dem[df_filtre_dem["montant"] >= montant_min]

            afficher_boutons_export(
                df_filtre_dem[["id", "date", "titre", "montant", "fournisseur", "statut", "etape_actuelle"]],
                "mes_demandes_achat", "Mes Demandes d'Achat", key_prefix="mes_demandes"
            )

            for _, r in df_filtre_dem.iterrows():
                with st.expander(f"📌 #{r['id']} - {r['titre']} ({r['montant']:,.2f} €) - Statut: {r['statut']}"):
                    st.markdown(pill_statut(r['statut']), unsafe_allow_html=True)
                    st.write(f"**Description :** {r['cahier_charges']}")
                    
                    c_del1, c_del2 = st.columns([4, 1])
                    with c_del2:
                        if st.button("🗑️ Supprimer", key=f"del_dem_{r['id']}"):
                            archiver_dans_corbeille(nom_departement, "Demande d'Achat", f"#{r['id']} - {r['titre']} ({r['montant']} €)", {"statut": r['statut']})
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM demandes WHERE id = ?", (r['id'],))
                            conn.commit()
                            conn.close()
                            ajouter_log("Suppression Demande", nom_departement, f"Demande #{r['id']} supprimée : {r['titre']}")
                            st.success("Demande supprimée et archivée.")
                            st.rerun()

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
                                
                                nouv_etape = "achats" if type_profil != "achats" else "finance"
                                nouv_statut = f"En attente validation {nouv_etape.capitalize()} (Après correction)"
                                
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE demandes SET titre=?, cahier_charges=?, montant=?, fichier_devis=?, statut=?, etape_actuelle=?, retour_remarque='' WHERE id=?
                                """, (c_titre, c_desc, c_montant, nom_f, nouv_statut, nouv_etape, r['id']))
                                conn.commit()
                                conn.close()
                                ajouter_log("Correction Demande", nom_departement, f"Demande #{r['id']} corrigée et renvoyée")
                                st.success("Demande corrigée et renvoyée en validation !")
                                st.rerun()
        else:
            st.info("Aucune demande émise.")

    # 3. ESPACE DE VALIDATION CORRIGÉ (FLUX FINANCE -> DIRECTION)
    if est_controleur:
        with sub_tabs[2]:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if type_profil == "achats":
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'achats' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
            elif type_profil == "finance":
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'finance' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
            else:
                cursor.execute("SELECT * FROM demandes WHERE etape_actuelle = 'direction' OR statut LIKE 'En attente%'")
            
            demandes_a_traiter = cursor.fetchall()
            conn.close()

            if demandes_a_traiter:
                df_a_traiter = pd.DataFrame(demandes_a_traiter, columns=[
                    "id", "departement", "titre", "cahier_charges", "montant", "fournisseur",
                    "statut", "etape_actuelle", "avis_achats", "avis_finance", "motif_refus",
                    "date", "fichier_devis", "retour_remarque"
                ])
                afficher_boutons_export(
                    df_a_traiter[["id", "date", "departement", "titre", "montant", "fournisseur", "statut"]],
                    "dossiers_a_valider", "Dossiers en Attente de Validation", key_prefix="validation"
                )
                for d in demandes_a_traiter:
                    d_id, d_dept, d_titre, d_desc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_motif, d_date, d_fich, d_rem = d
                    
                    with st.expander(f"📥 Dossier #{d_id} - [{d_dept}] {d_titre} ({d_montant} €)"):
                        st.write(f"**Description :** {d_desc}")
                        st.write(f"**Fournisseur :** {d_fourn}")
                        
                        col_v1, col_v2, col_v3 = st.columns(3)
                        
                        # APPROUVER CORRIGÉ (FLUX SANS BUG ET PASSAGE DIRECTION OBLIGATOIRE POUR LA FINANCE)
                        with col_v1:
                            if st.button(f"🟢 Approuver #{d_id}", key=f"app_{d_id}"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                
                                if type_profil == "achats":
                                    prochaine = "direction" if d_dept == "Finance & Comptabilité" else "finance"
                                    st_msg = "En attente validation Direction" if prochaine == "direction" else "En attente validation Finance"
                                    cursor.execute("UPDATE demandes SET avis_achats='Approuvé', etape_actuelle=?, statut=? WHERE id=?", (prochaine, st_msg, d_id))
                                
                                elif type_profil == "finance":
                                    # Correction demandée : La finance approuve mais renvoie obligatoirement à la direction pour le décaissement final !
                                    cursor.execute("UPDATE demandes SET avis_finance='Approuvé', etape_actuelle='direction', statut='En attente validation Direction' WHERE id=?", (d_id,))
                                
                                else: # Direction Générale (Seule habilitée à décaisser définitivement)
                                    cursor.execute("UPDATE demandes SET etape_actuelle='terminee', statut='Validé & Financé' WHERE id=?", (d_id,))
                                    conn.commit()
                                    conn.close()
                                    solde_actuel = get_valeur_globale("solde_restant")
                                    set_valeur_globale("solde_restant", solde_actuel - float(d_montant))
                                    ajouter_log("Décaissement", nom_departement, f"Dossier #{d_id} validé et financé ({d_montant} €)")
                                    st.success(f"Dossier #{d_id} approuvé et décaissement effectué !")
                                    st.rerun()
                                    
                                conn.commit()
                                conn.close()
                                ajouter_log("Approbation", nom_departement, f"Dossier #{d_id} approuvé par {type_profil}")
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
                                ajouter_log("Demande de Modification", nom_departement, f"Dossier #{d_id} renvoyé pour correction : {remarque}")
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
                                ajouter_log("Refus Demande", nom_departement, f"Dossier #{d_id} refusé : {motif}")
                                st.error("Dossier refusé.")
                                st.rerun()
            else:
                st.info("Aucune demande en attente de validation pour votre pôle.")

# ==========================================
# 4. MODULE MESSAGERIE & CHAT UNIFIÉ
# ==========================================
@st.fragment(run_every="3s")
def afficher_zone_messages(discussion_id, nom_dept):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, expediteur, texte, date, lus_json FROM messages_chat WHERE discussion_id = ?", (discussion_id,))
    messages = cursor.fetchall()
    
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
                
                c_m1, c_m2 = st.columns([5, 1])
                with c_m1:
                    with st.chat_message(role, avatar=avatar):
                        st.markdown(f"**{exp}** <small style='color: #8b949e;'>({dt})</small>", unsafe_allow_html=True)
                        st.write(txt)
                with c_m2:
                    if is_me:
                        if st.button("🗑️", key=f"del_msg_{m_id}", help="Supprimer ce message"):
                            archiver_dans_corbeille(nom_dept, "Message Chat", txt[:40], {"discussion_id": discussion_id, "date": dt})
                            conn_del = get_db_connection()
                            cursor_del = conn_del.cursor()
                            cursor_del.execute("DELETE FROM messages_chat WHERE id = ?", (m_id,))
                            conn_del.commit()
                            conn_del.close()
                            st.rerun()
        else:
            st.info("Discussion démarrée. Envoyez le premier message !")
    conn.close()

def afficher_module_messagerie_unifiee(nom_departement, type_profil):
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
        cursor.execute("SELECT id, nom_groupe, membres_json, archives_par FROM discussions ORDER BY id DESC")
        toutes_discs = cursor.fetchall()
        
        discussions_utilisateur = []
        for d_id, nom_g, membres_j, archives_j in toutes_discs:
            membres = json.loads(membres_j)
            archives = json.loads(archives_j) if archives_j else []
            if nom_departement in membres and nom_departement not in archives:
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
            if st.session_state.discussion_active_id is None or st.session_state.discussion_active_id not in [d[0] for d in discussions_utilisateur]:
                st.session_state.discussion_active_id = discussions_utilisateur[0][0]

            for d_id, label, nom_g, count in discussions_utilisateur:
                type_button = "primary" if st.session_state.discussion_active_id == d_id else "secondary"
                if st.button(label, key=f"btn_disc_{d_id}", use_container_width=True, type=type_button):
                    st.session_state.discussion_active_id = d_id
                    st.rerun()
        else:
            st.session_state.discussion_active_id = None
            st.info("Aucune discussion active.")

    with col_chat:
        if st.session_state.discussion_active_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT nom_groupe, membres_json, createur FROM discussions WHERE id = ?", (st.session_state.discussion_active_id,))
            disc_info = cursor.fetchone()
            conn.close()

            if disc_info:
                nom_g, membres_j, createur = disc_info
                membres = json.loads(membres_j)
                est_createur = (createur == nom_departement)

                c_head1, c_head2, c_head3 = st.columns([4, 1, 1])
                with c_head1:
                    st.markdown(f"""
                    <div class="channel-header">
                        <b style="font-size: 1.1rem; color: #ffffff;">👥 {nom_g}</b><br>
                        <small style="color: #8b949e;">Membres : {', '.join(membres)}</small>
                    </div>
                    """, unsafe_allow_html=True)
                with c_head2:
                    if st.button("🚪 Quitter", key=f"quitter_{st.session_state.discussion_active_id}", help="La discussion disparaît de votre liste, elle reste visible pour les autres membres", use_container_width=True):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT archives_par FROM discussions WHERE id = ?", (st.session_state.discussion_active_id,))
                        archives_actuel = json.loads(cursor.fetchone()[0] or "[]")
                        if nom_departement not in archives_actuel:
                            archives_actuel.append(nom_departement)
                        cursor.execute("UPDATE discussions SET archives_par = ? WHERE id = ?", (json.dumps(archives_actuel), st.session_state.discussion_active_id))
                        conn.commit()
                        conn.close()
                        ajouter_log("Quitter Discussion", nom_departement, f"A quitté la discussion : {nom_g}")
                        st.session_state.discussion_active_id = None
                        st.rerun()
                with c_head3:
                    if est_createur or type_profil == "fondateur":
                        if st.button("🗑️ Supprimer", key=f"suppr_disc_{st.session_state.discussion_active_id}", help="Suppression définitive pour tous les membres", use_container_width=True):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("SELECT id, expediteur, texte, date FROM messages_chat WHERE discussion_id = ?", (st.session_state.discussion_active_id,))
                            tous_msgs = cursor.fetchall()
                            archiver_dans_corbeille(
                                nom_departement, "Discussion Complète", f"{nom_g} ({len(tous_msgs)} message(s))",
                                {"membres": membres, "messages": [{"expediteur": m[1], "texte": m[2], "date": m[3]} for m in tous_msgs]}
                            )
                            cursor.execute("DELETE FROM messages_chat WHERE discussion_id = ?", (st.session_state.discussion_active_id,))
                            cursor.execute("DELETE FROM discussions WHERE id = ?", (st.session_state.discussion_active_id,))
                            conn.commit()
                            conn.close()
                            ajouter_log("Suppression Discussion", nom_departement, f"Discussion supprimée définitivement : {nom_g}")
                            st.session_state.discussion_active_id = None
                            st.success("Discussion supprimée et archivée pour la Direction.")
                            st.rerun()

                afficher_zone_messages(st.session_state.discussion_active_id, nom_departement)

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

# ==========================================
# 5. JOURNAL DE BORD QUOTIDIEN
# ==========================================
def afficher_module_journal_bord(nom_departement):
    st.subheader(f"📖 Journal de Bord Quotidien & Cahier de Notes — {nom_departement}")
    st.markdown("Consignez ici le fil des événements, activités, observations et faits marquants du département par date et heure.")
    
    col_saisie, col_historique = st.columns([1.2, 1.8])

    with col_saisie:
        st.markdown("#### ✍️ Ajouter une note")
        with st.form("form_journal_note", clear_on_submit=True):
            date_selectionnee = st.date_input("Date de l'événement", value=datetime.now())
            note_texte = st.text_area("Note / Compte-rendu quotidien", height=140, placeholder="Ex: Début de la récolte sur la parcelle B...")
            auteur_nom = st.text_input("Auteur / Rédacteur", value=f"Équipe {nom_departement}")
            
            if st.form_submit_button("📘 Enregistrer dans le Journal") and note_texte:
                heure_actuelle = datetime.now().strftime("%H:%M")
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO journal_bord (departement, auteur, note, date_note, heure_note)
                    VALUES (?, ?, ?, ?, ?)
                """, (nom_departement, auteur_nom, note_texte, str(date_selectionnee), heure_actuelle))
                conn.commit()
                conn.close()
                st.success("Note ajoutée au journal de bord !")
                st.rerun()

    with col_historique:
        st.markdown("#### 📜 Historique & Notes du Département")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, auteur, note, date_note, heure_note FROM journal_bord WHERE departement = ? ORDER BY date_note DESC, id DESC", (nom_departement,))
        notes = cursor.fetchall()
        conn.close()

        if notes:
            st.markdown('<div class="filter-bar"><div class="filter-bar-title">🔎 Filtrer</div>', unsafe_allow_html=True)
            fj1, fj2, fj3 = st.columns([1.2, 1.2, 2])
            with fj1:
                dates_dispos = ["Toutes les dates"] + sorted(list(set(n[3] for n in notes)), reverse=True)
                filtre_d = st.selectbox("📅 Date", dates_dispos)
            with fj2:
                auteurs_dispos = ["Tous"] + sorted(list(set(n[1] for n in notes)))
                filtre_auteur = st.selectbox("👤 Auteur", auteurs_dispos)
            with fj3:
                recherche_note = st.text_input("Rechercher dans les notes")
            st.markdown('</div>', unsafe_allow_html=True)

            notes_filtrees = [
                n for n in notes
                if (filtre_d == "Toutes les dates" or filtre_d == n[3])
                and (filtre_auteur == "Tous" or filtre_auteur == n[1])
                and (not recherche_note or recherche_note.lower() in n[2].lower())
            ]

            df_export_journal = pd.DataFrame([{
                "Date": n[3], "Heure": n[4], "Auteur": n[1], "Note": n[2]
            } for n in notes_filtrees])
            afficher_boutons_export(df_export_journal, f"journal_de_bord_{nom_departement}", "Journal de Bord", key_prefix="journal")

            if not notes_filtrees:
                st.info("Aucune note ne correspond aux filtres.")

            for n_id, n_auteur, n_txt, n_date, n_heure in notes_filtrees:
                c_n1, c_n2 = st.columns([5, 1])
                with c_n1:
                    st.markdown(f"""
                    <div class="note-card">
                        <div class="note-date">📅 {n_date} à {n_heure} | Par : {n_auteur}</div>
                        <div style="margin-top: 8px; font-size: 0.95rem; color: #e6edf3;">{n_txt}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c_n2:
                    if st.button("🗑️", key=f"del_note_{n_id}", help="Supprimer cette note"):
                        archiver_dans_corbeille(nom_departement, "Journal de Bord", n_txt[:40], {"date": n_date, "auteur": n_auteur})
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM journal_bord WHERE id = ?", (n_id,))
                        conn.commit()
                        conn.close()
                        st.success("Note supprimée et archivée.")
                        st.rerun()
        else:
            st.info("Aucune note enregistrée dans le journal pour le moment.")

# ==========================================
# 6. MODULE SUIVI GLOBAL POUR PÔLE DE CONTRÔLE
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
    st.markdown('<div class="filter-bar"><div class="filter-bar-title">🔎 Filtrer</div>', unsafe_allow_html=True)
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        depts_dispos = ["Tous"] + sorted(df_demandes['departement'].unique().tolist())
        dept_filtre = st.selectbox("Département Émetteur", depts_dispos)
    with col_f2:
        statuts_dispos = ["Tous"] + sorted(df_demandes['statut'].unique().tolist())
        statut_filtre = st.selectbox("Statut de validation", statuts_dispos)
    with col_f3:
        recherche_g = st.text_input("Recherche (titre/fournisseur)")
    with col_f4:
        montant_min_g = st.number_input("Montant minimum (€)", min_value=0.0, step=100.0)
    st.markdown('</div>', unsafe_allow_html=True)

    df_filtré = df_demandes.copy()
    if dept_filtre != "Tous":
        df_filtré = df_filtré[df_filtré['departement'] == dept_filtre]
    if statut_filtre != "Tous":
        df_filtré = df_filtré[df_filtré['statut'] == statut_filtre]
    if recherche_g:
        masque_g = df_filtré['titre'].str.contains(recherche_g, case=False, na=False) | df_filtré['fournisseur'].str.contains(recherche_g, case=False, na=False)
        df_filtré = df_filtré[masque_g]
    if montant_min_g > 0:
        df_filtré = df_filtré[df_filtré['montant'] >= montant_min_g]

    colonnes_affichees = ['id', 'date', 'departement', 'titre', 'montant', 'fournisseur', 'statut', 'etape_actuelle', 'avis_achats', 'avis_finance']
    afficher_boutons_export(df_filtré[colonnes_affichees], "suivi_global_demandes", "Suivi Global des Demandes d'Achat", key_prefix="suivi_global")

    st.dataframe(
        df_filtré[colonnes_affichees],
        use_container_width=True,
        hide_index=True
    )

# ==========================================
# 7. MODULE DIRECTION : CORBEILLE & HISTORIQUE DES SUPPRESSIONS
# ==========================================
def afficher_module_direction_corbeille():
    st.subheader("🗑️ Supervisions des Éléments Supprimés (Corbeille Centralisée)")
    st.markdown("Cet espace exclusif à la Direction Générale liste l'ensemble des éléments supprimés par les différents départements (messages, notes, demandes, études, cahiers des charges) pour des besoins d'audit et de traçabilité.")

    conn = get_db_connection()
    df_corbeille = pd.read_sql_query("SELECT * FROM corbeille_archives ORDER BY id DESC", conn)
    conn.close()

    if not df_corbeille.empty:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            dept_c_filtre = st.selectbox("Filtrer par Département :", ["Tous"] + list(df_corbeille['departement_auteur'].unique()))
        with col_c2:
            type_c_filtre = st.selectbox("Filtrer par Type d'élément :", ["Tous"] + list(df_corbeille['type_element'].unique()))

        df_c_filtre = df_corbeille.copy()
        if dept_c_filtre != "Tous":
            df_c_filtre = df_c_filtre[df_c_filtre['departement_auteur'] == dept_c_filtre]
        if type_c_filtre != "Tous":
            df_c_filtre = df_c_filtre[df_c_filtre['type_element'] == type_c_filtre]

        afficher_boutons_export(
            df_c_filtre[['id', 'date_suppression', 'departement_auteur', 'type_element', 'resume']],
            "corbeille_archives", "Corbeille & Historique des Suppressions", key_prefix="corbeille"
        )

        for _, row in df_c_filtre.iterrows():
            with st.expander(f"🗑️ [{row['type_element']}] - Département : {row['departement_auteur']} (Supprimé le {row['date_suppression']})"):
                st.write(f"**Résumé / Contenu abrégé :** {row['resume']}")
                if row['details_json']:
                    try:
                        details = json.loads(row['details_json'])
                        st.json(details)
                    except:
                        pass
        
        st.markdown("---")
        if st.button("🧹 Vider entièrement la corbeille d'archives"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM corbeille_archives")
            conn.commit()
            conn.close()
            st.success("La corbeille a été vidée.")
            st.rerun()
    else:
        st.info("Aucun élément supprimé pour l'instant.")

# ==========================================
# 8. MODULE DIRECTION : AUDIT & TRAÇABILITÉ DES CONNEXIONS
# ==========================================
def afficher_module_audit():
    st.subheader("🕵️ Audit & Traçabilité (Connexions, Actions, Durées)")
    st.markdown("Historique complet des connexions et actions de tous les collaborateurs — réservé à la Direction Générale.")

    conn = get_db_connection()
    df_logs = pd.read_sql_query("SELECT * FROM logs_audit ORDER BY id DESC", conn)
    conn.close()

    if df_logs.empty:
        st.info("Aucun événement enregistré pour le moment.")
        return

    # --- Calcul des durées de connexion à partir des logs de déconnexion ---
    import re
    durees_par_acteur = {}
    nb_sessions_par_acteur = {}
    for _, row in df_logs[df_logs['action'] == 'Déconnexion'].iterrows():
        m = re.search(r"(\d+)h(\d+)min", str(row['details']))
        if m:
            minutes = int(m.group(1)) * 60 + int(m.group(2))
            durees_par_acteur[row['acteur']] = durees_par_acteur.get(row['acteur'], 0) + minutes
            nb_sessions_par_acteur[row['acteur']] = nb_sessions_par_acteur.get(row['acteur'], 0) + 1

    if durees_par_acteur:
        st.markdown("#### ⏱️ Temps de connexion cumulé par collaborateur")
        df_temps = pd.DataFrame([
            {
                "Collaborateur": acteur,
                "Sessions terminées": nb_sessions_par_acteur.get(acteur, 0),
                "Temps cumulé": f"{minutes // 60}h{minutes % 60:02d}min",
                "Minutes totales": minutes
            }
            for acteur, minutes in sorted(durees_par_acteur.items(), key=lambda x: -x[1])
        ])
        st.dataframe(df_temps.drop(columns=["Minutes totales"]), use_container_width=True, hide_index=True)
        afficher_boutons_export(df_temps, "temps_connexion_utilisateurs", "Temps de Connexion par Utilisateur", key_prefix="temps_connexion")

    st.markdown("---")
    st.markdown("#### 📜 Journal détaillé des actions")
    st.markdown('<div class="filter-bar"><div class="filter-bar-title">🔎 Filtrer</div>', unsafe_allow_html=True)
    ca1, ca2, ca3 = st.columns(3)
    with ca1:
        acteurs_dispo = ["Tous"] + sorted(df_logs['acteur'].unique().tolist())
        acteur_filtre = st.selectbox("Collaborateur", acteurs_dispo)
    with ca2:
        actions_dispo = ["Toutes"] + sorted(df_logs['action'].unique().tolist())
        action_filtre = st.selectbox("Type d'action", actions_dispo)
    with ca3:
        recherche_audit = st.text_input("Rechercher dans les détails")
    st.markdown('</div>', unsafe_allow_html=True)

    df_logs_filtres = df_logs.copy()
    if acteur_filtre != "Tous":
        df_logs_filtres = df_logs_filtres[df_logs_filtres['acteur'] == acteur_filtre]
    if action_filtre != "Toutes":
        df_logs_filtres = df_logs_filtres[df_logs_filtres['action'] == action_filtre]
    if recherche_audit:
        df_logs_filtres = df_logs_filtres[df_logs_filtres['details'].str.contains(recherche_audit, case=False, na=False)]

    afficher_boutons_export(
        df_logs_filtres[['id', 'date', 'acteur', 'action', 'details']],
        "journal_audit", "Journal d'Audit Complet", key_prefix="audit"
    )
    st.dataframe(
        df_logs_filtres[['date', 'acteur', 'action', 'details']],
        use_container_width=True, hide_index=True
    )

# ==========================================
# 9. MODULE RECHERCHE GLOBALE (TOUS DÉPARTEMENTS)
# ==========================================
def afficher_module_recherche_globale(nom_departement, type_profil):
    st.subheader("🔍 Recherche Globale")
    st.markdown("Recherchez en une fois dans les études, cahiers des charges, demandes d'achat et notes de journal auxquels vous avez accès.")

    requete = st.text_input("🔎 Terme à rechercher", placeholder="Ex : irrigation, devis pompe, budget maintenance...")
    if not requete:
        st.info("Saisissez un mot-clé pour lancer la recherche.")
        return

    q = requete.lower()
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Études ---
    cursor.execute("SELECT id, departement, titre, donnees_json, destinataires_partage, date FROM etudes_metier")
    resultats_etudes = []
    for e_id, e_dept, e_titre, e_json, e_dest, e_date in cursor.fetchall():
        dests = json.loads(e_dest) if e_dest else []
        visible = (e_dept == nom_departement) or (nom_departement in dests) or (type_profil == "fondateur")
        data = json.loads(e_json) if e_json else {}
        texte = f"{e_titre} {data.get('details', '')}".lower()
        if visible and q in texte:
            resultats_etudes.append((e_id, e_dept, e_titre, e_date))

    # --- Cahiers des charges ---
    cursor.execute("SELECT id, departement, titre, contenu, destinataires_avis, date FROM cahiers_charges")
    resultats_cdc = []
    for c_id, c_dept, c_titre_raw, c_txt, c_dest, c_date in cursor.fetchall():
        dests = json.loads(c_dest) if c_dest else []
        visible = (c_dept == nom_departement) or (nom_departement in dests) or (type_profil == "fondateur")
        titre_seul = c_titre_raw.split("||")[0]
        texte = f"{titre_seul} {c_txt}".lower()
        if visible and q in texte:
            resultats_cdc.append((c_id, c_dept, titre_seul, c_date))

    # --- Demandes d'achat ---
    if type_profil == "fondateur":
        cursor.execute("SELECT id, departement, titre, cahier_charges, fournisseur, statut, montant, date FROM demandes")
    else:
        cursor.execute("SELECT id, departement, titre, cahier_charges, fournisseur, statut, montant, date FROM demandes WHERE departement = ?", (nom_departement,))
    resultats_demandes = []
    for d_id, d_dept, d_titre, d_desc, d_fourn, d_statut, d_montant, d_date in cursor.fetchall():
        texte = f"{d_titre} {d_desc} {d_fourn}".lower()
        if q in texte:
            resultats_demandes.append((d_id, d_dept, d_titre, d_statut, d_montant, d_date))

    # --- Journal de bord (du département uniquement) ---
    cursor.execute("SELECT id, auteur, note, date_note FROM journal_bord WHERE departement = ?", (nom_departement,))
    resultats_journal = [n for n in cursor.fetchall() if q in n[2].lower()]

    conn.close()

    total = len(resultats_etudes) + len(resultats_cdc) + len(resultats_demandes) + len(resultats_journal)
    st.markdown(f"**{total} résultat(s) trouvé(s) pour « {requete} »**")
    st.markdown("---")

    if resultats_etudes:
        st.markdown(f"#### ⚙️ Études ({len(resultats_etudes)})")
        for e_id, e_dept, e_titre, e_date in resultats_etudes:
            st.write(f"📁 [{e_dept}] **{e_titre}** — {e_date}")

    if resultats_cdc:
        st.markdown(f"#### 📋 Cahiers des Charges ({len(resultats_cdc)})")
        for c_id, c_dept, t_titre, c_date in resultats_cdc:
            st.write(f"📄 [{c_dept}] **{t_titre}** — {c_date}")

    if resultats_demandes:
        st.markdown(f"#### 🛒 Demandes d'Achat ({len(resultats_demandes)})")
        for d_id, d_dept, d_titre, d_statut, d_montant, d_date in resultats_demandes:
            st.markdown(f"📌 #{d_id} [{d_dept}] **{d_titre}** ({d_montant:,.2f} €) {pill_statut(d_statut)}", unsafe_allow_html=True)

    if resultats_journal:
        st.markdown(f"#### 📖 Journal de Bord ({len(resultats_journal)})")
        for n_id, n_auteur, n_txt, n_date in resultats_journal:
            st.write(f"📅 {n_date} — Par {n_auteur} : {n_txt[:120]}{'...' if len(n_txt) > 120 else ''}")

    if total == 0:
        st.info("Aucun résultat ne correspond à votre recherche.")

# ==========================================
# 10. MODULE STATISTIQUES (DIRECTION / ACHATS / FINANCE)
# ==========================================
def afficher_module_statistiques():
    st.subheader("📈 Statistiques par Département")

    conn = get_db_connection()
    df_demandes = pd.read_sql_query("SELECT * FROM demandes", conn)
    df_etudes = pd.read_sql_query("SELECT * FROM etudes_metier", conn)
    df_cdc = pd.read_sql_query("SELECT * FROM cahiers_charges", conn)
    conn.close()

    if df_demandes.empty and df_etudes.empty and df_cdc.empty:
        st.info("Pas encore assez de données pour générer des statistiques.")
        return

    depts = sorted(set(df_demandes['departement'].tolist() + df_etudes['departement'].tolist() + df_cdc['departement'].tolist()))
    lignes = []
    for d in depts:
        dem_dept = df_demandes[df_demandes['departement'] == d]
        nb_dem = len(dem_dept)
        nb_validees = len(dem_dept[dem_dept['statut'] == 'Validé & Financé'])
        nb_refusees = len(dem_dept[dem_dept['statut'] == 'Refusé'])
        taux_appro = (nb_validees / nb_dem * 100) if nb_dem > 0 else 0
        volume = dem_dept['montant'].sum() if nb_dem > 0 else 0
        lignes.append({
            "Département": d,
            "Études publiées": len(df_etudes[df_etudes['departement'] == d]),
            "CDC publiés": len(df_cdc[df_cdc['departement'] == d]),
            "Demandes émises": nb_dem,
            "Validées": nb_validees,
            "Refusées": nb_refusees,
            "Taux d'approbation": f"{taux_appro:.0f} %",
            "Volume demandé (€)": f"{volume:,.2f}"
        })

    df_stats = pd.DataFrame(lignes)
    st.dataframe(df_stats, use_container_width=True, hide_index=True)
    afficher_boutons_export(df_stats, "statistiques_departements", "Statistiques par Département", key_prefix="stats_dept")

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Études publiées", len(df_etudes))
    c2.metric("Total Cahiers des Charges publiés", len(df_cdc))
    c3.metric("Total Demandes émises", len(df_demandes))

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
    afficher_module_messagerie_unifiee(nom_dept, profil["type"])

elif st.session_state.tab_actif == "📖 Journal de Bord":
    afficher_module_journal_bord(nom_dept)

elif st.session_state.tab_actif == "📊 Pôle de Contrôle (Suivi Global)":
    afficher_module_suivi_global_controle()

elif st.session_state.tab_actif == "🔍 Recherche Globale":
    afficher_module_recherche_globale(nom_dept, profil["type"])

elif st.session_state.tab_actif == "📈 Statistiques":
    afficher_module_statistiques()

elif st.session_state.tab_actif == "🕵️ Audit & Traçabilité":
    afficher_module_audit()

elif st.session_state.tab_actif == "🗑️ Corbeille & Historique Suppressions":
    afficher_module_direction_corbeille()
