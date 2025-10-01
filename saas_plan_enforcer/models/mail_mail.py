# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailMail(models.Model):
    """
    Extender mail.mail para controlar límite de emails externos por día.
    """
    _inherit = 'mail.mail'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Hook al crear email - validar límite diario de emails externos.
        """
        try:
            # Obtener límites del plan
            limits = self.env['saas.plan.manager'].get_plan_limits()
            max_emails = limits.get('max_external_emails_per_day', -1)

            # Si hay límite (-1 = ilimitado)
            if max_emails > 0:
                # Contar emails externos enviados HOY
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                emails_today = self.search_count([
                    ('create_date', '>=', today_start),
                    ('email_to', '!=', False),  # Que tenga destinatario
                    ('state', 'in', ['outgoing', 'sent'])  # Enviados o por enviar
                ])

                # Contar cuántos emails externos se van a crear
                external_emails = len([
                    v for v in vals_list
                    if v.get('email_to') and not self._is_internal_email(v.get('email_to'))
                ])

                if emails_today + external_emails > max_emails:
                    raise UserError(_(
                        '⚠️ Límite Diario de Emails Alcanzado\n\n'
                        'Tu plan permite enviar %s emails externos por día.\n'
                        'Ya has enviado %s emails hoy.\n\n'
                        '💡 Opciones:\n'
                        '• Espera hasta mañana (se resetea a medianoche)\n'
                        '• Actualiza tu plan para mayor capacidad\n\n'
                        'Los emails internos (dentro de tu empresa) no cuentan en este límite.'
                    ) % (max_emails, emails_today))

                _logger.info(f"✅ Email creation allowed: {emails_today}/{max_emails} emails today")

        except UserError:
            raise  # Re-raise UserError
        except Exception as e:
            # Si falla consulta, permitir envío pero loggear
            _logger.error(f"Error checking email limit: {str(e)}")
            _logger.warning("⚠️ Allowing email send due to limit check failure")

        return super().create(vals_list)

    def _is_internal_email(self, email_to):
        """
        Verificar si un email es interno (no cuenta en el límite).

        :param email_to: Email del destinatario
        :return: True si es email interno
        """
        if not email_to:
            return True

        # Obtener dominio de la empresa
        company_domain = self.env.company.email
        if company_domain and '@' in company_domain:
            internal_domain = company_domain.split('@')[1]

            # Verificar si el email_to pertenece al mismo dominio
            if '@' in email_to and email_to.split('@')[1] == internal_domain:
                return True

        # Verificar si el email pertenece a algún usuario del sistema
        internal_user = self.env['res.users'].sudo().search([
            ('login', '=', email_to)
        ], limit=1)

        return bool(internal_user)
