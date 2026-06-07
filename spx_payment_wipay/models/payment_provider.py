import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('wipay', 'WiPay')], ondelete={'wipay': 'set default'})

    wipay_account_number = fields.Char(
        string='WiPay Account Number',
        help='Your LIVE WiPay account number. In sandbox, WiPay uses 1234567890.'
    )
    wipay_api_key = fields.Char(
        string='WiPay API Key',
        groups='base.group_system',
        help='Used to validate the MD5 hash returned by WiPay. Sandbox API key is 123.'
    )
    wipay_country_code = fields.Selection([
        ('TT', 'Trinidad & Tobago'),
        ('JM', 'Jamaica'),
        ('BB', 'Barbados'),
        ('GY', 'Guyana'),
    ], string='WiPay Country', default='TT')
    wipay_fee_structure = fields.Selection([
        ('customer_pay', 'Customer Pays Fee'),
        ('merchant_absorb', 'Merchant Absorbs Fee'),
        ('split', 'Split Fee'),
    ], string='Fee Structure', default='customer_pay', required=True)
    wipay_avs = fields.Boolean(string='Enable AVS', default=False)
    wipay_card_type = fields.Selection([
        ('', 'Let Customer Select'),
        ('visa', 'Visa'),
        ('mastercard', 'Mastercard'),
    ], string='Card Type', default='')
    wipay_origin = fields.Char(string='Origin', default='Spxcorp-Odoo', help='Custom origin sent to WiPay. Must be 1-32 characters and begin/end alphanumeric.')

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)
        if currency_id:
            currency = self.env['res.currency'].browse(currency_id)
            supported = ('TTD', 'USD', 'JMD')
            providers = providers.filtered(lambda p: p.code != 'wipay' or currency.name in supported)
        return providers

    def _wipay_get_api_url(self):
        self.ensure_one()
        base = {
            'TT': 'https://tt.wipayfinancial.com/plugins/payments/request',
            'JM': 'https://jm.wipayfinancial.com/plugins/payments/request',
            'BB': 'https://bb.wipayfinancial.com/plugins/payments/request',
            'GY': 'https://gy.wipayfinancial.com/plugins/payments/request',
        }.get(self.wipay_country_code or 'TT')
        return base

    def _wipay_get_environment(self):
        self.ensure_one()
        return 'sandbox' if self.state == 'test' else 'live'

    def _wipay_validate_credentials(self):
        self.ensure_one()
        if self.code != 'wipay':
            return
        if not self.wipay_account_number:
            raise UserError(_('Please enter the WiPay Account Number.'))
        if not self.wipay_api_key:
            raise UserError(_('Please enter the WiPay API Key.'))
        if not self.wipay_country_code:
            raise UserError(_('Please select the WiPay Country.'))
