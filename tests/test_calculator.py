"""
Tests unitaires pour le module calculator
"""

import unittest
from decimal import Decimal
from core.calculator import AmountCalculator

class TestAmountCalculator(unittest.TestCase):
    
    def setUp(self):
        """Prépare les données de test"""
        self.invoice_data = {
            'period_start': '2025-06-30',
            'period_end': '2025-06-30',
            'raf_hours': 8.0,
            'invoice_hours': 38.0,
            'total_charges': 1145.60,
            'vat_rate': 20,
            'raf_details': {
                'Heures travaillées': 8,
                'Prime de Panier de Chantier': 1,
                'Indemnité de Transport': 1
            },
            'lines': [
                {
                    'description': 'Heures travaillées',
                    'quantity': 35.0,
                    'unit': 'HUR',
                    'unit_price': 24.42160,
                    'total': 854.76
                },
                {
                    'description': 'Heures Supplémentaires 125%',
                    'quantity': 1.0,
                    'unit': 'HUR',
                    'unit_price': 30.52700,
                    'total': 30.53
                },
                {
                    'description': 'Prime de 13 ème Mois',
                    'quantity': 35.0,
                    'unit': 'PCE',
                    'unit_price': 1.97200,
                    'total': 69.02
                },
                {
                    'description': 'Prime de Panier de Chantier',
                    'quantity': 5.0,
                    'unit': 'PCE',
                    'unit_price': 0.47500,
                    'total': 2.38
                },
                {
                    'description': 'Indemnité de Transport',
                    'quantity': 5.0,
                    'unit': 'PCE',
                    'unit_price': 18.20000,
                    'total': 91.00
                }
            ]
        }
    
    def test_calculate_ratio(self):
        """Test le calcul du ratio RAF/Facture"""
        calculator = AmountCalculator(self.invoice_data)
        ratio = calculator._calculate_ratio()
        
        # 8h RAF / 38h facturées = 0.2105...
        self.assertAlmostEqual(ratio, 0.2105, places=3)
    
    def test_calculate_adjustments_single_day(self):
        """Test le calcul des ajustements pour un jour unique"""
        calculator = AmountCalculator(self.invoice_data)
        adjustments = calculator.calculate_adjustments()
        
        # Vérifier que les heures cibles sont correctes
        self.assertEqual(adjustments['target_hours'], 8.0)
        
        # Vérifier que les heures supplémentaires sont supprimées
        hs_adjustment = None
        for desc, adj in adjustments['lines'].items():
            if 'supplémentaire' in desc.lower():
                hs_adjustment = adj
                break
        
        if hs_adjustment:
            self.assertEqual(hs_adjustment['action'], 'remove')
            self.assertEqual(hs_adjustment['new_quantity'], 0)
            self.assertEqual(hs_adjustment['new_amount'], 0)
        
        # Vérifier que les paniers/transport sont à 1
        for desc, adj in adjustments['lines'].items():
            if 'panier' in desc.lower() or 'transport' in desc.lower():
                self.assertEqual(adj['new_quantity'], 1)
    
    def test_calculate_new_totals(self):
        """Test le calcul des nouveaux totaux"""
        calculator = AmountCalculator(self.invoice_data)
        adjustments = calculator.calculate_adjustments()
        
        # Vérifier que le nouveau total HT est autour de 240€
        self.assertGreater(adjustments['new_total_charges'], 230)
        self.assertLess(adjustments['new_total_charges'], 250)
        
        # Vérifier que la TVA est 20% du HT
        expected_tax = adjustments['new_total_charges'] * 0.20
        self.assertAlmostEqual(
            adjustments['new_total_tax'], 
            expected_tax, 
            delta=0.01
        )
        
        # Vérifier que TTC = HT + TVA
        expected_total = adjustments['new_total_charges'] + adjustments['new_total_tax']
        self.assertAlmostEqual(
            adjustments['new_total_amount'],
            expected_total,
            delta=0.01
        )
    
    def test_cent_adjustment(self):
        """Test l'ajustement du centime d'écart"""
        # Créer une situation avec un écart de centime
        self.invoice_data['raf_details'] = {
            'Heures travaillées': 8.01  # Légèrement différent
        }
        
        calculator = AmountCalculator(self.invoice_data)
        adjustments = calculator.calculate_adjustments()
        
        # Vérifier qu'il n'y a pas d'écart > 1€
        # (l'ajustement du centime devrait avoir corrigé)
        total_lines = sum(adj['new_amount'] for adj in adjustments['lines'].values())
        self.assertAlmostEqual(
            total_lines,
            adjustments['new_total_charges'],
            delta=0.01
        )

if __name__ == '__main__':
    unittest.main()
