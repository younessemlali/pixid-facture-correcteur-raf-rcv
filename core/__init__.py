"""
Core module for PIXID Invoice Corrector
"""

from .parser import XMLParser
from .detector import InconsistencyDetector
from .calculator import AmountCalculator
from .fixer import InvoiceFixer
from .validator import InvoiceValidator

__all__ = [
    'XMLParser',
    'InconsistencyDetector',
    'AmountCalculator',
    'InvoiceFixer',
    'InvoiceValidator'
]

__version__ = '1.0.0'
