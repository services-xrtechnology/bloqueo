# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrConfigParameter(models.Model):
    """
    Proteger parámetros críticos del sistema.
    Solo el usuario admin secreto (login='1028') puede modificarlos.
    """
    _inherit = 'ir.config_parameter'

    # Parámetros protegidos de nuestro módulo
    PROTECTED_PARAMS = [
        'saas.operations.secret',
        'saas.master.url',
        'web.max_file_upload_size',
        'saas.plan.file_size_limit',
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Proteger solo nuestros parámetros"""
        for vals in vals_list:
            if vals.get('key') in self.PROTECTED_PARAMS:
                self._check_admin_secret()
        return super().create(vals_list)

    def write(self, vals):
        """Proteger solo nuestros parámetros"""
        for param in self:
            if param.key in self.PROTECTED_PARAMS:
                self._check_admin_secret()
        return super().write(vals)

    def unlink(self):
        """Proteger solo nuestros parámetros"""
        for param in self:
            if param.key in self.PROTECTED_PARAMS:
                self._check_admin_secret()
        return super().unlink()

    def _check_admin_secret(self):
        """
        Verificar que el usuario actual sea el admin secreto (login='1028').
        """
        current_user = self.env.user

        # Permitir si es el usuario secreto
        if current_user.login == '1028':
            _logger.info(f"✅ Admin secreto (1028) modificando parámetro protegido")
            return True

        # Permitir en modo instalación (cuando se instala el módulo)
        if self.env.context.get('module_install'):
            return True

        # Bloquear para cualquier otro usuario
        raise UserError(_(
            '🔒 Parámetro Protegido\n\n'
            'Este parámetro del sistema está protegido y solo puede ser modificado '
            'por el administrador principal.\n\n'
            'Si necesitas cambiar esta configuración, contacta al administrador.'
        ))
