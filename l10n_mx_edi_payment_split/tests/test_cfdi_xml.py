from unittest.mock import patch
from datetime import timedelta
from freezegun import freeze_time

from odoo import fields
from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon, mocked_l10n_mx_edi_pac
from odoo.tests import tagged, Form
from odoo.tools import mute_logger


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSplitPayment(TestMxEdiCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_mx.mx_coa', edi_format_ref='l10n_mx_edi.edi_cfdi_3_3'):
        super().setUpClass(chart_template_ref=chart_template_ref, edi_format_ref=edi_format_ref)

        cls.today = fields.Date.today()

        # Rename EUR to something else and create a new EUR with defined rates.
        # Done like this because currencies should be fetched by name, not by xml_id
        cls.env.ref('base.EUR').name = 'FEUR'
        cls.env['res.currency'].flush(['name'])
        cls.fake_eur_data = cls.setup_multi_currency_data(default_values={
            'name': 'EUR',
            'symbol': '€',
            'rounding': 0.01,
            'l10n_mx_edi_decimal_places': 2,
        }, rate2016=6.0, rate2017=4.0)

        cls.fake_usd_data['rates'][0].inverse_company_rate = 20
        cls.fake_usd_data['rates'][1].inverse_company_rate = 25

        cls.fake_eur_data['rates'][0].inverse_company_rate = 22.50
        cls.fake_eur_data['rates'][1].inverse_company_rate = 24.75

        cls.journal_mxn = (
            cls.env['account.journal']
            .with_context(default_company_id=cls.invoice.company_id.id)
            .create({
                'name': 'MXN Journal Bank',
                'code': 'JBMXN',
                'type': 'bank',
                'currency_id': cls.invoice.company_id.currency_id.id,
            })
        )
        cls.journal_usd = (
            cls.env['account.journal']
            .with_context(default_company_id=cls.invoice.company_id.id)
            .create({
                'name': 'USD Journal Bank',
                'code': 'JBUSD',
                'type': 'bank',
                'currency_id': cls.fake_usd_data['currency'].id,
            })
        )

    def create_payment(self, invoices, payment_type, journal, amount=False, date=False, custom_rate=None,
                       account_id=None, csv=None, handling='reconcile'):
        """Creating payment using wizard"""
        ctx = {
            'active_model': 'account.move', 'active_ids': invoices.ids,
            'default_l10n_mx_edi_force_generate_cfdi': True}
        date = date or (self.today + timedelta(days=1))
        register = Form(self.env['account.split.payment.register'].with_context(**ctx))
        register.payment_date = date
        register.journal_id = journal
        if csv:
            register.csv_file = csv
        if amount:
            register.amount = amount
        if account_id:
            register.writeoff_account_id = account_id
            register.payment_difference_handling = handling
        payment = register.save()
        if custom_rate:
            payment.write({'custom_rate': custom_rate})
        return payment

    def test_payment_mxn(self):
        with freeze_time(self.frozen_today), \
             mute_logger('py.warnings'), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_invoice_pac',
                   new=mocked_l10n_mx_edi_pac), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_payment_pac',
                   new=mocked_l10n_mx_edi_pac):

            inv_mxn = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.invoice.company_id.currency_id.id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 100})],
            })
            inv_usd = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_usd_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 5.0})],
            })
            inv_eur = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_eur_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 4.4})],
            })
            invoices = (inv_mxn + inv_usd + inv_eur)
            invoices.action_post()

            payment = self.create_payment(invoices, 'outbound', self.journal_mxn, date='2017-01-01')
            pline_mxn = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_mxn.currency_id)
            pline_usd = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_usd.currency_id)
            pline_eur = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_eur.currency_id)

            pline_mxn.payment_currency_amount = 90
            pline_usd.payment_currency_amount = 80
            pline_usd.payment_amount = 4
            pline_eur.payment_currency_amount = 69
            pline_eur.payment_amount = 3
            payment._compute_from_lines()
            payment.amount = payment.company_currency_amount

            self.assertEqual(payment.payment_difference, 0)
            self.assertEqual(payment.company_difference, 0)

            payment_record = payment._create_split_payments()

            self.assertAlmostEqual(pline_mxn.invoice_id.amount_residual, 10)
            self.assertAlmostEqual(pline_usd.invoice_id.amount_residual, 1)
            self.assertAlmostEqual(pline_eur.invoice_id.amount_residual, 1.4)

            receivable_lines = payment_record.line_ids.filtered(lambda x: x.account_id.internal_type == 'receivable')
            line_mxn = receivable_lines.filtered(lambda x: x.currency_id == inv_mxn.currency_id)
            line_usd = receivable_lines.filtered(lambda x: x.currency_id == inv_usd.currency_id)
            line_eur = receivable_lines.filtered(lambda x: x.currency_id == inv_eur.currency_id)
            self.assertEqual(line_mxn.balance, -90)
            self.assertEqual(line_mxn.amount_currency, -90)
            self.assertEqual(line_usd.balance, -80)
            self.assertEqual(line_usd.amount_currency, -4)
            self.assertEqual(line_eur.balance, -69)
            self.assertEqual(line_eur.amount_currency, -3)

            self._process_documents_web_services(inv_mxn)
            inv_mxn.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(inv_usd)
            inv_usd.l10n_mx_edi_cfdi_uuid = '567891234'
            self._process_documents_web_services(inv_eur)
            inv_eur.l10n_mx_edi_cfdi_uuid = '987654321'

            generated_files = self._process_documents_web_services(payment_record.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">1</attribute>
                        <attribute name="Serie">JBMXN/2017/01/</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos Version="2.0">
                                <Totales MontoTotalPagos="239.00"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    FormaDePagoP="99" MonedaP="MXN" Monto="239.00" TipoCambioP="1"
                                    NumOperacion="INV/2016/00001 INV/2016/00002 INV/2016/00003">
                                        <DoctoRelacionado
                                            IdDocumento="123456789" Folio="1" Serie="INV/2016/"
                                            MonedaDR="MXN" NumParcialidad="1" ObjetoImpDR="01" EquivalenciaDR="1"
                                            ImpSaldoAnt="100.00" ImpPagado="90.00" ImpSaldoInsoluto="10.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="0.050000"
                                            IdDocumento="567891234" Folio="2" Serie="INV/2016/"
                                            MonedaDR="USD" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="5.00" ImpPagado="4.00" ImpSaldoInsoluto="1.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="0.043478"
                                            IdDocumento="987654321" Folio="3" Serie="INV/2016/"
                                            MonedaDR="EUR" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="4.40" ImpPagado="3.00" ImpSaldoInsoluto="1.40"/>
                                    </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

            # Let's do a second payment in split to fully pay all invoices.
            # This time the wizard default values are to be used.

            payment = self.create_payment(invoices, 'outbound', self.journal_mxn, date='2017-01-01')
            pline_mxn = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_mxn.currency_id)
            pline_usd = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_usd.currency_id)
            pline_eur = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_eur.currency_id)

            self.assertEqual(payment.amount, 69.65)
            self.assertEqual(payment.payment_difference, 0)
            self.assertEqual(payment.company_difference, 0)

            payment_record = payment._create_split_payments()

            self.assertEqual(pline_mxn.invoice_id.amount_residual, 0)
            self.assertEqual(pline_usd.invoice_id.amount_residual, 0)
            self.assertEqual(pline_eur.invoice_id.amount_residual, 0)

            receivable_lines = payment_record.line_ids.filtered(lambda x: x.account_id.internal_type == 'receivable')
            line_mxn = receivable_lines.filtered(lambda x: x.currency_id == inv_mxn.currency_id)
            line_usd = receivable_lines.filtered(lambda x: x.currency_id == inv_usd.currency_id)
            line_eur = receivable_lines.filtered(lambda x: x.currency_id == inv_eur.currency_id)
            self.assertEqual(line_mxn.balance, -10)
            self.assertEqual(line_mxn.amount_currency, -10)
            self.assertEqual(line_usd.balance, -25)
            self.assertEqual(line_usd.amount_currency, -1)
            self.assertEqual(line_eur.balance, -34.65)
            self.assertEqual(line_eur.amount_currency, -1.4)

            self._process_documents_web_services(inv_mxn)
            inv_mxn.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(inv_usd)
            inv_usd.l10n_mx_edi_cfdi_uuid = '567891234'
            self._process_documents_web_services(inv_eur)
            inv_eur.l10n_mx_edi_cfdi_uuid = '987654321'

            generated_files = self._process_documents_web_services(payment_record.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">2</attribute>
                        <attribute name="Serie">JBMXN/2017/01/</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos Version="2.0">
                                <Totales MontoTotalPagos="69.65"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    FormaDePagoP="99" MonedaP="MXN" Monto="69.65" TipoCambioP="1"
                                    NumOperacion="INV/2016/00001 INV/2016/00002 INV/2016/00003">
                                        <DoctoRelacionado
                                            EquivalenciaDR="1" IdDocumento="123456789" Folio="1" Serie="INV/2016/"
                                            MonedaDR="MXN" NumParcialidad="2" ObjetoImpDR="01"
                                            ImpSaldoAnt="10.00" ImpPagado="10.00" ImpSaldoInsoluto="0.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="0.040000"
                                            IdDocumento="567891234" Folio="2" Serie="INV/2016/"
                                            MonedaDR="USD" NumParcialidad="2" ObjetoImpDR="01"
                                            ImpSaldoAnt="1.00" ImpPagado="1.00" ImpSaldoInsoluto="0.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="0.040404"
                                            IdDocumento="987654321" Folio="3" Serie="INV/2016/"
                                            MonedaDR="EUR" NumParcialidad="2" ObjetoImpDR="01"
                                            ImpSaldoAnt="1.40" ImpPagado="1.40" ImpSaldoInsoluto="0.00"/>
                                    </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_usd_one_payment_default_rate(self):
        with freeze_time(self.frozen_today), \
             mute_logger('py.warnings'), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_invoice_pac',
                   new=mocked_l10n_mx_edi_pac), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_payment_pac',
                   new=mocked_l10n_mx_edi_pac):

            inv_mxn = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.invoice.company_id.currency_id.id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 100})],
            })
            inv_usd = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_usd_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 5.0})],
            })
            inv_eur = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_eur_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 4.4})],
            })
            invoices = (inv_mxn + inv_usd + inv_eur)
            invoices.action_post()

            payment = self.create_payment(invoices, 'outbound', self.journal_usd, date='2017-01-01')
            pline_mxn = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_mxn.currency_id)
            pline_usd = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_usd.currency_id)
            pline_eur = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_eur.currency_id)

            self.assertEqual(payment.payment_difference, 0)
            self.assertEqual(payment.company_difference, 0)

            payment_record = payment._create_split_payments()

            self.assertAlmostEqual(pline_mxn.amount, 100)
            self.assertAlmostEqual(pline_mxn.payment_amount, 100)
            self.assertAlmostEqual(pline_mxn.payment_currency_amount, 4)
            self.assertAlmostEqual(pline_mxn.company_currency_amount, 100)
            self.assertAlmostEqual(pline_usd.amount, 5)
            self.assertAlmostEqual(pline_usd.payment_amount, 5)
            self.assertAlmostEqual(pline_usd.payment_currency_amount, 5)
            self.assertAlmostEqual(pline_usd.company_currency_amount, 125)
            self.assertAlmostEqual(pline_eur.amount, 4.4)
            self.assertAlmostEqual(pline_eur.payment_amount, 4.4)
            self.assertAlmostEqual(pline_eur.payment_currency_amount, 4.36)
            self.assertAlmostEqual(pline_eur.company_currency_amount, 108.9)

            receivable_lines = payment_record.line_ids.filtered(lambda x: x.account_id.internal_type == 'receivable')
            line_mxn = receivable_lines.filtered(lambda x: x.name == inv_mxn.name)
            line_usd = receivable_lines.filtered(lambda x: x.name == inv_usd.name)
            line_eur = receivable_lines.filtered(lambda x: x.name == inv_eur.name)
            self.assertEqual(line_mxn.balance, -100)
            self.assertEqual(line_mxn.amount_currency, -4)
            self.assertEqual(line_usd.balance, -125)
            self.assertEqual(line_usd.amount_currency, -5)
            self.assertEqual(line_eur.balance, -108.9)
            self.assertEqual(line_eur.amount_currency, -4.4)

            self._process_documents_web_services(inv_mxn)
            inv_mxn.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(inv_usd)
            inv_usd.l10n_mx_edi_cfdi_uuid = '567891234'
            self._process_documents_web_services(inv_eur)
            inv_eur.l10n_mx_edi_cfdi_uuid = '987654321'

            generated_files = self._process_documents_web_services(payment_record.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">1</attribute>
                        <attribute name="Serie">JBUSD/2017/01/</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos Version="2.0">
                                <Totales MontoTotalPagos="334.00"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    FormaDePagoP="99" MonedaP="USD"
                                    TipoCambioP="25.000000" Monto="13.36"
                                    NumOperacion="INV/2016/00001 INV/2016/00002 INV/2016/00003">
                                        <DoctoRelacionado
                                            EquivalenciaDR="25.000000"
                                            IdDocumento="123456789" Folio="1" Serie="INV/2016/"
                                            MonedaDR="MXN" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="100.00" ImpPagado="100.00" ImpSaldoInsoluto="0.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="1" IdDocumento="567891234" Folio="2" Serie="INV/2016/"
                                            MonedaDR="USD" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="5.00" ImpPagado="5.00" ImpSaldoInsoluto="0.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="1.009174"
                                            IdDocumento="987654321" Folio="3" Serie="INV/2016/"
                                            MonedaDR="EUR" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="4.40" ImpPagado="4.40" ImpSaldoInsoluto="0.00"/>
                                    </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_usd_one_payment_custom_rate_at_line(self):
        with freeze_time(self.frozen_today), \
             mute_logger('py.warnings'), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_invoice_pac',
                   new=mocked_l10n_mx_edi_pac), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_payment_pac',
                   new=mocked_l10n_mx_edi_pac):

            inv_mxn = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.invoice.company_id.currency_id.id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 100})],
            })
            inv_usd = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_usd_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 5.0})],
            })
            inv_eur = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_eur_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 4.4})],
            })
            invoices = (inv_mxn + inv_usd + inv_eur)
            invoices.action_post()

            payment = self.create_payment(invoices, 'outbound', self.journal_usd, date='2017-01-01')
            pline_mxn = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_mxn.currency_id)
            pline_usd = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_usd.currency_id)
            pline_eur = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_eur.currency_id)

            pline_mxn.payment_currency_amount = 3
            pline_mxn.payment_amount = 72
            payment._compute_from_lines()
            payment.amount = payment.company_currency_amount

            self.assertEqual(payment.payment_difference, 0)
            self.assertEqual(payment.company_difference, 0)

            payment_record = payment._create_split_payments()

            self.assertAlmostEqual(pline_mxn.amount, 100)
            self.assertAlmostEqual(pline_mxn.payment_amount, 72)
            self.assertAlmostEqual(pline_mxn.payment_currency_amount, 3)
            self.assertAlmostEqual(pline_mxn.company_currency_amount, 72)
            self.assertAlmostEqual(pline_usd.amount, 5)
            self.assertAlmostEqual(pline_usd.payment_amount, 5)
            self.assertAlmostEqual(pline_usd.payment_currency_amount, 5)
            self.assertAlmostEqual(pline_usd.company_currency_amount, 125)
            self.assertAlmostEqual(pline_eur.amount, 4.4)
            self.assertAlmostEqual(pline_eur.payment_amount, 4.4)
            self.assertAlmostEqual(pline_eur.payment_currency_amount, 4.36)
            self.assertAlmostEqual(pline_eur.company_currency_amount, 108.9)

            receivable_lines = payment_record.line_ids.filtered(lambda x: x.account_id.internal_type == 'receivable')
            line_mxn = receivable_lines.filtered(lambda x: x.name == inv_mxn.name)
            line_usd = receivable_lines.filtered(lambda x: x.name == inv_usd.name)
            line_eur = receivable_lines.filtered(lambda x: x.name == inv_eur.name)
            self.assertEqual(line_mxn.balance, -72)
            self.assertEqual(line_mxn.amount_currency, -3)
            self.assertEqual(line_usd.balance, -125)
            self.assertEqual(line_usd.amount_currency, -5)
            self.assertEqual(line_eur.balance, -108.9)
            self.assertEqual(line_eur.amount_currency, -4.4)

            self._process_documents_web_services(inv_mxn)
            inv_mxn.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(inv_usd)
            inv_usd.l10n_mx_edi_cfdi_uuid = '567891234'
            self._process_documents_web_services(inv_eur)
            inv_eur.l10n_mx_edi_cfdi_uuid = '987654321'

            generated_files = self._process_documents_web_services(payment_record.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">1</attribute>
                        <attribute name="Serie">JBUSD/2017/01/</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos Version="2.0">
                                <Totales MontoTotalPagos="309.00"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    FormaDePagoP="99" MonedaP="USD"
                                    TipoCambioP="25.000000" Monto="12.36"
                                    NumOperacion="INV/2016/00001 INV/2016/00002 INV/2016/00003">
                                        <DoctoRelacionado
                                            EquivalenciaDR="24.000000"
                                            IdDocumento="123456789" Folio="1" Serie="INV/2016/"
                                            MonedaDR="MXN" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="100.00" ImpPagado="72.00" ImpSaldoInsoluto="28.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="1" IdDocumento="567891234" Folio="2" Serie="INV/2016/"
                                            MonedaDR="USD" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="5.00" ImpPagado="5.00" ImpSaldoInsoluto="0.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="1.009174"
                                            IdDocumento="987654321" Folio="3" Serie="INV/2016/"
                                            MonedaDR="EUR" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="4.40" ImpPagado="4.40" ImpSaldoInsoluto="0.00"/>
                                    </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_payment_usd_custom_rate_at_line_odoo_signing_way(self):
        # Be careful: Signing a Payment that was split with Original Odoo
        # method of retrieving values leads too  Strange New Worlds.
        # Checking out here: Left With Odoo / Right with Odoo signing way
        # https://git.vauxoo.com/vauxoo/mexico/uploads/f1027d1bed5c0b14f4d9fc729a6fe4a0/Odoo_l10n_mx_edi_sign.png
        with freeze_time(self.frozen_today), \
             mute_logger('py.warnings'), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_invoice_pac',
                   new=mocked_l10n_mx_edi_pac), \
             patch('odoo.addons.l10n_mx_edi.models.account_edi_format.AccountEdiFormat._l10n_mx_edi_post_payment_pac',
                   new=mocked_l10n_mx_edi_pac):

            inv_mxn = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.invoice.company_id.currency_id.id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 100})],
            })
            inv_usd = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_usd_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 5.0})],
            })
            inv_eur = self.env['account.move'].with_context(edi_test_mode=True).create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'currency_id': self.fake_eur_data['currency'].id,
                'invoice_date': '2016-12-31',
                'date': '2016-12-31',
                'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'price_unit': 4.4})],
            })
            invoices = (inv_mxn + inv_usd + inv_eur)
            invoices.action_post()

            payment = self.create_payment(invoices, 'outbound', self.journal_usd, date='2017-01-01')
            pline_mxn = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_mxn.currency_id)
            pline_usd = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_usd.currency_id)
            pline_eur = payment.payment_invoice_ids.filtered(lambda x: x.currency_id == inv_eur.currency_id)

            pline_mxn.payment_currency_amount = 3
            pline_mxn.payment_amount = 72
            payment._compute_from_lines()
            payment.amount = payment.company_currency_amount

            self.assertEqual(payment.payment_difference, 0)
            self.assertEqual(payment.company_difference, 0)

            payment_record = payment._create_split_payments()

            self.assertAlmostEqual(pline_mxn.amount, 100)
            self.assertAlmostEqual(pline_mxn.payment_amount, 72)
            self.assertAlmostEqual(pline_mxn.payment_currency_amount, 3)
            self.assertAlmostEqual(pline_mxn.company_currency_amount, 72)
            self.assertAlmostEqual(pline_usd.amount, 5)
            self.assertAlmostEqual(pline_usd.payment_amount, 5)
            self.assertAlmostEqual(pline_usd.payment_currency_amount, 5)
            self.assertAlmostEqual(pline_usd.company_currency_amount, 125)
            self.assertAlmostEqual(pline_eur.amount, 4.4)
            self.assertAlmostEqual(pline_eur.payment_amount, 4.4)
            self.assertAlmostEqual(pline_eur.payment_currency_amount, 4.36)
            self.assertAlmostEqual(pline_eur.company_currency_amount, 108.9)

            receivable_lines = payment_record.line_ids.filtered(lambda x: x.account_id.internal_type == 'receivable')
            line_mxn = receivable_lines.filtered(lambda x: x.name == inv_mxn.name)
            line_usd = receivable_lines.filtered(lambda x: x.name == inv_usd.name)
            line_eur = receivable_lines.filtered(lambda x: x.name == inv_eur.name)
            self.assertEqual(line_mxn.balance, -72)
            self.assertEqual(line_mxn.amount_currency, -3)
            self.assertEqual(line_usd.balance, -125)
            self.assertEqual(line_usd.amount_currency, -5)
            self.assertEqual(line_eur.balance, -108.9)
            self.assertEqual(line_eur.amount_currency, -4.4)

            self._process_documents_web_services(inv_mxn)
            inv_mxn.l10n_mx_edi_cfdi_uuid = '123456789'
            self._process_documents_web_services(inv_usd)
            inv_usd.l10n_mx_edi_cfdi_uuid = '567891234'
            self._process_documents_web_services(inv_eur)
            inv_eur.l10n_mx_edi_cfdi_uuid = '987654321'

            # This Parameter will make Odoo to sign with its own method in l10n_mx_edi.
            self.env['ir.config_parameter'].sudo().set_param('skip_sign_with_l10n_mx_edi_payment_split', 'do_not_sign')

            generated_files = self._process_documents_web_services(payment_record.move_id, {'cfdi_3_3'})
            self.assertTrue(generated_files)
            cfdi = generated_files[0]

            current_etree = self.get_xml_tree_from_string(cfdi)
            expected_etree = self.with_applied_xpath(
                self.get_xml_tree_from_string(self.expected_payment_cfdi_values),
                '''
                    <xpath expr="//Comprobante" position="attributes">
                        <attribute name="Folio">1</attribute>
                        <attribute name="Serie">JBUSD/2017/01/</attribute>
                    </xpath>
                    <xpath expr="//Complemento" position="replace">
                        <Complemento>
                            <Pagos Version="2.0">
                                <Totales MontoTotalPagos="309.00"/>
                                <Pago
                                    FechaPago="2017-01-01T12:00:00"
                                    FormaDePagoP="99" MonedaP="USD"
                                    TipoCambioP="25.000000" Monto="12.36"
                                    NumOperacion="INV/2016/00001 INV/2016/00002 INV/2016/00003">
                                        <DoctoRelacionado
                                            EquivalenciaDR="25.087109"
                                            IdDocumento="123456789" Folio="1" Serie="INV/2016/"
                                            MonedaDR="MXN" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="100.00" ImpPagado="72.00" ImpSaldoInsoluto="28.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="1" IdDocumento="567891234" Folio="2" Serie="INV/2016/"
                                            MonedaDR="USD" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="5.00" ImpPagado="5.00" ImpSaldoInsoluto="0.00"/>
                                        <DoctoRelacionado
                                            EquivalenciaDR="1" IdDocumento="987654321" Folio="3" Serie="INV/2016/"
                                            MonedaDR="EUR" NumParcialidad="1" ObjetoImpDR="01"
                                            ImpSaldoAnt="4.40" ImpPagado="4.40" ImpSaldoInsoluto="0.00"/>
                                    </Pago>
                            </Pagos>
                        </Complemento>
                    </xpath>
                ''',
            )
            self.assertXmlTreeEqual(current_etree, expected_etree)
