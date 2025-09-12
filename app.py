"""
PIXID Invoice Corrector - Application Streamlit
Corrige les factures XML lors des semaines à cheval sur deux mois
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import io
import json

from core.parser import XMLParser
from core.detector import InconsistencyDetector
from core.calculator import AmountCalculator
from core.fixer import InvoiceFixer
from core.validator import InvoiceValidator

# Configuration de la page
st.set_page_config(
    page_title="PIXID Invoice Corrector",
    page_icon="📄",
    layout="wide"
)

def main():
    st.title("🔧 PIXID Invoice Corrector")
    st.markdown("Correction automatique des factures XML lors des semaines à cheval sur deux mois")
    
    # Upload du fichier
    uploaded_file = st.file_uploader(
        "Choisissez un fichier XML PIXID",
        type=['xml'],
        help="Fichier de facture au format HR-XML SIDES"
    )
    
    if uploaded_file is not None:
        # Lecture du fichier
        xml_content = uploaded_file.read()
        
        try:
            # Parsing du XML
            parser = XMLParser(xml_content)
            invoice_data = parser.parse()
            
            # Détection des incohérences
            detector = InconsistencyDetector(invoice_data)
            issues = detector.detect()
            
            # Affichage de l'analyse
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Période détectée (RAF)", 
                         f"{invoice_data['period_start']} → {invoice_data['period_end']}")
                st.metric("Heures RAF", f"{invoice_data['raf_hours']:.2f}h")
            
            with col2:
                st.metric("Heures facturées", f"{invoice_data['invoice_hours']:.2f}h")
                st.metric("Montant HT facturé", f"{invoice_data['total_charges']:.2f} €")
            
            with col3:
                if issues['has_inconsistency']:
                    st.error("⚠️ Incohérence détectée")
                    st.caption(issues['message'])
                else:
                    st.success("✅ Facture cohérente")
            
            # Si incohérence détectée, proposer la correction
            if issues['has_inconsistency']:
                st.markdown("---")
                st.subheader("🔄 Correction proposée")
                
                # Calcul des ajustements
                calculator = AmountCalculator(invoice_data)
                adjustments = calculator.calculate_adjustments()
                
                # Affichage du tableau comparatif
                df_comparison = create_comparison_table(invoice_data, adjustments)
                st.dataframe(df_comparison, use_container_width=True)
                
                # Bouton de correction
                if st.button("🚀 Appliquer la correction", type="primary"):
                    with st.spinner("Correction en cours..."):
                        # Application des corrections
                        fixer = InvoiceFixer(parser.tree, adjustments)
                        fixed_tree = fixer.fix()
                        
                        # Validation
                        validator = InvoiceValidator(fixed_tree)
                        validation_result = validator.validate()
                        
                        if validation_result['is_valid']:
                            st.success("✅ Correction appliquée avec succès!")
                            
                            # Affichage des résultats de validation
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("RAF = Lignes", 
                                         "✅" if validation_result['raf_equals_lines'] else "❌")
                            with col2:
                                st.metric("Lignes = Total HT", 
                                         "✅" if validation_result['lines_equal_total'] else "❌")
                            with col3:
                                st.metric("TVA correcte", 
                                         "✅" if validation_result['tax_correct'] else "❌")
                            
                            # Génération du XML corrigé
                            fixed_xml = fixer.to_string()
                            
                            # Bouton de téléchargement
                            st.download_button(
                                label="📥 Télécharger le XML corrigé",
                                data=fixed_xml,
                                file_name=f"corrected_{uploaded_file.name}",
                                mime="text/xml"
                            )
                            
                            # Rapport de correction
                            report = generate_report(invoice_data, adjustments, validation_result)
                            st.download_button(
                                label="📊 Télécharger le rapport (JSON)",
                                data=json.dumps(report, indent=2, ensure_ascii=False),
                                file_name=f"report_{uploaded_file.name.replace('.xml', '.json')}",
                                mime="application/json"
                            )
                        else:
                            st.error(f"❌ Erreur de validation: {validation_result['error']}")
            
            # Affichage des détails techniques
            with st.expander("🔍 Détails techniques"):
                st.json({
                    "Invoice ID": invoice_data.get('invoice_id'),
                    "TimeCards Position": invoice_data.get('timecards_position'),
                    "VAT Rate": f"{invoice_data.get('vat_rate', 20)}%",
                    "Namespaces": invoice_data.get('namespaces', {})
                })
                
        except Exception as e:
            st.error(f"❌ Erreur lors du traitement: {str(e)}")
            st.exception(e)

def create_comparison_table(invoice_data, adjustments):
    """Crée un tableau comparatif avant/après correction"""
    data = []
    
    for line_type, values in adjustments['lines'].items():
        data.append({
            'Description': line_type,
            'Quantité avant': values.get('old_quantity', 0),
            'Quantité après': values.get('new_quantity', 0),
            'Montant avant (€)': values.get('old_amount', 0),
            'Montant après (€)': values.get('new_amount', 0),
            'Action': values.get('action', 'Ajuster')
        })
    
    # Ajout des totaux
    data.append({
        'Description': '**TOTAL HT**',
        'Quantité avant': '',
        'Quantité après': '',
        'Montant avant (€)': invoice_data['total_charges'],
        'Montant après (€)': adjustments['new_total_charges'],
        'Action': ''
    })
    
    return pd.DataFrame(data)

def generate_report(invoice_data, adjustments, validation_result):
    """Génère un rapport de correction au format JSON"""
    return {
        'timestamp': datetime.now().isoformat(),
        'invoice_id': invoice_data.get('invoice_id'),
        'original': {
            'period': f"{invoice_data['period_start']} → {invoice_data['period_end']}",
            'hours': invoice_data['invoice_hours'],
            'total_ht': invoice_data['total_charges'],
            'total_ttc': invoice_data['total_amount']
        },
        'corrected': {
            'period': f"{adjustments['target_period_start']} → {adjustments['target_period_end']}",
            'hours': adjustments['target_hours'],
            'total_ht': adjustments['new_total_charges'],
            'total_ttc': adjustments['new_total_amount']
        },
        'validation': validation_result,
        'adjustments': adjustments
    }

if __name__ == "__main__":
    main()
