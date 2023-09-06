-- Delete all views but websites
DELETE FROM
    ir_ui_view
WHERE
    (
        id NOT IN (
            SELECT view_id FROM report_layout
        )
    AND
        id NOT IN (
            SELECT view_id FROM website_page
        )
    AND
        name NOT IN (
            'My Dashboard',
            'credit_limit',
            'res.partner.form',
            'res.partner.property.form.inherit',
            'report_picking',
            'report_picking_inherit',
            'cfdiv33',
            'cfdiv33_inherit',
            'report_followup_print_all_inherit - old view, inherited from account_reports.report_followup_print_all',
            'report_invoice_document',
            'report_invoice_document_inherit',
            'report_invoice_document_mx',
            'report_invoice_document_mx_inherit',
            'report_payment_document_mx',
            'report_payment_document_mx_inherit',
            'report_payment_receipt_document',
            'report_payment_receipt_document_inherit',
            'report_saleorder_document',
            'report_saleorder_document_inherit'
        )
    );

-- As well as their external IDs
DELETE FROM
    ir_model_data
WHERE
    model = 'ir.ui.view'
    AND res_id NOT IN (SELECT id FROM ir_ui_view);

-- Delete mail templates with external ID
WITH deleted_extid AS (
    DELETE FROM
        ir_model_data
    WHERE
        model = 'mail.template'
        AND module != '__export__'
    RETURNING
        res_id
)
DELETE FROM
    mail_template AS template
USING
    deleted_extid
WHERE
    template.id = deleted_extid.res_id;
