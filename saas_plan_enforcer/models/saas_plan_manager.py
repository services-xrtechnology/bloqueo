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
        Siempre consulta en tiempo real, usa caché solo como fallback si falla.

        :param force_refresh: No usado, se mantiene por compatibilidad
        :return: dict con límites
        """
        # SIEMPRE consultar servidor primero (tiempo real)
        limits = self._fetch_limits_from_server()

        # Si obtuvo límites válidos, retornarlos
        if limits and limits.get('max_users', -1) > 0:
            return limits

        # FALLBACK: Si falló conexión, usar caché como último recurso
        cache = self.search([], limit=1)
        if cache and cache.cached_limits:
            try:
                cached_limits = json.loads(cache.cached_limits)
                _logger.warning(f"⚠️ Using cached limits as fallback (server unreachable)")
                return cached_limits
            except (json.JSONDecodeError, TypeError):
                _logger.error("Cache corrupted and server unreachable")

        # Si todo falla, límites de emergencia
        _logger.error("No limits available, using emergency limits")
        return self._get_emergency_limits()

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
            'max_companies': 1,
            'max_file_size_mb': 10,
            'blocked_modules': [
                'stock', 'stock_*',
                'purchase', 'purchase_*',
                'mrp', 'mrp_*',
                'hr', 'hr_*',
                'account_accountant',
                'mass_mailing*',
                'marketing_automation*',
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
                    'Max file size: %s MB'
                ) % (
                    self.cached_plan_name or 'Unknown',
                    limits.get('max_users', 'N/A'),
                    limits.get('max_file_size_mb', 'N/A')
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

            # Guardar límites como parámetros locales
            config = self.env['ir.config_parameter'].sudo()
            config.set_param('saas.plan.file_size_limit', str(limits.get('max_file_size_mb', 20)))

            # Actualizar límite web nativo de Odoo (en bytes)
            max_mb = limits.get('max_file_size_mb', 20)
            if max_mb > 0:
                max_bytes = max_mb * 1024 * 1024  # Convertir MB a bytes
                config.set_param('web.max_file_upload_size', str(max_bytes))
                _logger.info(f"📊 Updated web.max_file_upload_size to {max_mb}MB ({max_bytes} bytes)")

            config.set_param('saas.plan.limits_last_sync', str(fields.Datetime.now()))

            _logger.info(f"✅ Plan limits synced nightly: file_size={max_mb}MB")

        except Exception as e:
            _logger.error(f"Error syncing plan limits: {str(e)}")
