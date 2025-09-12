"""
Module de parsing XML pour les factures PIXID
Extrait les données nécessaires à la correction
"""

from lxml import etree
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import re

class XMLParser:
    def __init__(self, xml_content):
        """
        Initialise le parser avec le contenu XML
        
        Args:
            xml_content: Contenu XML en bytes ou string
        """
        if isinstance(xml_content, str):
            xml_content = xml_content.encode('utf-8')
        
        self.tree = etree.fromstring(xml_content)
        self.namespaces = self._extract_namespaces()
        
    def _extract_namespaces(self):
        """Extrait tous les namespaces du document"""
        ns_map = {}
        for prefix, namespace in self.tree.nsmap.items():
            if prefix:
                ns_map[prefix] = namespace
            else:
                ns_map['default'] = namespace
        return ns_map
    
    def parse(self):
        """
        Parse le document XML et extrait toutes les données nécessaires
        
        Returns:
            dict: Données structurées de la facture
        """
        invoice = self._find_invoice()
        
        data = {
            'tree': self.tree,
            'namespaces': self.namespaces,
            'invoice_id': self._get_invoice_id(invoice),
            'timecards_position': self._detect_timecards_position(invoice),
            'period_start': None,
            'period_end': None,
            'raf_hours': 0,
            'raf_details': {},
            'invoice_hours': 0,
            'lines': [],
            'total_charges': 0,
            'total_tax': 0,
            'total_amount': 0,
            'vat_rate': 20,  # Par défaut
            'deb_per': None,
            'fin_per': None
        }
        
        # Extraction des TimeCards (RAF)
        timecards = self._extract_timecards(invoice, data['timecards_position'])
        data.update(self._parse_timecards(timecards))
        
        # Extraction des totaux de l'entête
        header = invoice.find('.//Header', self.namespaces)
        if header is not None:
            data.update(self._parse_header(header))
        
        # Extraction des lignes de facture
        data['lines'] = self._parse_lines(invoice)
        
        # Calcul des heures facturées depuis les lignes
        data['invoice_hours'] = self._calculate_invoice_hours(data['lines'])
        
        return data
    
    def _find_invoice(self):
        """Trouve l'élément Invoice dans le document"""
        # Recherche avec namespace
        invoice = self.tree.find('.//Invoice', self.namespaces)
        if invoice is None:
            # Recherche sans namespace
            invoice = self.tree.find('.//*[local-name()="Invoice"]')
        if invoice is None:
            raise ValueError("Aucune facture trouvée dans le document XML")
        return invoice
    
    def _get_invoice_id(self, invoice):
        """Extrait l'ID de la facture"""
        # Cherche dans Header/DocumentIds
        doc_id = invoice.find('.//Header/DocumentIds//Id', self.namespaces)
        if doc_id is None:
            doc_id = invoice.find('.//*[local-name()="Header"]/*[local-name()="DocumentIds"]//*[local-name()="Id"]')
        
        if doc_id is not None and doc_id.text:
            return doc_id.text.strip()
        return "UNKNOWN"
    
    def _detect_timecards_position(self, invoice):
        """Détecte si les TimeCards sont en Header ou en Line"""
        # Recherche en Header
        header_tc = invoice.find('.//Header//TimeCard', self.namespaces)
        if header_tc is None:
            header_tc = invoice.find('.//*[local-name()="Header"]//*[local-name()="TimeCard"]')
        
        if header_tc is not None:
            return 'header'
        
        # Recherche en Line
        line_tc = invoice.find('.//Line//TimeCard', self.namespaces)
        if line_tc is None:
            line_tc = invoice.find('.//*[local-name()="Line"]//*[local-name()="TimeCard"]')
        
        if line_tc is not None:
            return 'line'
        
        return None
    
    def _extract_timecards(self, invoice, position):
        """Extrait tous les TimeCards selon leur position"""
        timecards = []
        
        if position == 'header':
            timecards = invoice.findall('.//Header//TimeCard', self.namespaces)
            if not timecards:
                timecards = invoice.findall('.//*[local-name()="Header"]//*[local-name()="TimeCard"]')
        elif position == 'line':
            timecards = invoice.findall('.//Line//TimeCard', self.namespaces)
            if not timecards:
                timecards = invoice.findall('.//*[local-name()="Line"]//*[local-name()="TimeCard"]')
        
        return timecards
    
    def _parse_timecards(self, timecards):
        """Parse les TimeCards et extrait les informations RAF"""
        data = {
            'period_start': None,
            'period_end': None,
            'raf_hours': 0,
            'raf_details': {}
        }
        
        for timecard in timecards:
            # Extraction des dates de période
            period_start = timecard.find('.//PeriodStartDate', self.namespaces)
            period_end = timecard.find('.//PeriodEndDate', self.namespaces)
            
            if period_start is None:
                period_start = timecard.find('.//*[local-name()="PeriodStartDate"]')
            if period_end is None:
                period_end = timecard.find('.//*[local-name()="PeriodEndDate"]')
            
            if period_start is not None and period_start.text:
                data['period_start'] = period_start.text
            if period_end is not None and period_end.text:
                data['period_end'] = period_end.text
            
            # Extraction des TimeInterval
            intervals = timecard.findall('.//TimeInterval', self.namespaces)
            if not intervals:
                intervals = timecard.findall('.//*[local-name()="TimeInterval"]')
            
            for interval in intervals:
                interval_type = interval.get('type', 'Unknown')
                
                # Extraction de la durée ou quantité
                duration = interval.find('.//Duration', self.namespaces)
                if duration is None:
                    duration = interval.find('.//*[local-name()="Duration"]')
                
                quantity = interval.find('.//Quantity', self.namespaces)
                if quantity is None:
                    quantity = interval.find('.//*[local-name()="Quantity"]')
                
                value = 0
                if duration is not None and duration.text:
                    value = float(duration.text)
                elif quantity is not None and quantity.text:
                    value = float(quantity.text)
                
                # Accumulation par type
                if interval_type not in data['raf_details']:
                    data['raf_details'][interval_type] = 0
                data['raf_details'][interval_type] += value
                
                # Calcul des heures RAF totales
                if 'heure' in interval_type.lower():
                    data['raf_hours'] += value
        
        return data
    
    def _parse_header(self, header):
        """Parse l'entête de la facture"""
        data = {}
        
        # Total HT
        total_charges = header.find('.//TotalCharges', self.namespaces)
        if total_charges is None:
            total_charges = header.find('.//*[local-name()="TotalCharges"]')
        if total_charges is not None and total_charges.text:
            data['total_charges'] = float(total_charges.text)
        
        # TVA
        total_tax = header.find('.//TotalTax', self.namespaces)
        if total_tax is None:
            total_tax = header.find('.//*[local-name()="TotalTax"]')
        if total_tax is not None and total_tax.text:
            data['total_tax'] = float(total_tax.text)
        
        # Total TTC
        total_amount = header.find('.//TotalAmount', self.namespaces)
        if total_amount is None:
            total_amount = header.find('.//*[local-name()="TotalAmount"]')
        if total_amount is not None and total_amount.text:
            data['total_amount'] = float(total_amount.text)
        
        # Taux de TVA
        tax_percent = header.find('.//Tax/PercentQuantity', self.namespaces)
        if tax_percent is None:
            tax_percent = header.find('.//*[local-name()="Tax"]/*[local-name()="PercentQuantity"]')
        if tax_percent is not None and tax_percent.text:
            data['vat_rate'] = float(tax_percent.text)
        
        # Période facturée (DEB_PER / FIN_PER)
        descriptions = header.findall('.//Description', self.namespaces)
        if not descriptions:
            descriptions = header.findall('.//*[local-name()="Description"]')
        
        for desc in descriptions:
            owner = desc.get('owner', '')
            if owner == 'DEB_PER' and desc.text:
                data['deb_per'] = desc.text
            elif owner == 'FIN_PER' and desc.text:
                data['fin_per'] = desc.text
        
        return data
    
    def _parse_lines(self, invoice):
        """Parse les lignes de facture"""
        lines = []
        
        # Recherche de toutes les lignes
        xml_lines = invoice.findall('.//Line', self.namespaces)
        if not xml_lines:
            xml_lines = invoice.findall('.//*[local-name()="Line"]')
        
        for line in xml_lines:
            line_data = self._parse_single_line(line)
            if line_data:
                lines.append(line_data)
        
        return lines
    
    def _parse_single_line(self, line):
        """Parse une ligne de facture unique"""
        line_data = {
            'type': None,
            'description': None,
            'quantity': 0,
            'unit': None,
            'unit_price': 0,
            'total': 0,
            'element': line  # Garde la référence pour la modification
        }
        
        # Type de ligne (ReasonCode)
        reason_code = line.find('.//ReasonCode', self.namespaces)
        if reason_code is None:
            reason_code = line.find('.//*[local-name()="ReasonCode"]')
        if reason_code is not None and reason_code.text:
            line_data['type'] = reason_code.text
        
        # Description
        description = line.find('.//Description', self.namespaces)
        if description is None:
            description = line.find('.//*[local-name()="Description"]')
        if description is not None and description.text:
            line_data['description'] = description.text
        
        # Quantité
        item_quantity = line.find('.//ItemQuantity', self.namespaces)
        if item_quantity is None:
            item_quantity = line.find('.//*[local-name()="ItemQuantity"]')
        if item_quantity is not None and item_quantity.text:
            line_data['quantity'] = float(item_quantity.text)
            line_data['unit'] = item_quantity.get('uom', 'PCE')
        
        # Prix unitaire
        price_amount = line.find('.//Price/Amount', self.namespaces)
        if price_amount is None:
            price_amount = line.find('.//*[local-name()="Price"]/*[local-name()="Amount"]')
        if price_amount is not None and price_amount.text:
            line_data['unit_price'] = float(price_amount.text)
        
        # Total ligne
        charge_total = line.find('.//Charges/Charge/Total', self.namespaces)
        if charge_total is None:
            charge_total = line.find('.//*[local-name()="Charges"]/*[local-name()="Charge"]/*[local-name()="Total"]')
        if charge_total is not None and charge_total.text:
            line_data['total'] = float(charge_total.text)
        
        return line_data
    
    def _calculate_invoice_hours(self, lines):
        """Calcule le total des heures facturées depuis les lignes"""
        total_hours = 0
        
        for line in lines:
            if line['description'] and 'heure' in line['description'].lower():
                if line['unit'] == 'HUR' or line['unit'] == 'hur':
                    total_hours += line['quantity']
        
        return total_hours
