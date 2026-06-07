{
    'name': 'WiPay Sheveion Callender',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'WiPay payment provider for Odoo Website Checkout, Portal Payments, and Payment Links',
    'author': 'Sheveion Callender',
    'website': 'https://spxcorp.com',
    'license': 'LGPL-3',
    'depends': ['payment', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_templates.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
}
