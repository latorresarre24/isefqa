odoo.define("l10n_mx_hr_expense.checks_widget_owl", (require) => {
    "use strict";
    const AbstractField = require("web.AbstractFieldOwl");
    const field_registry = require("web.field_registry_owl");
    class ChecksWidgetOwl extends AbstractField {
        constructor(...args) {
            super(...args);
            this.messages = JSON.parse(this.value) || {};
            this.failed = 0;
            this.succeeded = 0;
            if (this.value) {
                this.failed = Object.keys(this.messages.fail).length || 0;
                this.succeeded = Object.keys(this.messages.ok).length || 0;
            }
        }
        _onClickSucceeded() {
            return this.rpc({
                model: this.model,
                method: "json2qweb",
                args: ["json_input", this.value],
            }).then((rendered_view) => {
                $(
                    this.env.qweb.renderToString("l10n_mx_hr_expense.ExpenseChecksModal", {
                        rendered_view,
                    })
                ).modal();
            });
        }
    }
    ChecksWidgetOwl.template = "l10n_mx_hr_expense.ExpenseChecks";
    ChecksWidgetOwl.style = owl.tags.css`
    .expenses_compact_alert {
        margin: 0px;
        padding: 0.1rem 0.1rem;
    }
    `;
    field_registry.add("expenses_checks", ChecksWidgetOwl);
    return ChecksWidgetOwl;
});
