odoo.define('pos_cfdi_usage.CFDIUsageLine', (require) => {
    'use strict';
    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');

    class CFDIUsageLine extends PosComponent {
        get highlight() {
            return this.props.usage == this.props.selectedUsage ? 'highlight' : '';
        }
    }
    CFDIUsageLine.template = 'CFDIUsageLine';

    Registries.Component.add(CFDIUsageLine);

    return CFDIUsageLine;
});
