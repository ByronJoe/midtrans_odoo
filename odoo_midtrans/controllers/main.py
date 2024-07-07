from hashlib import sha512
import json
import logging
from odoo.exceptions import ValidationError
from odoo import http
from odoo.http import request
import requests
import base64
logger = logging.getLogger(__name__)

def _prune_dict(data):
    if isinstance(data, dict):
        return {key: _prune_dict(value)\
                for key, value in data.items() if value is not None}

    return data

class MidtransController(http.Controller):
    @http.route(['/shop/paymentmidtrans/transaction/',
        '/shop/paymentmidtrans/transaction/<int:so_id>',
        '/shop/paymentmidtrans/transaction/<int:so_id>/<string:access_token>'], type='json', auth="public", website=True)
    def payment_transaction(self, provider_id, save_token=False, so_id=None, access_token=None, token=None, **kwargs):
        """ Json method that creates a payment.transaction, used to create a
        transaction when the user clicks on 'pay now' button. After having
        created the transaction, the event continues and the user is redirected
        to the acquirer website.

        :param int provider_id: id of a payment.provider record. If not set the
                                user is redirected to the checkout page
        """
        # Ensure a payment acquirer is selected
        if not provider_id:
            return False
        else:
            return True

    @http.route('/midtrans/get_snap_js', auth='public', type='json')
    def get_snap_js(self, **post):
        acquirer = request.env.ref('odoo_midtrans.payment_acquirer_midtrans')
        response = {
            'production': '0',
            'client_key': acquirer.midtrans_client_key
        }
        if acquirer:
            response = {
                'production': '1' if acquirer.state == 'enabled' else '0',
                'client_key': acquirer.midtrans_client_key
            }
        else:
            raise ValidationError('(get_snap_js) provider_id is required.')
        return response

    @http.route('/midtrans/get_token', auth='public', type='json')
    def get_token(self, **post):
        # Check Provider
        acquirer = request.env.ref('odoo_midtrans.payment_acquirer_midtrans')
        provider_id = post.get('provider_id') or acquirer.id
        if not provider_id:
            raise ValidationError('provider_id is required.')
        try:
            provider_id = int(provider_id)
        except (ValueError, TypeError):
            raise ValidationError('Invalid provider_id.')
        # Check Sale Order
        order_id = post.get('order_id')
        if not order_id:
            raise ValidationError('order_id is required.')
        try:
            order_id = int(order_id)
        except (ValueError, TypeError):
            raise ValidationError('Invalid order_id.')
        order = request.env['sale.order'].sudo().browse(order_id)
        # Check Amount
        amount = post.get('amount')
        if not amount:
            raise ValidationError('amount is required.')
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            raise ValidationError('Invalid amount.')
        # Check Reference
        reference = post.get('reference')
        if not reference:
            raise ValidationError('reference is required.')
        # Check Return URL
        return_url = post.get('return_url')
        if not return_url:
            raise ValidationError('return_url is required.')
        response = {'return_url': return_url}

        AUTH_STRING = base64.b64encode((acquirer.midtrans_server_key + ':').encode('utf-8'))
        AUTH_STRING = 'Basic ' + str(AUTH_STRING.decode("utf-8"))

        headers = {
            'accept': 'application/json',
            'type': 'application/json',
            'auth': AUTH_STRING,
        }

        payload = {
            'transaction_details': {
                'order_id': reference,
                'gross_amount': amount
            },
            'customer_details': {
                'first_name': post.get('partner_first_name'),
                'last_name': post.get('partner_last_name'),
                'email': post.get('partner_email'),
                'phone': post.get('partner_phone'),
            },
            'credit_card': {
                'secure': True,
                'save_card': True,
            }
        }
        response['endpoint'] = acquirer.get_backend_endpoint()
        payload = _prune_dict(payload)
        resp = requests.post(acquirer.get_backend_endpoint(), json=payload,
                headers=headers, auth=(acquirer.midtrans_server_key, ''))
        response['csrf_token'] = post.get('csrf_token')
        if resp.status_code >= 200 and resp.status_code < 300:
            reply = resp.json()
            response['snap_token'] = reply['token']
            response['redirect_url'] = reply['redirect_url']
            response['client_key'] = acquirer.midtrans_client_key
            if acquirer.state == 'test':
                response['production'] = '0'
            else:
                response['production'] = '1'
        elif resp.text:
            reply = resp.json()
            if 'error_messages' in reply:
                response['snap_errors'] = resp.json().get('error_messages', [])

            else:
                logger.warn('Unexpected Midtrans response: %i: %s',resp.status_code, resp.text)
        else:
            response['snap_errors'] = ['Unknown error.']
        return response

    @http.route('/midtrans/validate', auth='public', type='json')
    def payment_validate(self, **post):
        reference = post.get('reference')
        if not reference:
            raise ValidationError('reference is required.')

        status = post.get('transaction_status')
        if not status:
            raise ValidationError('transaction_status is required.')

        message = post.get('message')
        if not message:
            raise ValidationError('message is required.')

        tx = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference)], limit=1)

        if (status == 'pending' and tx.state == 'draft') or\
                (status == 'done' and tx.state != 'done') or\
                status == 'error':
            tx_message = str(tx.state_message) if tx.state_message else ''
            tx.write({'state': status, 'state_message': tx_message + '\n\n' + message})

        orders = tx.sale_order_ids
        for order in orders:
            if status == 'done' and order.state not in  ('done', 'sale'):
                order.sudo().action_confirm()
            elif status == 'pending' and order.state not in ('done', 'sale', 'sent'):
                order.action_quotation_sent()

    @http.route(['/midtrans/confirmation'], auth='public', type="http", website=True, sitemap=False, csrf=False)
    def midtrans_confirmation(self, response, callback_key, **post):
        response = json.loads(response)
        request.session['session_token'] = response['custom_field1']
        sale_order_id = response['order_id'].split("-")[0]
        if sale_order_id:
            order = request.env['sale.order'].sudo().search([('name', '=', sale_order_id)])
            return request.render("website_sale.confirmation", {'order': order, 'csrf': response['custom_field1']})
        else:
            return request.redirect('/shop')

    @http.route('/midtrans/notification', auth='public', csrf=False, type='json')
    def midtrans_notification(self, **post):
        post = request.jsonrequest

        reference = post.get('order_id')
        if not reference:
            raise ValidationError('order_id is required.')
        
        code = post.get('status_code')
        if not code:
            raise ValidationError('status_code is required.')

        tx_status = post.get('transaction_status')
        if not tx_status:
            raise ValidationError('transaction_status is required.')

        if code == '200':
            if tx_status in ('settlement', 'refund', 'chargeback', 'partial_refund', 'partial_chargeback'):
                status = 'done'
            elif tx_status in ('cancel'):
                status = 'cancel'
            else:
                status = 'pending'
        elif code == '201':
            status = 'pending'
        else:
            status = 'error'

        message = post.get('status_message')
        if not message:
            raise ValidationError('status_message is required.')

        tx = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference)], limit=1)

        ## Security check
        acquirer = tx.provider_id
        signature_data = post['order_id'] + post['status_code'] +\
                post['gross_amount'] + acquirer.midtrans_server_key
        assert post['signature_key'] == sha512(signature_data.encode('utf-8')).hexdigest()

        ## Update database
        if (status == 'pending' and tx.state in ('draft', 'pending')) or\
                status in ('done', 'error', 'cancel'):
            tx_message = str(tx.state_message) if tx.state_message else ''
            tx.write({'state': status, 'state_message': tx_message + '\n\n' + message})

        orders = tx.sale_order_ids
        for order in orders:
            if status == 'done' and order.state not in  ('done', 'sale'):
                order.sudo().action_confirm()
            elif status == 'pending' and order.state not in ('done', 'sale','sent'):
                order.action_quotation_sent()
        return {}

    @http.route(['/shop/selesai'], type='http', auth="public", website=True, csrf=False)
    def payment_selesai(self):
        return request.redirect('/shop')
