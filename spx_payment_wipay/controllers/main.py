import logging
from werkzeug import utils

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WiPayController(http.Controller):

    @http.route('/payment/wipay/redirect', type='http', auth='public', methods=['POST', 'GET'], csrf=False, website=True)
    def wipay_redirect(self, reference=None, **kwargs):
        if not reference:
            reference = kwargs.get('reference')
        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'wipay'),
        ], limit=1)
        if not tx:
            return request.redirect('/payment/status')
        hosted_url = tx._wipay_request_hosted_page()
        return utils.redirect(hosted_url)

    @http.route('/payment/wipay/return', type='http', auth='public', methods=['GET', 'POST'], csrf=False, website=True)
    def wipay_return(self, **data):
        _logger.info('WiPay return data: %s', data)
        try:
            tx = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('wipay', data)
            tx._process_notification_data(data)
        except Exception:
            _logger.exception('WiPay return processing failed.')
        return request.redirect('/payment/status')
