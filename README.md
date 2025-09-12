# PIXID Invoice Corrector

Application Streamlit pour corriger automatiquement les factures XML PIXID lors des semaines à cheval sur deux mois.

## 🎯 Problème résolu

Lorsqu'une semaine de travail chevauche deux mois, l'ERP envoie la semaine complète dans le XML (ex: 38h) alors que seule une partie doit être facturée (ex: 8h du lundi). Cela crée des écarts RAF/RCV dans PIXID.

## 📦 Installation

```bash
git clone https://github.com/[votre-compte]/pixid-corrector.git
cd pixid-corrector
pip install -r requirements.txt
```

## 🚀 Utilisation

```bash
streamlit run app.py
```

1. Uploadez votre fichier XML
2. L'application détecte automatiquement la période à facturer depuis les TimeCards
3. Cliquez sur "Corriger"
4. Vérifiez la prévisualisation
5. Téléchargez le XML corrigé

## 📁 Structure du projet

```
pixid-corrector/
├── app.py                 # Interface Streamlit principale
├── core/
│   ├── __init__.py
│   ├── parser.py         # Parsing et extraction XML
│   ├── detector.py       # Détection des incohérences
│   ├── calculator.py     # Calculs et ajustements
│   ├── fixer.py         # Application des corrections
│   └── validator.py      # Validation des invariants
├── tests/
│   ├── fixtures/         # Fichiers XML de test
│   └── test_*.py        # Tests unitaires
├── requirements.txt
└── README.md
```

## ✅ Règles de correction

- **Heures travaillées** : Proportionnel à la période (8h/38h pour un jour)
- **13e mois** : Au prorata des heures
- **Paniers/Transport** : 1 unité par jour facturé
- **HS/RTT** : Supprimés si hors période
- **TVA** : 20% par défaut
- **Arrondis** : 2 décimales

## 🔧 Configuration

Les paramètres par défaut peuvent être modifiés dans `config.py`

## 📊 Validation

L'application garantit :
- RAF (TimeCards) = Somme des lignes = TotalCharges
- Structure XML préservée (ordre, attributs, namespaces)
- Conformité PIXID (champs obligatoires, formats)
