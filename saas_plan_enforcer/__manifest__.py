# -*- coding: utf-8 -*-
{
    'name': 'SaaS Plan Enforcer',
    'version': '17.0.1.0.1',
    'category': 'Technical',
    'summary': 'Control de límites y acceso según plan de suscripción',
    'description': """
SaaS Plan Enforcer
==================

Módulo que se instala en las instancias cliente para controlar:
* Límite de usuarios según el plan
* Bloqueo de módulos no permitidos
* Límite de emails externos por día

Funciona consultando al servidor principal via API usando el db_name.
    """,
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

        # Views
        'views/ir_module_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
