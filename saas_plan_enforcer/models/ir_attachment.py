# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    """
    Extender ir.attachment para controlar límite absoluto de archivos.

    NOTA: El límite del plan se controla vía web.max_file_upload_size (Odoo nativo).
    Este hook solo valida el límite ABSOLUTO del sistema (100MB).
    """
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Hook al crear attachment - validar límite absoluto del sistema.
        El límite del plan ya lo controla Odoo con web.max_file_upload_size.
        """
        try:
            # Límite absoluto del sistema (nadie puede exceder, ni admin)
            ABSOLUTE_MAX_MB = 100

            # Validar cada archivo
            for vals in vals_list:
                file_size = vals.get('file_size', 0)

                if file_size > 0:
                    # Convertir a MB
                    size_mb = file_size / (1024 * 1024)

                    # Validar solo límite absoluto del sistema
                    if size_mb > ABSOLUTE_MAX_MB:
                        raise UserError(_(
                            '❌ Archivo Demasiado Grande\n\n'
                            'Tamaño del archivo: %.1f MB\n'
                            'Límite máximo del sistema: %s MB\n\n'
                            'Este límite aplica para todos los usuarios.\n'
                            'Por favor, reduce el tamaño del archivo.'
                        ) % (size_mb, ABSOLUTE_MAX_MB))

                    # Log para archivos grandes (pero permitidos)
                    if size_mb > 50:
                        _logger.warning(f"📎 Very large file uploaded: {size_mb:.1f}MB (absolute limit: {ABSOLUTE_MAX_MB}MB)")

        except UserError:
            raise
        except Exception as e:
            # Si falla validación, permitir pero loggear
            _logger.error(f"Error checking file size limit: {str(e)}")
            _logger.warning("⚠️ Allowing file upload due to validation failure")

        return super().create(vals_list)
