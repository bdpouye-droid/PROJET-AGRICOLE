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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================

st.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

# ==========================================
# DOSSIERS DE STOCKAGE & CACHE OPTIMISÉ
# ==========================================

DOSSIER_UPLOADS = "uploads_devis"
DOSSIER_ETUDES = "uploads_etudes"
DOSSIER_CDC = "uploads_cdc"
os.makedirs(DOSSIER_UPLOADS, exist_ok=True)
os.makedirs(DOSSIER_ETUDES, exist_ok=True)
os.makedirs(DOSSIER_CDC, exist_ok=True)
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
      color: #e8e8ec;
    }
    .stCard * { color: #e8e8ec; }
    .pill-valide { background-color: #2ea043; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-refuse { background-color: #f85149; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-modif { background-color: #d29922; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-attente { background-color: #5b8def; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .notif-centre-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: none;
      z-index: 9999;
    }
    .notif-centre-box {
      background-color: var(--bg-card);
      border: 1px solid var(--success);
      color: white;
      padding: 1.1rem 2rem;
      border-radius: 12px;
      font-size: 1.1rem;
      font-weight: 600;
      box-shadow: 0 10px 30px rgba(0,0,0,0.55);
      display: flex;
      align-items: center;
      gap: 0.7rem;
      animation: notifCentreAnim 2.8s ease forwards;
    }
    .notif-centre-icon { font-size: 1.6rem; }
    @keyframes notifCentreAnim {
      0%   { opacity: 0; transform: scale(0.85) translateY(10px); }
      10%  { opacity: 1; transform: scale(1) translateY(0); }
      85%  { opacity: 1; transform: scale(1) translateY(0); }
      100% { opacity: 0; transform: scale(0.95) translateY(-6px); }
    }
    [data-testid="stTabs"] [data-baseweb="tab-panel"] {
      background-color: #ffffff;
      color: #1a1a1a;
      border-radius: 0 12px 12px 12px;
      padding: 1.2rem;
      box-shadow: 0 4px 18px rgba(0,0,0,0.08);
      margin-top: -1px;
    }
    [data-testid="stTabs"] [data-baseweb="tab-panel"] * { color: inherit; }
  </style>
""", unsafe_allow_html=True)

# ==========================================
# NOTIFICATION CENTRÉE ANIMÉE
# ==========================================

def notifier_succes(message, icon="✅"):
    """À appeler juste avant st.rerun() pour afficher une notification animée
    au centre de l'écran une fois la page rechargée."""
    st.session_state["_notif_centre"] = {"message": message, "icon": icon}


def afficher_notification_centre():
    """Affiche (une seule fois) la notification en attente, s'il y en a une."""
    notif = st.session_state.pop("_notif_centre", None)
    if notif:
        st.markdown(f"""
        <div class="notif-centre-overlay">
          <div class="notif-centre-box">
            <span class="notif-centre-icon">{notif['icon']}</span>
            <span class="notif-centre-texte">{notif['message']}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)


# ==========================================
# UTILITAIRES : EXPORT EXCEL / PDF & CACHE
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

_UNITES_FR = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
              "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
_DIZAINES_FR = ["", "", "vingt", "trente", "quarante", "cinquante", "soixante", "soixante-dix", "quatre-vingt", "quatre-vingt-dix"]

def _trois_chiffres_en_lettres_fr(n: int) -> str:
    mots = []
    centaines, reste = divmod(n, 100)
    if centaines > 0:
        mots.append(("cent" if centaines == 1 else _UNITES_FR[centaines] + " cent") + ("s" if centaines > 1 and reste == 0 else ""))
    if reste > 0:
        if reste < 20:
            mots.append(_UNITES_FR[reste])
        else:
            dizaine, unite = divmod(reste, 10)
            if dizaine in (7, 9):
                mots.append(_DIZAINES_FR[dizaine - 1] + "-" + _UNITES_FR[10 + unite])
            elif unite == 0:
                mots.append(_DIZAINES_FR[dizaine])
            elif unite == 1 and dizaine != 8:
                mots.append(_DIZAINES_FR[dizaine] + " et un")
            else:
                mots.append(_DIZAINES_FR[dizaine] + "-" + _UNITES_FR[unite])
    return " ".join(mots)

def nombre_en_lettres_fr(n: int) -> str:
    if n == 0:
        return "zéro"
    groupes_noms = ["", " mille", " million", " milliard"]
    parties = []
    temp, i = n, 0
    while temp > 0:
        groupe = temp % 1000
        if groupe > 0:
            mot = "mille" if (i == 1 and groupe == 1) else _trois_chiffres_en_lettres_fr(groupe) + groupes_noms[i]
            parties.insert(0, mot)
        temp //= 1000
        i += 1
    return " ".join(parties)

def montant_en_lettres(montant: float, devise: str = "EUR") -> str:
    entier = int(montant)
    centimes = round((montant - entier) * 100)
    nom_devise = {"EUR": "euros", "USD": "dollars", "XOF": "francs CFA"}.get(devise, devise)
    texte = f"{nombre_en_lettres_fr(entier)} {nom_devise}"
    if centimes > 0:
        texte += f" et {nombre_en_lettres_fr(centimes)} centime{'s' if centimes > 1 else ''}"
    return texte[0].upper() + texte[1:]

def generer_pdf_bon_commande(demande: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = getSampleStyleSheet()
    style_n = styles["Normal"]
    style_b = ParagraphStyle("bloc_bold", parent=style_n, fontName="Helvetica-Bold")
    style_titre = ParagraphStyle("titre_bc", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#2b3542"))

    montant_total = float(demande.get("montant") or 0)
    devise = demande.get("devise") or "EUR"
    numero_bc = f"BC-{datetime.now().year}-{int(demande['id']):05d}"

    elements = []

    # --- En-tête : logo + numéro/date ---
    if os.path.exists(CHEMIN_LOGO):
        logo_cell = Image(CHEMIN_LOGO, width=3.2 * cm, height=3.2 * cm, kind="proportional")
    else:
        logo_cell = Paragraph("<b>NATIKA GROUP</b>", styles["Heading2"])
    bloc_titre = [
        Paragraph("BON DE COMMANDE", style_titre),
        Paragraph(f"<b>N° {numero_bc}</b>", style_n),
        Paragraph(f"Date d'émission : {demande.get('date_validation', '—')}", style_n),
    ]
    entete = Table([[logo_cell, bloc_titre]], colWidths=[4 * cm, 12.7 * cm])
    entete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    elements.append(entete)
    elements.append(Spacer(1, 0.9 * cm))

    # --- Vendeur / Acheteur ---
    bloc_vendeur = [Paragraph("<b>FOURNISSEUR</b>", style_b), Paragraph(demande.get("fournisseur") or "—", style_n)]
    bloc_acheteur = [
        Paragraph("<b>ACHETEUR</b>", style_b),
        Paragraph("Natika Group", style_n),
        Paragraph(f"Département : {demande.get('departement', '—')}", style_n),
    ]
    parties = Table([[bloc_vendeur, bloc_acheteur]], colWidths=[8.35 * cm, 8.35 * cm])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (0, 0), 0.6, colors.HexColor("#c7c4ba")),
        ("BOX", (1, 0), (1, 0), 0.6, colors.HexColor("#c7c4ba")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(parties)
    elements.append(Spacer(1, 0.9 * cm))

    # --- Objet de la commande ---
    objet = Table([
        ["Désignation", "Montant"],
        [Paragraph(f"<b>{demande.get('titre', '')}</b><br/>{demande.get('besoins') or ''}", style_n),
         f"{montant_total:,.2f} {devise}"],
    ], colWidths=[13 * cm, 3.7 * cm])
    objet.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c9473")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(objet)
    elements.append(Spacer(1, 0.4 * cm))

    total_tbl = Table([["TOTAL À PAYER", f"{montant_total:,.2f} {devise}"]], colWidths=[13 * cm, 3.7 * cm])
    total_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2b3542")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(total_tbl)
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"<i>Arrêté à la somme de : {montant_en_lettres(montant_total, devise)}.</i>", style_n))
    elements.append(Spacer(1, 0.9 * cm))

    # --- Échéancier de paiement ---
    elements.append(Paragraph("<b>Modalités de paiement</b>", style_b))
    elements.append(Spacer(1, 0.2 * cm))
    tranches = demande.get("tranches") or []
    if tranches:
        data_tr = [["Tranche", "Déclencheur", "%", "Montant"]]
        for i, t in enumerate(tranches):
            pct = t.get("pourcentage", 0)
            data_tr.append([f"Tranche {i + 1}", t.get("declencheur", ""), f"{pct}%", f"{montant_total * pct / 100:,.2f} {devise}"])
        tr_tbl = Table(data_tr, colWidths=[2.3 * cm, 8 * cm, 1.4 * cm, 5 * cm])
        tr_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5b8def")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ]))
        elements.append(tr_tbl)
    else:
        elements.append(Paragraph("—", style_n))
    elements.append(Spacer(1, 1.4 * cm))

    # --- Signature ---
    elements.append(Paragraph(
        "Date et signature de l'acheteur, précédée de la mention « Bon pour accord »", style_n
    ))
    elements.append(Spacer(1, 2 * cm))
    elements.append(Paragraph(
        f"Document généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')} suite à la validation "
        f"finale de la Direction Générale — Référence interne demande n°{demande['id']}.", styles["Italic"]
    ))

    doc.build(elements)
    return buffer.getvalue()

def generer_pdf_bon_reception(demande: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = getSampleStyleSheet()
    style_n = styles["Normal"]
    style_b = ParagraphStyle("bloc_bold_r", parent=style_n, fontName="Helvetica-Bold")
    style_titre = ParagraphStyle("titre_br", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#2b3542"))

    numero_br = f"BR-{datetime.now().year}-{int(demande['id']):05d}"
    elements = []

    if os.path.exists(CHEMIN_LOGO):
        logo_cell = Image(CHEMIN_LOGO, width=3.2 * cm, height=3.2 * cm, kind="proportional")
    else:
        logo_cell = Paragraph("<b>NATIKA GROUP</b>", styles["Heading2"])
    bloc_titre = [
        Paragraph("BON DE RÉCEPTION", style_titre),
        Paragraph(f"<b>N° {numero_br}</b>", style_n),
        Paragraph(f"Clôturé le : {demande.get('date_cloture', '—')}", style_n),
    ]
    entete = Table([[logo_cell, bloc_titre]], colWidths=[4 * cm, 12.7 * cm])
    entete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    elements.append(entete)
    elements.append(Spacer(1, 0.9 * cm))

    elements.append(Paragraph(f"<b>Référence demande :</b> n°{demande['id']}", style_n))
    elements.append(Paragraph(f"<b>Département :</b> {demande.get('departement', '—')}", style_n))
    elements.append(Paragraph(f"<b>Intitulé :</b> {demande.get('titre', '—')}", style_n))
    elements.append(Paragraph(f"<b>Fournisseur :</b> {demande.get('fournisseur', '—')}", style_n))
    elements.append(Spacer(1, 0.6 * cm))

    elements.append(Paragraph("<b>Historique des réceptions déclarées</b>", style_b))
    elements.append(Spacer(1, 0.2 * cm))
    receptions = demande.get("receptions") or []
    if receptions:
        data_r = [["Date", "Conformité", "Motif", "Remarque"]]
        for r in receptions:
            data_r.append([r.get("date", ""), r.get("conformite", ""), r.get("motif", "") or "—", r.get("remarque", "") or "—"])
        r_tbl = Table(data_r, colWidths=[3 * cm, 3 * cm, 4 * cm, 6.7 * cm])
        r_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c9473")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(r_tbl)
    else:
        elements.append(Paragraph("—", style_n))
    elements.append(Spacer(1, 0.6 * cm))

    elements.append(Paragraph(f"<b>Statut final :</b> {demande.get('statut_final', '—')}", style_n))
    if demande.get("suivi_litige"):
        elements.append(Paragraph(f"<b>Suivi / commentaire Achats :</b> {demande.get('suivi_litige')}", style_n))
    elements.append(Spacer(1, 1.2 * cm))
    elements.append(Paragraph(
        f"Document généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — clôturé par les Achats, "
        f"trace interne de réception, n'engage pas le fournisseur.", styles["Italic"]
    ))

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
    if "validé" in s or "financé" in s or "approuvé" in s or "signé" in s:
        classe = "pill-valide"
    elif "refusé" in s:
        classe = "pill-refuse"
    elif "modification" in s:
        classe = "pill-modif"
    else:
        classe = "pill-attente"
    return f'<span class="{classe}">{statut}</span>'

def date_du_jour_fr() -> str:
    """Formate la date du jour en français, sans dépendre de la locale du serveur."""
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    maintenant = datetime.now()
    return f"{jours[maintenant.weekday()]} {maintenant.day} {mois[maintenant.month - 1]} {maintenant.year}"

def est_recent(date_str, heures=48):
    """Renvoie True si la date (format '%Y-%m-%d %H:%M') a moins de `heures` heures."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return (datetime.now() - d).total_seconds() < heures * 3600
    except (ValueError, TypeError):
        return False

def compter_nouveaux_elements(nom_dept, type_profil):
    """Compte, à partir des données déjà existantes (pas de table séparée),
    les éléments récents ou nécessitant une action pour le profil connecté."""
    total = 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT destinataires_partage, date FROM etudes_metier WHERE archive = 0")
        for dests_json, d in cursor.fetchall():
            dests = json.loads(dests_json) if dests_json else []
            if (nom_dept in dests or type_profil == "fondateur") and est_recent(d):
                total += 1

        cursor.execute("SELECT date FROM cahiers_charges WHERE archive = 0")
        for (d,) in cursor.fetchall():
            if est_recent(d):
                total += 1

        if type_profil in ["achats", "finance", "fondateur"]:
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = ? AND statut LIKE 'En attente%' AND archive = 0", (nom_dept,))
            total += cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM demandes WHERE departement = ? AND statut = 'Modif demandée' AND archive = 0", (nom_dept,))
            total += cursor.fetchone()[0]

        conn.close()
    except sqlite3.OperationalError:
        pass
    return total

def parser_tranches(modalites_json) -> list:
    try:
        return json.loads(modalites_json) if modalites_json else []
    except (json.JSONDecodeError, TypeError):
        return []

def parser_receptions(receptions_json) -> list:
    return parser_tranches(receptions_json)

def formater_modalites_paiement(modalites_json: str) -> str:
    try:
        tranches = json.loads(modalites_json) if modalites_json else []
    except (json.JSONDecodeError, TypeError):
        return "—"
    if not tranches:
        return "—"
    return " | ".join([f"{t.get('pourcentage', 0)}% — {t.get('declencheur', '')}" for t in tranches])

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
    conn = sqlite3.connect("database.db", check_same_thread=False, timeout=15)
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
        fichier_cdc TEXT DEFAULT '',
        archive INTEGER DEFAULT 0
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
    conn = sqlite3.connect("database.db", check_same_thread=False, timeout=15)
    cursor = conn.cursor()
    migrations = [
        ("etudes_metier", "vus_json", "TEXT DEFAULT '[]'"),
        ("cahiers_charges", "vus_par_json", "TEXT DEFAULT '[]'"),
        ("demandes", "fournisseur_retenu", "TEXT DEFAULT ''"),
        ("demandes", "archive", "INTEGER DEFAULT 0"),
        ("etudes_metier", "archive", "INTEGER DEFAULT 0"),
        ("cahiers_charges", "archive", "INTEGER DEFAULT 0"),
        ("cahiers_charges", "fichier_cdc", "TEXT DEFAULT ''"),
        # --- Bon de commande, paiement par tranches, budget engagé/décaissé ---
        ("demandes", "devise", "TEXT DEFAULT 'EUR'"),
        ("demandes", "modalites_paiement_json", "TEXT DEFAULT '[]'"),
        ("demandes", "statut_paiement", "TEXT DEFAULT 'Non payée'"),
        ("demandes", "bon_commande_genere", "INTEGER DEFAULT 0"),
        ("demandes", "bon_commande_date", "TEXT DEFAULT ''"),
        ("demandes", "montant_engage", "REAL DEFAULT 0"),
        # --- Circuit de réception / clôture ---
        ("demandes", "receptions_json", "TEXT DEFAULT '[]'"),
        ("demandes", "statut_reception", "TEXT DEFAULT ''"),
        ("demandes", "suivi_litige", "TEXT DEFAULT ''"),
        # --- Seuil d'approbation simplifiée & annulations/avoirs ---
        ("demandes", "annulee", "INTEGER DEFAULT 0"),
        ("demandes", "motif_annulation", "TEXT DEFAULT ''"),
        ("demandes", "avoir_json", "TEXT DEFAULT ''"),
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
    conn = sqlite3.connect("database.db", check_same_thread=False, timeout=15)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    return conn

@st.cache_data(ttl=60)
def get_valeur_globale_cached(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_store WHERE key = ?", (key,))
    val = cursor.fetchone()
    conn.close()
    return float(val[0]) if val else 0.0

def get_valeur_globale(key):
    return get_valeur_globale_cached(key)

def set_valeur_globale(key, val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO global_store (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()
    st.cache_data.clear()

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

# Constantes réutilisées pour cibler les notifications par département
DEPT_ACHATS = UTILISATEURS["DEP12"]["dept"]
DEPT_FINANCE = UTILISATEURS["DEP13"]["dept"]
DEPT_DIRECTION = UTILISATEURS["fondateur"]["dept"]

# ==========================================
# GESTION DE LA SESSION
# ==========================================

if 'user_connecte' not in st.session_state:
    st.session_state.user_connecte = None
if 'tab_actif' not in st.session_state:
    st.session_state.tab_actif = "1. Études & Ingénierie"

afficher_notification_centre()

# ==========================================
# AUTHENTIFICATION & BARRE LATÉRALE
# ==========================================

if st.session_state.user_connecte is None:
    # Écran de connexion : sidebar masquée, carte centrée sur fond dégradé
    st.markdown("""
    <style>
      [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f6f5f1 0%, #eae7e0 100%);
      }
      [data-testid="stSidebar"] { display: none; }
      [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff;
        border-radius: 18px;
        box-shadow: 0 14px 40px rgba(0,0,0,0.14);
        border: none;
        padding: 0.5rem;
      }
      div.stButton > button {
        background-color: #7c9473;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 0;
      }
      div.stButton > button:hover {
        background-color: #6a8062;
        color: white;
        border: none;
      }
      [data-testid="stTextInput"] label {
        color: #2b2b28 !important;
        font-weight: 600;
      }
      [data-testid="stTextInput"] input {
        background-color: #f4f3ef !important;
        color: #1a1a1a !important;
        border: 1px solid #d8d5cc !important;
        border-radius: 6px !important;
      }
      [data-testid="stTextInput"] input::placeholder {
        color: #8b887f !important;
      }
      [data-testid="stTextInputRootElement"] {
        background-color: #f4f3ef !important;
        border: 1px solid #d8d5cc !important;
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 9vh;'></div>", unsafe_allow_html=True)
    col_g, col_c, col_d = st.columns([1, 1.2, 1])
    with col_c:
        with st.container(border=True):
            if os.path.exists(CHEMIN_LOGO):
                lg1, lg2, lg3 = st.columns([1, 1.4, 1])
                with lg2:
                    st.image(CHEMIN_LOGO, use_container_width=True)
            else:
                st.markdown("<h2 style='text-align:center;'>🏢 Bureau d'Études</h2>", unsafe_allow_html=True)
            st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
            username = st.text_input("Identifiant")
            password = st.text_input("Mot de passe", type="password")
            if st.button("Se connecter", use_container_width=True):
                if username in UTILISATEURS and UTILISATEURS[username]["mdp"] == password:
                    st.session_state.user_connecte = username
                    st.session_state.heure_connexion = datetime.now()
                    ajouter_log("Connexion", UTILISATEURS[username]["nom"], "Connexion réussie")
                    notifier_succes("Connexion établie avec succès !", icon="✅")
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
    st.stop()

# Écran connecté : logo + infos dans la sidebar normale
if os.path.exists(CHEMIN_LOGO):
    st.sidebar.image(CHEMIN_LOGO, use_container_width=True)
else:
    st.sidebar.markdown("## 🏢 Bureau d'Études")
st.sidebar.markdown("---")

user_key = st.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

st.sidebar.success(f"Connecté : {profil['nom']}")
st.sidebar.markdown(
    f"<div style='display:inline-flex; align-items:center; gap:6px; background-color:rgba(124,148,115,0.18); "
    f"color:#cfe0c8; padding:4px 10px; border-radius:14px; font-size:0.82rem; margin-bottom:6px;'>"
    f"📅 {date_du_jour_fr()}</div>",
    unsafe_allow_html=True
)
st.sidebar.markdown("---")

if st.sidebar.button("Se déconnecter"):
    duree = ""
    if "heure_connexion" in st.session_state:
        delta = datetime.now() - st.session_state.heure_connexion
        minutes = int(delta.total_seconds() // 60)
        duree = f"Durée de session : {minutes // 60}h{minutes % 60:02d}min"
    ajouter_log("Déconnexion", profil["nom"], duree or "Durée de session inconnue")
    st.session_state.user_connecte = None
    notifier_succes("Déconnexion effectuée.", icon="ℹ️")
    st.rerun()

st.title(f"Tableau de Bord - {profil['nom']}")

if profil["type"] in ["finance", "fondateur"]:
    b_total = get_valeur_globale("budget_global")
    b_engage = get_valeur_globale("budget_engage")
    b_decaisse = get_valeur_globale("budget_decaisse")
    b_solde = max(0.0, b_total - b_engage)
    c_b1, c_b2, c_b3 = st.columns(3)
    c_b1.metric("Budget Global Allocation", f"{b_total:,.2f} €")
    c_b2.metric("Budget Engagé", f"{b_engage:,.2f} €", help="Montant des demandes validées par la Direction, virement ou non encore effectué.")
    c_b3.metric("Solde Disponible", f"{b_solde:,.2f} €", help="Budget Global − Budget Engagé.")
    st.caption(f"💳 Budget décaissé (virements confirmés) : {b_decaisse:,.2f} €")
    st.markdown("---")

# ==========================================
# NAVIGATION ONGLETS PRINCIPAUX
# ==========================================

onglets_possibles = ["1. Études & Ingénierie", "2. Cahiers des Charges", "3. Besoins & Achats", "📖 Journal de Bord", "🔍 Recherche Globale"]
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
    t1, t2, t3, t4 = st.tabs(["1. Nouvelle Étude & Partage", "2. Études Reçues", "3. 📜 Historique & Gestion", "4. 🗄️ Archives des Études"])

    with t1:
        with st.form("form_nouvelle_etude", clear_on_submit=True):
            titre = st.text_input("Titre de l'étude / Note technique")
            desc = st.text_area("Description et paramètres")
            destinataires = st.multiselect("Partager cette étude avec d'autres départements", tous_depts)
            fichier = st.file_uploader("Pièce jointe (PDF, Excel, DWG, etc.)", type=["pdf", "xlsx", "docx", "dwg"])
            submitted = st.form_submit_button("Diffuser l'étude")

            if submitted:
                if not titre:
                    st.error("Le titre est obligatoire.")
                else:
                    nom_fichier = enregistrer_fichier_securise(DOSSIER_ETUDES, fichier)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        """INSERT INTO etudes_metier (departement, titre, donnees_json, fichier_etude, destinataires_partage, date, archive) 
                           VALUES (?, ?, ?, ?, ?, ?, 0)""",
                        (nom_departement, titre, desc, nom_fichier, json.dumps(destinataires), datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    notifier_succes("Étude enregistrée et partagée avec succès !", icon="✅")
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
                prefixe = "🆕 " if est_recent(r[6]) else ""
                with st.expander(f"{prefixe}📁 [{r[1]}] {r[2]} (Émise le {r[6]})"):
                    st.write(f"**Description & Paramètres :** {r[3]}")
                    proposer_telechargement(DOSSIER_ETUDES, r[4], "📥 Télécharger le document", f"dl_etude_recue_{r[0]}")

    with t3:
        st.markdown("### Vos études émises")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titre, donnees_json, fichier_etude, date, destinataires_partage FROM etudes_metier WHERE departement = ? AND archive = 0", (nom_departement,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            st.info("Vous n'avez publié aucune étude active.")
        else:
            for r in rows:
                eid, etitrans, edesc, efich, edate, edests = r
                with st.expander(f"📄 {etitrans} (le {edate})"):
                    st.write(f"**Description & Paramètres :** {edesc}")
                    st.write(f"**Partagé avec :** {', '.join(json.loads(edests)) if edests else 'Aucun'}")
                    proposer_telechargement(DOSSIER_ETUDES, efich, "📥 Télécharger le document associé", f"dl_etude_emise_{eid}")
                    
                    if st.button("🗄️ Archiver cette étude", key=f"btn_arch_etude_{eid}"):
                        conn_a = get_db_connection()
                        cur_a = conn_a.cursor()
                        cur_a.execute("UPDATE etudes_metier SET archive = 1 WHERE id = ?", (eid,))
                        conn_a.commit()
                        conn_a.close()
                        archiver_dans_corbeille(nom_departement, "Étude Métier", f"Étude : {etitrans}", {"id": eid, "titre": etitrans})
                        notifier_succes("Étude archivée avec succès.", icon="✅")
                        st.rerun()

    with t4:
        st.markdown("### 🗄️ Archives des Études")
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, date FROM etudes_metier WHERE archive = 1 ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, date FROM etudes_metier WHERE departement = ? AND archive = 1 ORDER BY id DESC", (nom_departement,))
        archives_etudes = cursor.fetchall()
        conn.close()

        if not archives_etudes:
            st.info("Aucune étude archivée.")
        else:
            for ae in archives_etudes:
                ae_id, ae_dept, ae_titre, ae_desc, ae_fich, ae_date = ae
                with st.expander(f"🗄️ [{ae_dept}] {ae_titre} (Archivée - Émise le {ae_date})"):
                    st.write(f"**Description :** {ae_desc}")
                    proposer_telechargement(DOSSIER_ETUDES, ae_fich, "📥 Télécharger l'étude archivée", f"dl_etude_arch_{ae_id}")


# ==========================================
# 2. MODULE CAHIERS DES CHARGES
# ==========================================

def afficher_module_cdc(nom_departement, type_profil):
    st.subheader("📋 Cahiers des Charges & Documents Partagés")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    with st.form("form_cdc", clear_on_submit=True):
        titre = st.text_input("Titre du Cahier des Charges")
        contenu = st.text_area("Contenu détaillé / Spécifications techniques")
        destinataires = st.multiselect("Demander un avis / partage aux départements", tous_depts)
        fichier_cdc = st.file_uploader("Pièce jointe du Cahier des Charges (PDF, Word, etc.)", type=["pdf", "docx", "xlsx"])
        submitted = st.form_submit_button("Publier le Cahier des Charges")
        
        if submitted:
            if not titre:
                st.error("Le titre est obligatoire.")
            else:
                nom_fich_cdc = enregistrer_fichier_securise(DOSSIER_CDC, fichier_cdc)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis, fichier_cdc, archive) 
                       VALUES (?, ?, ?, ?, ?, ?, 0)""",
                    (nom_departement, titre, contenu, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(destinataires), nom_fich_cdc)
                )
                conn.commit()
                conn.close()
                notifier_succes("Cahier des charges publié avec succès.", icon="✅")
                st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Cahiers des Charges disponibles")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis, fichier_cdc FROM cahiers_charges WHERE archive = 0")
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        cid, cdept, ctitre, ccont, cdate, cdests, cfich = r
        prefixe = "🆕 " if est_recent(cdate) else ""
        with st.expander(f"{prefixe}📋 {ctitre} ({cdept} - {cdate})"):
            st.write(ccont)
            proposer_telechargement(DOSSIER_CDC, cfich, "📥 Télécharger la pièce jointe du CDC", f"dl_cdc_{cid}")


# ==========================================
# 3. MODULE BESOINS & ACHATS (WORKFLOW ADAPTÉ 3 DÉPARTEMENTS PILOTES)
# ==========================================

def afficher_module_achats(nom_departement, type_profil):
    st.subheader("🛒 Espace Demandes d'Achat")
    
    # 4 onglets bien distincts comme demandé
    onglets_achats = ["📋 Soumettre une demande", "📊 Suivi des demandes", "📦 Suivi d'exécution", "🗄️ Archives des demandes"]
    tabs_res = st.tabs(onglets_achats)
    
    with tabs_res[0]:
        st.markdown("### ➕ Soumettre une nouvelle demande d'achat")
        
        if type_profil != "achats" and type_profil != "finance" and type_profil != "fondateur":
            with st.form("form_nouvelle_demande", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien du Cahier des Charges / Étude associée (optionnel)")
                fournisseur_presenti = st.text_input("Fournisseur pressenti (optionnel)")
                fichier_devis = st.file_uploader("Joindre un devis initial / document descriptif (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                soumettre = st.form_submit_button("Soumettre la demande")
                if soumettre:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé de la demande ainsi que les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", 0.0, fournisseur_presenti, "En attente Achats", "Achats", "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", "", 0)
                        )
                        conn.commit()
                        conn.close()
                        notifier_succes("Demande transmise aux Achats avec succès !")
                        st.rerun()

        elif type_profil == "achats":
            with st.form("form_nouvelle_demande_achats", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien associé (optionnel)")
                fournisseur_retenu_saisie = st.text_input("Fournisseur retenu")
                montant_defini = st.number_input("Prix définitif (€)", min_value=0.0, step=10.0)
                fichier_devis = st.file_uploader("Joindre le devis / document justificatif (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                
                soumettre_achats = st.form_submit_button("Soumettre la demande (Circuit direct Finance)")
                if soumettre_achats:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé et les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", montant_defini, fournisseur_retenu_saisie, "En attente Finance", "Finance", "Validé", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", fournisseur_retenu_saisie, "")
                        )
                        conn.commit()
                        conn.close()
                        notifier_succes("Demande transmise directement à la Finance avec succès !")
                        st.rerun()

        elif type_profil == "finance":
            with st.form("form_nouvelle_demande_finance", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien associé (optionnel)")
                fournisseur_presenti = st.text_input("Fournisseur pressenti (optionnel)")
                fichier_devis = st.file_uploader("Joindre un devis initial / document (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                
                soumettre_fin = st.form_submit_button("Soumettre la demande (Circuit Achats -> Direction)")
                if soumettre_fin:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé et les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", 0.0, fournisseur_presenti, "En attente Achats", "Achats", "En attente", "Validé", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", "", "")
                        )
                        conn.commit()
                        conn.close()
                        notifier_succes("Demande transmise aux Achats avec succès !", icon="✅")
                        st.rerun()

        elif type_profil == "fondateur":
            with st.form("form_nouvelle_demande_dir", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien associé (optionnel)")
                fournisseur_presenti = st.text_input("Fournisseur pressenti (optionnel)")
                fichier_devis = st.file_uploader("Joindre un devis initial / document (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                
                soumettre_dir_emis = st.form_submit_button("Soumettre la demande (Circuit complet Achats -> Finance -> Direction)")
                if soumettre_dir_emis:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé et les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", 0.0, fournisseur_presenti, "En attente Achats", "Achats", "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", "", "")
                        )
                        conn.commit()
                        conn.close()
                        notifier_succes("Demande transmise aux Achats avec succès !", icon="✅")
                        st.rerun()

    with tabs_res[1]:
        st.markdown("### Suivi de vos demandes & Validations en attente")
        
        # Interface de validation si le profil a des rôles spécifiques
        if type_profil == "achats":
            st.markdown("#### 🛒 Demandes en attente de traitement & Sourcing (Achats)")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 AND etape_actuelle = 'Achats' ORDER BY id DESC")
            demandes_achats = cursor.fetchall()
            conn.close()

            if demandes_achats:
                for d in demandes_achats:
                    did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                    with st.expander(f"🛒 [{d_dept}] {d_titre}"):
                        st.write(f"**Émetteur** : {d_dept} | **Date** : {d_date}")
                        st.write(f"**Besoins spécifiques & Cahier des charges** : {d_cc}")
                        st.write(f"**Fournisseur pressenti (émetteur)** : {d_fournisseur or 'Aucun'}")
                        proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis / document initial", f"dl_achats_{did}")
                        
                        with st.form(f"form_traitement_achats_{did}"):
                            fournisseur_retenu_saisie = st.text_input("Définir le fournisseur retenu (Sourcing)", value=d_f_retenu or d_fournisseur)
                            montant_definitif = st.number_input("Saisir le prix définitif négocié (€)", min_value=0.0, step=10.0, value=float(d_montant or 0.0))
                            nouveau_fichier_achat = st.file_uploader("Ajouter / Remplacer le devis achats consolidé (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"], key=f"f_achat_{did}")

                            st.markdown("**Modalités de paiement** (utilisées uniquement si la demande est validée)")
                            nb_tranches = st.selectbox("Nombre de tranches de paiement", [1, 2], key=f"nb_tranches_{did}")
                            declencheurs_possibles = ["Acompte à la signature (validation Direction)", "À l'envoi du bon de commande", "À la réception", "Date fixe / Autre"]
                            declencheur_1 = st.selectbox("Déclencheur — Tranche 1", declencheurs_possibles, key=f"decl1_{did}")
                            pourcentage_1 = st.number_input("% — Tranche 1", min_value=0, max_value=100, value=100 if nb_tranches == 1 else 50, key=f"pct1_{did}")
                            if nb_tranches == 2:
                                declencheur_2 = st.selectbox("Déclencheur — Tranche 2", declencheurs_possibles, index=2, key=f"decl2_{did}")
                                pourcentage_2 = st.number_input("% — Tranche 2", min_value=0, max_value=100, value=50, key=f"pct2_{did}")

                            action_achat = st.selectbox("Décision Achats", ["Valider", "Demander une modification", "Refuser définitivement"])
                            motif_achat = st.text_area("Commentaire / Motif (obligatoire en cas de modification ou refus)")
                            
                            valider_action = st.form_submit_button("Appliquer la décision Achats")
                            if valider_action:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                fich_u = enregistrer_fichier_securise(DOSSIER_UPLOADS, nouveau_fichier_achat) if nouveau_fichier_achat else d_fich
                                
                                if action_achat == "Valider":
                                    if d_dept == "Finance & Comptabilité":
                                        nouveau_statut = "En attente Direction"
                                        nouvelle_etape = "Direction Générale"
                                    else:
                                        nouveau_statut = "En attente Finance"
                                        nouvelle_etape = "Finance"
                                    avis_a = "Validé"
                                    motif_maj = ""
                                    tranches = [{"declencheur": declencheur_1, "pourcentage": pourcentage_1, "statut": "en_attente", "reference": "", "date_execution": "", "note": ""}]
                                    if nb_tranches == 2:
                                        tranches.append({"declencheur": declencheur_2, "pourcentage": pourcentage_2, "statut": "en_attente", "reference": "", "date_execution": "", "note": ""})
                                    modalites_json = json.dumps(tranches)
                                elif action_achat == "Demander une modification":
                                    nouveau_statut = "Modif demandée"
                                    nouvelle_etape = "Émetteur"
                                    avis_a = "Modification demandée"
                                    motif_maj = f"[Achats] {motif_achat}"
                                    modalites_json = None
                                else:
                                    nouveau_statut = "Refusé"
                                    nouvelle_etape = "Clôturé"
                                    avis_a = "Refusé"
                                    motif_maj = f"[Achats] {motif_achat}"
                                    modalites_json = None
                                    
                                if modalites_json is not None:
                                    cursor.execute(
                                        """UPDATE demandes SET fournisseur_retenu = ?, montant = ?, fichier_devis = ?, statut = ?, etape_actuelle = ?, avis_achats = ?, motif_refus = ?, modalites_paiement_json = ? WHERE id = ?""",
                                        (fournisseur_retenu_saisie, montant_definitif, fich_u, nouveau_statut, nouvelle_etape, avis_a, motif_maj, modalites_json, did)
                                    )
                                else:
                                    cursor.execute(
                                        """UPDATE demandes SET fournisseur_retenu = ?, montant = ?, fichier_devis = ?, statut = ?, etape_actuelle = ?, avis_achats = ?, motif_refus = ? WHERE id = ?""",
                                        (fournisseur_retenu_saisie, montant_definitif, fich_u, nouveau_statut, nouvelle_etape, avis_a, motif_maj, did)
                                    )
                                conn.commit()
                                conn.close()
                                notifier_succes("Décision enregistrée avec succès !", icon="✅")
                                st.rerun()

        elif type_profil == "finance":
            st.markdown("#### 💰 Demandes en attente d'analyse budgétaire (Finance)")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 AND etape_actuelle = 'Finance' ORDER BY id DESC")
            demandes_finance = cursor.fetchall()
            conn.close()

            if demandes_finance:
                for d in demandes_finance:
                    did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                    with st.expander(f"💰 [{d_dept}] {d_titre} — {float(d_montant or 0):,.2f} €"):
                        st.write(f"- **Émetteur** : {d_dept}")
                        st.write(f"- **Description** : {d_cc}")
                        st.write(f"- **Fournisseur retenu (Achats)** : {fournisseur_affiche(d_fournisseur, d_f_retenu)}")
                        st.write(f"- **Prix définitif** : {float(d_montant or 0):,.2f} €")
                        proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis", f"dl_fin_{did}")
                        
                        with st.form(f"form_traitement_finance_{did}"):
                            action_fin = st.selectbox("Décision Finance", ["Valider", "Demander une modification", "Refuser (problème budgétaire)"])
                            motif_fin = st.text_area("Commentaire / Motif financier")
                            
                            valider_fin = st.form_submit_button("Appliquer la décision financière")
                            if valider_fin:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_fin == "Valider":
                                    nouveau_statut = "En attente Direction"
                                    nouvelle_etape = "Direction Générale"
                                    avis_f = "Validé"
                                    motif_maj = ""
                                elif action_fin == "Demander une modification":
                                    nouveau_statut = "Modif demandée"
                                    nouvelle_etape = "Émetteur"
                                    avis_f = "Modification demandée"
                                    motif_maj = f"[Finance] {motif_fin}"
                                else:
                                    nouveau_statut = "Refusé"
                                    nouvelle_etape = "Clôturé"
                                    avis_f = "Refusé"
                                    motif_maj = f"[Finance] {motif_fin}"
                                    
                                cursor.execute(
                                    """UPDATE demandes SET statut = ?, etape_actuelle = ?, avis_finance = ?, motif_refus = ? WHERE id = ?""",
                                    (nouveau_statut, nouvelle_etape, avis_f, motif_maj, did)
                                )
                                conn.commit()
                                conn.close()
                                notifier_succes("Décision financière enregistrée !", icon="✅")
                                st.rerun()

            st.markdown("---")
            st.markdown("#### 💳 Virements à traiter")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, departement, titre, fournisseur_retenu, montant, devise, modalites_paiement_json, statut_paiement, statut_reception
                   FROM demandes WHERE archive = 0 AND etape_actuelle = 'Exécution' AND statut_paiement != 'Entièrement payée' ORDER BY id DESC"""
            )
            demandes_virements = cursor.fetchall()
            conn.close()

            if not demandes_virements:
                st.caption("Aucun virement en attente pour le moment.")
            else:
                for dv in demandes_virements:
                    dv_id, dv_dept, dv_titre, dv_fournisseur, dv_montant, dv_devise, dv_modalites_json, dv_statut_paie, dv_statut_reception = dv
                    try:
                        tranches = json.loads(dv_modalites_json) if dv_modalites_json else []
                    except (json.JSONDecodeError, TypeError):
                        tranches = []
                    with st.expander(f"💳 [{dv_dept}] {dv_titre} — {float(dv_montant or 0):,.2f} {dv_devise} — {dv_statut_paie}"):
                        st.write(f"**Fournisseur :** {dv_fournisseur or '—'}")
                        for i, tr in enumerate(tranches):
                            declencheur = tr.get("declencheur", "")
                            deja_payee = tr.get("statut") == "payee"
                            # Une tranche "À la réception" n'est déverrouillée qu'une fois la réception clôturée par les Achats
                            verrouillee = (declencheur == "À la réception" and dv_statut_reception != "Clôturée")
                            montant_tranche = float(dv_montant or 0) * float(tr.get("pourcentage", 0)) / 100

                            if deja_payee:
                                st.success(f"✅ Tranche {i+1} ({tr.get('pourcentage')}% — {declencheur}) payée le {tr.get('date_execution', '')} — Réf. {tr.get('reference', '')}")
                            elif verrouillee:
                                st.info(f"🔒 Tranche {i+1} ({tr.get('pourcentage')}% — {declencheur}) — pas encore déclenchée (en attente de la réception, module à venir).")
                            else:
                                st.markdown(f"**🔓 Tranche {i+1} prête à payer — {tr.get('pourcentage')}% — {declencheur} — {montant_tranche:,.2f} {dv_devise}**")
                                with st.form(f"form_virement_{dv_id}_{i}"):
                                    reference_vir = st.text_input("Référence du virement", key=f"ref_{dv_id}_{i}")
                                    date_vir = st.date_input("Date d'exécution", value=date.today(), key=f"date_{dv_id}_{i}")
                                    montant_vir = st.number_input("Montant réellement viré", min_value=0.0, value=montant_tranche, step=10.0, key=f"mont_{dv_id}_{i}")
                                    preuve_vir = st.file_uploader("Preuve du virement (capture d'écran, PDF)", type=["pdf", "png", "jpg", "jpeg"], key=f"preuve_{dv_id}_{i}")
                                    note_vir = st.text_area("Note / modalités (optionnel)", key=f"note_{dv_id}_{i}")
                                    confirmer_vir = st.form_submit_button("Confirmer ce virement")
                                    if confirmer_vir:
                                        fich_preuve = enregistrer_fichier_securise(DOSSIER_UPLOADS, preuve_vir) if preuve_vir else ""
                                        tranches[i]["statut"] = "payee"
                                        tranches[i]["reference"] = reference_vir
                                        tranches[i]["date_execution"] = date_vir.strftime("%Y-%m-%d")
                                        tranches[i]["montant_verse"] = montant_vir
                                        tranches[i]["preuve"] = fich_preuve
                                        tranches[i]["note"] = note_vir

                                        toutes_payees = all(t.get("statut") == "payee" for t in tranches)
                                        nouveau_statut_paiement = "Entièrement payée" if toutes_payees else "Partiellement payée"

                                        conn_v = get_db_connection()
                                        cur_v = conn_v.cursor()
                                        cur_v.execute(
                                            "UPDATE demandes SET modalites_paiement_json = ?, statut_paiement = ? WHERE id = ?",
                                            (json.dumps(tranches), nouveau_statut_paiement, dv_id)
                                        )
                                        conn_v.commit()
                                        conn_v.close()

                                        budget_decaisse_actuel = get_valeur_globale("budget_decaisse")
                                        set_valeur_globale("budget_decaisse", budget_decaisse_actuel + montant_vir)

                                        notifier_succes("Virement enregistré avec succès !", icon="✅")
                                        st.rerun()

        elif type_profil == "fondateur":
            st.markdown("#### ✍️ Demandes en attente de validation finale (Direction Générale)")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 AND etape_actuelle = 'Direction Générale' ORDER BY id DESC")
            demandes_dir = cursor.fetchall()
            conn.close()

            if demandes_dir:
                for d in demandes_dir:
                    did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                    with st.expander(f"✍️ [{d_dept}] {d_titre} — {float(d_montant or 0):,.2f} €"):
                        st.write(f"- **Émetteur** : {d_dept}")
                        st.write(f"- **Description** : {d_cc}")
                        st.write(f"- **Fournisseur retenu** : {fournisseur_affiche(d_fournisseur, d_f_retenu)}")
                        st.write(f"- **Montant** : {float(d_montant or 0):,.2f} €")
                        proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le dossier", f"dl_dir_{did}")
                        
                        with st.form(f"form_traitement_dir_{did}"):
                            action_dir = st.selectbox("Décision Direction Générale", ["Valider et signer (Exécution finale)", "Demander une modification", "Refuser définitivement"])
                            motif_dir = st.text_area("Commentaire / Motif de la Direction")
                            
                            valider_dir = st.form_submit_button("Appliquer la décision finale")
                            if valider_dir:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_dir == "Valider et signer (Exécution finale)":
                                    nouveau_statut = "Validé & Signé"
                                    nouvelle_etape = "Exécution"
                                    motif_maj = ""
                                    montant_dem = float(d_montant or 0)
                                    budget_engage_actuel = get_valeur_globale("budget_engage")
                                    set_valeur_globale("budget_engage", budget_engage_actuel + montant_dem)
                                    bc_genere = 1
                                    bc_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                                elif action_dir == "Demander une modification":
                                    nouveau_statut = "Modif demandée"
                                    nouvelle_etape = "Émetteur"
                                    motif_maj = f"[Direction] {motif_dir}"
                                    bc_genere = 0
                                    bc_date = ""
                                else:
                                    nouveau_statut = "Refusé"
                                    nouvelle_etape = "Clôturé"
                                    motif_maj = f"[Direction] {motif_dir}"
                                    bc_genere = 0
                                    bc_date = ""
                                    
                                cursor.execute(
                                    """UPDATE demandes SET statut = ?, etape_actuelle = ?, motif_refus = ?, bon_commande_genere = ?, bon_commande_date = ?, montant_engage = ? WHERE id = ?""",
                                    (nouveau_statut, nouvelle_etape, motif_maj, bc_genere, bc_date, float(d_montant or 0) if bc_genere else 0, did)
                                )
                                conn.commit()
                                conn.close()
                                notifier_succes("Décision finale enregistrée avec succès !", icon="✅")
                                st.rerun()

        # Affichage des demandes propres au département ou global pour le fondateur
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, bon_commande_genere, bon_commande_date, modalites_paiement_json, statut_paiement, devise, statut_reception, receptions_json, suivi_litige FROM demandes WHERE archive = 0 ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, bon_commande_genere, bon_commande_date, modalites_paiement_json, statut_paiement, devise, statut_reception, receptions_json, suivi_litige FROM demandes WHERE departement = ? AND archive = 0 ORDER BY id DESC", (nom_departement,))
        demandes = cursor.fetchall()
        conn.close()

        if not demandes:
            st.info("Aucune demande active en cours.")
        else:
            for d in demandes:
                did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu, d_bc_genere, d_bc_date, d_modalites, d_statut_paiement, d_devise, d_statut_reception, d_receptions_json, d_suivi_litige = d
                try:
                    montant_aff = float(d_montant) if d_montant is not None else 0.0
                except (ValueError, TypeError):
                    montant_aff = 0.0

                with st.container():
                    st.markdown(f"""
                        <div class="stCard">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div><b>[{d_dept}] {d_titre}</b> (Étape actuelle : <i>{d_etape}</i>)</div>
                                <div>{pill_statut(d_statut)}</div>
                            </div>
                            <div style="color: var(--text-muted); font-size: 0.9rem; margin-top: 5px;">
                                Montant validé : <b>{montant_aff:,.2f} €</b> | Date : {d_date}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    c_det, c_arch = st.columns([4, 1])
                    with c_det:
                        with st.expander("🔍 Voir les détails complets & historique"):
                            st.write(f"- **Besoins spécifiques** : {d_cc}")
                            st.write(f"- **Fournisseur** : {fournisseur_affiche(d_fournisseur, d_f_retenu)}")
                            st.write(f"- **Avis Achats** : {d_avis_a} | **Avis Finance** : {d_avis_f}")
                            if d_motif:
                                st.warning(f"Motif / Remarque : {d_motif}")
                            proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis", f"dl_devis_{did}")

                            if d_bc_genere:
                                st.markdown("---")
                                st.success(f"📄 Bon de commande généré le {d_bc_date}")
                                pdf_bc = generer_pdf_bon_commande({
                                    "id": did, "departement": d_dept, "titre": d_titre, "besoins": d_cc,
                                    "fournisseur": d_f_retenu or d_fournisseur, "montant": d_montant, "devise": d_devise,
                                    "date_validation": d_bc_date, "tranches": parser_tranches(d_modalites),
                                })
                                st.download_button(
                                    "📥 Télécharger le bon de commande (PDF)", data=pdf_bc,
                                    file_name=f"Bon_Commande_{did}.pdf", mime="application/pdf", key=f"dl_bc_{did}"
                                )
                                st.caption(f"💳 Statut paiement : {d_statut_paiement} — Modalités : {formater_modalites_paiement(d_modalites)}")

                            if d_statut_reception == "Clôturée":
                                st.markdown("---")
                                st.success("🚚 Réception clôturée")
                                pdf_br = generer_pdf_bon_reception({
                                    "id": did, "departement": d_dept, "titre": d_titre, "fournisseur": d_f_retenu or d_fournisseur,
                                    "receptions": parser_receptions(d_receptions_json), "statut_final": d_statut,
                                    "suivi_litige": d_suivi_litige, "date_cloture": d_date,
                                })
                                st.download_button(
                                    "📥 Télécharger le bon de réception (PDF)", data=pdf_br,
                                    file_name=f"Bon_Reception_{did}.pdf", mime="application/pdf", key=f"dl_br_{did}"
                                )

                            if d_statut == "Modif demandée" and d_dept == nom_departement:
                                st.markdown("---")
                                st.info("🔄 Cette demande nécessite une modification suite à un retour.")
                                with st.form(f"form_modif_demandeur_{did}"):
                                    nouveau_titre = st.text_input("Modifier l'intitulé", value=d_titre)
                                    nouveaux_besoins = st.text_area("Modifier les besoins spécifiques", value=d_cc)
                                    nouveau_fichier = st.file_uploader("Remplacer le document / devis", type=["pdf", "png", "jpg", "jpeg"], key=f"file_mod_{did}")
                                    resoumettre = st.form_submit_button("Modifier et resoumettre")
                                    if resoumettre:
                                        fich_final = enregistrer_fichier_securise(DOSSIER_UPLOADS, nouveau_fichier) if nouveau_fichier else d_fich
                                        if d_dept == "Achats & Approvisionnements":
                                            prochaine_etape = "Finance"
                                            nouveau_statut_res = "En attente Finance"
                                        else:
                                            prochaine_etape = "Achats"
                                            nouveau_statut_res = "En attente Achats"

                                        conn_m = get_db_connection()
                                        cur_m = conn_m.cursor()
                                        cur_m.execute(
                                            """UPDATE demandes SET titre = ?, cahier_charges = ?, statut = ?, etape_actuelle = ?, motif_refus = ?, fichier_devis = ? WHERE id = ?""",
                                            (nouveau_titre, nouveaux_besoins, nouveau_statut_res, prochaine_etape, "", fich_final, did)
                                        )
                                        conn_m.commit()
                                        conn_m.close()
                                        notifier_succes("Demande modifiée et transmise avec succès !", icon="✅")
                                        st.rerun()

                    with c_arch:
                        if st.button("🗄️ Archiver", key=f"btn_archiver_{did}", use_container_width=True):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE demandes SET archive = 1 WHERE id = ?", (did,))
                            conn.commit()
                            conn.close()
                            archiver_dans_corbeille(nom_departement, "Demande d'Achat", f"Demande : {d_titre}", {"id": did, "titre": d_titre, "montant": montant_aff})
                            notifier_succes("Demande archivée avec succès.", icon="✅")
                            st.rerun()

    with tabs_res[2]:
        st.markdown("### 📦 Suivi d'exécution — du bon de commande à la clôture")
        st.caption("Toute demande dont le bon de commande a été généré reste ici tant qu'elle n'est pas entièrement soldée (paiement complet + réception confirmée). Elle ne part en Archives qu'une fois totalement exécutée.")
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil in ["achats", "finance", "fondateur"]:
            cursor.execute(
                """SELECT id, departement, titre, cahier_charges, fournisseur_retenu, montant, devise, statut, bon_commande_date,
                          modalites_paiement_json, statut_paiement, statut_reception, receptions_json, suivi_litige
                   FROM demandes WHERE archive = 0 AND etape_actuelle = 'Exécution' ORDER BY id DESC"""
            )
        else:
            cursor.execute(
                """SELECT id, departement, titre, cahier_charges, fournisseur_retenu, montant, devise, statut, bon_commande_date,
                          modalites_paiement_json, statut_paiement, statut_reception, receptions_json, suivi_litige
                   FROM demandes WHERE archive = 0 AND etape_actuelle = 'Exécution' AND departement = ? ORDER BY id DESC""",
                (nom_departement,)
            )
        demandes_execution = cursor.fetchall()
        conn.close()

        if not demandes_execution:
            st.info("Aucune demande en cours d'exécution actuellement.")
        else:
            for de in demandes_execution:
                (de_id, de_dept, de_titre, de_besoins, de_fourn, de_montant, de_devise, de_statut, de_bc_date,
                 de_modalites, de_statut_paiement, de_statut_reception, de_receptions_json, de_suivi_litige) = de
                tranches = parser_tranches(de_modalites)
                nb_payees = sum(1 for t in tranches if t.get("statut") == "payee")
                nb_total = len(tranches) if tranches else 1
                receptions = parser_receptions(de_receptions_json)
                reception_affichee = de_statut_reception or "En attente de livraison"

                with st.container():
                    st.markdown(f"""
                        <div class="stCard">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div><b>[{de_dept}] {de_titre}</b> — Fournisseur : {de_fourn or '—'}</div>
                                <div>{pill_statut(de_statut)}</div>
                            </div>
                            <div style="color: var(--text-muted); font-size: 0.9rem; margin-top: 5px;">
                                📄 Bon de commande : {de_bc_date} | 💳 Paiement : {nb_payees}/{nb_total} tranche(s) — {de_statut_paiement} | 🚚 Réception : {reception_affichee}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    with st.expander("🔍 Voir le détail complet"):
                        pdf_bc_suivi = generer_pdf_bon_commande({
                            "id": de_id, "departement": de_dept, "titre": de_titre, "besoins": de_besoins,
                            "fournisseur": de_fourn, "montant": de_montant, "devise": de_devise,
                            "date_validation": de_bc_date, "tranches": tranches,
                        })
                        st.download_button("📥 Télécharger le bon de commande (PDF)", data=pdf_bc_suivi,
                                            file_name=f"Bon_Commande_{de_id}.pdf", mime="application/pdf", key=f"dl_bc_suivi_{de_id}")
                        for i, t in enumerate(tranches):
                            etat = "✅ Payée" if t.get("statut") == "payee" else "🔒 En attente"
                            st.write(f"- Tranche {i+1} ({t.get('pourcentage')}% — {t.get('declencheur')}) : {etat}")

                        st.markdown("---")
                        st.markdown("#### 🚚 Réception")

                        if receptions:
                            for r in receptions:
                                st.write(f"- **{r.get('date')}** — {r.get('conformite')}"
                                         + (f" ({r.get('motif')})" if r.get('motif') else "")
                                         + (f" — _{r.get('remarque')}_" if r.get('remarque') else ""))
                                proposer_telechargement(DOSSIER_UPLOADS, r.get("fichier", ""), "📎 Bon de livraison importé", f"dl_bl_{de_id}_{r.get('date','')}")
                        else:
                            st.caption("Aucun bon de livraison importé pour le moment.")

                        if de_suivi_litige:
                            st.info(f"📝 Suivi Achats : {de_suivi_litige}")

                        # --- ÉMETTEUR : importer le bon de livraison et déclarer la conformité ---
                        if de_dept == nom_departement and de_statut_reception in ("", "Rejetée — nouvelle livraison attendue"):
                            st.markdown("##### 📥 Réception de la commande")
                            with st.form(f"form_reception_{de_id}"):
                                conformite = st.selectbox("Conformité de la livraison reçue", ["Conforme", "Non conforme", "Partiel"], key=f"conf_{de_id}")
                                motif_nc = ""
                                if conformite != "Conforme":
                                    motif_nc = st.selectbox("Motif", ["Quantité incomplète", "Produit endommagé", "Mauvaise référence livrée", "Autre"], key=f"motifnc_{de_id}")
                                remarque_reception = st.text_area("Remarque (optionnel)", key=f"remarque_{de_id}")
                                fichier_bl = st.file_uploader("Bon de livraison (pièce jointe, scan/photo)", type=["pdf", "png", "jpg", "jpeg"], key=f"fichierbl_{de_id}")
                                valider_reception = st.form_submit_button("Confirmer la réception")
                                if valider_reception:
                                    fich_bl = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_bl) if fichier_bl else ""
                                    receptions.append({
                                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        "conformite": conformite, "motif": motif_nc,
                                        "remarque": remarque_reception, "fichier": fich_bl,
                                    })
                                    nouveau_statut_reception = "En attente de contrôle" if conformite == "Conforme" else "Réception contestée"
                                    conn_r = get_db_connection()
                                    cur_r = conn_r.cursor()
                                    cur_r.execute("UPDATE demandes SET receptions_json = ?, statut_reception = ? WHERE id = ?",
                                                  (json.dumps(receptions), nouveau_statut_reception, de_id))
                                    conn_r.commit()
                                    conn_r.close()
                                    notifier_succes("Réception confirmée et transmise aux Achats !", icon="✅")
                                    st.rerun()

                        # --- ACHATS : contrôle et clôture ---
                        if type_profil == "achats" and de_statut_reception in ("En attente de contrôle", "Réception contestée"):
                            st.markdown("##### ✅ Contrôle Achats")
                            if de_statut_reception == "En attente de contrôle":
                                if st.button("Contrôler et clôturer la demande", key=f"cloture_ok_{de_id}"):
                                    pdf_br = generer_pdf_bon_reception({
                                        "id": de_id, "departement": de_dept, "titre": de_titre, "fournisseur": de_fourn,
                                        "receptions": receptions, "statut_final": "Clôturée", "suivi_litige": de_suivi_litige,
                                        "date_cloture": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    })
                                    conn_c = get_db_connection()
                                    cur_c = conn_c.cursor()
                                    cur_c.execute("UPDATE demandes SET etape_actuelle = 'Clôturé', statut = 'Clôturée', statut_reception = 'Clôturée' WHERE id = ?", (de_id,))
                                    conn_c.commit()
                                    conn_c.close()
                                    notifier_succes("Demande contrôlée et clôturée !", icon="✅")
                                    st.rerun()
                            else:
                                st.warning("Réception contestée — traiter avec le fournisseur (canal externe) avant de trancher.")
                                with st.form(f"form_litige_{de_id}"):
                                    nouveau_suivi = st.text_area("Statut du traitement (visible par tous)", value=de_suivi_litige, key=f"suivi_{de_id}")
                                    maj_suivi = st.form_submit_button("Mettre à jour le suivi")
                                    if maj_suivi:
                                        conn_s = get_db_connection()
                                        cur_s = conn_s.cursor()
                                        cur_s.execute("UPDATE demandes SET suivi_litige = ? WHERE id = ?", (nouveau_suivi, de_id))
                                        conn_s.commit()
                                        conn_s.close()
                                        notifier_succes("Suivi mis à jour.", icon="✅")
                                        st.rerun()

                                c_cl, c_rj, c_esc = st.columns(3)
                                with c_cl:
                                    if st.button("Clôturer avec réserve", key=f"cloture_reserve_{de_id}", use_container_width=True):
                                        pdf_br = generer_pdf_bon_reception({
                                            "id": de_id, "departement": de_dept, "titre": de_titre, "fournisseur": de_fourn,
                                            "receptions": receptions, "statut_final": "Clôturée avec réserve", "suivi_litige": de_suivi_litige,
                                            "date_cloture": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        })
                                        conn_c = get_db_connection()
                                        cur_c = conn_c.cursor()
                                        cur_c.execute("UPDATE demandes SET etape_actuelle = 'Clôturé', statut = 'Clôturée avec réserve', statut_reception = 'Clôturée' WHERE id = ?", (de_id,))
                                        conn_c.commit()
                                        conn_c.close()
                                        notifier_succes("Demande clôturée avec réserve.", icon="✅")
                                        st.rerun()
                                with c_rj:
                                    if st.button("Rejeter (redemander livraison)", key=f"rejeter_{de_id}", use_container_width=True):
                                        conn_c = get_db_connection()
                                        cur_c = conn_c.cursor()
                                        cur_c.execute("UPDATE demandes SET statut_reception = ? WHERE id = ?", ("Rejetée — nouvelle livraison attendue", de_id))
                                        conn_c.commit()
                                        conn_c.close()
                                        notifier_succes("Livraison rejetée, en attente d'une nouvelle réception.", icon="✅")
                                        st.rerun()
                                with c_esc:
                                    if st.button("Escalader à la Direction", key=f"escalade_{de_id}", use_container_width=True):
                                        conn_c = get_db_connection()
                                        cur_c = conn_c.cursor()
                                        cur_c.execute("UPDATE demandes SET statut_reception = ? WHERE id = ?", ("Escaladée à la Direction", de_id))
                                        conn_c.commit()
                                        conn_c.close()
                                        notifier_succes("Litige escaladé à la Direction.", icon="✅")
                                        st.rerun()

                        # --- DIRECTION : trancher un litige escaladé ---
                        if type_profil == "fondateur" and de_statut_reception == "Escaladée à la Direction":
                            st.markdown("##### ⚖️ Litige escaladé — décision Direction")
                            with st.form(f"form_direction_litige_{de_id}"):
                                note_direction = st.text_area("Décision / instruction de la Direction", key=f"notedir_{de_id}")
                                trancher = st.form_submit_button("Renvoyer aux Achats avec instruction")
                                if trancher:
                                    suivi_maj = (de_suivi_litige + "\n" if de_suivi_litige else "") + f"[Direction] {note_direction}"
                                    conn_d = get_db_connection()
                                    cur_d = conn_d.cursor()
                                    cur_d.execute("UPDATE demandes SET suivi_litige = ?, statut_reception = 'Réception contestée' WHERE id = ?", (suivi_maj, de_id))
                                    conn_d.commit()
                                    conn_d.close()
                                    notifier_succes("Instruction transmise aux Achats.", icon="✅")
                                    st.rerun()

    with tabs_res[3]:
        st.markdown("### 🗄️ Archives des demandes d'achat")
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
# 4. JOURNAL DE BORD QUOTIDIEN
# ==========================================

def afficher_module_journal_bord(nom_departement):
    st.subheader(f"📖 Journal de Bord Quotidien & Cahier de Notes — {nom_departement}")
    with st.form("form_journal", clear_on_submit=True):
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
            notifier_succes("Note ajoutée au journal.", icon="✅")
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
# 5. MODULE SUIVI GLOBAL POUR PÔLE DE CONTRÔLE
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

    st.caption("💡 Cliquez sur une ligne pour voir le détail complet de la demande.")
    evenement = st.dataframe(
        df_suivi,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    lignes_selectionnees = evenement.selection.rows if evenement and evenement.selection else []
    if lignes_selectionnees:
        id_demande_selectionnee = int(df_suivi.iloc[lignes_selectionnees[0]]["ID"])
        afficher_dialogue_detail_demande(id_demande_selectionnee)

    afficher_boutons_export(df_suivi, "Suivi_Global_Controle", "Supervision Globale")


@st.dialog("Détail de la demande")
def afficher_dialogue_detail_demande(id_demande):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT departement, titre, cahier_charges, montant, fournisseur, fournisseur_retenu,
                  statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date,
                  bon_commande_genere, bon_commande_date, modalites_paiement_json, statut_paiement, devise
           FROM demandes WHERE id = ?""",
        (id_demande,)
    )
    d = cursor.fetchone()
    conn.close()

    if not d:
        st.warning("Cette demande n'existe plus (elle a peut-être été archivée ou supprimée).")
        return

    (dept, titre, besoins, montant, fournisseur_pressenti, fournisseur_retenu,
     statut, etape, avis_achats, avis_finance, motif, date_demande,
     bc_genere, bc_date, modalites_json, statut_paiement, devise) = d

    st.markdown(f"### #{id_demande} — {titre}")
    st.markdown(f"**Département demandeur :** {dept}")
    st.markdown(f"**Date de la demande :** {date_demande}")
    st.markdown(f"**Statut :** {pill_statut(statut)}", unsafe_allow_html=True)
    st.markdown(f"**Étape actuelle :** {etape}")
    st.markdown("---")
    st.markdown("**Besoins spécifiques :**")
    st.write(besoins or "—")
    st.markdown(f"**Montant :** {montant:,.2f} {devise}" if montant else "**Montant :** —")
    st.markdown(f"**Fournisseur pressenti :** {fournisseur_pressenti or '—'}")
    if fournisseur_retenu:
        st.markdown(f"**Fournisseur retenu :** {fournisseur_retenu}")
    if avis_achats and avis_achats != "En attente":
        st.markdown(f"**Avis Achats :** {avis_achats}")
    if avis_finance and avis_finance != "En attente":
        st.markdown(f"**Avis Finance :** {avis_finance}")
    if motif:
        st.markdown(f"**Motif (refus / modification demandée) :** {motif}")

    if bc_genere:
        st.markdown("---")
        st.markdown(f"**📄 Bon de commande** généré le {bc_date}")
        st.markdown(f"**💳 Statut paiement :** {statut_paiement} — {formater_modalites_paiement(modalites_json)}")
        pdf_bc = generer_pdf_bon_commande({
            "id": id_demande, "departement": dept, "titre": titre, "besoins": besoins,
            "fournisseur": fournisseur_retenu or fournisseur_pressenti, "montant": montant, "devise": devise,
            "date_validation": bc_date, "tranches": parser_tranches(modalites_json),
        })
        st.download_button("📥 Télécharger le bon de commande (PDF)", data=pdf_bc,
                            file_name=f"Bon_Commande_{id_demande}.pdf", mime="application/pdf", key=f"dl_bc_dialog_{id_demande}")


# ==========================================
# 6. MODULE CORBEILLE & HISTORIQUE
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
# 7. MODULE AUDIT & TRAÇABILITÉ (AVEC BOUTON DE REMISE À ZÉRO RÉSERVÉ AU FONDATEUR)
# ==========================================

def afficher_module_audit():
    st.subheader("🕵️ Pointage — Connexions & Durées de Présence")
    
    if profil["type"] == "fondateur":
        with st.container(border=True):
            st.markdown("### ⚠️ Zone de Réinitialisation Globale (Crash-Test)")
            st.markdown("Ce bouton permet de remettre l'ensemble des données de l'application à zéro (demandes, études, cahiers des charges, journaux, corbeille, logs) et de réinitialiser le budget global.")
            
            confirmation_reset = st.checkbox("Je confirme vouloir tout effacer et réinitialiser l'application")
            if st.button("🗑️ Réinitialiser toutes les données (Remise à zéro)", type="primary"):
                if confirmation_reset:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM demandes")
                    cursor.execute("DELETE FROM etudes_metier")
                    cursor.execute("DELETE FROM cahiers_charges")
                    cursor.execute("DELETE FROM journal_bord")
                    cursor.execute("DELETE FROM corbeille_archives")
                    cursor.execute("DELETE FROM logs_audit")
                    conn.commit()
                    conn.close()
                    set_valeur_globale("budget_global", 100000.0)
                    set_valeur_globale("budget_engage", 0.0)
                    set_valeur_globale("budget_decaisse", 0.0)
                    notifier_succes("Application réinitialisée à zéro avec succès !", icon="✅")
                    st.rerun()
                else:
                    st.warning("Veuillez cocher la case de confirmation pour exécuter la réinitialisation.")
        st.markdown("---")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, acteur, action, details FROM logs_audit ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.info("Aucun journal d'audit disponible.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtre_acteur = st.text_input("Filtrer par acteur / utilisateur")
        with col_f2:
            filtre_action = st.selectbox("Filtrer par type d'action", ["Tous", "Connexion", "Déconnexion", "Validation", "Création", "Réinitialisation"])

        logs_filtres = []
        for r in rows:
            _, r_date, r_acteur, r_action, r_details = r
            if filtre_acteur and filtre_acteur.lower() not in r_acteur.lower():
                continue
            if filtre_action != "Tous" and filtre_action.lower() not in r_action.lower():
                continue
            logs_filtres.append(r)

        if not logs_filtres:
            st.warning("Aucun journal ne correspond aux filtres sélectionnés.")
        else:
            for r in logs_filtres:
                r_id, r_date, r_acteur, r_action, r_details = r
                badge_color = "var(--accent)"
                if "connexion" in r_action.lower():
                    badge_color = "var(--success)"
                elif "déconnexion" in r_action.lower():
                    badge_color = "var(--danger)"
                elif "validation" in r_action.lower():
                    badge_color = "var(--warning)"
                elif "réinitialisation" in r_action.lower():
                    badge_color = "var(--danger)"

                st.markdown(f"""
                    <div class="stCard" style="border-left: 4px solid {badge_color};">
                        <div style="display: flex; justify-content: space-between; font-weight: bold;">
                            <span>👤 {r_acteur}</span>
                            <span style="color: var(--text-muted); font-size: 0.85rem;">🕒 {r_date}</span>
                        </div>
                        <div style="margin-top: 6px;">
                            <span style="background-color: {badge_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">{r_action}</span>
                            <span style="margin-left: 8px; font-size: 0.95rem;">{r_details}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        df_audit = pd.DataFrame(rows, columns=["ID", "Date", "Acteur", "Action", "Détails"])
        afficher_boutons_export(df_audit, "Logs_Audit", "Journal d'Audit", "audit_exp")


# ==========================================
# 8. MODULE RECHERCHE GLOBALE
# ==========================================

def afficher_module_recherche_globale(nom_departement, type_profil):
    st.subheader("🔍 Recherche Globale")
    terme = st.text_input("Mot-clé à rechercher dans les études, demandes, statuts ou départements")
    if terme:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT titre, departement, 'Étude' FROM etudes_metier WHERE titre LIKE ? OR donnees_json LIKE ? OR departement LIKE ?", (f"%{terme}%", f"%{terme}%", f"%{terme}%"))
        res_etudes = cursor.fetchall()
        cursor.execute("SELECT titre, departement, 'Demande Achat' FROM demandes WHERE titre LIKE ? OR cahier_charges LIKE ? OR statut LIKE ? OR departement LIKE ?", (f"%{terme}%", f"%{terme}%", f"%{terme}%", f"%{terme}%"))
        res_demandes = cursor.fetchall()
        conn.close()

        tous_res = res_etudes + res_demandes
        if not tous_res:
            st.warning("Aucun résultat trouvé.")
        else:
            for r in tous_res:
                st.write(f"- **[{r[2]}]** {r[0]} *(Émis par {r[1]})*")


# ==========================================
# 9. MODULE STATISTIQUES
# ==========================================

def afficher_module_statistiques():
    st.subheader("📈 Statistiques par Département")
    conn = get_db_connection()
    df_dem = pd.read_sql_query("SELECT departement, montant FROM demandes", conn)
    conn.close()

    if df_dem.empty:
        st.info("Pas assez de données pour afficher les statistiques.")
    else:
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
