# -*- coding: utf-8 -*-
import subprocess
import logging
import os
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ModuleOperationsController(http.Controller):
    """
    Controlador para operaciones de módulos vía API.
    Permite al servidor principal ejecutar comandos de upgrade/install.
    """

    def _validate_secret(self, secret_token):
        """Validar token de seguridad"""
        if not secret_token:
            return False

        # Obtener token configurado
        config_token = request.env['ir.config_parameter'].sudo().get_param('saas.operations.secret', '')

        if not config_token:
            _logger.error("⚠️ No operations secret configured")
            return False

        return secret_token == config_token

    @http.route('/api/module/upgrade', type='json', auth='public', methods=['POST'], csrf=False)
    def upgrade_module(self, module_name=None, secret_token=None, **kw):
        """
        Actualizar (upgrade) un módulo específico.

        Params:
            module_name: Nombre técnico del módulo (ej: 'saas_plan_enforcer')
            secret_token: Token de seguridad

        Returns:
            dict: {'success': bool, 'message': str, 'output': str}
        """
        try:
            # Validar autenticación
            if not self._validate_secret(secret_token):
                return {
                    'success': False,
                    'error': 'Unauthorized - Invalid secret token'
                }

            if not module_name:
                return {
                    'success': False,
                    'error': 'module_name is required'
                }

            _logger.info(f"🔄 Starting upgrade of module: {module_name}")

            # Usar el mecanismo interno de Odoo para actualizar módulo
            # Buscar el módulo
            Module = request.env['ir.module.module'].sudo()
            module = Module.search([('name', '=', module_name)], limit=1)

            if not module:
                return {
                    'success': False,
                    'error': f"Module '{module_name}' not found in this instance"
                }

            if module.state not in ['installed', 'to upgrade']:
                return {
                    'success': False,
                    'error': f"Module '{module_name}' is not installed (state: {module.state})"
                }

            # Marcar para actualizar
            module.button_immediate_upgrade()

            _logger.info(f"✅ Module {module_name} upgrade initiated")

            return {
                'success': True,
                'message': f"Module '{module_name}' upgraded successfully",
                'module': module_name,
                'new_state': module.state
            }

        except Exception as e:
            _logger.error(f"❌ Error in upgrade endpoint: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/module/install', type='json', auth='public', methods=['POST'], csrf=False)
    def install_module(self, repo_url=None, branch=None, module_name=None, secret_token=None, **kw):
        """
        Instalar un módulo nuevo desde repositorio.

        Params:
            repo_url: URL del repositorio GitHub
            branch: Branch a usar
            module_name: Nombre del módulo a instalar
            secret_token: Token de seguridad

        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            # Validar autenticación
            if not self._validate_secret(secret_token):
                return {
                    'success': False,
                    'error': 'Unauthorized - Invalid secret token'
                }

            if not all([repo_url, branch, module_name]):
                return {
                    'success': False,
                    'error': 'repo_url, branch, and module_name are required'
                }

            _logger.info(f"📦 Installing module: {module_name} from {repo_url}")

            # Obtener db_name (ya incluye .cloudpepper.site)
            db_name = request.env.cr.dbname

            # Clonar repo en extra-addons si no existe
            extra_addons_path = f"/var/odoo/{db_name}/extra-addons"
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            repo_path = f"{extra_addons_path}/{repo_name}"

            # Git clone si no existe
            if not os.path.exists(repo_path):
                clone_cmd = f"cd {extra_addons_path} && git clone -b {branch} {repo_url}"
                _logger.info(f"📥 Cloning: {clone_cmd}")
                subprocess.run(clone_cmd, shell=True, check=True, timeout=60)
            else:
                # Git pull si ya existe
                pull_cmd = f"cd {repo_path} && git pull"
                _logger.info(f"🔄 Pulling: {pull_cmd}")
                subprocess.run(pull_cmd, shell=True, check=True, timeout=30)

            # Instalar módulo con odoo-bin (sin sudo, ya somos usuario odoo)
            install_cmd = f"cd /var/odoo/{db_name} && venv/bin/python3 src/odoo-bin -c odoo.conf -d {db_name} --no-http --stop-after-init --init {module_name}"

            _logger.info(f"📤 Installing: {install_cmd}")

            result = subprocess.run(
                install_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            success = result.returncode == 0

            if success:
                _logger.info(f"✅ Module {module_name} installed successfully")
                return {
                    'success': True,
                    'message': f"Module '{module_name}' installed successfully",
                    'module': module_name
                }
            else:
                _logger.error(f"❌ Error installing {module_name}")
                return {
                    'success': False,
                    'error': result.stderr[:500]
                }

        except Exception as e:
            _logger.error(f"❌ Error in install endpoint: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/instance/restart', type='json', auth='public', methods=['POST'], csrf=False)
    def restart_instance(self, secret_token=None, **kw):
        """
        Reiniciar servicio de Odoo de esta instancia.

        Params:
            secret_token: Token de seguridad
        """
        try:
            if not self._validate_secret(secret_token):
                return {'success': False, 'error': 'Unauthorized'}

            db_name = request.env.cr.dbname
            service_name = f"odona-{db_name}"

            # Reiniciar servicio systemd
            cmd = f"systemctl restart {service_name}"

            _logger.info(f"🔄 Restarting service: {service_name}")

            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode == 0:
                _logger.info(f"✅ Service restarted")
                return {
                    'success': True,
                    'message': 'Instance restarted successfully'
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr.decode()
                }

        except Exception as e:
            _logger.error(f"Error restarting: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
