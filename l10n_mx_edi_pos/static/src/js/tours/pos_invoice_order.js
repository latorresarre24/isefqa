odoo.define("mx_pos.pos_invoice_order_tour", function (require) {
    "use strict";

    const {makeFullOrder} = require("point_of_sale.tour.CompositeTourMethods");
    const {getSteps, startSteps} = require("point_of_sale.tour.utils");
    const tour = require("web_tour.tour");

    startSteps();

    makeFullOrder({
        orderlist: [
            ["Office Chair Black", "2", "120.5"],
        ],
        customer: "Azure Interior",
        payment: ["Cash", "241"],
    });

    tour.register("mx_pos_invoice_order", {test: true}, getSteps());

    return {};
});
