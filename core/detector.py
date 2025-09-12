"""
Module de détection des incohérences dans les factures PIXID
Identifie les semaines à cheval et les écarts RAF/Facture
"""

from datetime import datetime, timedelta
from dateutil import parser as date_parser

class InconsistencyDetector:
    def __init__(self, invoice_data):
        """
        Initialise le détecteur avec les données de facture
        
        Args:
            invoice_data: Dictionnaire des données parsées
        """
        self.data = invoice_data
        
    def detect(self):
        """
        Détecte les incohérences dans la facture
        
        Returns:
            dict: Résultat de la détection avec détails
        """
        result = {
            'has_inconsistency': False,
            'type': None,
            'message': None,
            'details': {}
        }
        
        # Vérification 1: Écart entre heures RAF et heures facturées
        if self._check_hours_mismatch():
            result['has_inconsistency'] = True
            result['type'] = 'hours_mismatch'
            result['message'] = f"Écart détecté: RAF {self.data['raf_hours']:.2f}h vs Facture {self.data['invoice_hours']:.2f}h"
            result['details']['raf_hours'] = self.data['raf_hours']
            result['details']['invoice_hours'] = self.data['invoice_hours']
        
        # Vérification 2: Semaine à cheval sur deux mois
        week_overlap = self._check_week_overlap()
        if week_overlap['is_overlapping']:
            result['has_inconsistency'] = True
            result['type'] = 'week_overlap'
            result['message'] = f"Semaine à cheval détectée: {week_overlap['week_start']} → {week_overlap['week_end']}"
            result['details'].update(week_overlap)
        
        # Vérification 3: Écart entre montants RAF et facture
        amount_mismatch = self._check_amount_mismatch()
        if amount_mismatch['has_mismatch']:
            result['has_inconsistency'] = True
            if result['type']:
                result['type'] = 'multiple'
            else:
                result['type'] = 'amount_mismatch'
            result['message'] = f"Écart montants: RAF estimé {amount_mismatch['raf_amount']:.2f}€ vs Facture {amount_mismatch['invoice_amount']:.2f}€"
            result['details'].update(amount_mismatch)
        
        # Vérification 4: Incohérence période déclarée vs RAF
        period_issue = self._check_period_consistency()
        if period_issue['is_inconsistent']:
            result['has_inconsistency'] = True
            result['details']['period_issue'] = period_issue['message']
        
        return result
    
    def _check_hours_mismatch(self):
        """Vérifie s'il y a un écart entre heures RAF et heures facturées"""
        raf_hours = self.data.get('raf_hours', 0)
        invoice_hours = self.data.get('invoice_hours', 0)
        
        # Tolérance de 0.01h pour les arrondis
        if abs(raf_hours - invoice_hours) > 0.01:
            return True
        return False
    
    def _check_week_overlap(self):
        """Détecte si la période chevauche deux mois"""
        result = {
            'is_overlapping': False,
            'week_start': None,
            'week_end': None,
            'month_start': None,
            'month_end': None
        }
        
        # Parse les dates de période
        try:
            if self.data.get('period_start') and self.data.get('period_end'):
                start_date = date_parser.parse(self.data['period_start']).date()
                end_date = date_parser.parse(self.data['period_end']).date()
                
                # Trouve le début et fin de semaine
                week_start = self._find_week_start(start_date)
                week_end = week_start + timedelta(days=6)
                
                result['week_start'] = week_start.isoformat()
                result['week_end'] = week_end.isoformat()
                
                # Vérifie si la semaine chevauche deux mois
                if week_start.month != week_end.month:
                    result['is_overlapping'] = True
                    result['month_start'] = week_start.month
                    result['month_end'] = week_end.month
                    
                    # Détermine quelle partie de la semaine est facturée
                    if start_date == end_date:
                        # Un seul jour facturé
                        result['invoiced_period'] = 'single_day'
