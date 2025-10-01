# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """
    Extender res.users para controlar límite de usuarios según el plan.
    """
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Hook al crear usuario - validar límite del plan.
        """
        # Obtener límites del plan
        try:
            limits = self.env['saas.plan.manager'].get_plan_limits()
            max_users = limits.get('max_users', -1)

            # Si hay límite (-1 = ilimitado)
            if max_users > 0:
                # Contar usuarios activos actuales
                current_users = self.search_count([
                    ('active', '=', True),
                    ('share', '=', False)  # Solo usuarios internos
                ])

                # Validar por cada usuario que se intenta crear
                new_users_count = len([v for v in vals_list if not v.get('share', False)])

                if current_users + new_users_count > max_users:
                    raise UserError(_(
                        '⚠️ Límite de Usuarios Alcanzado\n\n'
                        'Tu plan permite un máximo de %s usuarios.\n'
                        'Actualmente tienes %s usuarios activos.\n\n'
                        '💡 Actualiza tu plan para agregar más usuarios.\n\n'
                        'Contacta a soporte o visita tu portal de cliente.'
                    ) % (max_users, current_users))

                _logger.info(f"✅ User creation allowed: {current_users}/{max_users} users")

        except UserError:
            raise  # Re-raise UserError para mostrar al usuario
        except Exception as e:
            # Si falla la consulta, permitir crear pero loggear error
            _logger.error(f"Error checking user limit: {str(e)}")
            _logger.warning("⚠️ Allowing user creation due to limit check failure")

        return super().create(vals_list)
