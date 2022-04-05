# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Partner First Name - Last Name',
    'version': '15.0.0.1',
    'category': 'CRM',
    'summary': 'Partner First Name Last Name on partner add first name and last name in contacts and leads. When user enter first name and last name its reflect in main name of contacts and leads customer first name last name on customer first and last name on partner',
    'description': """
      
      Partner First Name Last Name in odoo,
      Set Partner FirstName LastName in Contacts in odoo,
      set Partner FirstName LastName in Leads in odoo,
      Partner First Name in odoo,
      Partner Last Name in odoo,
    
    """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.in',
    'depends': ['crm'],
    'data': [
        'views/partner.xml',
        'views/crm_lead_view.xml',
    ],
    'demo': [],
    'test': [],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://youtu.be/UzSS6Sd8Bpg',
    "images":['static/description/Banner.png'],
}
