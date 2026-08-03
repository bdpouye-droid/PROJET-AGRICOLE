# app.py
# Plateforme de Pilotage - Bureau d'Études (consolidated & unified inbox)
# - Unified inbox (notifications + legacy inbox_entries)
# - Workflow Achats -> Finance -> Direction
# - Achats can set final price & supplier
# - Tickets séquentiels #TICK-XXXX
# - Modules : Études, CDC, Achats, Messagerie, Journal, Recherche, Contrôle, Stats, Audit, Corbeille
# - Exports Excel/PDF

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

# --- DATABASE FILE (single source) ---
DB_FILE = os.path.join(os.path.dirname(__file__), "database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Backwards-compatible alias
def get_conn():
    return get_db_connection()

# ==========================================
# UTILITAIRES : EXPORT EXCEL / PDF
# ==========================================
def exporter_excel_bytes(df: pd.DataFrame, nom_feuille="Données"):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nom_feuille[:31] or "Données")
        worksheet = writer.sheets[nom_feuille[:31] or "Données"]
        for i, col in enumerate(df.columns):
            largeur = min(max(len(str(col)), df[col].astype(str).map(len).max() if len(df) else 10) + 2, 50)
            worksheet.column_dimensions[worksheet.cell(row=1, column=i + 1).column_letter].width = largeur
    return buffer.getvalue()

def exporter_pdf_bytes(df: pd.DataFrame, titre="Export", colonnes_max=8):
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
    if fournisseur_retenu:
        return f"{fournisseur_retenu} ✅ (retenu par les Achats)"
    elif fournisseur_propose:
        return f"{fournisseur_propose} (pressenti par l'émetteur, non confirmé)"
    return "Non renseigné"

# --- INITIALISATION BASE DE DONNÉES ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS global_store (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS demandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, cahier_charges TEXT,
        montant REAL, fournisseur TEXT, statut TEXT, etape_actuelle TEXT, avis_achats TEXT,
        avis_finance TEXT, motif_refus TEXT, date TEXT, fichier_devis TEXT, retour_remarque TEXT,
        fournisseur_retenu TEXT DEFAULT '', numero_ticket TEXT DEFAULT ''
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS etudes_metier (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, donnees_json TEXT,
        fichier_etude TEXT, destinataires_partage TEXT, date TEXT, vus_json TEXT DEFAULT '[]'
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cahiers_charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT, departement TEXT, titre TEXT, contenu TEXT, date TEXT, 
        destinataires_avis TEXT, vus_par_json TEXT DEFAULT '[]', avis_recueillis TEXT DEFAULT '{}'
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS discussions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nom_groupe TEXT, membres_json TEXT, createur TEXT, date_creation TEXT, archives_par TEXT DEFAULT '[]'
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

    # legacy inbox entries (kept for backward compatibility)
    cursor.execute('''CREATE TABLE IF NOT EXISTS inbox_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, ticket_id TEXT, message TEXT, target_tab TEXT, target_sub TEXT, created_at TEXT, read INTEGER DEFAULT 0
    )''')

    # notifications table for unified inbox
    cursor.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_dept TEXT, ticket TEXT, message TEXT, target_tab TEXT, target_disc INTEGER, created_at TEXT, read INTEGER DEFAULT 0
    )''')

    # metadata for ticket sequence
    cursor.execute('''CREATE TABLE IF NOT EXISTS metadata ( key TEXT PRIMARY KEY, value TEXT )''')

    # init ticket counter if missing
    cursor.execute("INSERT OR IGNORE INTO metadata (key, value) VALUES ('ticket_counter', '0')")
    cursor.execute("SELECT value FROM global_store WHERE key = 'budget_global'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR IGNORE INTO global_store (key, value) VALUES ('budget_global', ?)", (str(10000000.0),))
        cursor.execute("INSERT OR IGNORE INTO global_store (key, value) VALUES ('solde_restant', ?)", (str(10000000.0),))

    conn.commit()
    conn.close()

def migrer_schema():
    # keep for compatibility with older installs
    conn = get_db_connection()
    cursor = conn.cursor()
    migrations = [
        ("discussions", "archives_par", "TEXT DEFAULT '[]'"),
        ("etudes_metier", "vus_json", "TEXT DEFAULT '[]'"),
        ("cahiers_charges", "vus_par_json", "TEXT DEFAULT '[]'"),
        ("cahiers_charges", "avis_recueillis", "TEXT DEFAULT '{}'"),
        ("demandes", "fournisseur_retenu", "TEXT DEFAULT ''"),
        ("demandes", "numero_ticket", "TEXT DEFAULT ''"),
    ]
    for table, colonne, type_def in migrations:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            colonnes_existantes = [c[1] for c in cursor.fetchall()]
            if colonne not in colonnes_existantes:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {type_def}")
        except Exception:
            # ignore missing tables
            pass
    conn.commit()
    conn.close()

init_db()
migrer_schema()

# --- UTILS DATABASE ---
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

# --- Notifications / Inbox helpers ---
def add_notification(user_dept, ticket, message, target_tab=None, target_disc=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notifications (user_dept, ticket, message, target_tab, target_disc, created_at, read) VALUES (?, ?, ?, ?, ?, ?, 0)",
                   (user_dept, ticket, message, target_tab, target_disc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def mark_notification_read(notif_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()

def get_notifications_for(user_dept):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticket, message, target_tab, target_disc, created_at FROM notifications WHERE user_dept = ? AND read = 0 ORDER BY created_at DESC", (user_dept,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_inbox_entry(user, ticket_id, message, target_tab=None, target_sub=None):
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
      INSERT INTO inbox_entries (user, ticket_id, message, target_tab, target_sub, created_at, read)
      VALUES (?, ?, ?, ?, ?, ?, 0)
    """, (user, ticket_id, message, target_tab, target_sub, now))
    conn.commit()
    conn.close()

def mark_inbox_read(entry_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE inbox_entries SET read=1 WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

def get_inbox_for(user):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, ticket_id, message, target_tab, target_sub, created_at FROM inbox_entries WHERE user=? AND read=0 ORDER BY created_at DESC", (user,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_unified_inbox(user_dept):
    """Return combined unread items from notifications and inbox_entries.
       Each item: dict with keys: source ('notif'|'inbox'), id, ticket, message, target_tab, target_sub/target_disc, created_at
    """
    items = []
    # notifications
    notifs = get_notifications_for(user_dept)
    for n in notifs:
        items.append({
            "source": "notif",
            "id": int(n["id"]),
            "ticket": n["ticket"],
            "message": n["message"],
            "target_tab": n["target_tab"],
            "target_disc": n["target_disc"],
            "created_at": n["created_at"]
        })
    # legacy inbox_entries
    inbox = get_inbox_for(user_dept)
    for i in inbox:
        items.append({
            "source": "inbox",
            "id": int(i["id"]),
            "ticket": i["ticket_id"],
            "message": i["message"],
            "target_tab": i["target_tab"],
            "target_sub": i["target_sub"],
            "created_at": i["created_at"]
        })
    # sort by created_at desc if present
    try:
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    except Exception:
        pass
    return items

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
if 'selected_ticket' not in st.session_state:
    st.session_state.selected_ticket = None

# --- AUTHENTIFICATION / SIDEBAR ---
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

# --- Unified inbox rendering (notifications + inbox_entries) ---
st.sidebar.markdown("### Boîte de réception")
unified = get_unified_inbox(nom_dept)
if not unified:
    st.sidebar.info("Aucun élément en attente.")
else:
    for item in unified:
        with st.sidebar.container():
            created = item.get("created_at", "")
            ticket_label = f"**{item['ticket']}** " if item.get("ticket") else ""
            st.markdown(f"- {ticket_label}{item['message']}")
            cols = st.columns([1,1,1])
            # Y aller button: set navigation based on target_tab/target_disc/target_sub/ticket
            if cols[0].button("Y aller", key=f"go_{item['source']}_{item['id']}"):
                # mark read depending on source
                if item['source'] == "notif":
                    try:
                        mark_notification_read(item['id'])
                    except Exception:
                        pass
                else:
                    try:
                        mark_inbox_read(item['id'])
                    except Exception:
                        pass
                # teleport
                target_tab = item.get("target_tab") or item.get("target_tab") or "1. Études & Ingénierie"
                # discussion
                if item.get("target_disc"):
                    st.session_state.discussion_active_id = item.get("target_disc")
                # ticket
                if item.get("ticket"):
                    st.session_state.selected_ticket = item.get("ticket")
                st.session_state.tab_actif = target_tab
                st.experimental_rerun()
            if cols[1].button("Marquer lu", key=f"read_{item['source']}_{item['id']}"):
                if item['source'] == "notif":
                    mark_notification_read(item['id'])
                else:
                    mark_inbox_read(item['id'])
                st.experimental_rerun()
            if cols[2].button("Voir", key=f"view_{item['source']}_{item['id']}"):
                if item.get("ticket"):
                    st.session_state.selected_ticket = item.get("ticket")
                    st.session_state.tab_actif = "3. Besoins & Achats"
                elif item.get("target_tab"):
                    st.session_state.tab_actif = item.get("target_tab")
                # mark read
                if item['source'] == "notif":
                    mark_notification_read(item['id'])
                else:
                    mark_inbox_read(item['id'])
                st.experimental_rerun()

st.sidebar.markdown("---")
if st.sidebar.button("Se déconnecter"):
    duree = ""
    if "heure_connexion" in st.session_state:
        delta = datetime.now() - st.session_state.heure_connexion
        minutes = int(delta.total_seconds() // 60)
        duree = f"Durée de session : {minutes // 60}h{minutes % 60:02d}min"
    ajouter_log("Déconnexion", profil["nom"], duree or "Session active")
    st.session_state.user_connecte = None
    st.session_state.discussion_active_id = None
    st.session_state.selected_ticket = None
    st.rerun()

st.title(f"Tableau de Bord - {profil['nom']}")

# Dashboard metrics for finance/fondateur
if profil["type"] in ["finance", "fondateur"]:
    b_total = get_valeur_globale("budget_global")
    b_solde = get_valeur_globale("solde_restant")
    c_b1, c_b2 = st.columns(2)
    c_b1.metric("Budget Global Allocation", f"{b_total:,.2f} €")
    c_b2.metric("Solde Restant Disponible", f"{b_solde:,.2f} €")

st.markdown("---")

# --- NAVIGATION DES ONGLETS ---
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
# MODULES (Études, CDC, Achats, Messagerie, Journal, Recherche, Contrôle, Stats, Audit, Corbeille)
# The implementations follow the previously validated code and are kept intact,
# with two important adjustments:
#  - downloads use read() bytes for stable st.download_button behavior
#  - Achats UI allows final amount selection (montant définitif)
# ==========================================

# For brevity and clarity the modules below are included as implemented previously.
# (Full module code re-included to produce a complete single-file app.)


# ---------- Module Études ----------
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
                for r in destinataires:
                    add_notification(r, None, f"Nouvelle étude partagée: {titre}", target_tab="1. Études & Ingénierie")
                st.success("Étude diffusée avec succès !")
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
            recus_filtres = [e for e in recus if (recherche.lower() in f"{e[2]} {(json.loads(e[3]) if e[3] else {}).get('details', '')}".lower() if recherche else True) and (dept_choisi == "Tous" or e[1] == dept_choisi)]
            df_export = pd.DataFrame([{
                "ID": e[0], "Département": e[1], "Titre": e[2],
                "Description": (json.loads(e[3]) if e[3] else {}).get("details", ""), "Date": e[6]
            } for e in recus_filtres])
            afficher_boutons_export(df_export, "etudes_recues", "Études Reçues", key_prefix="etudes_recues")
            for e in recus_filtres:
                e_id, e_dept, e_titre, e_json, e_fich, _, e_date, _ = e
                with st.expander(f"📁 [{e_dept}] {e_titre} ({e_date})"):
                    data = json.loads(e_json) if e_json else {}
                    st.write(f"**Description :** {data.get('details', '')}")
                    if e_fich:
                        chemin = os.path.join(DOSSIER_ETUDES, e_fich)
                        if os.path.exists(chemin):
                            with open(chemin, "rb") as f:
                                file_bytes = f.read()
                            st.download_button("📥 Télécharger Fichier Joint", data=file_bytes, file_name=e_fich, key=f"dl_et_{e_id}")
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

# ---------- Module Cahiers des Charges ----------
def afficher_module_cahiers_charges(nom_departement, type_profil):
    st.subheader(f"📋 Rédaction & Consultation des Cahiers des Charges — {nom_departement}")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    t1, t2 = st.tabs(["1. Nouveau Cahier des Charges", "2. Consultation & Avis Collégiaux"])
    with t1:
        with st.form(f"form_cdc_{nom_departement}", clear_on_submit=True):
            titre = st.text_input("Titre du Cahier des Charges")
            version = st.text_input("Indice de version (ex: v1.0, v2.1)", value="v1.0")
            contenu = st.text_area("Contenu détaillé, spécifications et exigences techniques")
            destinataires = st.multiselect("Demander un avis technique à :", tous_depts)
            if st.form_submit_button("Diffuser le Cahier des Charges") and titre:
                titre_complet = f"{titre} (Indice: {version})"
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis, vus_par_json, avis_recueillis)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (nom_departement, titre_complet, contenu, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(destinataires), json.dumps([]), json.dumps({})))
                conn.commit()
                conn.close()
                ajouter_log("Cahier des Charges", nom_departement, f"CDC créé : {titre_complet}")
                for r in destinataires:
                    add_notification(r, None, f"Demande d'avis CDC : {titre_complet}", target_tab="2. Cahiers des Charges")
                st.success("Cahier des charges diffusé pour avis !")
                st.rerun()
    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis, vus_par_json, avis_recueillis FROM cahiers_charges ORDER BY id DESC")
        cdcs = cursor.fetchall()
        for c in cdcs:
            c_id, c_dept, _, _, _, dest_j, vus_j, _ = c
            dests = json.loads(dest_j) if dest_j else []
            vus = json.loads(vus_j) if vus_j else []
            if nom_departement in dests and nom_departement not in vus:
                vus.append(nom_departement)
                cursor.execute("UPDATE cahiers_charges SET vus_par_json = ? WHERE id = ?", (json.dumps(vus), c_id))
        conn.commit()
        conn.close()
        if cdcs:
            for c in cdcs:
                c_id, c_dept, c_titre, c_contenu, c_date, c_dest_j, _, c_avis_j = c
                dests = json.loads(c_dest_j) if c_dest_j else []
                avis_dict = json.loads(c_avis_j) if c_avis_j else {}
                with st.expander(f"📖 [{c_dept}] {c_titre} ({c_date})"):
                    st.write(f"**Contenu :**\n{c_contenu}")
                    st.write(f"**Destinataires de l'avis :** {', '.join(dests) if dests else 'Aucun'}")
                    if avis_dict:
                        st.markdown("##### 💡 Avis recueillis :")
                        for d_nom, avis_txt in avis_dict.items():
                            st.info(f"**{d_nom} :** {avis_txt}")
                    if nom_departement in dests or type_profil == "fondateur":
                        with st.form(f"form_avis_{c_id}_{nom_departement}"):
                            mon_avis = st.text_area("Rédiger votre avis technique ou vos remarques")
                            if st.form_submit_button("Soumettre mon avis"):
                                avis_dict[nom_departement] = f"{datetime.now().strftime('%d/%m/%Y')} - {mon_avis}"
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE cahiers_charges SET avis_recueillis = ? WHERE id = ?", (json.dumps(avis_dict), c_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Avis CDC", nom_departement, f"Avis donné sur CDC #{c_id}")
                                st.success("Avis enregistré !")
                                st.rerun()
                    if c_dept == nom_departement or type_profil == "fondateur":
                        if st.button("🗑️ Supprimer ce Cahier des Charges", key=f"del_cdc_{c_id}"):
                            archiver_dans_corbeille(c_dept, "Cahier des Charges", c_titre, {"contenu": c_contenu, "date": c_date})
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM cahiers_charges WHERE id = ?", (c_id,))
                            conn.commit()
                            conn.close()
                            ajouter_log("Suppression CDC", nom_departement, f"CDC supprimé : {c_titre}")
                            st.success("Cahier des charges supprimé.")
                            st.rerun()
        else:
            st.info("Aucun cahier des charges disponible.")

# ---------- Module Achats (workflow strict) ----------
def afficher_module_achats(nom_departement, type_profil):
    st.subheader(f"🛒 Gestion des Besoins, Demandes d'Achat & Workflow — {nom_departement}")
    t1, t2 = st.tabs(["1. Émettre une Demande", "2. Suivi, Validation & Circuit Achats/Finance"])
    with t1:
        with st.form(f"form_demande_{nom_departement}", clear_on_submit=True):
            titre = st.text_input("Intitulé du besoin / équipement / prestation")
            cahier_charges = st.text_area("Spécifications et justification du besoin")
            montant = st.number_input("Montant estimé (€) - Optionnel", min_value=0.0, step=100.0, value=0.0)
            fournisseur = st.text_input("Fournisseur pressenti (Optionnel)")
            devis_fich = st.file_uploader("📥 Joindre un devis / pièce justificative", type=["pdf", "png", "jpg", "xlsx"])
            if st.form_submit_button("Soumettre la demande d'achat") and titre:
                nom_f = enregistrer_fichier_securise(DOSSIER_UPLOADS, devis_fich)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM demandes")
                nb_total = cursor.fetchone()[0] + 1
                numero_ticket = f"#TICK-{nb_total:04d}"
                cursor.execute("""
                    INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, numero_ticket)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nom_departement, titre, cahier_charges, montant if montant > 0 else None, fournisseur, "En attente Achats", "achats", "", "", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_f, "", numero_ticket))
                conn.commit()
                conn.close()
                ajouter_log("Demande d'Achat", nom_departement, f"Demande créée : {numero_ticket} - {titre}")
                add_notification("Achats & Approvisionnements", numero_ticket, f"Nouvelle demande à sourcer : {titre}", target_tab="3. Besoins & Achats")
                st.success(f"Demande enregistrée avec le ticket {numero_ticket} et transmise au pôle Achats !")
                st.rerun()
    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, numero_ticket FROM demandes ORDER BY id DESC")
        demandes = cursor.fetchall()
        conn.close()
        if demandes:
            df_export = pd.DataFrame([{
                "Ticket": d[15], "Émetteur": d[1], "Intitulé": d[2], "Montant": d[4] if d[4] else ""
            } for d in demandes])
            afficher_boutons_export(df_export, "suivi_achats", "Suivi des Demandes d'Achat", key_prefix="achats_suivi")
            for d in demandes:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_avis_ach, d_avis_fin, d_motif, d_date, d_fich, d_retour, d_fourn_retenu, d_ticket = d
                with st.expander(f"{d_ticket or '#TICK-0000'} [{d_dept}] {d_titre} — {d_montant or 0:,.2f} € | Statut : {d_statut}"):
                    st.markdown(f"**Description :** {d_cc}")
                    st.write(f"**Fournisseur proposé par l'émetteur :** {d_fourn or 'Aucun'}")
                    st.write(f"**Fournisseur retenu (Achats) :** {d_fourn_retenu or 'En attente de validation Achats'}")
                    st.markdown(f"**Statut actuel :** {pill_statut(d_statut)}", unsafe_allow_html=True)
                    if d_fich:
                        chemin = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin):
                            with open(chemin, "rb") as f:
                                df_bytes = f.read()
                            st.download_button("📥 Télécharger le devis joint", data=df_bytes, file_name=d_fich, key=f"dl_devis_{d_id}")
                    # CIRCUIT ACHATS (DEP12)
                    if (profil["type"] == "achats" or profil["type"] == "fondateur") and d_etape == "achats":
                        st.markdown("---")
                        st.markdown("#### 🛡️ Validation pôle Achats")
                        with st.form(f"form_achats_{d_id}"):
                            fourn_retenu_input = st.text_input("Confirmer ou modifier le fournisseur retenu", value=d_fourn_retenu or d_fourn or "")
                            # Achats can set definitive price (0 => unchanged)
                            montant_definitif = st.number_input("Montant définitif (Décidé par Achats) - 0 = inchangé", min_value=0.0, step=1.0, value=float(d_montant) if d_montant else 0.0)
                            avis_achats_input = st.text_area("Avis technique et conditions d'achat", value=d_avis_ach or "")
                            action_achats = st.radio("Décision Achats :", ["Valider et transmettre à la Finance", "Demander une modification", "Refuser"], key=f"act_ach_{d_id}")
                            if st.form_submit_button("Valider l'étape Achats"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                montant_to_save = None
                                try:
                                    if montant_definitif and float(montant_definitif) > 0.0:
                                        montant_to_save = float(montant_definitif)
                                except Exception:
                                    montant_to_save = None
                                if action_achats == "Valider et transmettre à la Finance":
                                    if montant_to_save is not None:
                                        cursor.execute("UPDATE demandes SET etape_actuelle = 'finance', statut = 'En attente Finance', fournisseur_retenu = ?, avis_achats = ?, montant = ? WHERE id = ?", (fourn_retenu_input, avis_achats_input, montant_to_save, d_id))
                                    else:
                                        cursor.execute("UPDATE demandes SET etape_actuelle = 'finance', statut = 'En attente Finance', fournisseur_retenu = ?, avis_achats = ? WHERE id = ?", (fourn_retenu_input, avis_achats_input, d_id))
                                    msg = "Validé par Achats, transmis à la Finance"
                                    add_notification("Finance & Comptabilité", d_ticket, f"Demande {d_ticket} prête pour contrôle financier.", target_tab="3. Besoins & Achats")
                                elif action_achats == "Demander une modification":
                                    if montant_to_save is not None:
                                        cursor.execute("UPDATE demandes SET statut = 'Demande de Modification', fournisseur_retenu = ?, avis_achats = ?, retour_remarque = ?, montant = ? WHERE id = ?", (fourn_retenu_input, avis_achats_input, avis_achats_input, montant_to_save, d_id))
                                    else:
                                        cursor.execute("UPDATE demandes SET statut = 'Demande de Modification', fournisseur_retenu = ?, avis_achats = ?, retour_remarque = ? WHERE id = ?", (fourn_retenu_input, avis_achats_input, avis_achats_input, d_id))
                                    msg = "Demande de modification renvoyée à l'émetteur"
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} nécessite une modification : {avis_achats_input}", target_tab="3. Besoins & Achats")
                                else:
                                    cursor.execute("UPDATE demandes SET statut = 'Refusé Achats', motif_refus = ? WHERE id = ?", (avis_achats_input, d_id))
                                    msg = "Demande refusée par les Achats"
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} a été refusée par Achats : {avis_achats_input}", target_tab="3. Besoins & Achats")
                                conn.commit()
                                conn.close()
                                ajouter_log("Validation Achats", nom_dept, f"Ticket {d_ticket}: {msg}")
                                st.success("Action enregistrée avec succès !")
                                st.rerun()
                    # CIRCUIT FINANCE
                    elif (profil["type"] == "finance" or profil["type"] == "fondateur") and d_etape == "finance":
                        st.markdown("---")
                        st.markdown("#### 💰 Contrôle Pôle Finance")
                        with st.form(f"form_finance_{d_id}"):
                            avis_fin_input = st.text_area("Analyse budgétaire et imputation", value=d_avis_fin or "")
                            action_fin = st.radio("Décision Finance :", ["Valider et transmettre à la Direction Générale", "Demander une modification", "Refuser (Hors budget)"], key=f"act_fin_{d_id}")
                            if st.form_submit_button("Valider l'étape Finance"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_fin == "Valider et transmettre à la Direction Générale":
                                    cursor.execute("UPDATE demandes SET etape_actuelle = 'direction', statut = 'En attente Direction', avis_finance = ? WHERE id = ?", (avis_fin_input, d_id))
                                    msg = "Validé par Finance, transmis à la Direction"
                                    add_notification("Direction Générale", d_ticket, f"Demande {d_ticket} validée par Finance et prête pour suivi.", target_tab="📊 Pôle de Contrôle (Suivi Global)")
                                elif action_fin == "Demander une modification":
                                    cursor.execute("UPDATE demandes SET statut = 'Demande de Modification', avis_finance = ?, retour_remarque = ? WHERE id = ?", (avis_fin_input, avis_fin_input, d_id))
                                    msg = "Demande de modification renvoyée"
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} nécessite une modification suite au contrôle Finance.", target_tab="3. Besoins & Achats")
                                else:
                                    cursor.execute("UPDATE demandes SET statut = 'Refusé Finance', motif_refus = ? WHERE id = ?", (avis_fin_input, d_id))
                                    msg = "Refusé par la Finance"
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} a été refusée par Finance : {avis_fin_input}", target_tab="3. Besoins & Achats")
                                conn.commit()
                                conn.close()
                                ajouter_log("Validation Finance", nom_dept, f"Ticket {d_ticket}: {msg}")
                                st.success("Action Finance enregistrée !")
                                st.rerun()
                    # CIRCUIT DIRECTION
                    elif profil["type"] == "fondateur" and d_etape == "direction":
                        st.markdown("---")
                        st.markdown("#### 👑 Arbitrage Direction Générale")
                        with st.form(f"form_dir_{d_id}"):
                            action_dir = st.radio("Arbitrage Final :", ["Approuver et engager le budget", "Refuser définitivement"], key=f"act_dir_{d_id}")
                            motif_dir = st.text_area("Commentaire de la Direction")
                            if st.form_submit_button("Confirmer l'arbitrage"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_dir == "Approuver et engager le budget":
                                    cursor.execute("UPDATE demandes SET statut = 'Validé & Financé', etape_actuelle = 'cloture', motif_refus = ? WHERE id = ?", (motif_dir, d_id))
                                    solde_actuel = get_valeur_globale("solde_restant")
                                    set_valeur_globale("solde_restant", max(0.0, solde_actuel - (d_montant or 0.0)))
                                    msg = f"Approuvé par la Direction ({d_montant:,.2f} € déduits du solde)" if d_montant else "Approuvé par la Direction"
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} a été approuvée par la Direction.", target_tab="3. Besoins & Achats")
                                else:
                                    cursor.execute("UPDATE demandes SET statut = 'Refusé Direction', motif_refus = ? WHERE id = ?", (motif_dir, d_id))
                                    msg = "Refusé par la Direction"
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} a été refusée par la Direction : {motif_dir}", target_tab="3. Besoins & Achats")
                                conn.commit()
                                conn.close()
                                ajouter_log("Arbitrage Direction", nom_dept, f"Ticket {d_ticket}: {msg}")
                                st.success("Arbitrage enregistré !")
                                st.rerun()
                    # CORRECTION PAR L'ÉMETTEUR
                    if d_dept == nom_departement and d_statut == "Demande de Modification":
                        st.markdown("---")
                        st.markdown("#### ✏️ Corriger votre demande suite aux remarques")
                        st.info(f"Remarque / Demande de modification : {d_retour}")
                        with st.form(f"form_correction_{d_id}"):
                            nouveau_titre = st.text_input("Intitulé", value=d_titre)
                            nouveau_cc = st.text_area("Description corrigée", value=d_cc)
                            nouveau_montant = st.number_input("Montant (€)", value=d_montant or 0.0)
                            if st.form_submit_button("Renvoyer pour validation Achats"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE demandes SET titre = ?, cahier_charges = ?, montant = ?, statut = 'En attente Achats', etape_actuelle = 'achats', retour_remarque = '' WHERE id = ?", (nouveau_titre, nouveau_cc, nouveau_montant, d_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Correction Demande", nom_departement, f"Ticket {d_ticket} corrigé et renvoyé")
                                add_notification("Achats & Approvisionnements", d_ticket, f"Demande {d_ticket} resoumise après correction.", target_tab="3. Besoins & Achats")
                                st.success("Demande renvoyée aux Achats !")
                                st.rerun()
        else:
            st.info("Aucune demande d'achat enregistrée.")

# ---------- Module Messagerie ----------
def afficher_module_messagerie(nom_departement):
    st.subheader(f"💬 Messagerie Interne & Salons de Discussion — {nom_departement}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom_groupe, membres_json, createur, archives_par FROM discussions")
    discs = cursor.fetchall()
    tous_depts = [u["dept"] for u in UTILISATEURS.values()]
    c_g1, c_g2 = st.columns([2, 1])
    with c_g1:
        with st.expander("➕ Créer un nouveau salon de discussion"):
            with st.form("form_creer_salon", clear_on_submit=True):
                nom_salon = st.text_input("Nom du salon ou projet")
                membres_choisis = st.multiselect("Membres participants", tous_depts, default=[nom_departement])
                if st.form_submit_button("Créer le salon") and nom_salon:
                    if nom_departement not in membres_choisis:
                        membres_choisis.append(nom_departement)
                    cursor.execute("INSERT INTO discussions (nom_groupe, membres_json, createur, date_creation, archives_par) VALUES (?, ?, ?, ?, ?)",
                                   (nom_salon, json.dumps(membres_choisis), nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps([])))
                    conn.commit()
                    st.success("Salon créé avec succès !")
                    st.rerun()
    mes_discs = []
    for d in discs:
        d_id, d_nom, d_membres_j, d_createur, d_archives_j = d
        membres = json.loads(d_membres_j) if d_membres_j else []
        archives = json.loads(d_archives_j) if d_archives_j else []
        if nom_departement in membres and nom_departement not in archives:
            mes_discs.append(d)
    conn.close()
    if mes_discs:
        noms_discs = {f"{d[1]} (Créé par {d[3]})": d[0] for d in mes_discs}
        selected_key = st.selectbox("Sélectionner un salon de discussion", list(noms_discs.keys()), key="select_salon_actif")
        active_disc_id = noms_discs[selected_key]
        st.session_state.discussion_active_id = active_disc_id
        st.markdown("---")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, expediteur, texte, date, lus_json FROM messages_chat WHERE discussion_id = ? ORDER BY id ASC", (active_disc_id,))
        messages = cursor.fetchall()
        for m in messages:
            m_id, m_exp, _, _, m_lus_j = m
            lus = json.loads(m_lus_j) if m_lus_j else []
            if m_exp != nom_departement and nom_departement not in lus:
                lus.append(nom_departement)
                cursor.execute("UPDATE messages_chat SET lus_json = ? WHERE id = ?", (json.dumps(lus), m_id))
        conn.commit()
        for m_id, m_exp, m_texte, m_date, _ in messages:
            is_me = (m_exp == nom_departement)
            align = "right" if is_me else "left"
            bg = "#1f2937" if is_me else "#111827"
            st.markdown(f"""
                <div style="text-align: {align}; margin-bottom: 8px;">
                    <span style="font-size: 0.75rem; color: #8b96a5;"><b>{m_exp}</b> — {m_date}</span><br>
                    <div style="display: inline-block; background-color: {bg}; padding: 8px 12px; border-radius: 8px; text-align: left; max-width: 75%; border: 1px solid #374151;">
                        {m_texte}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        with st.form(f"form_envoi_msg_{active_disc_id}", clear_on_submit=True):
            nouveau_texte = st.text_input("Votre message")
            if st.form_submit_button("Envoyer") and nouveau_texte:
                cursor.execute("INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json) VALUES (?, ?, ?, ?, ?)",
                               (active_disc_id, nom_departement, nouveau_texte, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps([nom_departement])))
                conn.commit()
                st.rerun()
        conn.close()
    else:
        st.info("Vous ne participez à aucun salon actif pour le moment.")

# ---------- Journal, Recherche, Control, Stats, Audit, Corbeille ----------
def afficher_journal_bord(nom_departement, type_profil):
    st.subheader(f"📖 Journal de Bord & Notes Opérationnelles — {nom_departement}")
    t1, t2 = st.tabs(["1. Ajouter une Note", "2. Consulter le Journal"])
    with t1:
        with st.form("form_journal", clear_on_submit=True):
            note = st.text_area("Contenu de la note, événement ou rapport d'activité")
            if st.form_submit_button("Enregistrer dans le Journal") and note:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO journal_bord (departement, auteur, note, date_note, heure_note) VALUES (?, ?, ?, ?, ?)",
                               (nom_departement, profil["nom"], note, date.today().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M")))
                conn.commit()
                conn.close()
                ajouter_log("Journal de Bord", nom_departement, "Nouvelle note enregistrée")
                st.success("Note ajoutée au journal !")
                st.rerun()
    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT id, departement, auteur, note, date_note, heure_note FROM journal_bord ORDER BY id DESC" if type_profil == "fondateur" else "SELECT id, departement, auteur, note, date_note, heure_note FROM journal_bord WHERE departement = ? ORDER BY id DESC"
        cursor.execute(query, () if type_profil == "fondateur" else (nom_departement,))
        notes = cursor.fetchall()
        conn.close()
        if notes:
            for n_id, n_dept, n_auteur, n_note, n_date, n_heure in notes:
                st.markdown(f"""
                    <div class="note-card">
                        <span class="note-date">[{n_dept}] Par {n_auteur} le {n_date} à {n_heure}</span>
                        <p style="margin-top: 6px; margin-bottom: 0;">{n_note}</p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Aucune note dans le journal.")

def afficher_recherche_globale():
    st.subheader("🔍 Recherche Globale dans la Plateforme")
    terme = st.text_input("Mot-clé à rechercher (études, cahiers des charges, achats, notes)")
    if terme:
        t = f"%{terme}%"
        conn = get_db_connection()
        cursor = conn.cursor()
        st.markdown("### ⚙️ Études Métier correspondantes")
        cursor.execute("SELECT id, departement, titre, date FROM etudes_metier WHERE titre LIKE ? OR donnees_json LIKE ?", (t, t))
        for r in cursor.fetchall():
            st.write(f"- **[{r[1]}] {r[2]}** ({r[3]})")
        st.markdown("### 📋 Cahiers des Charges correspondants")
        cursor.execute("SELECT id, departement, titre, date FROM cahiers_charges WHERE titre LIKE ? OR contenu LIKE ?", (t, t))
        for r in cursor.fetchall():
            st.write(f"- **[{r[1]}] {r[2]}** ({r[3]})")
        st.markdown("### 🛒 Demandes d'Achat correspondantes")
        cursor.execute("SELECT id, numero_ticket, departement, titre, montant FROM demandes WHERE titre LIKE ? OR cahier_charges LIKE ? OR numero_ticket LIKE ?", (t, t, t))
        for r in cursor.fetchall():
            st.write(f"- **{r[1]} [{r[2]}]** {r[3]} ({r[4]:,.2f} €)")
        conn.close()

def afficher_pole_controle():
    st.subheader("📊 Pôle de Contrôle & Suivi Global des Activités")
    conn = get_db_connection()
    df_demandes = pd.read_sql_query("SELECT numero_ticket, departement, titre, montant, statut, etape_actuelle, date FROM demandes", conn)
    df_etudes = pd.read_sql_query("SELECT id, departement, titre, date FROM etudes_metier", conn)
    conn.close()
    st.markdown("#### 🛒 Synthèse des Demandes d'Achat Globales")
    if not df_demandes.empty:
        afficher_boutons_export(df_demandes, "controle_demandes", "Synthèse Globale des Demandes", key_prefix="ctrl_dem")
        st.dataframe(df_demandes, use_container_width=True)
    else:
        st.info("Aucune donnée d'achat.")
    st.markdown("#### ⚙️ Synthèse des Études Techniques Globales")
    if not df_etudes.empty:
        afficher_boutons_export(df_etudes, "controle_etudes", "Synthèse Globale des Études", key_prefix="ctrl_etu")
        st.dataframe(df_etudes, use_container_width=True)
    else:
        st.info("Aucune étude enregistrée.")

def afficher_statistiques():
    st.subheader("📈 Statistiques & Indicateurs Clés de Performance")
    conn = get_db_connection()
    df_dem = pd.read_sql_query("SELECT statut, montant FROM demandes", conn)
    conn.close()
    if not df_dem.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Demandes", len(df_dem))
        c2.metric("Montant Global Cumulé", f"{df_dem['montant'].sum():,.2f} €")
        c3.metric("Montant Moyen par Demande", f"{df_dem['montant'].mean():,.2f} €")
        st.markdown("#### Répartition par Statut")
        st.bar_chart(df_dem["statut"].value_counts())
    else:
        st.info("Pas assez de données pour afficher les statistiques.")

def afficher_audit_tracabilite():
    st.subheader("🕵️ Logs d'Audit & Traçabilité Complète du Système")
    conn = get_db_connection()
    df_logs = pd.read_sql_query("SELECT id, date, acteur, action, details FROM logs_audit ORDER BY id DESC", conn)
    conn.close()
    if not df_logs.empty:
        afficher_boutons_export(df_logs, "logs_audit_systeme", "Journal d'Audit et Sécurité", key_prefix="audit_logs")
        st.dataframe(df_logs, use_container_width=True)
    else:
        st.info("Aucun log enregistré.")

def afficher_corbeille():
    st.subheader("🗑️ Corbeille & Historique des Éléments Supprimés")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement_auteur, type_element, resume, details_json, date_suppression FROM corbeille_archives ORDER BY id DESC")
    archives = cursor.fetchall()
    conn.close()
    if archives:
        for a_id, a_dept, a_type, a_resume, a_details, a_date in archives:
            with st.expander(f"🗑️ [{a_type}] {a_resume} (Supprimé par {a_dept} le {a_date})"):
                st.write(f"**Détails archivés :** {a_details}")
                if st.button("Vider de la corbeille définitivement", key=f"vider_arch_{a_id}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM corbeille_archives WHERE id = ?", (a_id,))
                    conn.commit()
                    conn.close()
                    st.success("Élément supprimé définitivement.")
                    st.rerun()
    else:
        st.info("La corbeille est vide.")

# ---------- ROUTAGE PRINCIPAL ----------
tab_act = st.session_state.tab_actif

if tab_act == "1. Études & Ingénierie":
    afficher_module_etudes(nom_dept, profil["type"])
elif tab_act == "2. Cahiers des Charges":
    afficher_module_cahiers_charges(nom_dept, profil["type"])
elif tab_act == "3. Besoins & Achats":
    afficher_module_achats(nom_dept, profil["type"])
elif tab_act == "4. Messagerie & Chat":
    afficher_module_messagerie(nom_dept)
elif tab_act == "📖 Journal de Bord":
    afficher_journal_bord(nom_dept, profil["type"])
elif tab_act == "🔍 Recherche Globale":
    afficher_recherche_globale()
elif tab_act == "📊 Pôle de Contrôle (Suivi Global)" and profil["type"] in ["achats", "finance", "fondateur"]:
    afficher_pole_controle()
elif tab_act == "📈 Statistiques" and profil["type"] in ["achats", "finance", "fondateur"]:
    afficher_statistiques()
elif tab_act == "🕵️ Audit & Traçabilité" and profil["type"] == "fondateur":
    afficher_audit_tracabilite()
elif tab_act == "🗑️ Corbeille & Historique Suppressions" and profil["type"] == "fondateur":
    afficher_corbeille()
else:
    st.info("Section inconnue — sélectionnez une section dans la barre latérale.")
