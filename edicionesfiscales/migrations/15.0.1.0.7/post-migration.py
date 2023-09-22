import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    move_attachment_from_account_payment_to_account_move(cr)

def move_attachment_from_account_payment_to_account_move(cr):
    """
    The way to search the cfdi of account.payment is performed over the related journal entry (account.move).
    That is the reason to move the related attachments from account.payment to account.move.
    """
    cr.execute(
        """
        UPDATE
            ir_attachment AS it
        SET
            res_model = 'account.move',
            res_id = ap.move_id
        FROM
            account_payment AS ap
        WHERE
            it.res_model = 'account.payment'
            AND it.res_id = ap.id
        """
    )
    _logger.info("%d attachments were moved from account.payment to account.move", cr.rowcount)
