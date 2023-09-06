import base64
import logging

from odoo import models

_logger = logging.getLogger(__name__)

try:
    from OpenSSL import crypto
except ImportError:
    _logger.warning(
        "OpenSSL library not found. If you plan to use l10n_mx_edi, "
        "please install the library from https://pypi.python.org/pypi/pyOpenSSL"
    )


class Certificate(models.Model):
    _inherit = "l10n_mx_edi.certificate"

    def get_encrypted_cadena(self, cadena, encryption_type=False):
        """Encrypt the cadena using the private key."""
        self.ensure_one()
        if not encryption_type:
            return super().get_encrypted_cadena(cadena)
        key_pem = self.get_pem_key(self.key, self.password)
        private_key = crypto.load_privatekey(crypto.FILETYPE_PEM, bytes(key_pem))
        cadena_crypted = crypto.sign(private_key, bytes(cadena.encode()), encryption_type)
        return base64.b64encode(cadena_crypted)
