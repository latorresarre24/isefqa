# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from lxml import etree

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.purchase.controllers.portal import CustomerPortal


class PurchaseOrderAttachments(CustomerPortal):

    @http.route(['/purchase/order_attachments/<int:order_id>'],
                type='http', auth="user", methods=['POST'], website=True)
    def attach_files(self, order_id, access_token=None, **post):
        try:
            order_sudo = self._document_check_access('purchase.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        att = request.env['ir.attachment']
        xml = post.get('xml')
        try:
            errors, filename = att.parse_xml(xml, order_sudo)
        except etree.XMLSyntaxError as e:
            error = _("\nXML syntax error. The XML is not correctly formed. Please check the CFDI XML: \n\n%s") % e.msg
            return request.redirect('%s&upload_errors=%s' % (order_sudo.get_portal_url(), error))

        if errors.get('wrongfiles'):
            return request.redirect('%s&upload_errors=%s' % (
                order_sudo.get_portal_url(), order_sudo.process_errors(errors.get('wrongfiles'))))
        order_sudo.insert_attachment(post, filename)
        return request.redirect(order_sudo.get_portal_url() + '&upload_success=1')


class MxCustomerPortal(CustomerPortal):

    @http.route(['/my/purchase/<int:order_id>'], type='http', auth="public", website=True)
    def portal_my_purchase_order(self, order_id=None, access_token=None, **kw):
        res = super().portal_my_purchase_order(order_id, access_token, **kw)
        res.qcontext['upload_success'] = kw.get('upload_success', False)
        res.qcontext['upload_errors'] = kw.get('upload_errors', False).split('\n') if (
            kw.get('upload_errors', False)) else False
        return res
