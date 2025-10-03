# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    """
    Extender res.company para controlar límite de empresas según el plan.
    """
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Hook al crear empresa - validar límite del plan.
        """
        try:
            # Obtener límites del plan
            limits = self.env['saas.plan.manager'].get_plan_limits()
            max_companies = limits.get('max_companies', -1)

            # Si hay límite (-1 = ilimitado)
            if max_companies > 0:
                # Contar empresas activas actuales
                current_companies = self.search_count([
                    ('active', '=', True)
                ])

                # Validar
                new_companies = len(vals_list)

                if current_companies + new_companies > max_companies:
                    raise UserError(_(
                        '⚠️ Límite de Empresas Alcanzado\n\n'
                        'Tu plan permite un máximo de %s empresas.\n'
                        'Actualmente tienes %s empresas activas.\n\n'
                        '💡 Actualiza tu plan para gestionar más empresas.\n\n'
                        'Los planes superiores permiten multi-empresa.'
                    ) % (max_companies, current_companies))

                _logger.info(f"✅ Company creation allowed: {current_companies}/{max_companies} companies")

        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error checking company limit: {str(e)}")
            _logger.warning("⚠️ Allowing company creation due to limit check failure")

        return super().create(vals_list)
