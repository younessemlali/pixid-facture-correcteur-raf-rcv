"""
Module de calcul des ajustements pour les factures PIXID
Calcule les nouvelles quantités et montants après correction
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from dateutil import parser as date_parser

class AmountCalculator:
    def __init__(self, invoice_data):
        """
        Initialise le calculateur avec les données de facture
        
        Args:
            invoice_data: Dictionnaire des données parsées
        """
        self.data = invoice_data
        self.vat_rate = Decimal(str(invoice_data.get('vat_rate', 20))) / Decimal('100')
        
    def calculate_adjustments(self):
        """
        Calcule tous les ajustements nécessaires
        
        Returns:
            dict: Dictionnaire des ajustements à appliquer
        """
        adjustments = {
            'target_period_start': self.data['period_start'],
            'target_period_end': self.data['period_end'],
            'target_hours': self.data['raf_hours'],
            'ratio': self._calculate_ratio(),
            'lines': {},
            'new_total_charges': Decimal('0'),
            'new_total_tax': Decimal('0'),
            'new_total_amount': Decimal('0')
        }
        
        # Calcul des ajustements par ligne
        for line in self.data['lines']:
            line_adjustment = self._calculate_line_adjustment(line, adjustments['ratio'])
            if line_adjustment:
                adjustments['lines'][line['description']] = line_adjustment
                adjustments['new_total_charges'] += Decimal(str(line_adjustment['new_amount']))
        
        # Calcul de la TVA et du TTC
        adjustments['new_total_tax'] = self._round_decimal(
            adjustments['new_total_charges'] * self.vat_rate
        )
        adjustments['new_total_amount'] = adjustments['new_total_charges'] + adjustments['new_total_tax']
        
        # Vérification et ajustement du centime si nécessaire
        adjustments = self._adjust_cent_difference(adjustments)
        
        # Conversion en float pour l'affichage
        adjustments['new_total_charges'] = float(adjustments['new_total_charges'])
        adjustments['new_total_tax'] = float(adjustments['new_total_tax'])
        adjustments['new_total_amount'] = float(adjustments['new_total_amount'])
        
        return adjustments
    
    def _calculate_ratio(self):
        """Calcule le ratio RAF/Facture pour l'ajustement"""
        if self.data['invoice_hours'] > 0:
            return self.data['raf_hours'] / self.data['invoice_hours']
        return 1.0
    
    def _calculate_line_adjustment(self, line, ratio):
        """
        Calcule l'ajustement pour une ligne spécifique
        
        Args:
            line: Données de la ligne
            ratio: Ratio d'ajustement RAF/Facture
        
        Returns:
            dict: Ajustements pour cette ligne
        """
        adjustment = {
            'old_quantity': line['quantity'],
            'old_amount': line['total'],
            'unit_price': line['unit_price'],
            'action': 'adjust'
        }
        
        # Règles de calcul selon le type de ligne
        description = line.get('description', '').lower()
        
        # Heures travaillées et heures supplémentaires
        if 'heure' in description and 'supplémentaire' not in description:
            # Heures normales : appliquer le ratio
            adjustment['new_quantity'] = self._round_quantity(line['quantity'] * ratio)
            adjustment['new_amount'] = self._calculate_line_amount(
                adjustment['new_quantity'], 
                line['unit_price']
            )
        
        elif 'supplémentaire' in description or 'hs' in description.lower():
            # Heures supplémentaires : supprimer si période réduite à 1 jour
            if self.data['period_start'] == self.data['period_end']:
                adjustment['new_quantity'] = 0
                adjustment['new_amount'] = 0
                adjustment['action'] = 'remove'
            else:
                adjustment['new_quantity'] = self._round_quantity(line['quantity'] * ratio)
                adjustment['new_amount'] = self._calculate_line_amount(
                    adjustment['new_quantity'], 
                    line['unit_price']
                )
        
        elif 'rtt' in description:
            # RTT : supprimer si période réduite
            if self.data['period_start'] == self.data['period_end']:
                adjustment['new_quantity'] = 0
                adjustment['new_amount'] = 0
                adjustment['action'] = 'remove'
            else:
                adjustment['new_quantity'] = self._round_quantity(line['quantity'] * ratio)
                adjustment['new_amount'] = self._calculate_line_amount(
                    adjustment['new_quantity'], 
                    line['unit_price']
                )
        
        elif '13' in description and 'mois' in description:
            # 13e mois : au prorata des heures
            adjustment['new_quantity'] = self._round_quantity(line['quantity'] * ratio)
            adjustment['new_amount'] = self._calculate_line_amount(
                adjustment['new_quantity'], 
                line['unit_price']
            )
        
        elif 'panier' in description or 'transport' in description:
            # Paniers et transport : 1 par jour travaillé
            days_worked = self._calculate_days_worked()
            adjustment['new_quantity'] = days_worked
            adjustment['new_amount'] = self._calculate_line_amount(
                adjustment['new_quantity'], 
                line['unit_price']
            )
        
        else:
            # Autres lignes : appliquer le ratio par défaut
            adjustment['new_quantity'] = self._round_quantity(line['quantity'] * ratio)
            adjustment['new_amount'] = self._calculate_line_amount(
                adjustment['new_quantity'], 
                line['unit_price']
            )
        
        return adjustment
    
    def _calculate_days_worked(self):
        """Calcule le nombre de jours travaillés dans la période cible"""
        try:
            start = date_parser.parse(self.data['period_start']).date()
            end = date_parser.parse(self.data['period_end']).date()
            
            # Si même jour, c'est 1 jour
            if start == end:
                return 1
            
            # Sinon calculer le nombre de jours ouvrés
            days = (end - start).days + 1
            # Simplification : on ne compte pas les weekends pour l'instant
            return min(days, 5)  # Maximum 5 jours ouvrés par semaine
            
        except:
            return 1  # Par défaut 1 jour
    
    def _calculate_line_amount(self, quantity, unit_price):
        """Calcule le montant d'une ligne"""
        amount = Decimal(str(quantity)) * Decimal(str(unit_price))
        return float(self._round_decimal(amount))
    
    def _round_quantity(self, quantity):
        """Arrondit une quantité"""
        if 'heure' in str(quantity).lower():
            # Pour les heures, garder 2 décimales
            return round(quantity, 2)
        else:
            # Pour les autres, arrondir à l'entier
            return round(quantity)
    
    def _round_decimal(self, value):
        """Arrondit une valeur décimale à 2 décimales"""
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def _adjust_cent_difference(self, adjustments):
        """
        Ajuste le centime d'écart si nécessaire
        
        Args:
            adjustments: Dictionnaire des ajustements
        
        Returns:
            dict: Ajustements modifiés si nécessaire
        """
        # Calcul de l'écart éventuel
        raf_total = Decimal('0')
        
        # Calcul du total RAF depuis les détails
        for type_name, value in self.data['raf_details'].items():
            if 'heure' in type_name.lower():
                # Estimation basée sur le taux horaire moyen
                if self.data['invoice_hours'] > 0:
                    hourly_rate = Decimal(str(self.data['total_charges'])) / Decimal(str(self.data['invoice_hours']))
                    raf_total += Decimal(str(value)) * hourly_rate
        
        # Si écart de moins de 1€, ajuster la plus petite ligne
        difference = abs(raf_total - adjustments['new_total_charges'])
        
        if difference > 0 and difference < Decimal('1'):
            # Trouver la plus petite ligne non nulle
            smallest_line = None
            smallest_amount = None
            
            for desc, adj in adjustments['lines'].items():
                if adj['new_amount'] > 0:
                    if smallest_amount is None or adj['new_amount'] < smallest_amount:
                        smallest_line = desc
                        smallest_amount = adj['new_amount']
            
            # Ajuster la plus petite ligne
            if smallest_line:
                if raf_total > adjustments['new_total_charges']:
                    adjustments['lines'][smallest_line]['new_amount'] += float(difference)
                else:
                    adjustments['lines'][smallest_line]['new_amount'] -= float(difference)
                
                # Recalculer les totaux
                adjustments['new_total_charges'] = Decimal('0')
                for adj in adjustments['lines'].values():
                    adjustments['new_total_charges'] += Decimal(str(adj['new_amount']))
                
                adjustments['new_total_tax'] = self._round_decimal(
                    adjustments['new_total_charges'] * self.vat_rate
                )
                adjustments['new_total_amount'] = adjustments['new_total_charges'] + adjustments['new_total_tax']
        
        return adjustments
