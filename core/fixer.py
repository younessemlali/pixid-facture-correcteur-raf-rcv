"""
Module de correction des factures PIXID
Applique les ajustements calculés au document XML
"""

from lxml import etree
from decimal import Decimal, ROUND_HALF_UP
from copy import deepcopy
from dateutil import parser as date_parser

class InvoiceFixer:
    def __init__(self, tree, adjustments):
        """
        Initialise le correcteur avec l'arbre XML et les ajustements
        
        Args:
            tree: Arbre XML lxml
            adjustments: Dictionnaire des ajustements à appliquer
        """
        self.tree = deepcopy(tree)  # Copie pour ne pas modifier l'original
        self.adjustments = adjustments
        self.namespaces = self._extract_namespaces()
        
    def _extract_namespaces(self):
        """Extrait les namespaces du document"""
        ns_map = {}
        for prefix, namespace in self.tree.nsmap.items():
            if prefix:
                ns_map[prefix] = namespace
            else:
                ns_map['default'] = namespace
        return ns_map
    
    def fix(self):
        """
        Applique toutes les corrections au document
        
        Returns:
            lxml.etree: Arbre XML corrigé
        """
        # 1. Corriger les TimeCards (filtrer les intervalles hors période)
        self._fix_timecards()
        
        # 2. Corriger les lignes de facture
        self._fix_invoice_lines()
        
        # 3. Corriger les totaux de l'entête
        self._fix_header_totals()
        
        # 4. Corriger les dates DEB_PER/FIN_PER
        self._fix_period_dates()
        
        return self.tree
    
    def _fix_timecards(self):
        """Filtre les TimeIntervals pour ne garder que ceux de la période cible"""
        # Trouver tous les TimeCards
        timecards = self.tree.findall('.//TimeCard', self.namespaces)
        if not timecards:
            timecards = self.tree.findall('.//*[local-name()="TimeCard"]')
        
        target_start = date_parser.parse(self.adjustments['target_period_start']).date()
        target_end = date_parser.parse(self.adjustments['target_period_end']).date()
        
        for timecard in timecards:
            # Mise à jour des dates de période
            period_start = timecard.find('.//PeriodStartDate', self.namespaces)
            if period_start is None:
                period_start = timecard.find('.//*[local-name()="PeriodStartDate"]')
            if period_start is not None:
                period_start.text = self.adjustments['target_period_start']
            
            period_end = timecard.find('.//PeriodEndDate', self.namespaces)
            if period_end is None:
                period_end = timecard.find('.//*[local-name()="PeriodEndDate"]')
            if period_end is not None:
                period_end.text = self.adjustments['target_period_end']
            
            # Filtrer les TimeIntervals
            intervals = timecard.findall('.//TimeInterval', self.namespaces)
            if not intervals:
                intervals = timecard.findall('.//*[local-name()="TimeInterval"]')
            
            for interval in intervals:
                # Vérifier les dates de l'intervalle
                start_dt = interval.find('.//StartDateTime', self.namespaces)
                if start_dt is None:
                    start_dt = interval.find('.//*[local-name()="StartDateTime"]')
                
                end_dt = interval.find('.//EndDateTime', self.namespaces)
                if end_dt is None:
                    end_dt = interval.find('.//*[local-name()="EndDateTime"]')
                
                # Si l'intervalle est hors période, le supprimer
                if start_dt is not None and end_dt is not None:
                    try:
                        interval_start = date_parser.parse(start_dt.text).date()
                        interval_end = date_parser.parse(end_dt.text).date()
                        
                        if interval_start < target_start or interval_end > target_end:
                            # Supprimer cet intervalle
                            parent = interval.getparent()
                            parent.remove(interval)
                    except:
                        pass
    
    def _fix_invoice_lines(self):
        """Corrige les lignes de facture selon les ajustements"""
        # Trouver toutes les lignes
        lines = self.tree.findall('.//Line', self.namespaces)
        if not lines:
            lines = self.tree.findall('.//*[local-name()="Line"]')
        
        for line in lines:
            # Identifier la ligne par sa description
            desc_elem = line.find('.//Description', self.namespaces)
            if desc_elem is None:
                desc_elem = line.find('.//*[local-name()="Description"]')
            
            if desc_elem is not None and desc_elem.text:
                description = desc_elem.text
                
                # Chercher l'ajustement correspondant
                adjustment = None
                for desc_key, adj in self.adjustments['lines'].items():
                    if desc_key in description or description in desc_key:
                        adjustment = adj
                        break
                
                if adjustment:
                    if adjustment['action'] == 'remove':
                        # Supprimer la ligne
                        parent = line.getparent()
                        parent.remove(line)
                    else:
                        # Ajuster les valeurs
                        self._update_line_values(line, adjustment)
    
    def _update_line_values(self, line, adjustment):
        """Met à jour les valeurs d'une ligne"""
        # Quantité
        item_qty = line.find('.//ItemQuantity', self.namespaces)
        if item_qty is None:
            item_qty = line.find('.//*[local-name()="ItemQuantity"]')
        if item_qty is not None:
            item_qty.text = str(adjustment['new_quantity'])
        
        # Montant total
        charge_total = line.find('.//Charges/Charge/Total', self.namespaces)
        if charge_total is None:
            charge_total = line.find('.//*[local-name()="Charges"]/*[local-name()="Charge"]/*[local-name()="Total"]')
        if charge_total is not None:
            charge_total.text = f"{adjustment['new_amount']:.2f}"
        
        # Mise à jour de la période dans la description si nécessaire
        desc_elem = line.find('.//Description', self.namespaces)
        if desc_elem is None:
            desc_elem = line.find('.//*[local-name()="Description"]')
        
        if desc_elem is not None and desc_elem.text:
            # Remplacer les dates dans la description
            old_text = desc_elem.text
            if ' au ' in old_text:
                # Extraire la partie avant la date
                prefix = old_text.split(' au ')[0]
                # Reconstruire avec la nouvelle période
                if self.adjustments['target_period_start'] == self.adjustments['target_period_end']:
                    desc_elem.text = f"{prefix} du {self.adjustments['target_period_start']}"
                else:
                    desc_elem.text = f"{prefix} du {self.adjustments['target_period_start']} au {self.adjustments['target_period_end']}"
    
    def _fix_header_totals(self):
        """Corrige les totaux dans l'entête"""
        header = self.tree.find('.//Header', self.namespaces)
        if header is None:
            header = self.tree.find('.//*[local-name()="Header"]')
        
        if header is not None:
            # Total HT
            total_charges = header.find('.//TotalCharges', self.namespaces)
            if total_charges is None:
                total_charges = header.find('.//*[local-name()="TotalCharges"]')
            if total_charges is not None:
                total_charges.text = f"{self.adjustments['new_total_charges']:.2f}"
            
            # TVA
            total_tax = header.find('.//TotalTax', self.namespaces)
            if total_tax is None:
                total_tax = header.find('.//*[local-name()="TotalTax"]')
            if total_tax is not None:
                total_tax.text = f"{self.adjustments['new_total_tax']:.2f}"
            
            # Total TTC
            total_amount = header.find('.//TotalAmount', self.namespaces)
            if total_amount is None:
                total_amount = header.find('.//*[local-name()="TotalAmount"]')
            if total_amount is not None:
                total_amount.text = f"{self.adjustments['new_total_amount']:.2f}"
            
            # Nombre d'heures facturées
            nb_heures = header.find('.//*[@owner="NbHeuresFacturees"]', self.namespaces)
            if nb_heures is None:
                # Recherche alternative
                descriptions = header.findall('.//Description', self.namespaces)
                if not descriptions:
                    descriptions = header.findall('.//*[local-name()="Description"]')
                
                for desc in descriptions:
                    if desc.get('owner') == 'NbHeuresFacturees':
                        desc.text = f"{self.adjustments['target_hours']:.2f}"
                        break
    
    def _fix_period_dates(self):
        """Corrige les dates DEB_PER et FIN_PER"""
        header = self.tree.find('.//Header', self.namespaces)
        if header is None:
            header = self.tree.find('.//*[local-name()="Header"]')
        
        if header is not None:
            descriptions = header.findall('.//Description', self.namespaces)
            if not descriptions:
                descriptions = header.findall('.//*[local-name()="Description"]')
            
            for desc in descriptions:
                owner = desc.get('owner', '')
                if owner == 'DEB_PER':
                    desc.text = self.adjustments['target_period_start']
                elif owner == 'FIN_PER':
                    desc.text = self.adjustments['target_period_end']
    
    def to_string(self):
        """
        Convertit l'arbre XML en string
        
        Returns:
            str: XML sous forme de string
        """
        return etree.tostring(
            self.tree, 
            pretty_print=True, 
            xml_declaration=True, 
            encoding='UTF-8'
        ).decode('utf-8')
