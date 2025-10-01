# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrModuleModule(models.Model):
    """
    Extender ir.module.module para bloquear instalación de módulos no permitidos.
    """
    _inherit = 'ir.module.module'

    def button_immediate_install(self):
        """
        Hook al instalar módulo - validar que esté permitido según el plan.
        """
        for module in self:
            try:
                # Obtener límites del plan
                limits = self.env['saas.plan.manager'].get_plan_limits()
                blocked_modules = limits.get('blocked_modules', [])

                if blocked_modules and self._is_module_blocked(module.name, blocked_modules):
                    # Buscar en qué plan está disponible
                    available_in = self._get_plan_availability(module.name)

                    raise UserError(_(
                        '❌ Módulo No Disponible en tu Plan\n\n'
                        'El módulo "%s" no está incluido en tu plan actual.\n\n'
                        '%s\n\n'
                        '💡 Opciones:\n'
                        '• Actualiza tu plan para acceder a este módulo\n'
                        '• Contacta a soporte para más información\n\n'
                        'Visita tu portal de cliente para cambiar de plan.'
                    ) % (
                        module.shortdesc or module.name,
                        available_in
                    ))

                _logger.info(f"✅ Module installation allowed: {module.name}")

            except UserError:
                raise  # Re-raise UserError
            except Exception as e:
                # Si falla consulta, loggear pero permitir (fail-open para no bloquear operación)
                _logger.error(f"Error checking module limit for {module.name}: {str(e)}")
                _logger.warning(f"⚠️ Allowing module installation due to limit check failure")

        return super().button_immediate_install()

    def _is_module_blocked(self, module_name, blocked_list):
        """
        Verificar si un módulo está en la lista de bloqueados.
        Soporta wildcards con *.

        :param module_name: Nombre técnico del módulo
        :param blocked_list: Lista de módulos bloqueados
        :return: True si está bloqueado
        """
        for pattern in blocked_list:
            if pattern.endswith('*'):
                # Wildcard: stock* bloquea stock, stock_account, stock_landed_costs, etc.
                prefix = pattern[:-1]
                if module_name.startswith(prefix):
                    return True
            else:
                # Match exacto
                if module_name == pattern:
                    return True

        return False

    def _get_plan_availability(self, module_name):
        """
        Determinar en qué planes está disponible el módulo.
        Esto es una ayuda visual para el usuario.
        """
        # Mapeo simplificado de módulos a planes
        module_plans = {
            'stock': '✅ Disponible desde Plan 2 ($100/mes)',
            'account_accountant': '✅ Disponible desde Plan 3 ($140/mes)',
            'hr_payroll': '✅ Disponible en Plan 4 ($200/mes)',
        }

        # Buscar por familia de módulos
        for key, message in module_plans.items():
            if module_name.startswith(key):
                return message

        return '✅ Disponible en planes superiores'

    @api.model
    def action_view_plan_info(self):
        """
        Acción para mostrar información del plan actual.
        """
        limits = self.get_plan_limits(force_refresh=True)

        cache = self.search([], limit=1)
        plan_name = cache.cached_plan_name if cache else 'Unknown'

        message = _(
            '<strong>Plan Actual:</strong> %s<br/><br/>'
            '<strong>Límites:</strong><br/>'
            '• Usuarios máximos: %s<br/>'
            '• Emails externos/día: %s<br/>'
            '• Módulos bloqueados: %s<br/><br/>'
            '<em>Última sincronización: %s</em>'
        ) % (
            plan_name,
            limits.get('max_users', 'N/A'),
            limits.get('max_external_emails_per_day', 'N/A'),
            len(limits.get('blocked_modules', [])),
            cache.last_sync if cache else 'Never'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Información del Plan'),
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }
