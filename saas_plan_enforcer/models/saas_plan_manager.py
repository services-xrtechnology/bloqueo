# -*- coding: utf-8 -*-
import logging
import requests
import json
from datetime import datetime, date
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaasPlanManager(models.Model):
    """
    Servicio central para consultar límites del plan desde el servidor principal.
    Usa el db_name para identificar la instancia.
    """
    _name = 'saas.plan.manager'
    _description = 'SaaS Plan Limits Manager'

    # Campo para cachear los límites (evitar consultas constantes)
    name = fields.Char(default='Plan Limits Cache')
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    cached_limits = fields.Text(string='Cached Limits', readonly=True)
    cached_plan_name = fields.Char(string='Plan Name', readonly=True)

    def get_plan_limits(self, force_refresh=False):
        """
        Obtener límites del plan consultando al servidor principal.
        Usa caché para evitar consultas constantes.

        :param force_refresh: Forzar consulta aunque haya caché
        :return: dict con límites
        """
        # Intentar usar caché si es reciente (menos de 1 hora)
        cache = self.search([], limit=1)

        if cache and not force_refresh and cache.last_sync:
            # Verificar si el caché es reciente
            if isinstance(cache.last_sync, datetime):
                time_diff = datetime.now() - cache.last_sync
                if time_diff.total_seconds() < 3600:  # 1 hora
                    try:
                        limits = json.loads(cache.cached_limits)
                        _logger.info(f"✅ Using cached plan limits (age: {time_diff.total_seconds()}s)")
                        return limits
                    except (json.JSONDecodeError, TypeError):
                        _logger.warning("Cache corrupted, fetching fresh limits")

        # Consultar al servidor principal
        return self._fetch_limits_from_server()

    def _fetch_limits_from_server(self):
        """
        Consultar límites al servidor principal via API.
        """
        try:
            # Obtener configuración
            config = self.env['ir.config_parameter'].sudo()
            master_url = config.get_param('saas.master.url', 'http://localhost:8069')
            db_name = self.env.cr.dbname

            _logger.info(f"🔍 Fetching plan limits from {master_url} for db: {db_name}")

            # Llamar a la API
            api_url = f"{master_url}/api/subscription/limits"

            response = requests.post(
                api_url,
                json={'params': {'db_name': db_name}},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Extraer result de estructura JSONRPC si existe
                result = data.get('result', data)

                if result.get('success'):
                    limits = result.get('limits', {})

                    # Actualizar caché
                    self._update_cache(limits, result.get('plan_name', 'Unknown'))

                    _logger.info(f"✅ Plan limits fetched successfully: {result.get('plan_name')}")
                    return limits
                else:
                    _logger.error(f"API returned error: {result.get('error')}")
                    return result.get('limits', self._get_emergency_limits())
            else:
                _logger.error(f"API call failed with status: {response.status_code}")
                return self._get_emergency_limits()

        except requests.exceptions.RequestException as e:
            _logger.error(f"Network error fetching plan limits: {str(e)}")
            return self._get_emergency_limits()
        except Exception as e:
            _logger.error(f"Error fetching plan limits: {str(e)}", exc_info=True)
            return self._get_emergency_limits()

    def _update_cache(self, limits, plan_name):
        """Actualizar caché de límites."""
        try:
            cache = self.search([], limit=1)

            cache_vals = {
                'last_sync': fields.Datetime.now(),
                'cached_limits': json.dumps(limits),
                'cached_plan_name': plan_name,
            }

            if cache:
                cache.write(cache_vals)
            else:
                cache_vals['name'] = 'Plan Limits Cache'
                self.create(cache_vals)

        except Exception as e:
            _logger.error(f"Error updating cache: {str(e)}")

    def _get_emergency_limits(self):
        """
        Límites de emergencia cuando no se puede consultar al servidor.
        Usar límites MUY restrictivos para seguridad.
        """
        _logger.warning("⚠️ Using emergency limits (server unreachable)")

        return {
            'max_users': 3,
            'max_external_emails_per_day': 10,
            'blocked_modules': [
                'stock', 'stock_*',
                'purchase', 'purchase_*',
                'mrp', 'mrp_*',
                'hr', 'hr_*',
                'account_accountant',
            ]
        }

    def action_refresh_limits(self):
        """Acción manual para refrescar límites."""
        limits = self.get_plan_limits(force_refresh=True)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Limits Refreshed'),
                'message': _(
                    'Plan: %s\n'
                    'Max users: %s\n'
                    'Max emails/day: %s'
                ) % (
                    self.cached_plan_name or 'Unknown',
                    limits.get('max_users', 'N/A'),
                    limits.get('max_external_emails_per_day', 'N/A')
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_sync_plan_limits(self):
        """
        Cron job nocturno para sincronizar límites del plan.
        Se ejecuta cada noche a las 00:05 AM.
        """
        try:
            # Consultar límites frescos del servidor
            limits = self.get_plan_limits(force_refresh=True)

            # Guardar límite de emails como parámetro local
            config = self.env['ir.config_parameter'].sudo()
            config.set_param('saas.plan.email_limit', str(limits.get('max_external_emails_per_day', 100)))
            config.set_param('saas.plan.email_limit_last_sync', str(fields.Datetime.now()))

            _logger.info(f"✅ Plan limits synced nightly: email_limit={limits.get('max_external_emails_per_day')}")

            # Limpiar contadores de días anteriores
            today_key = f"saas.email_counter.{fields.Date.today()}"
            all_counters = config.search([('key', 'like', 'saas.email_counter.%')])
            old_counters = all_counters.filtered(lambda p: p.key != today_key)

            if old_counters:
                _logger.info(f"🧹 Cleaned {len(old_counters)} old email counters")
                old_counters.unlink()

        except Exception as e:
            _logger.error(f"Error syncing plan limits: {str(e)}")
