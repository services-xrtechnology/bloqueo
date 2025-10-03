# -*- coding: utf-8 -*-
import logging
from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    """
    Extender ir.attachment para controlar tamaño máximo de archivos según el plan.
    """
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Hook al crear attachment - validar tamaño según límites del plan.
        """
        try:
            # Límite absoluto del sistema (nadie puede exceder)
            ABSOLUTE_MAX_MB = 100

            # Obtener límite del plan desde parámetro local (sincronizado nocturnamente)
            config = self.env['ir.config_parameter'].sudo()
            max_mb_param = config.get_param('saas.plan.file_size_limit', False)

            if max_mb_param:
                # Usar límite sincronizado
                max_mb = int(max_mb_param)
            else:
                # Fallback: Consultar API si no hay parámetro
                limits = self.env['saas.plan.manager'].get_plan_limits()
                max_mb = limits.get('max_file_size_mb', 20)
                # Guardar para próximas veces
                if max_mb > 0:
                    config.set_param('saas.plan.file_size_limit', str(max_mb))

            # Validar cada archivo
            for vals in vals_list:
                file_size = vals.get('file_size', 0)

                if file_size > 0:
                    # Convertir a MB
                    size_mb = file_size / (1024 * 1024)

                    # Validar límite absoluto del sistema
                    if size_mb > ABSOLUTE_MAX_MB:
                        raise UserError(_(
                            '❌ Archivo Demasiado Grande\n\n'
                            'Tamaño del archivo: %.1f MB\n'
                            'Límite máximo del sistema: %s MB\n\n'
                            'Por favor reduce el tamaño del archivo.'
                        ) % (size_mb, ABSOLUTE_MAX_MB))

                    # Validar límite del plan (si no es ilimitado)
                    if max_mb > 0 and size_mb > max_mb:
                        raise UserError(_(
                            '⚠️ Archivo Excede Límite de tu Plan\n\n'
                            'Tamaño del archivo: %.1f MB\n'
                            'Tu plan permite máximo: %s MB\n\n'
                            '💡 Opciones:\n'
                            '• Reduce el tamaño del archivo\n'
                            '• Actualiza tu plan para mayor capacidad\n\n'
                            'Límite absoluto del sistema: 100MB'
                        ) % (size_mb, max_mb))

                    # Log para archivos grandes (pero permitidos)
                    if size_mb > 10:
                        _logger.info(f"📎 Large file uploaded: {size_mb:.1f}MB (limit: {max_mb}MB)")

        except UserError:
            raise
        except Exception as e:
            # Si falla consulta, permitir pero loggear
            _logger.error(f"Error checking file size limit: {str(e)}")
            _logger.warning("⚠️ Allowing file upload due to limit check failure")

        return super().create(vals_list)
