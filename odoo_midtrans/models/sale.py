from odoo.exceptions import ValidationError
import requests
import base64
from odoo import fields, models
from datetime import datetime

def _prune_dict(data):
    if isinstance(data, dict):
        return {key: _prune_dict(value)\
                for key, value in data.items() if value is not None}
    return data

class MidtransStatus(models.TransientModel):
    _name = 'midtrans.wizard'

    name = fields.Char(default='Midtrans Payment Status')
    status = fields.Char('Status')
    message = fields.Char('Message')
    payment_type = fields.Char('Payment Type')

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def update_midtrans_status(self, post):
        if post.get('status_code','000') != '000':
            status_message = post.get('status_message','')
            tx_status = post.get('transaction_status','')
            code = post.get('status_code','')
            payment_type = post.get('payment_type','')

            message = '\n\n====' + str(datetime.today())
            message += '\nStatus : ' + tx_status
            message += '\nPayment Type : ' + payment_type
            message += '\nMessage : ' + status_message

            if code == '200':
                if tx_status in ('settlement', 'refund', 'chargeback',
                        'partial_refund', 'partial_chargeback'):
                    status = 'done'
                elif tx_status in ('cancel'):
                    status = 'cancel'
                else:
                    status = 'pending'
            elif code == '201':
                status = 'pending'
            else:
                status = 'error'

            self.write({
                'state': status,
                'state_message': str(self.state_message) + str(message)
            })

            orders = self.sale_order_ids
            for order in orders:
                if status == 'done' and order.state not in  ('done', 'sale'):
                    order.sudo().action_confirm()
                elif status == 'pending' and order.state not in ('done', 'sale', 'sent'):
                    order.write({'state': 'sent'})
                elif status in ['error', 'cancel'] and order.state not in ('cancel'):
                    order.write({'state': 'cancel'})

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def get_midtrans_payment_status(self, reference):
        acquirer = self.env.ref('odoo_midtrans.payment_acquirer_midtrans')
        if acquirer:
            AUTH_STRING = base64.b64encode((acquirer.midtrans_server_key + ':').encode('utf-8'))
            AUTH_STRING = 'Basic ' + str(AUTH_STRING.decode("utf-8"))
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': AUTH_STRING,
            }
            resp = requests.get(acquirer.get_status_url(reference),headers=headers)
            return resp
        else:
            return {"status_code" : "000"}

    def check_midtrans_payment_status(self, show_message=True):
        for record in self:
            payments = self.env['payment.transaction'].search([
                ('sale_order_ids','=', record.id),
                ('provider_code','=','midtrans')], limit=1, order='id desc')
            if payments:
                for payment in payments:
                    status = record.get_midtrans_payment_status(payment.reference).json()
                    if record.state in ['sent', 'sale']:
                        payment.update_midtrans_status(status)
                    if show_message and status.get('status_code','000') != '000':
                        wizard = self.env['midtrans.wizard'].create({
                                'message' : status.get('status_message',''),
                                'status' : status.get('transaction_status',''),
                                'payment_type' : status.get('payment_type','')
                            })
                        return {
                            'type': 'ir.actions.act_window',
                            'name': 'Midtrans Payment Status',
                            'view_type': 'form',
                            'view_mode': 'form',
                            'res_model': 'midtrans.wizard',
                            'target': 'new',
                            'res_id': wizard.id,
                            'context': {}
                        }
            else:
                if show_message:
                    raise ValidationError('Tidak ada pembayaran dengan Midtrans')

    def run_check_midtrans_payment_status(self):
        orders = self.search([('state','=','sent')],order='id desc')
        for order in orders:
            order.check_midtrans_payment_status(show_message=False)

    def has_to_be_signed(self, include_draft=False):
        res = super(SaleOrder, self).has_to_be_signed(include_draft)
        return False

    def has_to_be_paid(self, include_draft=False):
        res = super(SaleOrder, self).has_to_be_paid(include_draft)
        return False

class Currency(models.Model):
    _inherit = 'res.currency'

    def write(self, vals):
        midtrans = self.env.ref('odoo_midtrans.payment_acquirer_midtrans')
        currency_IDR = self.env.ref('base.IDR')
        for rec in self:
            if rec == currency_IDR and 'active' in vals and not vals['active'] and midtrans.state in ['enabled', 'test']:
                raise ValidationError('Tidak dapat di Non Aktifkan. Module Odoo Midtrans memperlukan currency IDR untuk menghitung kurs')
        return super(Currency, self).write(vals)
