/** @odoo-module **/

import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { Component, xml } from "@odoo/owl";

class StajyerSnippet extends Component {
    static template = "stajyer_takip.StajyerSnippet";

    setup() {
        this.loadStajyerler();
    }

    async loadStajyerler() {
        const res = await fetch("/stajyer/snippet/data");
        const data = await res.json();

        this.props.stajyer_list = data.stajyers;
        this.render();
    }
}

registry.category("snippets").add("stajyer_snippet", StajyerSnippet);
