import hashlib
import json
import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.http import request
from werkzeug import urls

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    wipay_transaction_id = fields.Char(string='WiPay Transaction ID', readonly=True)
    wipay_status = fields.Char(string='WiPay Status', readonly=True)
    wipay_message = fields.Char(string='WiPay Message', readonly=True)
    wipay_hash = fields.Char(string='WiPay Hash', readonly=True)
    wipay_card = fields.Char(string='WiPay Card', readonly=True)

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'wipay':
            return res
        return {
            'api_url': '/payment/wipay/redirect',
            'reference': self.reference,
        }

    def _wipay_build_payload(self):
        self.ensure_one()
        provider = self.provider_id
        provider._wipay_validate_credentials()

        base_url = self.provider_id.get_base_url()
        response_url = urls.url_join(base_url, '/payment/wipay/return')
        partner = self.partner_id
        currency_name = self.currency_id.name
        if currency_name not in ('TTD', 'USD', 'JMD'):
            raise UserError(_('WiPay only supports TTD, USD, and JMD in this module.'))

        # WiPay order_id length differs by processor. Keep it short and unique.
        order_id = (self.reference or self.acquirer_reference or str(self.id)).replace('/', '-').replace(' ', '-')[:16]

        payload = {
            'account_number': provider.wipay_account_number,
            'avs': '1' if provider.wipay_avs else '0',
            'country_code': provider.wipay_country_code or 'TT',
            'currency': currency_name,
            'environment': provider._wipay_get_environment(),
            'fee_structure': provider.wipay_fee_structure or 'customer_pay',
            'method': 'credit_card',
            'order_id': order_id,
            'origin': (provider.wipay_origin or 'Spxcorp-Odoo')[:32],
            'response_url': response_url,
            'total': '%.2f' % self.amount,
            'version': '19.0.1.0.0',
            'name': partner.name or '',
            'email': partner.email or '',
            'phone': partner.phone or partner.mobile or '',
        }
        if provider.wipay_card_type:
            payload['card_type'] = provider.wipay_card_type
        # Store the full Odoo reference in data so we can recover it if needed.
        payload['data'] = json.dumps({'reference': self.reference, 'tx_id': self.id})
        return payload

    def _wipay_request_hosted_page(self):
        self.ensure_one()
        payload = self._wipay_build_payload()
        api_url = self.provider_id._wipay_get_api_url()
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        try:
            response = requests.post(api_url, data=payload, headers=headers, timeout=30)
            data = response.json()
        except Exception as exc:
            _logger.exception('WiPay hosted page request failed for transaction %s', self.reference)
            raise UserError(_('Could not connect to WiPay. Please try again. Details: %s') % exc)

        if response.status_code >= 400 or not data.get('url'):
            raise UserError(_('WiPay rejected the payment request: %s') % (data.get('message') or response.text))

        self.write({
            'wipay_transaction_id': data.get('transaction_id'),
            'provider_reference': data.get('transaction_id') or self.provider_reference,
        })
        return data['url']

    @classmethod
    def _get_tx_from_notification_data(cls, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'wipay':
            return tx
        order_id = notification_data.get('order_id')
        transaction_id = notification_data.get('transaction_id')
        domain = [('provider_code', '=', 'wipay')]
        if transaction_id:
            tx = cls.env['payment.transaction'].sudo().search(domain + ['|', ('wipay_transaction_id', '=', transaction_id), ('provider_reference', '=', transaction_id)], limit=1)
            if tx:
                return tx
        if order_id:
            tx = cls.env['payment.transaction'].sudo().search(domain + [('reference', 'ilike', order_id)], limit=1, order='id desc')
            if tx:
                return tx
        raise ValidationError(_('WiPay: no transaction found for notification data.'))

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != 'wipay':
            return

        status = notification_data.get('status')
        transaction_id = notification_data.get('transaction_id')
        returned_hash = notification_data.get('hash')
        total = notification_data.get('total') or '%.2f' % self.amount
        provider = self.provider_id

        values = {
            'wipay_transaction_id': transaction_id,
            'provider_reference': transaction_id or self.provider_reference,
            'wipay_status': status,
            'wipay_message': notification_data.get('message'),
            'wipay_hash': returned_hash,
            'wipay_card': notification_data.get('card'),
        }
        self.write(values)

        if status == 'success':
            if returned_hash and transaction_id and provider.wipay_api_key:
                expected = hashlib.md5((transaction_id + str(total) + provider.wipay_api_key).encode()).hexdigest()
                if expected != returned_hash:
                    self._set_error(_('WiPay hash validation failed.'))
                    return
            self._set_done()
        elif status == 'failed':
            self._set_canceled(_('WiPay payment failed: %s') % (notification_data.get('message') or 'Failed'))
        else:
            self._set_error(_('WiPay payment error: %s') % (notification_data.get('message') or 'Error'))
