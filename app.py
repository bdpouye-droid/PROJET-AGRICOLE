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
    st.write(f"- **[{r[1]}] {r[2]}** ({r[3]})")
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

def fournisseur_affiche(fournisseur_propose: str, fournisseur_retenu: str) -> str:
    """Le fournisseur retenu par les Achats prévaut toujours sur la proposition de l'émetteur."""
    if fournisseur_retenu:
        return f"{fournisseur_retenu} ✅ (retenu par les Achats)"
    elif fournisseur_propose:
        return f"{fournisseur_propose} (pressenti par l'émetteur, non confirmé)"
    return "Non renseigné"

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
        ("demandes", "fournisseur_retenu", "TEXT DEFAULT ''"),
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
            "icone": "💬", "label": f"Vous avez un message non lu dans « {notif['nom']} » ({notif['count']})",
            "cible_tab": "4. Messagerie & Chat", "cible_disc": notif["disc_id"], "key": f"chat_{notif['disc_id']}"
        })

    # --- Études reçues non consultées ---
    cursor.execute("SELECT id, departement, titre, destinataires_partage, vus_json FROM etudes_metier WHERE departement != ?", (nom_dept,))
    for e_id, e_dept, e_titre, dest_j, vus_j in cursor.fetchall():
        dests = json.loads(dest_j) if dest_j else []
        vus = json.loads(vus_j) if vus_j else []
        if nom_dept in dests and nom_dept not in vus:
            notifs.append({
                "icone": "⚙️", "label": f"Vous avez une nouvelle étude à consulter, envoyée par {e_dept} : « {e_titre} »",
                "cible_tab": "1. Études & Ingénierie", "cible_disc": None, "key": f"etude_{e_id}"
            })

    # --- Cahiers des charges reçus non consultés ---
    cursor.execute("SELECT id, departement, titre, destinataires_avis, vus_par_json FROM cahiers_charges WHERE departement != ?", (nom_dept,))
    for c_id, c_dept, c_titre_raw, dest_j, vus_j in cursor.fetchall():
        dests = json.loads(dest_j) if dest_j else []
        vus = json.loads(vus_j) if vus_j else []
        if nom_dept in dests and nom_dept not in vus:
            notifs.append({
                "icone": "📋", "label": f"Vous avez une demande d'avis sur un cahier des charges de {c_dept} : « {c_titre_raw.split('||')[0]} »",
                "cible_tab": "2. Cahiers des Charges", "cible_disc": None, "key": f"cdc_{c_id}"
            })

    # --- Demandes en attente de validation pour ce pôle ---
    if type_profil in ["achats", "finance", "fondateur"]:
        if type_profil == "achats":
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'achats' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
            libelle_role = "à sourcer / valider (Achats)"
        elif type_profil == "finance":
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'finance' AND statut NOT LIKE 'Validé%' AND statut NOT LIKE 'Refusé%'")
            libelle_role = "à contrôler (Finance)"
        else:
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'direction' OR statut LIKE 'En attente%'")
            libelle_role = "à valider (Direction)"
        nb_a_valider = cursor.fetchone()[0]
        if nb_a_valider > 0:
            notifs.append({
                "icone": "🛡️", "label": f"Vous avez {nb_a_valider} demande(s) d'achat {libelle_role}",
                "cible_tab": "3. Besoins & Achats", "cible_disc": None, "key": "valid_achats"
            })

    # --- Corrections demandées à l'émetteur ---
    cursor.execute("SELECT COUNT(*) FROM demandes WHERE departement = ? AND statut = 'Demande de Modification'", (nom_dept,))
    nb_corrections = cursor.fetchone()[0]
    if nb_corrections > 0:
        notifs.append({
            "icone": "✏️", "label": f"Vous avez {nb_corrections} demande(s) d'achat à corriger suite à une remarque",
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

if toutes_notifs:
    with st.container(border=True):
        st.markdown(f"##### 🔔 À faire — {len(toutes_notifs)} action(s) en attente")
        for notif in toutes_notifs:
            c_notif, c_bouton = st.columns([5, 1.3])
            with c_notif:
                st.write(f"{notif['icone']} {notif['label']}")
            with c_bouton:
                if st.button("👉 Y aller", key=f"banniere_{notif['key']}", use_container_width=True):
                    if notif["cible_disc"] is not None:
                        st.session_state.discussion_active_id = notif["cible_disc"]
                    st.session_state.tab_actif = notif["cible_tab"]
                    st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)

if profil["type"] in ["finance", "fondateur"]:
    b_total = get_valeur_globale("budget_global")
    b_solde = get_valeur_globale("solde_restant")
    c_b1, c_b2 = st.columns(2)
    c_b1.metric("Budget Global Allocation", f"{b_total:,.2f} €")
    c_b2.metric("Solde Restant Disponible", f"{b_solde:,.2f} €")

st.markdown("---")

# --- NAVIGATION ONGLET PRINCIPAL ---
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
                st.toast("Étude diffusée avec succès !", icon="✅")
                st.success("Étude diffusée !")
                st.rerun()

    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date, vus_json FROM etudes_metier WHERE departement != ? ORDER BY id DESC", (nom_departement,))
        etudes = cursor.fetchall()
        recus = [e for e in etudes if nom_departement in (json.loads(e[5]) if e[5] else []) or type_profil == "fondateur"]

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
    st.subheader(f"📋 Rédaction & Avis sur les Cahiers des Charges — {nom_departement}")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    t1, t2 = st.tabs(["1. Rédiger & Diffuser", "2. Cahiers Reçus & Avis"])

    with t1:
        with st.form("form_cdc", clear_on_submit=True):
            titre = st.text_input("Titre du Cahier des Charges")
            contenu = st.text_area("Contenu détaillé / Spécifications fonctionnelles")
            destinataires = st.multiselect("Demander l'avis de :", tous_depts)
            if st.form_submit_button("Publier et solliciter") and titre:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis)
                    VALUES (?, ?, ?, ?, ?)
                """, (nom_departement, titre, contenu, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(destinataires)))
                conn.commit()
                conn.close()
                ajouter_log("Cahier des Charges", nom_departement, f"CDC créé: {titre}")
                st.success("Cahier des charges publié !")
                st.rerun()

    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis, vus_par_json FROM cahiers_charges ORDER BY id DESC")
        cdcs = cursor.fetchall()

        recus = [c for c in cdcs if nom_departement in (json.loads(c[5]) if c[5] else []) or type_profil == "fondateur" or c[1] == nom_departement]

        for c in recus:
            if c[1] != nom_departement:
                vus = json.loads(c[6]) if c[6] else []
                if nom_departement not in vus:
                    vus.append(nom_departement)
                    cursor.execute("UPDATE cahiers_charges SET vus_par_json = ? WHERE id = ?", (json.dumps(vus), c[0]))
        conn.commit()
        conn.close()

        if recus:
            df_export_cdc = pd.DataFrame([{
                "ID": c[0], "Émetteur": c[1], "Titre": c[2].split('||')[0],
                "Contenu": c[3][:100], "Date": c[4]
            } for c in recus])
            afficher_boutons_export(df_export_cdc, "cahiers_charges", "Cahiers des Charges", key_prefix="cdc")

            for c in recus:
                c_id, c_dept, c_titre_raw, c_contenu, c_date, _, _ = c
                parties = c_titre_raw.split("||")
                titre_net = parties[0]
                avis_precedents = parties[1:]

                with st.expander(f"📌 [{c_dept}] {titre_net} ({c_date})"):
                    st.write(f"**Contenu :**\n{c_contenu}")
                    if avis_precedents:
                        st.markdown("---")
                        st.markdown("**Avis émis par les départements :**")
                        for av in avis_precedents:
                            st.markdown(f"- {av}")
                    
                    if c_dept != nom_departement:
                        with st.form(f"form_avis_{c_id}"):
                            commentaire_avis = st.text_area("Rédiger votre avis / remarque technique :", key=f"comm_avis_{c_id}")
                            if st.form_submit_button("Envoyer l'avis") and commentaire_avis:
                                nouveau_morceau = f"{nom_departement} : {commentaire_avis}"
                                nouveaux_parties = parties + [nouveau_morceau]
                                nouveau_titre_stock = "||".join(nouveaux_parties)
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE cahiers_charges SET titre = ? WHERE id = ?", (nouveau_titre_stock, c_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Avis CDC", nom_departement, f"Avis donné sur CDC #{c_id}")
                                st.success("Avis enregistré avec succès !")
                                st.rerun()
        else:
            st.info("Aucun cahier des charges disponible.")


# ==========================================
# 3. MODULE BESOINS & ACHATS
# ==========================================
def afficher_module_achats(nom_departement, type_profil):
    st.subheader(f"🛒 Expression des Besoins & Workflow d'Achats — {nom_departement}")
    t1, t2 = st.tabs(["1. Nouvelle Demande d'Achat", "2. Suivi & Traitement des Demandes"])

    with t1:
        with st.form("form_demande", clear_on_submit=True):
            titre = st.text_input("Intitulé du besoin / Achat")
            cahier_charges = st.text_area("Description et justification technique")
            montant = st.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
            fournisseur_prop = st.text_input("Fournisseur pressenti (optionnel)")
            fich = st.file_uploader("📥 Devis / Fichier justificatif", type=["pdf", "png", "jpg", "xlsx"])

            if st.form_submit_button("Soumettre la demande") and titre:
                nom_f = enregistrer_fichier_securise(DOSSIER_UPLOADS, fich)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nom_departement, titre, cahier_charges, montant, fournisseur_prop, "En attente Achats", "achats", "", "", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_f, "", ""))
                conn.commit()
                conn.close()
                ajouter_log("Demande d'Achat", nom_departement, f"Demande créée: {titre} ({montant} €)")
                st.success("Demande transmise au pôle Achats !")
                st.rerun()

    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes ORDER BY id DESC")
        demandes = cursor.fetchall()
        conn.close()

        if type_profil not in ["achats", "finance", "fondateur"]:
            demandes = [d for d in demandes if d[1] == nom_departement]

        if demandes:
            df_export_achats = pd.DataFrame([{
                "ID": d[0], "Département": d[1], "Titre": d[2], "Montant": d[4],
                "Fournisseur": fournisseur_affiche(d[5], d[14]), "Statut": d[6], "Étape": d[7], "Date": d[11]
            } for d in demandes])
            afficher_boutons_export(df_export_achats, "demandes_achats", "Suivi des Achats", key_prefix="achats")

            for d in demandes:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_av_achats, d_av_fin, d_motif, d_date, d_fich, d_remarque, d_fourn_retenu = d
                
                with st.expander(f"📦 [{d_dept}] {d_titre} — {d_montant:,.2f} € | Statut : {d_statut}"):
                    c_d1, c_d2 = st.columns(2)
                    with c_d1:
                        st.write(f"**Description :** {d_cc}")
                        st.write(f"**Fournisseur proposé :** {d_fourn or 'Aucun'}")
                        if d_fourn_retenu:
                            st.write(f"**Fournisseur validé (Achats) :** {d_fourn_retenu} ✅")
                        st.write(f"**Date de soumission :** {d_date}")
                        st.markdown(f"**Statut actuel :** {pill_statut(d_statut)}", unsafe_allow_html=True)
                        if d_remarque:
                            st.warning(f"**Remarque / Motif de modification :** {d_remarque}")
                    with c_d2:
                        if d_fich:
                            chemin = os.path.join(DOSSIER_UPLOADS, d_fich)
                            if os.path.exists(chemin):
                                with open(chemin, "rb") as f:
                                    st.download_button("📥 Télécharger Devis / Pièce", f, file_name=d_fich, key=f"dl_dem_{d_id}")

                    # Workflow actions
                    if type_profil == "achats" and d_etape == "achats":
                        st.markdown("---")
                        st.markdown("🛡️ **Validation Pôle Achats & Sourcing**")
                        with st.form(f"form_achats_{d_id}"):
                            fournisseur_valide = st.text_input("Fournisseur retenu (définitif)", value=d_fourn_retenu or d_fourn)
                            action_achats = st.selectbox("Action Achats", ["Valider et transmettre à la Finance", "Demander une modification", "Refuser"])
                            commentaire_achats = st.text_area("Commentaire / Motif")
                            if st.form_submit_button("Soumettre la décision Achats"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_achats.startswith("Valider"):
                                    cursor.execute("UPDATE demandes SET etape_actuelle = 'finance', statut = 'En attente Finance', avis_achats = ?, fournisseur_retenu = ? WHERE id = ?", (commentaire_achats, fournisseur_valide, d_id))
                                elif action_achats.startswith("Demander"):
                                    cursor.execute("UPDATE demandes SET statut = 'Demande de Modification', retour_remarque = ?, fournisseur_retenu = ? WHERE id = ?", (commentaire_achats, fournisseur_valide, d_id))
                                else:
                                    cursor.execute("UPDATE demandes SET statut = 'Refusé par Achats', motif_refus = ?, fournisseur_retenu = ? WHERE id = ?", (commentaire_achats, fournisseur_valide, d_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Action Achats", nom_departement, f"Demande #{d_id} traitée par Achats")
                                st.success("Décision enregistrée !")
                                st.rerun()

                    elif type_profil == "finance" and d_etape == "finance":
                        st.markdown("---")
                        st.markdown("💰 **Validation Pôle Finance & Contrôle Budgétaire**")
                        with st.form(f"form_finance_{d_id}"):
                            action_fin = st.selectbox("Action Finance", ["Valider et approuver le décaissement", "Demander une modification", "Refuser"])
                            commentaire_fin = st.text_area("Commentaire budgétaire")
                            if st.form_submit_button("Soumettre la décision Finance"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_fin.startswith("Valider"):
                                    # Déduction du solde global
                                    b_solde = get_valeur_globale("solde_restant")
                                    nouveau_solde = b_solde - d_montant
                                    set_valeur_globale("solde_restant", max(0.0, nouveau_solde))

                                    cursor.execute("UPDATE demandes SET etape_actuelle = 'termine', statut = 'Validé & Financé', avis_finance = ? WHERE id = ?", (commentaire_fin, d_id))
                                elif action_fin.startswith("Demander"):
                                    cursor.execute("UPDATE demandes SET statut = 'Demande de Modification', retour_remarque = ? WHERE id = ?", (commentaire_fin, d_id))
                                else:
                                    cursor.execute("UPDATE demandes SET statut = 'Refusé par Finance', motif_refus = ? WHERE id = ?", (commentaire_fin, d_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Action Finance", nom_departement, f"Demande #{d_id} validée/financée")
                                st.success("Décision financière enregistrée !")
                                st.rerun()

                    # Correction demandée à l'émetteur
                    if d_dept == nom_departement and d_statut == "Demande de Modification":
                        st.markdown("---")
                        st.markdown("✏️ **Modifier votre demande suite aux remarques**")
                        with st.form(f"form_corr_{d_id}"):
                            nouveau_titre = st.text_input("Titre", value=d_titre)
                            nouveau_cc = st.text_area("Description", value=d_cc)
                            nouveau_montant = st.number_input("Montant (€)", value=d_montant)
                            if st.form_submit_button("Renvoyer pour validation"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE demandes SET titre = ?, cahier_charges = ?, montant = ?, statut = 'En attente Achats', etape_actuelle = 'achats', retour_remarque = '' WHERE id = ?", (nouveau_titre, nouveau_cc, nouveau_montant, d_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Correction Demande", nom_departement, f"Demande #{d_id} modifiée et renvoyée")
                                st.success("Demande renvoyée aux Achats !")
                                st.rerun()
        else:
            st.info("Aucune demande d'achat enregistrée.")


# ==========================================
# 4. MESSAGERIE & CHAT INTERACTIF
# ==========================================
def afficher_module_chat(nom_departement):
    st.subheader(f"💬 Canaux de Discussion & Messagerie Inter-Départements — {nom_departement}")
    tous_depts = sorted(list(set(u["dept"] for u in UTILISATEURS.values())))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom_groupe, membres_json, createur, date_creation, archives_par FROM discussions")
    discussions = cursor.fetchall()
    conn.close()

    # Filtrer discussions accessibles
    discussions_accessibles = []
    for d in discussions:
        membres = json.loads(d[2])
        archives = json.loads(d[5]) if d[5] else []
        if nom_departement in membres and nom_departement not in archives:
            discussions_accessibles.append(d)

    c_g1, c_g2 = st.columns([1, 2.5])

    with c_g1:
        st.markdown("##### 📂 Canaux")
        if st.button("➕ Créer un nouveau canal", use_container_width=True):
            st.session_state.creer_canal_ouvert = True

        if st.session_state.get("creer_canal_ouvert", False):
            with st.form("form_nouveau_canal"):
                nom_g = st.text_input("Nom du canal / discussion")
                membres_choisis = st.multiselect("Membres invités :", tous_depts, default=[nom_departement])
                if st.form_submit_button("Créer") and nom_g:
                    if nom_departement not in membres_choisis:
                        membres_choisis.append(nom_departement)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO discussions (nom_groupe, membres_json, createur, date_creation, archives_par)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nom_g, json.dumps(membres_choisis), nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps([])))
                    conn.commit()
                    conn.close()
                    st.session_state.creer_canal_ouvert = False
                    st.success("Canal créé !")
                    st.rerun()

        st.markdown("---")
        if discussions_accessibles:
            for disc in discussions_accessibles:
                d_id, d_nom, _, _, _, _ = disc
                # Compter messages non lus
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT expediteur, lus_json FROM messages_chat WHERE discussion_id = ?", (d_id,))
                msgs = cursor.fetchall()
                conn.close()
                non_lus = sum(1 for exp, lus_j in msgs if exp != nom_departement and nom_departement not in (json.loads(lus_j) if lus_j else []))

                label_btn = f"💬 {d_nom}" + (f" ({non_lus})" if non_lus > 0 else "")
                is_selected = (st.session_state.get("discussion_active_id") == d_id)
                if st.button(label_btn, key=f"btn_disc_{d_id}", use_container_width=True, type="primary" if is_selected else "secondary"):
                    st.session_state.discussion_active_id = d_id
                    st.rerun()
        else:
            st.info("Aucun canal actif.")

    with c_g2:
        disc_id_actif = st.session_state.get("discussion_active_id")
        if disc_id_actif:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, nom_groupe, membres_json, createur, date_creation FROM discussions WHERE id = ?", (disc_id_actif,))
            disc_info = cursor.fetchone()
            conn.close()

            if disc_info:
                _, d_nom, membres_j, createur, d_date = disc_info
                membres = json.loads(membres_j)

                st.markdown(f"""
                <div class="channel-header">
                    <h4>💬 {d_nom}</h4>
                    <span style="color: var(--text-muted); font-size: 0.85rem;">Membres : {', '.join(membres)} | Créé par {createur} le {d_date}</span>
                </div>
                """, unsafe_allow_html=True)

                # Marquer messages comme lus
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, expediteur, lus_json FROM messages_chat WHERE discussion_id = ?", (disc_id_actif,))
                tous_msgs = cursor.fetchall()
                for m_id, exp, lus_j in tous_msgs:
                    lus = json.loads(lus_j) if lus_j else []
                    if exp != nom_departement and nom_departement not in lus:
                        lus.append(nom_departement)
                        cursor.execute("UPDATE messages_chat SET lus_json = ? WHERE id = ?", (json.dumps(lus), m_id))
                conn.commit()
                conn.close()

                # Affichage des messages
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT expediteur, texte, date, lus_json FROM messages_chat WHERE discussion_id = ? ORDER BY id ASC", (disc_id_actif,))
                messages = cursor.fetchall()
                conn.close()

                conteneur_msgs = st.container(height=400)
                with conteneur_msgs:
                    if messages:
                        for exp, txt, dt, lus_j in messages:
                            align = "right" if exp == nom_departement else "left"
                            bg_col = "rgba(91,141,239,0.15)" if exp == nom_departement else "var(--bg-card)"
                            border_col = "var(--accent)" if exp == nom_departement else "var(--border)"
                            st.markdown(f"""
                            <div style="text-align: {align}; margin-bottom: 10px;">
                                <div style="display: inline-block; background: {bg_col}; border: 1px solid {border_col}; padding: 10px 14px; border-radius: 12px; max-width: 75%; text-align: left;">
                                    <b style="font-size: 0.8rem; color: var(--accent);">{exp}</b><br>
                                    <span>{txt}</span><br>
                                    <span style="font-size: 0.7rem; color: var(--text-muted);">{dt}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Aucun message dans ce canal pour l'instant.")

                # Saisie nouveau message
                with st.form(f"form_msg_{disc_id_actif}", clear_on_submit=True):
                    texte_msg = st.text_input("Votre message...")
                    col_envoi, col_archive = st.columns([4, 1])
                    with col_envoi:
                        submit_msg = st.form_submit_button("Envoyer", use_container_width=True)
                    with col_archive:
                        submit_archive = st.form_submit_button("Archiver le canal", use_container_width=True)

                    if submit_msg and texte_msg:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json)
                            VALUES (?, ?, ?, ?, ?)
                        """, (disc_id_actif, nom_departement, texte_msg, datetime.now().strftime("%H:%M"), json.dumps([nom_departement])))
                        conn.commit()
                        conn.close()
                        st.rerun()

                    if submit_archive:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT archives_par FROM discussions WHERE id = ?", (disc_id_actif,))
                        res_arch = cursor.fetchone()
                        archives = json.loads(res_arch[0]) if res_arch and res_arch[0] else []
                        if nom_departement not in archives:
                            archives.append(nom_departement)
                        cursor.execute("UPDATE discussions SET archives_par = ? WHERE id = ?", (json.dumps(archives), disc_id_actif))
                        conn.commit()
                        conn.close()
                        st.session_state.discussion_active_id = None
                        st.success("Canal archivé pour votre département.")
                        st.rerun()
        else:
            st.info("Sélectionnez ou créez un canal de discussion à gauche.")


# ==========================================
# 5. JOURNAL DE BORD COLLABORATIF
# ==========================================
def afficher_module_journal(nom_departement):
    st.subheader(f"📖 Journal de Bord & Notes de Service — {nom_departement}")
    t1, t2 = st.tabs(["1. Rédiger une Note", "2. Consulter le Journal Global"])

    with t1:
        with st.form("form_journal", clear_on_submit=True):
            note = st.text_area("Contenu de la note / point d'étape")
            if st.form_submit_button("Publier dans le journal") and note:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO journal_bord (departement, auteur, note, date_note, heure_note)
                    VALUES (?, ?, ?, ?, ?)
                """, (nom_departement, profil["nom"], note, date.today().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M")))
                conn.commit()
                conn.close()
                ajouter_log("Journal de bord", nom_departement, "Note publiée")
                st.success("Note enregistrée dans le journal !")
                st.rerun()

    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, auteur, note, date_note, heure_note FROM journal_bord ORDER BY id DESC")
        notes = cursor.fetchall()
        conn.close()

        if notes:
            df_export_j = pd.DataFrame([{
                "ID": n[0], "Département": n[1], "Auteur": n[2], "Note": n[3], "Date": f"{n[4]} {n[5]}"
            } for n in notes])
            afficher_boutons_export(df_export_j, "journal_bord", "Journal de Bord", key_prefix="journal")

            for n in notes:
                n_id, n_dept, n_auteur, n_note, n_date, n_heure = n
                st.markdown(f"""
                <div class="note-card">
                    <span class="note-date">📅 {n_date} à {n_heure} — [{n_dept}] {n_auteur}</span>
                    <p style="margin-top: 8px; margin-bottom: 0;">{n_note}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Aucune note dans le journal de bord.")


# ==========================================
# 6. RECHERCHE GLOBALE MULTI-CRITÈRES
# ==========================================
def afficher_module_recherche(nom_departement):
    st.subheader("🔍 Recherche Globale Multi-Critères")
    recherche = st.text_input("Mot-clé à rechercher dans toute la plateforme (études, cahiers des charges, achats, notes)...")

    if recherche:
        kw = f"%{recherche}%"
        conn = get_db_connection()
        cursor = conn.cursor()

        st.markdown("---")
        st.markdown("##### ⚙️ Études Métier")
        cursor.execute("SELECT id, departement, titre, date FROM etudes_metier WHERE titre LIKE ? OR donnees_json LIKE ?", (kw, kw))
        for r in cursor.fetchall():
            st.write(f"- **[{r[1]}] {r[2]** ({r[3]})")

        st.markdown("##### 📋 Cahiers des Charges")
        cursor.execute("SELECT id, departement, titre, date FROM cahiers_charges WHERE titre LIKE ? OR contenu LIKE ?", (kw, kw))
        for r in cursor.fetchall():
            st.write(f"- **[{r[1]}] {r[2].split('||')[0]}** ({r[3]})")

        st.markdown("##### 🛒 Demandes d'Achat")
        cursor.execute("SELECT id, departement, titre, montant, statut, date FROM demandes WHERE titre LIKE ? OR cahier_charges LIKE ?", (kw, kw))
        for r in cursor.fetchall():
            st.write(f"- **[{r[1]}] {r[2]}** — {r[3]:,.2f} € (Statut: {r[4]})")

        st.markdown("##### 📖 Journal de Bord")
        cursor.execute("SELECT id, departement, auteur, note, date_note FROM journal_bord WHERE note LIKE ?", (kw,))
        for r in cursor.fetchall():
            st.write(f"- **[{r[1]}] {r[2]}** ({r[4]}) : {r[3][:100]}...")

        conn.close()
    else:
        st.info("Saisissez un mot-clé ci-dessus pour lancer la recherche transversale.")


# ==========================================
# 7. PÔLE DE CONTRÔLE (SUIVI GLOBAL)
# ==========================================
def afficher_module_controle():
    st.subheader("📊 Pôle de Contrôle & Pilotage Financier")
    b_total = get_valeur_globale("budget_global")
    b_solde = get_valeur_globale("solde_restant")
    b_engage = b_total - b_solde

    c1, c2, c3 = st.columns(3)
    c1.metric("Budget Global", f"{b_total:,.2f} €")
    c2.metric("Montant Engagé / Dépensé", f"{b_engage:,.2f} €")
    c3.metric("Solde Disponible", f"{b_solde:,.2f} €")

    st.markdown("---")
    st.markdown("##### 📑 Synthèse des Demandes d'Achats Validées & Financées")
    conn = get_db_connection()
    df_demandes = pd.read_sql_query("SELECT id, departement, titre, montant, fournisseur_retenu, statut, date FROM demandes", conn)
    conn.close()

    if not df_demandes.empty:
        afficher_boutons_export(df_demandes, "pole_controle_achats", "Synthèse Globale des Achats", key_prefix="controle")
        st.dataframe(df_demandes, use_container_width=True)
    else:
        st.info("Aucune donnée disponible.")


# ==========================================
# 8. STATISTIQUES
# ==========================================
def afficher_module_statistiques():
    st.subheader("📈 Statistiques & Analyses de la Plateforme")
    conn = get_db_connection()
    df_demandes = pd.read_sql_query("SELECT departement, montant, statut FROM demandes", conn)
    conn.close()

    if not df_demandes.empty:
        st.markdown("##### Montant total des demandes par département")
        df_group = df_demandes.groupby("departement")["montant"].sum().reset_index()
        st.bar_chart(df_group.set_index("departement"))

        afficher_boutons_export(df_group, "statistiques_montants", "Statistiques par Département", key_prefix="stats")
    else:
        st.info("Données insuffisantes pour générer les graphiques.")


# ==========================================
# 9. AUDIT & TRAÇABILITÉ (FONDATEUR)
# ==========================================
def afficher_module_audit():
    st.subheader("🕵️ Journal d'Audit & Traçabilité des Actions")
    conn = get_db_connection()
    df_audit = pd.read_sql_query("SELECT id, date, acteur, action, details FROM logs_audit ORDER BY id DESC", conn)
    conn.close()

    if not df_audit.empty:
        afficher_boutons_export(df_audit, "logs_audit", "Journal d'Audit", key_prefix="audit")
        st.dataframe(df_audit, use_container_width=True)
    else:
        st.info("Aucun journal d'audit enregistré.")


# ==========================================
# 10. CORBEILLE & HISTORIQUE SUPPRESSIONS (FONDATEUR)
# ==========================================
def afficher_module_corbeille():
    st.subheader("🗑️ Corbeille & Historique des Éléments Supprimés")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement_auteur, type_element, resume, details_json, date_suppression FROM corbeille_archives ORDER BY id DESC")
    archives = cursor.fetchall()
    conn.close()

    if archives:
        df_export_corr = pd.DataFrame([{
            "ID": a[0], "Département": a[1], "Type": a[2], "Résumé": a[3], "Date Suppression": a[5]
        } for a in archives])
        afficher_boutons_export(df_export_corr, "corbeille_archives", "Archives et Suppressions", key_prefix="corbeille")

        for a in archives:
            a_id, a_dept, a_type, a_resume, a_json, a_date = a
            with st.expander(f"🗑️ [{a_dept}] {a_type} : {a_resume} (Supprimé le {a_date})"):
                st.write(f"**Détails techniques stockés :** {a_json}")
    else:
        st.info("La corbeille est vide.")


# --- ROUTAGE DES ONGLETS PRINCIPAUX ---
onglet_courant = st.session_state.tab_actif

if onglet_courant == "1. Études & Ingénierie":
    afficher_module_etudes(nom_dept, profil["type"])
elif onglet_courant == "2. Cahiers des Charges":
    afficher_module_cdc(nom_dept, profil["type"])
elif onglet_courant == "3. Besoins & Achats":
    afficher_module_achats(nom_dept, profil["type"])
elif onglet_courant == "4. Messagerie & Chat":
    afficher_module_chat(nom_dept)
elif onglet_courant == "📖 Journal de Bord":
    afficher_module_journal(nom_dept)
elif onglet_courant == "🔍 Recherche Globale":
    afficher_module_recherche(nom_dept)
elif onglet_courant == "📊 Pôle de Contrôle (Suivi Global)":
    afficher_module_controle()
elif onglet_courant == "📈 Statistiques":
    afficher_module_statistiques()
elif onglet_courant == "🕵️ Audit & Traçabilité":
    afficher_module_audit()
elif onglet_courant == "🗑️ Corbeille & Historique Suppressions":
    afficher_module_corbeille()
