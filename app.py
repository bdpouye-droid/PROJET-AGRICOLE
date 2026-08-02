import streamlit as st
import datetime
import json

# ==========================================
# 1. INITIALISATION DE LA SESSION (DATABASE)
# ==========================================
st.set_page_config(page_title="ERP Enterprise & Direction", layout="wide", page_icon="🏢")

if "user_role" not in st.session_state:
    st.session_state.user_role = "Fondateur"  # Choix: Fondateur, Finance, Achats, Ingénierie, Employé

if "demandes_achat" not in st.session_state:
    st.session_state.demandes_achat = [
        {"id": 1, "article": "Câbles HR 50m", "montant": 1200, "demandeur": "Équipe Ingénierie", "statut": "En attente", "etape_actuelle": "finance"},
        {"id": 2, "article": "Serveur NAS 32TB", "montant": 4500, "demandeur": "Service IT", "statut": "Approuvée Finance", "etape_actuelle": "direction"}
    ]

if "solde_entreprise" not in st.session_state:
    st.session_state.solde_entreprise = 50000.0

if "canaux_chat" not in st.session_state:
    st.session_state.canaux_chat = {
        "Général": [
            {"id_msg": 1, "auteur": "Direction", "texte": "Bienvenue sur le chat d'entreprise !", "heure": "09:00"},
            {"id_msg": 2, "auteur": "Finance", "texte": "Les bilans du T2 sont prêts.", "heure": "09:15"}
        ],
        "Projet A": [
            {"id_msg": 1, "auteur": "Ingénierie", "texte": "Cahier des charges mis à jour.", "heure": "10:00"}
        ]
    }

if "etudes_ingenierie" not in st.session_state:
    st.session_state.etudes_ingenierie = [
        {"id": 1, "titre": "Étude d'impact réseau 2026", "auteur": "Ingénierie", "date": "2026-07-20"}
    ]

if "journal_de_bord" not in st.session_state:
    st.session_state.journal_de_bord = [
        {"id": 1, "auteur": "Chef de projet", "note": "Réception du matériel sur site.", "date": "2026-08-01"}
    ]

if "corbeille_direction" not in st.session_state:
    st.session_state.corbeille_direction = []


# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================
def archiver_dans_corbeille(type_element, nom_auteur, contenu_dict):
    st.session_state.corbeille_direction.append({
        "type": type_element,
        "auteur_suppression": st.session_state.user_role,
        "auteur_original": nom_auteur,
        "date_suppression": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "donnees": contenu_dict
    })

# ==========================================
# BARRE LATÉRALE - RÔLES & NAVIGATION
# ==========================================
st.sidebar.title("🏢 ERP Enterprise")
st.session_state.user_role = st.sidebar.selectbox(
    "Changer de rôle (Simulation)",
    ["Fondateur", "Finance", "Achats", "Ingénierie", "Employé"]
)

st.sidebar.markdown(f"**Rôle actif :** `{st.session_state.user_role}`")
st.sidebar.markdown(f"**Solde Actuel :** `{st.session_state.solde_entreprise:,.2f} €`")

menu = [
    "🛒 Besoins & Achats", 
    "💳 Validation Finance & Direction", 
    "💬 Messagerie & Chat", 
    "📐 Études & Ingénierie", 
    "📖 Journal de Bord"
]

if st.session_state.user_role == "Fondateur":
    menu.append("🗑️ Corbeille & Historique (Direction)")

choix_menu = st.sidebar.radio("Navigation", menu)

# ==========================================
# MODULE 1 : BESOINS & ACHATS (ANNULATION SEULEMENT)
# ==========================================
if choix_menu == "🛒 Besoins & Achats":
    st.title("🛒 Besoins & Demandes d'Achats")
    st.info("💡 **Règle :** Les demandes d'achats ne peuvent pas être supprimées définitivement pour des raisons d'audit. Elles peuvent uniquement être **annulées**.")
    
    with st.expander("➕ Formuler une nouvelle demande d'achat"):
        with st.form("form_achat"):
            article = st.text_input("Désignation de l'article / besoin")
            montant = st.number_input("Montant estimé (€)", min_value=1.0, value=100.0)
            submitted = st.form_submit_button("Soumettre la demande")
            if submitted and article:
                nouvel_id = max([d["id"] for d in st.session_state.demandes_achat], default=0) + 1
                st.session_state.demandes_achat.append({
                    "id": nouvel_id,
                    "article": article,
                    "montant": montant,
                    "demandeur": st.session_state.user_role,
                    "statut": "En attente Validation Finance",
                    "etape_actuelle": "finance"
                })
                st.success("Demande d'achat enregistrée et transmise à la Finance !")
                st.rerun()

    st.subheader("📋 Liste des demandes d'achat")
    for da in st.session_state.demandes_achat:
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
        col1.write(f"**#{da['id']}**")
        col2.write(f"**{da['article']}** ({da['montant']} €)")
        col3.write(f"Par: {da['demandeur']}")
        
        # Affichage Badge Statut
        if da['statut'] == "Annulée":
            col4.error("🚫 Annulée")
        elif da['statut'] == "Payée & Décaissement Effectué":
            col4.success("✅ Payée")
        else:
            col4.warning(da['statut'])

        # Action d'annulation (Pas de suppression)
        if da['statut'] not in ["Annulée", "Payée & Décaissement Effectué"]:
            if col5.button("🚫 Annuler la demande", key=f"cancel_da_{da['id']}"):
                da['statut'] = "Annulée"
                da['etape_actuelle'] = "annulee"
                st.toast(f"La demande #{da['id']} a été annulée avec succès.")
                st.rerun()

# ==========================================
# MODULE 2 : VALIDATION FINANCE & DIRECTION
# ==========================================
elif choix_menu == "💳 Validation Finance & Direction":
    st.title("💳 Workflow Validation & Decaissement")
    
    st.subheader("1️⃣ Étape Finance (Vérification du budget)")
    demandes_finance = [d for d in st.session_state.demandes_achat if d["etape_actuelle"] == "finance" and d["statut"] != "Annulée"]
    
    if not demandes_finance:
        st.caption("Aucune demande en attente de validation Finance.")
    else:
        for da in demandes_finance:
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.write(f"**{da['article']}** ({da['montant']} €) - Demandeur: {da['demandeur']}")
            
            if st.session_state.user_role in ["Finance", "Fondateur"]:
                if c2.button("✅ Approuver & Transmettre Direction", key=f"fin_app_{da['id']}"):
                    da['statut'] = "Approuvée par Finance (En attente Direction)"
                    da['etape_actuelle'] = "direction"
                    st.success("Transmis à la Direction Générale !")
                    st.rerun()
                if c3.button("❌ Rejeter", key=f"fin_rej_{da['id']}"):
                    da['statut'] = "Rejetée par Finance"
                    da['etape_actuelle'] = "rejetee"
                    st.rerun()

    st.divider()
    st.subheader("2️⃣ Étape Direction Générale (Décaissement Final)")
    demandes_dir = [d for d in st.session_state.demandes_achat if d["etape_actuelle"] == "direction" and d["statut"] != "Annulée"]
    
    if not demandes_dir:
        st.caption("Aucune demande en attente de validation de la Direction.")
    else:
        for da in demandes_dir:
            c1, c2, c3 = st.columns([4, 3, 3])
            c1.write(f"**{da['article']}** ({da['montant']} €) - Demandeur: {da['demandeur']}")
            
            if st.session_state.user_role == "Fondateur":
                if c2.button("💰 Valider le Décaissement Final", key=f"dir_pay_{da['id']}"):
                    if st.session_state.solde_entreprise >= da['montant']:
                        st.session_state.solde_entreprise -= da['montant']
                        da['statut'] = "Payée & Décaissement Effectué"
                        da['etape_actuelle'] = "terminee"
                        st.balloons()
                        st.success(f"Décaissement de {da['montant']} € effectué !")
                        st.rerun()
                    else:
                        st.error("Solde insuffisant pour procéder au décaissement.")
                if c3.button("❌ Refuser Décaissement", key=f"dir_ref_{da['id']}"):
                    da['statut'] = "Refusée par la Direction"
                    da['etape_actuelle'] = "rejetee"
                    st.rerun()
            else:
                c2.info("En attente d'approbation par le Fondateur.")

# ==========================================
# MODULE 3 : MESSAGERIE & CHAT (SUPPRESSION MESSAGE & CANAL)
# ==========================================
elif choix_menu == "💬 Messagerie & Chat":
    st.title("💬 Messagerie & Canaux de Discussion")
    
    col_canal, col_chat = st.columns([1, 3])
    
    with col_canal:
        st.subheader("📢 Canaux")
        canal_selectionne = st.radio("Sélectionner un canal", list(st.session_state.canaux_chat.keys()))
        
        st.divider()
        with st.expander("➕ Créer un canal"):
            nouveau_canal = st.text_input("Nom du canal")
            if st.button("Créer") and nouveau_canal:
                if nouveau_canal not in st.session_state.canaux_chat:
                    st.session_state.canaux_chat[nouveau_canal] = []
                    st.rerun()
        
        # Option de suppression de Canal
        st.divider()
        if st.button(f"🗑️ Supprimer le canal '{canal_selectionne}'", type="secondary"):
            if len(st.session_state.canaux_chat) > 1:
                discussion_supprimee = st.session_state.canaux_chat.pop(canal_selectionne)
                archiver_dans_corbeille(
                    type_element="Canal de Discussion",
                    nom_auteur="N/A",
                    contenu_dict={"canal": canal_selectionne, "messages": discussion_supprimee}
                )
                st.toast(f"Le canal '{canal_selectionne}' et son historique ont été supprimés.")
                st.rerun()
            else:
                st.error("Impossible de supprimer le dernier canal actif.")

    with col_chat:
        st.subheader(f"💬 Conversation : #{canal_selectionne}")
        
        # Zone des messages
        messages = st.session_state.canaux_chat[canal_selectionne]
        for idx, msg in enumerate(messages):
            c_msg, c_del = st.columns([6, 1])
            c_msg.markdown(f"**{msg['auteur']}** *({msg['heure']})* : {msg['texte']}")
            
            # Bouton de suppression de message individuel
            if c_del.button("🗑️", key=f"del_msg_{canal_selectionne}_{idx}"):
                msg_supprime = messages.pop(idx)
                archiver_dans_corbeille(
                    type_element="Message Chat",
                    nom_auteur=msg_supprime["auteur"],
                    contenu_dict={"canal": canal_selectionne, "message": msg_supprime}
                )
                st.rerun()
        
        # Envoi de message
        st.divider()
        with st.form("form_chat_msg", clear_on_submit=True):
            nouveau_texte = st.text_input("Écrire un message...")
            if st.form_submit_button("Envoyer") and nouveau_texte:
                messages.append({
                    "id_msg": len(messages) + 1,
                    "auteur": st.session_state.user_role,
                    "texte": nouveau_texte,
                    "heure": datetime.datetime.now().strftime("%H:%M")
                })
                st.rerun()

# ==========================================
# MODULE 4 : ÉTUDES & INGÉNIERIE
# ==========================================
elif choix_menu == "📐 Études & Ingénierie":
    st.title("📐 Études & Ingénierie")
    
    with st.expander("➕ Publier une nouvelle étude"):
        titre_etude = st.text_input("Titre du document/étude")
        if st.button("Publier") and titre_etude:
            nouv_etude = {
                "id": len(st.session_state.etudes_ingenierie) + 1,
                "titre": titre_etude,
                "auteur": st.session_state.user_role,
                "date": str(datetime.date.today())
            }
            st.session_state.etudes_ingenierie.append(nouv_etude)
            st.rerun()

    st.subheader("📚 Documents & Etudes partagées")
    for idx, etude in enumerate(st.session_state.etudes_ingenierie):
        c1, c2, c3 = st.columns([5, 2, 1])
        c1.write(f"📄 **{etude['titre']}** (Auteur: {etude['auteur']} | Date: {etude['date']})")
        if c3.button("🗑️", key=f"del_etude_{etude['id']}"):
            item = st.session_state.etudes_ingenierie.pop(idx)
            archiver_dans_corbeille("Étude & Ingénierie", item["auteur"], item)
            st.rerun()

# ==========================================
# MODULE 5 : JOURNAL DE BORD
# ==========================================
elif choix_menu == "📖 Journal de Bord":
    st.title("📖 Journal de Bord de l'Entreprise")
    
    with st.form("form_journal", clear_on_submit=True):
        note_texte = st.text_area("Ajouter une note au journal de bord")
        if st.form_submit_button("Enregistrer Note") and note_texte:
            st.session_state.journal_de_bord.append({
                "id": len(st.session_state.journal_de_bord) + 1,
                "auteur": st.session_state.user_role,
                "note": note_texte,
                "date": str(datetime.date.today())
            })
            st.rerun()

    st.subheader("📜 Historique des Notes")
    for idx, j in enumerate(st.session_state.journal_de_bord):
        c1, c2 = st.columns([6, 1])
        c1.info(f"**{j['auteur']}** ({j['date']}) : {j['note']}")
        if c2.button("🗑️", key=f"del_j_{j['id']}"):
            item = st.session_state.journal_de_bord.pop(idx)
            archiver_dans_corbeille("Journal de Bord", item["auteur"], item)
            st.rerun()

# ==========================================
# MODULE 6 : CORBEILLE DE LA DIRECTION (EXCLUSIF FONDATEUR)
# ==========================================
elif choix_menu == "🗑️ Corbeille & Historique (Direction)":
    st.title("🗑️ Corbeille Centralisée & Audit des Suppressions")
    st.warning("🔒 **Espace Réservé à la Direction Générale** : Cet onglet conserve la traçabilité complète de tout élément supprimé par les utilisateurs.")
    
    if st.button("🔥 Vider définitivement la corbeille"):
        st.session_state.corbeille_direction.clear()
        st.success("La corbeille a été vidée.")
        st.rerun()
        
    st.divider()
    
    if not st.session_state.corbeille_direction:
        st.info("La corbeille est actuellement vide.")
    else:
        for idx, item in enumerate(reversed(st.session_state.corbeille_direction)):
            with st.expander(f"🗑️ [{item['type']}] Supprimé le {item['date_suppression']} par {item['auteur_suppression']}"):
                st.write(f"**Auteur d'origine :** {item['auteur_original']}")
                st.json(item["donnees"])
