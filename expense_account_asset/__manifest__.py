# -*- coding: utf-8 -*-

{
    'name': 'Expense Assets Management',
    'description': """
Assets management
=================
Manage assets owned by a company or a person.
Keeps track of depreciations, and creates corresponding journal entries.

    """,
    'category': 'Accounting/Accounting',
    'sequence': 32,
    'depends': ['account_reports'],
    'data': [
        'views/account_asset_views.xml',
    ],
    'demo': [],
    'license': 'OEEL-1',
    'auto_install': True,
}
