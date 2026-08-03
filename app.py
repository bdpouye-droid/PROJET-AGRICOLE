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

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================

st.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

# ==========================================
# DOSSIERS DE STOCKAGE
# ==========================================

DOSSIER_UPLOADS = "uploads_devis"
DOSSIER_ETUDES = "uploads_etudes"
os.makedirs(DOSSIER_UPLOADS, exist_ok=True)
os.makedirs(DOSSIER_ETUDES, exist_ok=True)
CHEMIN_LOGO = "logo.png"

# ==========================================
# STYLE CSS PERSONNALISÉ & DESIGN MODERNE
# ==========================================

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
    .stCard {
      background-color: var(--bg-card);
      border: 1px solid var(--border);
      padding: 1rem;
      border-radius: 8px;
      margin-bottom: 0.8rem;
    }
    .pill-valide { background-color: #2ea043; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-refuse { background-color: #f85149; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-modif { background-color: #d29922; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-attente { background-color: #5b8def; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
  </style>
""", unsafe_allow_html=True)

# ==========================================
# UTILITAIRES : EXPORT EXCEL / PDF
# ==========================================

def _lignes_texte(df: pd.DataFrame):
    lignes = []
    for enregistrement in df.to_dict(orient="records"):
        lignes.append(["" if v is None else str(v) for v in enregistrement.values()])
    return lignes

def exporter_excel_bytes(df: pd.DataFrame, nom_feuille="Données"):
    buffer = io.BytesIO()
    feuille = nom_feuille[:31] or "Données"
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=feuille)
        try:
            worksheet = writer.sheets[feuille]
            lignes = _lignes_texte(df)
            for i, col in enumerate(df.columns):
                try:
                    largeur_contenu = max((len(ligne[i]) for ligne in lignes), default=10) if lignes else 10
                    largeur = min(max(len(str(col)), largeur_contenu) + 2, 50)
                except Exception:
                    largeur = 20
                worksheet.column_dimensions[worksheet.cell(row=1, column=i + 1).column_letter].width = largeur
        except Exception:
            pass
    return buffer.getvalue()

def exporter_pdf_bytes(df: pd.DataFrame, titre="Export", colonnes_max=8):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(titre, styles["Title"]), Spacer(1, 0.4 * cm)]
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))
    
    df_reduit = df.iloc[:, :colonnes_max]
    data = [list(df_reduit.columns)] + _lignes_texte(df_reduit)
    
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5b8def')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

def afficher_boutons_export(df: pd.DataFrame, nom_base: str, titre_pdf: str = None, key_prefix: str = ""):
    if df is None or df.empty:
        return
    try:
        excel_bytes = exporter_excel_bytes(df, nom_base)
        pdf_bytes = exporter_pdf_bytes(df, titre_pdf or nom_base)
    except Exception:
        st.caption("⚠️ Export momentanément indisponible pour cette liste.")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📊 Exporter en Excel",
            data=excel_bytes,
            file_name=f"{nom_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"xlsx_{key_prefix}",
            use_container_width=True
        )
    with c2:
        st.download_button(
            "📄 Exporter en PDF",
            data=pdf_bytes,
            file_name=f"{nom_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key=f"pdf_{key_prefix}",
            use_container_width=True
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
    return f'<span class="{classe}">{statut}</span>'

def fournisseur_affiche(fournisseur_propose: str, fournisseur_retenu: str) -> str:
    if fournisseur_retenu:
        return f"{fournisseur_retenu} ✅ (retenu par les Achats)"
    elif fournisseur_propose:
        return f"{fournisseur_propose} (pressenti par l'émetteur, non confirmé)"
    return "Non renseigné"

# ==========================================
# INITIALISATION BASE DE DONNÉES
# ==========================================

def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS global_store (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS demandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        titre TEXT,
        cahier_charges TEXT,
        montant REAL,
        fournisseur TEXT,
        statut TEXT,
        etape_actuelle TEXT,
        avis_achats TEXT,
        avis_finance TEXT,
        motif_refus TEXT,
        date TEXT,
        fichier_devis TEXT,
        retour_remarque TEXT,
        fournisseur_retenu TEXT DEFAULT '',
        archive INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS etudes_metier (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        titre TEXT,
        donnees_json TEXT,
        fichier_etude TEXT,
        destinataires_partage TEXT,
        date TEXT,
        archive INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cahiers_charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        titre TEXT,
        contenu TEXT,
        date TEXT,
        destinataires_avis TEXT,
        archive INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS discussions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_groupe TEXT,
        membres_json TEXT,
        createur TEXT,
        date_creation TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discussion_id INTEGER,
        expediteur TEXT,
        texte TEXT,
        date TEXT,
        lus_json TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS journal_bord (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        auteur TEXT,
        note TEXT,
        date_note TEXT,
        heure_note TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS corbeille_archives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement_auteur TEXT,
        type_element TEXT,
        resume TEXT,
        details_json TEXT,
        date_suppression TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        acteur TEXT,
        action TEXT,
        details TEXT
    )''')
    conn.commit()
    conn.close()

def migrer_schema():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    migrations = [
        ("discussions", "archives_par", "TEXT DEFAULT '[]'"),
        ("etudes_metier", "vus_json", "TEXT DEFAULT '[]'"),
        ("cahiers_charges", "vus_par_json", "TEXT DEFAULT '[]'"),
        ("demandes", "fournisseur_retenu", "TEXT DEFAULT ''"),
        ("demandes", "archive", "INTEGER DEFAULT 0"),
        ("etudes_metier", "archive", "INTEGER DEFAULT 0"),
        ("cahiers_charges", "archive", "INTEGER DEFAULT 0"),
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

def proposer_telechargement(dossier, nom_fichier, libelle, key):
    if not nom_fichier:
        return
    try:
        chemin = os.path.join(dossier, nom_fichier)
        if os.path.exists(chemin):
            with open(chemin, "rb") as f:
                st.download_button(libelle, f, file_name=nom_fichier, key=key)
        else:
            st.caption("📎 Pièce jointe indisponible (fichier introuvable).")
    except Exception:
        st.caption("📎 Impossible d'accéder à cette pièce jointe pour le moment.")

# ==========================================
# ROLES ET UTILISATEURS
# ==========================================

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

# ==========================================
# GESTION DE LA SESSION
# ==========================================

if 'user_connecte' not in st.session_state:
    st.session_state.user_connecte = None
if 'tab_actif' not in st.session_state:
    st.session_state.tab_actif = "1. Études & Ingénierie"
if 'discussion_active_id' not in st.session_state:
    st.session_state.discussion_active_id = None

# ==========================================
# AUTHENTIFICATION & BARRE LATÉRALE
# ==========================================

if os.path.exists(CHEMIN_LOGO):
    st.sidebar.image(CHEMIN_LOGO, use_container_width=True)
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

st.sidebar.success(f"Connecté : {profil['nom']}")
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

# ==========================================
# NAVIGATION ONGLETS PRINCIPAUX
# ==========================================

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

st.markdown("---")

# ==========================================
# 1. MODULE INGÉNIERIE & ÉTUDES MÉTIER
# ==========================================

def afficher_module_etudes(nom_departement, type_profil):
    st.subheader(f"⚙️ Centre d'Ingénierie & Traçabilité des Études — {nom_departement}")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    t1, t2, t3 = st.tabs(["1. Nouvelle Étude & Partage", "2. Études Reçues", "3. 📜 Historique & Gestion"])

    with t1:
        with st.form("form_nouvelle_etude"):
            titre = st.text_input("Titre de l'étude / Note technique")
            desc = st.text_area("Description & Paramètres (JSON ou texte structuré)")
            destinataires = st.multiselect("Partager cette étude avec d'autres départements", tous_depts)
            fichier = st.file_uploader("Pièce jointe (PDF, Excel, DWG, etc.)", type=["pdf", "xlsx", "docx"])
            submitted = st.form_submit_button("Diffuser l'étude")

            if submitted:
                if not titre:
                    st.error("Le titre est obligatoire.")
                else:
                    nom_fichier = enregistrer_fichier_securise(DOSSIER_ETUDES, fichier)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        """INSERT INTO etudes_metier (departement, titre, donnees_json, fichier_etude, destinataires_partage, date) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (nom_departement, titre, desc, nom_fichier, json.dumps(destinataires), datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    ajouter_log("Création Étude", nom_departement, f"Étude: {titre}")
                    st.success("Étude enregistrée et partagée avec succès !")
                    st.rerun()

    with t2:
        st.markdown("### Études partagées avec votre département")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier WHERE archive = 0")
        rows = cursor.fetchall()
        conn.close()

        recues = []
        for r in rows:
            dests = json.loads(r[5] if r[5] else "[]")
            if nom_departement in dests or type_profil == "fondateur":
                recues.append(r)

        if not recues:
            st.info("Aucune étude reçue pour le moment.")
        else:
            for r in recues:
                with st.expander(f"📁 [{r[1]}] {r[2]} (Émise le {r[6]})"):
                    st.write(f"**Contenu :** {r[3]}")
                    proposer_telechargement(DOSSIER_ETUDES, r[4], "📥 Télécharger le document", f"dl_etude_{r[0]}")

    with t3:
        st.markdown("### Vos études émises")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titre, date, destinataires_partage FROM etudes_metier WHERE departement = ? AND archive = 0", (nom_departement,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            st.info("Vous n'avez publié aucune étude active.")
        else:
            for r in rows:
                st.write(f"- **{r[1]}** (le {r[2]}) — Partagé avec : {', '.join(json.loads(r[3])) if r[3] else 'Aucun'}")


# ==========================================
# 2. MODULE CAHIERS DES CHARGES
# ==========================================

def afficher_module_cdc(nom_departement, type_profil):
    st.subheader("📋 Cahiers des Charges & Documents Partagés")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    with st.form("form_cdc"):
        titre = st.text_input("Titre du Cahier des Charges")
        contenu = st.text_area("Contenu détaillé / Spécifications techniques")
        destinataires = st.multiselect("Demander un avis / partage aux départements", tous_depts)
        submitted = st.form_submit_button("Publier le Cahier des Charges")
        
        if submitted:
            if not titre:
                st.error("Le titre est obligatoire.")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (nom_departement, titre, contenu, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(destinataires))
                )
                conn.commit()
                conn.close()
                ajouter_log("Création CDC", nom_departement, f"Cahier des charges: {titre}")
                st.success("Cahier des charges publié.")
                st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Cahiers des Charges disponibles")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE archive = 0")
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        with st.expander(f"📋 {r[2]} ({r[1]} - {r[4]})"):
            st.write(r[3])


# ==========================================
# 3. MODULE BESOINS & ACHATS (STRICT & SÉCURISÉ)
# ==========================================

def afficher_module_achats(nom_departement, type_profil):
    st.subheader("🛒 Gestion des Demandes d'Achat & Validations")
    
    tab_achats_1, tab_achats_2, tab_achats_3 = st.tabs(["📋 Soumettre & Suivi des Demandes", "📥 Validation Achats & Sourcing", "🗄️ Archives Demandes"])
    
    with tab_achats_1:
        if type_profil != "achats":
            with st.expander("➕ Émettre une nouvelle demande d'achat", expanded=False):
                with st.form("form_nouvelle_demande"):
                    titre_demande = st.text_input("Titre de la demande / Objet")
                    cahier_charges_ref = st.text_input("Référence ou lien du Cahier des Charges associé")
                    montant_estime = st.number_input("Montant estimé (€ - minimum 100€ recommandé)", min_value=0.0, step=100.0, value=100.0)
                    fournisseur_propose = st.text_input("Fournisseur pressenti (optionnel)")
                    fichier_devis = st.file_uploader("Joindre un devis / document (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                    
                    soumettre = st.form_submit_button("Soumettre la demande")
                    if soumettre:
                        if not titre_demande.strip():
                            st.warning("Veuillez renseigner un titre pour la demande.")
                        else:
                            nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute(
                                """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                                (nom_departement, titre_demande, cahier_charges_ref, montant_estime, fournisseur_propose, "En attente Achats", "Achats", "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", "")
                            )
                            conn.commit()
                            conn.close()
                            ajouter_log("Création Demande d'Achat", nom_departement, f"Demande '{titre_demande}' soumise pour {montant_estime}€")
                            st.success("✅ Demande transmise aux Achats avec succès !")
                            st.rerun()

        st.markdown("### Suivi de vos demandes")
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE departement = ? AND archive = 0 ORDER BY id DESC", (nom_departement,))
        demandes = cursor.fetchall()
        conn.close()

        if not demandes:
            st.info("Aucune demande active pour le moment.")
        else:
            for d in demandes:
                did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                
                # Conversion sécurisée du montant pour éviter le TypeError
                try:
                    montant_aff = float(d_montant) if d_montant is not None else 0.0
                except (ValueError, TypeError):
                    montant_aff = 0.0

                with st.container():
                    st.markdown(f"""
                        <div class="stCard">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div><b>[{d_dept}] {d_titre}</b></div>
                                <div>{pill_statut(d_statut)}</div>
                            </div>
                            <div style="color: var(--text-muted); font-size: 0.9rem; margin-top: 5px;">
                                Montant estimé : <b>{montant_aff:,.2f} €</b> | Date : {d_date}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    c_det, c_arch = st.columns([4, 1])
                    with c_det:
                        with st.expander("🔍 Voir les détails & historique"):
                            st.write(f"- **Cahier des charges associé** : {d_cc or 'Aucun'}")
                            st.write(f"- **Fournisseur** : {fournisseur_affiche(d_fournisseur, d_f_retenu)}")
                            st.write(f"- **Avis Achats** : {d_avis_a} | **Avis Finance** : {d_avis_f}")
                            if d_motif:
                                st.warning(f"Motif / Remarque : {d_motif}")
                            proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis / pièce jointe", f"dl_devis_{did}")
                    with c_arch:
                        if st.button("🗄️ Archiver", key=f"btn_archiver_{did}", use_container_width=True):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE demandes SET archive = 1 WHERE id = ?", (did,))
                            conn.commit()
                            conn.close()
                            archiver_dans_corbeille(nom_departement, "Demande d'Achat", f"Demande : {d_titre}", {"id": did, "titre": d_titre, "montant": montant_aff})
                            ajouter_log("Archivage Demande", nom_departement, f"Demande '{d_titre}' archivée")
                            st.success("Demande archivée avec succès.")
                            st.rerun()

    with tab_achats_2:
        # Restriction stricte aux achats
        if type_profil != "achats" and type_profil != "fondateur":
            st.warning("🔒 Espace strictement réservé au Département des Achats pour le traitement et la validation du sourcing.")
        else:
            st.markdown("### 📥 Boîte de réception des demandes Achats")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 AND (etape_actuelle = 'Achats' OR statut = 'En attente Achats') ORDER BY id DESC")
            demandes_a_traiter = cursor.fetchall()
            conn.close()

            if not demandes_a_traiter:
                st.info("Aucune demande en attente de traitement aux Achats.")
            else:
                for d in demandes_a_traiter:
                    did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                    
                    try:
                        montant_chiffre = float(d_montant) if d_montant is not None else 0.0
                    except (ValueError, TypeError):
                        montant_chiffre = 0.0

                    with st.expander(f"🛒 [{d_dept}] {d_titre} — {montant_chiffre:,.2f} €"):
                        st.write(f"**Date de soumission** : {d_date}")
                        st.write(f"**Cahier des charges** : {d_cc or 'N/A'}")
                        st.write(f"**Fournisseur pressenti par émetteur** : {d_fournisseur or 'Aucun'}")
                        proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis émetteur", f"dl_achats_{did}")
                        
                        with st.form(f"form_traitement_achats_{did}"):
                            nouveau_montant_ajuste = st.number_input("Ajuster le prix définitif après sourcing (€)", value=montant_chiffre, step=10.0, key=f"mnt_ajust_{did}")
                            fournisseur_retenu_saisie = st.text_input("Définir le fournisseur retenu", value=d_f_retenu or d_fournisseur, key=f"fourn_ret_{did}")
                            action_achat = st.selectbox("Action Achats", ["Valider et transmettre à la Finance", "Demander modification", "Refuser"], key=f"act_achats_{did}")
                            motif_achat = st.text_area("Commentaire / Motif", key=f"motif_achats_{did}")
                            
                            valider_action = st.form_submit_button("Appliquer la décision Achats")
                            if valider_action:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_achat == "Valider et transmettre à la Finance":
                                    nouveau_statut = "En attente Finance"
                                    nouvelle_etape = "Finance"
                                    avis_a = "Validé"
                                elif action_achat == "Demander modification":
                                    nouveau_statut = "Modif demandée"
                                    nouvelle_etape = "Émetteur"
                                    avis_a = "Modification demandée"
                                else:
                                    nouveau_statut = "Refusé"
                                    nouvelle_etape = "Clôturé"
                                    avis_a = "Refusé"
                                    
                                cursor.execute(
                                    """UPDATE demandes SET montant = ?, fournisseur_retenu = ?, statut = ?, etape_actuelle = ?, avis_achats = ?, motif_refus = ? WHERE id = ?""",
                                    (nouveau_montant_ajuste, fournisseur_retenu_saisie, nouveau_statut, nouvelle_etape, avis_a, motif_achat, did)
                                )
                                conn.commit()
                                conn.close()
                                ajouter_log("Traitement Achats", nom_departement, f"Demande {did} traitée : {action_achat}")
                                st.success("Décision enregistrée avec succès !")
                                st.rerun()

    with tab_achats_3:
        st.markdown("### 🗄️ Archives de vos demandes d'achat")
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, montant, statut, date FROM demandes WHERE archive = 1 ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, montant, statut, date FROM demandes WHERE departement = ? AND archive = 1 ORDER BY id DESC", (nom_departement,))
        archives = cursor.fetchall()
        conn.close()

        if not archives:
            st.info("Aucune demande archivée.")
        else:
            df_arch = pd.DataFrame(archives, columns=["ID", "Département", "Titre", "Montant (€)", "Statut", "Date"])
            st.dataframe(df_arch, use_container_width=True)
            afficher_boutons_export(df_arch, "archives_demandes", "Archives des Demandes d'Achat", "arch_dem")


# ==========================================
# 4. MODULE MESSAGERIE & CHAT UNIFIÉ
# ==========================================

@st.fragment(run_every="3s")
def afficher_zone_messages(discussion_id, nom_dept):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, expediteur, texte, date, lus_json FROM messages_chat WHERE discussion_id = ?", (discussion_id,))
    messages = cursor.fetchall()
    conn.close()

    container = st.container(height=400)
    with container:
        if not messages:
            st.info("Aucun message dans cette discussion.")
        for m in messages:
            st.markdown(f"**{m[1]}** *({m[3]})* : {m[2]}")

def afficher_module_messagerie_unifiee(nom_departement, type_profil):
    st.subheader("💬 Hub de Discussion & Communication Directe")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    t1, t2 = st.tabs(["💬 Discussions Actives", "➕ Créer un Groupe"])

    with t2:
        with st.form("form_nouveau_groupe"):
            nom_g = st.text_input("Nom du groupe ou sujet de discussion")
            membres = st.multiselect("Sélectionner les départements participants", tous_depts)
            sub_g = st.form_submit_button("Créer le groupe")
            if sub_g and nom_g:
                membres.append(nom_departement)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO discussions (nom_groupe, membres_json, createur, date_creation) 
                       VALUES (?, ?, ?, ?)""",
                    (nom_g, json.dumps(membres), nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                conn.close()
                st.success("Groupe créé avec succès !")
                st.rerun()

    with t1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom_groupe, membres_json, createur FROM discussions")
        all_discs = cursor.fetchall()
        conn.close()

        mes_discs = []
        for d in all_discs:
            membres = json.loads(d[2] if d[2] else "[]")
            if (nom_departement in membres or type_profil == "fondateur" or d[3] == nom_departement):
                mes_discs.append(d)

        if not mes_discs:
            st.info("Aucune discussion disponible. Créez un groupe pour commencer à échanger.")
        else:
            options = {f"{d[1]} (Créé par {d[3]})": d[0] for d in mes_discs}
            choix = st.selectbox("Sélectionnez une discussion", list(options.keys()))
            if choix:
                disc_id = options[choix]
                st.session_state.discussion_active_id = disc_id
                st.markdown("---")
                afficher_zone_messages(disc_id, nom_departement)

                with st.form(key=f"form_msg_{disc_id}", clear_on_submit=True):
                    texte_msg = st.text_input("Votre message")
                    envoyer = st.form_submit_button("Envoyer")
                    if envoyer and texte_msg:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json) 
                               VALUES (?, ?, ?, ?, ?)""",
                            (disc_id, nom_departement, texte_msg, datetime.now().strftime("%Y-%m-%d %H:%M"), "[]")
                        )
                        conn.commit()
                        conn.close()
                        st.rerun()


# ==========================================
# 5. JOURNAL DE BORD QUOTIDIEN
# ==========================================

def afficher_module_journal_bord(nom_departement):
    st.subheader(f"📖 Journal de Bord Quotidien & Cahier de Notes — {nom_departement}")
    with st.form("form_journal"):
        note = st.text_area("Note / Événement marquant du jour")
        submitted = st.form_submit_button("Enregistrer dans le journal")
        if submitted and note:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO journal_bord (departement, auteur, note, date_note, heure_note) 
                   VALUES (?, ?, ?, ?, ?)""",
                (nom_departement, profil["nom"], note, date.today().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"))
            )
            conn.commit()
            conn.close()
            st.success("Note ajoutée au journal.")
            st.rerun()

    st.markdown("---")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, auteur, note, date_note, heure_note FROM journal_bord WHERE departement = ? ORDER BY id DESC", (nom_departement,))
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        with st.container(border=True):
            st.markdown(f"**{r[1]}** — *{r[3]} à {r[4]}*")
            st.write(r[2])


# ==========================================
# 6. MODULE SUIVI GLOBAL POUR PÔLE DE CONTRÔLE
# ==========================================

def afficher_module_suivi_global_controle():
    st.subheader("📊 Pôle de Contrôle & Supervision Globale")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, montant, statut, etape_actuelle, date FROM demandes")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.info("Aucune donnée de suivi global.")
        return

    df_suivi = pd.DataFrame(rows, columns=["ID", "Département", "Titre", "Montant", "Statut", "Étape Actuelle", "Date"])
    st.dataframe(df_suivi, use_container_width=True)
    afficher_boutons_export(df_suivi, "Suivi_Global_Controle", "Supervision Globale")


# ==========================================
# 7. MODULE CORBEILLE & HISTORIQUE
# ==========================================

def afficher_module_direction_corbeille():
    st.subheader("🗑️ Supervisions des Éléments Supprimés (Corbeille Centralisée)")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement_auteur, type_element, resume, date_suppression FROM corbeille_archives")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.success("La corbeille est vide.")
    else:
        df_corb = pd.DataFrame(rows, columns=["ID", "Département Auteur", "Type", "Résumé", "Date Suppression"])
        st.dataframe(df_corb, use_container_width=True)
        afficher_boutons_export(df_corb, "Corbeille_Archives", "Historique des Suppressions")


# ==========================================
# 8. MODULE AUDIT & TRAÇABILITÉ
# ==========================================

def afficher_module_audit():
    st.subheader("🕵️ Audit & Traçabilité (Connexions, Actions, Durées)")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, acteur, action, details FROM logs_audit")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.info("Aucun journal d'audit disponible.")
    else:
        df_audit = pd.DataFrame(rows, columns=["ID", "Date", "Acteur", "Action", "Détails"])
        st.dataframe(df_audit, use_container_width=True)
        afficher_boutons_export(df_audit, "Logs_Audit", "Journal d'Audit")


# ==========================================
# 9. MODULE RECHERCHE GLOBALE
# ==========================================

def afficher_module_recherche_globale(nom_departement, type_profil):
    st.subheader("🔍 Recherche Globale")
    terme = st.text_input("Mot-clé à rechercher dans les études et demandes")
    if terme:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT titre, departement, 'Étude' FROM etudes_metier WHERE titre LIKE ? OR donnees_json LIKE ?", (f"%{terme}%", f"%{terme}%"))
        res_etudes = cursor.fetchall()
        cursor.execute("SELECT titre, departement, 'Demande Achat' FROM demandes WHERE titre LIKE ? OR cahier_charges LIKE ?", (f"%{terme}%", f"%{terme}%"))
        res_demandes = cursor.fetchall()
        conn.close()

        tous_res = res_etudes + res_demandes
        if not tous_res:
            st.warning("Aucun résultat trouvé.")
        else:
            for r in tous_res:
                st.write(f"- **[{r[2]}]** {r[0]} *(Émis par {r[1]})*")


# ==========================================
# 10. MODULE STATISTIQUES
# ==========================================

def afficher_module_statistiques():
    st.subheader("📈 Statistiques par Département")
    conn = get_db_connection()
    df_dem = pd.read_sql_query("SELECT departement, montant FROM demandes", conn)
    conn.close()

    if df_dem.empty:
        st.info("Pas assez de données pour afficher les statistiques.")
    else:
        # Conversion forcée pour s'assurer qu'il n'y ait pas de plantage de graphe
        df_dem['montant'] = pd.to_numeric(df_dem['montant'], errors='coerce').fillna(0)
        df_stats = df_dem.groupby("departement").sum().reset_index()
        st.bar_chart(df_stats, x="departement", y="montant")


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
