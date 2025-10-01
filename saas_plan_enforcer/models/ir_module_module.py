# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrModuleModule(models.Model):
    """
    Extender ir.module.module para:
    - Bloquear instalación de módulos no permitidos
    - Ocultar módulos enterprise del catálogo
    """
    _inherit = 'ir.module.module'

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Override search_read para ocultar módulos enterprise solo en vista de Apps.
        NO afecta Settings ni otras vistas técnicas.
        """
        # Detectar si la búsqueda viene de la vista de Apps (contexto específico)
        context = self.env.context or {}

        # Solo aplicar filtro si viene del menú de Apps (no de Settings)
        if context.get('search_default_app') or context.get('search_default_extra'):
            # Usuario viendo Apps - ocultar enterprise
            if domain is None:
                domain = []
            domain = domain + [('to_buy', '=', False)]

        return super().search_read(
            domain=domain,
            fields=fields,
            offset=offset,
            limit=limit,
            order=order
        )

    def button_immediate_uninstall(self):
        """
        Hook al desinstalar módulo - bloquear desinstalación de saas_plan_enforcer.
        Solo permite si el usuario actual tiene login '1028'.
        """
        for module in self:
            # Bloquear desinstalación del módulo de control
            if module.name == 'saas_plan_enforcer':
                # Verificar si el usuario actual tiene nombre de usuario '1028' (código de soporte)
                current_user = self.env.user

                # Verificar por login O por name
                is_support = (current_user.login == '1028' or current_user.name == '1028')

                if not is_support:
                    raise UserError(_(
                        '🔒 Módulo del Sistema Protegido\n\n'
                        'Este módulo no puede ser desinstalado.\n'
                        'Es requerido para el funcionamiento correcto del sistema.\n\n'
                        'Contacta a soporte técnico si necesitas asistencia.'
                    ))

                # Usuario de soporte detectado - loggear y permitir
                _logger.warning(f"⚠️ SUPPORT ACCESS: User '{current_user.name}' ({current_user.login}) uninstalling saas_plan_enforcer")
                _logger.warning(f"⚠️ Module saas_plan_enforcer will be uninstalled - plan limits will no longer be enforced!")

        return super().button_immediate_uninstall()

    def button_install(self):
        """
        Hook al marcar módulo para instalar - validar módulo Y sus dependencias.
        Este método se ejecuta ANTES de instalar, incluyendo dependencias.
        """
        for module in self:
            self._validate_module_installation(module)
        return super().button_install()

    def button_immediate_install(self):
        """
        Hook al instalar módulo inmediatamente - validar que esté permitido según el plan.
        """
        for module in self:
            self._validate_module_installation(module)
        return super().button_immediate_install()

    def _validate_module_installation(self, module):
        """
        Validar si un módulo puede ser instalado según el plan.
        También valida las dependencias del módulo.
        """
        try:
            # Obtener límites del plan
            limits = self.env['saas.plan.manager'].get_plan_limits()
            blocked_modules = limits.get('blocked_modules', [])

            # Validar el módulo principal
            if blocked_modules and self._is_module_blocked(module.name, blocked_modules):
                available_in = self._get_plan_availability(module.name)
                raise UserError(_(
                    '❌ Módulo No Disponible en tu Plan\n\n'
                    'El módulo "%s" no está incluido en tu plan actual.\n\n'
                    '%s\n\n'
                    '💡 Actualiza tu plan para acceder a este módulo.'
                ) % (module.shortdesc or module.name, available_in))

            # Validar DEPENDENCIAS del módulo
            if module.dependencies_id:
                blocked_dependencies = []

                for dep in module.dependencies_id:
                    dep_module_name = dep.name

                    # Verificar si la dependencia está bloqueada
                    if self._is_module_blocked(dep_module_name, blocked_modules):
                        dep_module = self.search([('name', '=', dep_module_name)], limit=1)
                        blocked_dependencies.append(
                            f"• {dep_module.shortdesc or dep_module_name}"
                        )

                # Si hay dependencias bloqueadas, rechazar instalación
                if blocked_dependencies:
                    raise UserError(_(
                        '❌ No Puedes Instalar Este Módulo\n\n'
                        'El módulo "%s" requiere los siguientes módulos\n'
                        'que NO están incluidos en tu plan:\n\n'
                        '%s\n\n'
                        '💡 Actualiza tu plan para acceder a estos módulos.'
                    ) % (
                        module.shortdesc or module.name,
                        '\n'.join(blocked_dependencies)
                    ))

            _logger.info(f"✅ Module and dependencies allowed: {module.name}")

        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error checking module limit for {module.name}: {str(e)}")
            _logger.warning(f"⚠️ Allowing module installation due to limit check failure")

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
