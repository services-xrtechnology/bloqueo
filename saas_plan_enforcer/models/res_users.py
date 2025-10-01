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

    def write(self, vals):
        """
        Hook al modificar usuario - validar límite al DESARCHIVAR.
        """
        # Solo validar si se está activando un usuario
        if vals.get('active') == True:
            try:
                limits = self.env['saas.plan.manager'].get_plan_limits()
                max_users = limits.get('max_users', -1)

                if max_users > 0:
                    # Contar usuarios que se van a activar (están inactivos ahora)
                    users_to_activate = self.filtered(lambda u: not u.active and not u.share)

                    if users_to_activate:
                        # Contar usuarios activos DESPUÉS de activar
                        current_active = self.search_count([
                            ('active', '=', True),
                            ('share', '=', False)
                        ])

                        future_total = current_active + len(users_to_activate)

                        if future_total > max_users:
                            raise UserError(_(
                                '⚠️ No Puedes Desarchivar Este Usuario\n\n'
                                'Tu plan permite un máximo de %s usuarios.\n'
                                'Actualmente tienes %s usuarios activos.\n'
                                'Desarchivar este usuario llevaría a %s usuarios.\n\n'
                                '💡 Opciones:\n'
                                '• Archiva otro usuario primero\n'
                                '• Actualiza tu plan para más capacidad\n\n'
                                'Contacta a soporte o visita tu portal de cliente.'
                            ) % (max_users, current_active, future_total))

                        _logger.info(f"✅ User activation allowed: {future_total}/{max_users} users after activation")

            except UserError:
                raise
            except Exception as e:
                _logger.error(f"Error checking user limit on activation: {str(e)}")
                _logger.warning("⚠️ Allowing user activation due to limit check failure")

        return super().write(vals)
