"""
Module de validation des factures PIXID
Vérifie que tous les invariants sont respectés après correction
"""

from lxml import etree
from decimal import Decimal, ROUND_HALF_UP
from dateutil import parser as date_parser

class InvoiceValidator:
    def __init__(self, tree):
        """
        Initialise le validateur avec l'arbre XML
        
        Args:
            tree: Arbre XML lxml à valider
        """
        self.tree = tree
        self.namespaces = self._extract_namespaces()
        self.tolerance = Decimal('0.01')  # Tolérance de 1 centime
        
    def _extract_namespaces(self):
        """Extrait les namespaces du document"""
        ns_map = {}
        for prefix, namespace in self.tree.nsmap.items():
            if prefix:
                ns_map[prefix] = namespace
            else:
                ns_map['default'] = namespace
        return ns_map
    
    def validate(self):
        """
        Effectue toutes les validations nécessaires
        
        Returns:
            dict: Résultat de la validation avec détails
        """
        result = {
            'is_valid': True,
            'raf_equals_lines': False,
            'lines_equal_total': False,
            'tax_correct': False,
            'mandatory_fields': False,
            'period_consistent': False,
            'errors': [],
            'warnings': []
        }
        
        # Validation 1: RAF = Somme des lignes
        raf_validation = self._validate_raf_equals_lines()
        result['raf_equals_lines'] = raf_validation['is_valid']
        if not raf_validation['is_valid']:
            result['is_valid'] = False
            result['errors'].append(raf_validation['error'])
        
        # Validation 2: Somme des lignes = TotalCharges
        lines_validation = self._validate_lines_equal_total()
        result['lines_equal_total'] = lines_validation['is_valid']
        if not lines_validation['is_valid']:
            result['is_valid'] = False
            result['errors'].append(lines_validation['error'])
        
        # Validation 3: TVA et TTC corrects
        tax_validation = self._validate_tax_amounts()
        result['tax_correct'] = tax_validation['is_valid']
        if not tax_validation['is_valid']:
            result['is_valid'] = False
            result['errors'].append(tax_validation['error'])
        
        # Validation 4: Champs obligatoires présents
        fields_validation = self._validate_mandatory_fields()
        result['mandatory_fields'] = fields_validation['is_valid']
        if not fields_validation['is_valid']:
            result['is_valid'] = False
            result['errors'].append(fields_validation['error'])
        
        # Validation 5: Cohérence des périodes
        period_validation = self._validate_period_consistency()
        result['period_consistent'] = period_validation['is_valid']
        if not period_validation['is_valid']:
            result['warnings'].append(period_validation['warning'])
        
        # Message d'erreur consolidé
        if not result['is_valid'] and result['errors']:
            result['error'] = '; '.join(result['errors'])
        
        return result
    
    def _validate_raf_equals_lines(self):
        """Vérifie que RAF = Somme des lignes"""
        result = {'is_valid': False, 'error': None}
        
        # Calculer le total RAF
        raf_total = Decimal('0')
        timecards = self.tree.findall('.//TimeCard', self.namespaces)
        if not timecards:
            timecards = self.tree.findall('.//*[local-name()="TimeCard"]')
        
        for timecard in timecards:
            intervals = timecard.findall('.//TimeInterval', self.namespaces)
            if not intervals:
                intervals = timecard.findall('.//*[local-name()="TimeInterval"]')
            
            for interval in intervals:
                # Pour simplifier, on estime le montant basé sur le type
                # Dans un cas réel, il faudrait mapper avec les tarifs exacts
                interval_type = interval.get('type', '')
                
                # Extraction de la valeur
                duration = interval.find('.//Duration', self.namespaces)
                if duration is None:
                    duration = interval.find('.//*[local-name()="Duration"]')
                
                quantity = interval.find('.//Quantity', self.namespaces)
                if quantity is None:
                    quantity = interval.find('.//*[local-name()="Quantity"]')
                
                # Estimation simplifiée du montant
                # Dans la vraie vie, il faudrait le tarif exact
                if
