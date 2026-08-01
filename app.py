import streamlit as st
import pandas as pd
from datetime import datetime

def main():
    st.set_page_config(
        page_title="Gestion des Demandes d'Achat",
        page_icon="📦",
        layout="wide"
    )

    st.title("📦 Application de Gestion des Demandes d'Achat")
    st.markdown("### Workflow Multi-département (Bureau d'Études / Achats / Finance / Direction)")

    # Initialisation de la base de données simulée dans st.session_state
    if "requests" not in st.session_state:
        st.session_state.requests = [
            {
                "id": 1,
                "title": "Renouvellement licences CAO / DAO",
                "department": "Bureau d'Études",
                "supplier": "Autodesk / Revendeur agréé",
                "amount": 2500.0,
                "status": "En attente Achats",
                "comment": "Renouvellement annuel indispensable pour l'équipe technique.",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            },
            {
                "id": 2,
                "title": "Achat postes de travail workstation",
                "department": "Bureau d'Études",
                "supplier": "À sourcer",
                "amount": 0.0,
                "status": "En attente Achats",
                "comment": "Besoin de 2 stations de travail hautes performances pour les nouveaux ingénieurs.",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ]

    # Sidebar pour la sélection des rôles et la vue globale
    st.sidebar.header("Navigation & Rôles")
    role = st.sidebar.selectbox(
        "Sélectionner le profil actif",
        [
            "Tableau de Bord Global",
            "Demandeur (Bureau d'Études)",
            "Service Achats (DEP11)",
            "Finance & Comptabilité (DEP12)",
            "Direction Générale"
        ]
    )

    st.sidebar.markdown("---")
    st.sidebar.info(f"**Profil Actuel :** {role}")

    # -------------------------------------------------------------------------
    # VUE 0 : TABLEAU DE BORD GLOBAL (Suivi complet pour administration/audit)
    # -------------------------------------------------------------------------
    if role == "Tableau de Bord Global":
        st.header("📊 Tableau de Bord Global des Demandes d'Achats")
        
        if not st.session_state.requests:
            st.info("Aucune demande enregistrée dans le système.")
        else:
            df = pd.DataFrame(st.session_state.requests)
            st.dataframe(df, use_container_width=True)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Demandes", len(df))
            col2.metric("En attente Achats", len(df[df["status"] == "En attente Achats"]))
            col3.metric("En attente Finance", len(df[df["status"] == "En attente Finance"]))
            col4.metric("Approuvées", len(df[df["status"] == "Approuvé et Signé"]))

    # -------------------------------------------------------------------------
    # VUE 1 : EXPRESSION DU BESOIN (Demandeur / Bureau d'Études)
    # -------------------------------------------------------------------------
    elif role == "Demandeur (Bureau d'Études)":
        st.header("1. Expression du Besoin - Bureau d'Études")
        
        tab_create, tab_track = st.tabs(["Nouvelle Demande", "Mes Demandes & Suivi"])
        
        with tab_create:
            with st.form("form_new_request", clear_on_submit=True):
                title = st.text_input("Intitulé de la demande *")
                department = st.selectbox("Département émetteur", ["Bureau d'Études", "R&D", "Projets", "Technique"])
                supplier = st.text_input("Fournisseur pressenti (Laisser 'À sourcer' si inconnu)", value="À sourcer")
                comment = st.text_area("Spécifications techniques / Justificatif détaillé *")
                uploaded_file = st.file_uploader("Joindre un devis ou fichier externe (PDF, PNG, JPG)", type=["pdf", "png", "jpg"])
                
                submitted = st.form_submit_button("Soumettre la demande")
                
                if submitted:
                    if not title or not comment:
                        st.error("Veuillez remplir l'intitulé et les spécifications techniques.")
                    else:
                        new_id = max([r["id"] for r in st.session_state.requests], default=0) + 1
                        st.session_state.requests.append({
                            "id": new_id,
                            "title": title,
                            "department": department,
                            "supplier": supplier,
                            "amount": 0.0,
                            "status": "En attente Achats",
                            "comment": comment,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        st.success(f"Demande #{new_id} soumise avec succès ! Statut initial : En attente Achats.")
                        st.rerun()

        with tab_track:
            st.subheader("Suivi de l'état d'avancement")
            for req in st.session_state.requests:
                with st.expander(f"Demande #{req['id']} : {req['title']} [{req['status']}]"):
                    st.write(f"**Département :** {req['department']}")
                    st.write(f"**Fournisseur :** {req['supplier']}")
                    st.write(f"**Montant estimé/chiffré :** {req['amount']} €")
                    st.write(f"**Spécifications :** {req['comment']}")
                    st.write(f"**Date de création :** {req['date']}")
                    
                    if req["status"] == "Modifications demandées":
                        st.warning("⚠️ Le service Achats demande des modifications sur cette demande.")
                        with st.form(f"edit_form_{req['id']}"):
                            updated_title = st.text_input("Modifier l'intitulé", value=req["title"])
                            updated_comment = st.text_input("Modifier les spécifications", value=req["comment"])
                            if st.form_submit_button("Renvoyer aux Achats"):
                                req["title"] = updated_title
                                req["comment"] = updated_comment
                                req["status"] = "En attente Achats"
                                st.success("Demande modifiée et renvoyée aux Achats !")
                                st.rerun()

    # -------------------------------------------------------------------------
    # VUE 2 : SOURCING, CHIFFRAGE & ANALYSE (Service Achats - DEP11)
    # -------------------------------------------------------------------------
    elif role == "Service Achats (DEP11)":
        st.header("2. Sourcing, Chiffrage & Analyse - Service Achats")
        
        pending_achats = [r for r in st.session_state.requests if r["status"] in ["En attente Achats", "Modifications demandées"]]
        
        if not pending_achats:
            st.info("Aucune demande en attente pour le service Achats.")
        else:
            for req in pending_achats:
                with st.expander(f"Demande #{req['id']} - {req['title']} ({req['department']})"):
                    st.write(f"**Demandeur / Spécifications :** {req['comment']}")
                    st.write(f"**Date :** {req['date']}")
                    
                    with st.form(f"achats_form_{req['id']}"):
                        new_supplier = st.text_input("Confirmer ou modifier le fournisseur", value=req["supplier"])
                        amount = st.number_input("Saisir le montant exact (€)", min_value=0.0, value=float(req["amount"]), step=10.0)
                        
                        col1, col2, col3 = st.columns(3)
                        val_btn = col1.form_submit_button("Valider & Transmettre Finance")
                        mod_btn = col2.form_submit_button("Demander modification")
                        ref_btn = col3.form_submit_button("Refus définitif")
                        
                        if val_btn:
                            req["supplier"] = new_supplier
                            req["amount"] = amount
                            req["status"] = "En attente Finance"
                            st.success("Demande validée et transmise au service Finance.")
                            st.rerun()
                        elif mod_btn:
                            req["status"] = "Modifications demandées"
                            st.warning("Demande renvoyée au demandeur pour modification.")
                            st.rerun()
                        elif ref_btn:
                            req["status"] = "Refusé (Bloqué)"
                            st.error("Demande clôturée (refus définitif).")
                            st.rerun()

    # -------------------------------------------------------------------------
    # VUE 3 : CONTRÔLE BUDGÉTAIRE (Finance & Comptabilité - DEP12)
    # -------------------------------------------------------------------------
    elif role == "Finance & Comptabilité (DEP12)":
        st.header("3. Contrôle Budgétaire - Finance & Comptabilité")
        
        pending_fin = [r for r in st.session_state.requests if r["status"] == "En attente Finance"]
        
        if not pending_fin:
            st.info("Aucune demande en attente de contrôle budgétaire.")
        else:
            for req in pending_fin:
                with st.expander(f"Demande #{req['id']} - {req['title']} | Montant : {req['amount']} €"):
                    st.write(f"**Département :** {req['department']}")
                    st.write(f"**Fournisseur validé :** {req['supplier']}")
                    st.write(f"**Spécifications :** {req['comment']}")
                    
                    col1, col2 = st.columns(2)
                    if col1.button("Valider le budget & Transmettre DG", key=f"fin_val_{req['id']}"):
                        req["status"] = "En attente Signature DG"
                        st.success("Contrôle budgétaire validé. Transmis à la Direction Générale.")
                        st.rerun()
                    if col2.button("Refuser (Budget insuffisant)", key=f"fin_ref_{req['id']}"):
                        req["status"] = "Refusé (Bloqué)"
                        st.error("Demande refusée par la finance.")
                        st.rerun()

    # -------------------------------------------------------------------------
    # VUE 4 : SIGNATURE EXÉCUTIVE (Direction Générale)
    # -------------------------------------------------------------------------
    elif role == "Direction Générale":
        st.header("4. Signature Exécutive - Direction Générale")
        
        pending_dg = [r for r in st.session_state.requests if r["status"] == "En attente Signature DG"]
        
        if not pending_dg:
            st.info("Aucune demande en attente de signature exécutive.")
        else:
            for req in pending_dg:
                with st.expander(f"Demande #{req['id']} - {req['title']} | Montant : {req['amount']} €"):
                    st.write(f"**Département :** {req['department']}")
                    st.write(f"**Fournisseur :** {req['supplier']}")
                    st.write(f"**Spécifications :** {req['comment']}")
                    
                    col1, col2 = st.columns(2)
                    if col1.button("Approuver et Signer", key=f"dg_sign_{req['id']}"):
                        req["status"] = "Approuvé et Signé"
                        st.success("La demande a été officiellement approuvée et signée !")
                        st.rerun()
                    if col2.button("Refuser la demande", key=f"dg_ref_{req['id']}"):
                        req["status"] = "Refusé (Bloqué)"
                        st.warning("Demande rejetée par la Direction Générale.")
                        st.rerun()

if __name__ == "__main__":
    main()
