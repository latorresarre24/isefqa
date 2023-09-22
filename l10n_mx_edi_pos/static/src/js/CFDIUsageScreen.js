odoo.define('pos_cfdi_usage.CFDIUsageScreen', (require) => {
    'use strict';
    const { debounce } = owl.utils;
    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');
    const CFDIUsageLine = require('pos_cfdi_usage.CFDIUsageLine');
    /**
     * Render this screen using `showTempScreen` to select usage.
     * When the shown screen is done, the call to `showTempScreen`
     * resolves to the selected usage. E.g.
     *
     * ```js
     * const { done, usage } = await showTempScreen('CFDIUsageScreen');
     * if (done) {
     *   // do something with the usage
     * }
     * ```
     *
     * @props usage - originally selected CFDI usage
     */
    class CFDIUsageScreen extends PosComponent {
        constructor() {
            super(...arguments);
            // We are not using useState here because the object
            // passed to useState converts the object and its contents
            // to Observer proxy. Not sure of the side-effects of making
            // a persistent object, such as pos, into owl.Observer. But it
            // is better to be safe.
            this.state = {
                query: null,
                selectedUsage: this.props.usage,
            };
            this.updateCFDIUsage = debounce(this.updateCFDIUsage, 70);
        };

        back () {
            this.props.resolve({ done: false, usage: false });
            this.trigger('close-temp-screen');
        };

        confirm () {
            this.props.resolve({ done: true, usage: this.state.selectedUsage });
            this.trigger('close-temp-screen');
        };

        get currentOrder () {
            return this.env.pos.get_order();
        };

        get usages () {
            const query = (this.state.query || '').trim();
            return query
                ? this.env.pos.search_usage_selection(query)
                : this.env.pos.usage_selection;
        };

        get isNextButtonVisible () {
            return !!this.state.selectedUsage;
        };

        /**
         * Returns the text and command of the next button.
         * The command field is used by the clickNext call.
         */
        get nextButton () {
            if (!this.props.usage) {
                return { command: 'set', text: this.env._t('Select usage') };
            };
            if (this.props.usage === this.state.selectedUsage) {
                return { command: 'deselect', text: this.env._t('Deselect usage') };
            };
            return { command: 'set', text: this.env._t('Change usage') };
        };

        // We declare this event handler as a debounce function in
        // order to lower its trigger rate.
        updateCFDIUsage ({ code, target: { value } }) {
            this.state.query = value;
            const usages = this.usages;
            if (code === 'Enter' && usages.length === 1) {
                this.state.selectedUsage = usages[0];
                this.clickNext();
            } else {
                this.render();
            }
        };

        clickUsage ({ detail: { usage } }) {
            this.state.selectedUsage = this.state.selectedUsage === usage ? null : usage;
            this.render();
        };

        clickNext () {
            this.state.selectedUsage = this.nextButton.command === 'set'
                ? this.state.selectedUsage
                : null;
            this.confirm();
        };
    };

    CFDIUsageScreen.template = 'CFDIUsageScreen';
    CFDIUsageScreen.components = { CFDIUsageLine };

    Registries.Component.add(CFDIUsageScreen);

    return CFDIUsageScreen;
});
