odoo.define('pos_cfdi_usage.PaymentScreen', (require) => {
    'use strict';
    const PaymentScreen = require('point_of_sale.PaymentScreen');

    const Inheritance = _PaymentScreen => class extends _PaymentScreen {
        constructor() {
            super(...arguments);
        };
        selectCFDIUsage () {
            this.showTempScreen('CFDIUsageScreen', {
                usage: this.currentOrder.get_usage()
            }).then(({ usage }) => {
                this.currentOrder.set_usage(usage);
            });
        };
        get CFDIUsageName () {
            const usage = this.currentOrder.get_usage();
            if (!usage) {
                return this.env._t('Choose');
            }
            if (usage.name.length > 20) {
                return usage.name.substring(0, 18) + '...';
            }
            return usage.name;
        }
    };

    require('point_of_sale.Registries').Component.extend(PaymentScreen, Inheritance);

    return Inheritance;
});
