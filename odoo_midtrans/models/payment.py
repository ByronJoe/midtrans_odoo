# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.http import request

class AcquirerMidtrans(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('midtrans', 'Midtrans')], ondelete = {'midtrans': 'set default'})
    midtrans_method = fields.Selection([('snap', 'SNAP')],string='Midtrans Method')
    midtrans_merchant_id = fields.Char('Midtrans Merchant ID',
            required_if_provider='midtrans', groups='base.group_user')
    midtrans_client_key = fields.Char('Midtrans Client Key',
            required_if_provider='midtrans', groups='base.group_user')
    midtrans_server_key = fields.Char('Midtrans Server Key',
            required_if_provider='midtrans', groups='base.group_user')

    @api.model
    def midtrans_form_generate_values(self, values):
        values['client_key'] = self.midtrans_client_key

        if not 'return_url' in values:
            values['return_url'] = '/'
        values['order'] = request.website.sale_get_order()

        # You must have currency IDR enabled
        amount = values['amount']
        currency = values['currency']
        currency_IDR = self.env.ref('base.IDR')
        assert currency_IDR.name == 'IDR'

        # Convert to IDR
        if currency.id != currency_IDR.id:
            values['amount'] = int(round(currency.compute(amount,currency_IDR)))
            values['currency'] = currency_IDR
            values['currency_id'] = currency_IDR.id
        else:
            values['amount'] = int(round(amount))

        return values

    def get_backend_endpoint(self):
        if self.state == 'test':
            return 'https://app.sandbox.midtrans.com/snap/v1/transactions'
        return 'https://app.midtrans.com/snap/v1/transactions'

    def get_status_url(self, reference):
        if self.state == 'test':
            return 'https://api.sandbox.midtrans.com/v2/' + reference + '/status'
        return 'https://api.midtrans.com/v2/' + reference + '/status'

    @api.model
    def _get_default_payment_method_id(self, code):
        if self.code != 'midtrans':
            return super()._get_default_payment_method_id(code)
        return self.env.ref('odoo_midtrans.payment_method_midtrans').id

class Transaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return midtrans-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'midtrans':
            return res

        order = self.env['sale.order'].sudo().search([('id','=',request.session['sale_order_id'])], limit=1)
        values={
            'return_url' : '/',
            'order_id' :order.id,
            'amount' : self.amount,
            'currency' : self.currency_id,
            'currency_id' : self.currency_id.id,
            'reference' : self.reference,
            'provider_id' : self.provider_id.id,
            'partner_first_name' : self.partner_id.name,
            'partner_email' : self.partner_id.email,
            'partner_phone' : self.partner_id.phone
        }

        # You must have currency IDR enabled
        amount= self.amount
        currency = self.currency_id
        currency_IDR = self.env.ref('base.IDR')
        assert currency_IDR.name == 'IDR'

        # Convert to IDR
        if currency.id != currency_IDR.id:
            values['amount'] = int(round(currency.compute(amount,currency_IDR)))
            values['currency'] = currency_IDR
            values['currency_id'] = currency_IDR.id
        else:
            values['amount'] = int(round(amount))

        return values

class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['midtrans'] = {'mode': 'unique', 'domain': [('type', '=', 'bank')]}
        return res