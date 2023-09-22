odoo.define('pos_cfdi_usage.models', (require) => {
    'use strict';
    const models = require('point_of_sale.models');
    const { _t } = require('web.core');

    models.load_fields('res.partner', ['l10n_mx_edi_usage']);

    const _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        initialize () {
            this.l10n_mx_edi_usage = this.l10n_mx_edi_usage || false;
            return _super_order.initialize.apply(this, arguments);
        },
        init_from_JSON (json) {
            const res = _super_order.init_from_JSON.call(this, json);
            if (json.l10n_mx_edi_usage) {
                this.set_usage(json.l10n_mx_edi_usage);
            } else {
                const client = this.get_client();
                const usage = (client ? client.l10n_mx_edi_usage : false) || '';
                this.set_usage(usage);
            }
            return res;
        },
        export_as_JSON () {
            const res = _super_order.export_as_JSON.call(this);
            res.l10n_mx_edi_usage = this.get_usage();
            return res;
        },
        set_usage (usage) {
            if (typeof(usage) == 'string') {
                usage = this.get_usage_byid(usage);
            }
            this.assert_editable();
            this.set('l10n_mx_edi_usage', usage);
        },
        get_usage () {
            return this.get('l10n_mx_edi_usage', false);
        },
        set_client (client) {
            if (client) {
                this.l10n_mx_edi_usage = client.l10n_mx_edi_usage;
            }
            return _super_order.set_client.call(this, client);
        },
        get_usage_byid (id) {
            for (const usage of this.pos.usage_selection) {
                if( usage.id === id){
                    return usage;
                }
            }
        },
    });


    const _super_posmodel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        initialize () {
            const res = _super_posmodel.initialize.apply(this, arguments);
            this.rpc({ model: 'pos.order', method: 'ui_get_usage_selection', args: [] }).then(
                fields => this.usage_selection = fields.map(
                    ([usageId, usageName]) => ({ id: usageId, name: usageName })
                )
            );
            return res;
        },
        search_usage_selection (query) {
            query = query.toLowerCase();
            return this.usage_selection.filter(
                ({ id, name }) => id.toLowerCase().includes(query) || name.toLowerCase().includes(query)
            );
        },
    });

});
