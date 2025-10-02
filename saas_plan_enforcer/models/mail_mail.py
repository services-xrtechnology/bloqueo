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
                # Contar cuántos emails externos se van a crear
                external_emails_count = len([
                    v for v in vals_list
                    if v.get('email_to') and not self._is_internal_email(v.get('email_to'))
                ])

                if external_emails_count > 0:
                    # Obtener contador diario desde parámetros del sistema
                    config = self.env['ir.config_parameter'].sudo()
                    today_key = f"saas.email_counter.{fields.Date.today()}"
                    current_count = int(config.get_param(today_key, '0'))

                    # Calcular nuevo total
                    new_total = current_count + external_emails_count

                    # Validar límite
                    if new_total > max_emails:
                        raise UserError(_(
                            '⚠️ Límite Diario de Emails Alcanzado\n\n'
                            'Tu plan permite enviar %s emails externos por día.\n'
                            'Ya has enviado %s emails hoy.\n'
                            'Intentas enviar %s más.\n\n'
                            '💡 Opciones:\n'
                            '• Espera hasta mañana (se resetea a medianoche)\n'
                            '• Actualiza tu plan para mayor capacidad\n\n'
                            'Los emails internos (dentro de tu empresa) no cuentan en este límite.'
                        ) % (max_emails, current_count, external_emails_count))

                    # Incrementar contador
                    config.set_param(today_key, str(new_total))

                    _logger.info(f"✅ Email sending allowed: {new_total}/{max_emails} emails today")

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

    @api.model
    def _cron_cleanup_old_email_counters(self):
        """
        Cron job para limpiar contadores de emails de días anteriores.
        Se ejecuta diariamente a medianoche.
        """
        try:
            config = self.env['ir.config_parameter'].sudo()
            today_key = f"saas.email_counter.{fields.Date.today()}"

            # Buscar todos los contadores de emails
            all_counters = config.search([
                ('key', 'like', 'saas.email_counter.%')
            ])

            # Borrar los que NO son de hoy
            old_counters = all_counters.filtered(lambda p: p.key != today_key)

            if old_counters:
                _logger.info(f"🧹 Cleaning {len(old_counters)} old email counters")
                old_counters.unlink()
            else:
                _logger.info("✅ No old email counters to clean")

        except Exception as e:
            _logger.error(f"Error cleaning email counters: {str(e)}")
