# -*- coding: utf-8 -*-
{
    'name': 'SaaS Plan Enforcer',
    'version': '17.0.1.2.5',
    'category': 'Technical',
    'summary': 'System Configuration Manager',
    'description': "",
    'author': 'XR Technology',
    'website': 'https://xrtechnology.com',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Data
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',

        # Views
        'views/ir_module_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
