# -*- coding: utf-8 -*-
{
    "name": "Odoo Midtrans",
    "author": "Byron Josafat M",
    "website": "https://www.linkedin.com/in/byron-josafat-martinelli-916877219",
    "version": "16.0.0.0",
    "depends": [
        'base', 'payment', 'website_sale'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_views.xml',
        'views/payment_midtrans_templates.xml',
        'data/payment_acquirer_data.xml',
        'data/data_schedule.xml',
        'views/sale.xml',
        'data/currency.xml',
    ],
    "qweb": [],
    'assets': {
        'web.assets_frontend': ['odoo_midtrans/static/src/js/main.js'],
        'web.assets_backend': ['odoo_midtrans/static/src/js/main.js']
    },
    "license": 'OPL-1',
    'installable': True
}
