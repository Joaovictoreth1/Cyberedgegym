import assert from "node:assert/strict";
import { test } from "node:test";
import { apiBaseUrl, submitLead } from "../lead-form.js";

const renderUrl = "https://cyberedge-api.onrender.com";

function leadFields() {
    const fields = new FormData();
    fields.set("nome", "  Maria Silva  ");
    fields.set("academia", "Academia Teste");
    fields.set("whatsapp", "(11) 99999-0000");
    fields.set("tier", "start");
    return fields;
}

test("selects loopback locally and the configured Render origin on Pages", () => {
    assert.equal(apiBaseUrl("localhost", renderUrl), "http://localhost:8000");
    assert.equal(apiBaseUrl("127.0.0.1", renderUrl), "http://localhost:8000");
    assert.equal(apiBaseUrl("joaovictoreth1.github.io", renderUrl + "/"), renderUrl);
});

test("posts only the lead fields and confirms on HTTP 201", async () => {
    const fields = leadFields();
    fields.set("extra", "discard");
    const result = await submitLead(renderUrl, fields, async (url, options) => {
        assert.equal(url, renderUrl + "/api/contato");
        assert.equal(options.method, "POST");
        assert.deepEqual(options.headers, { "Content-Type": "application/json" });
        assert.ok(options.signal instanceof AbortSignal);
        assert.deepEqual(JSON.parse(options.body), {
            nome: "Maria Silva",
            academia: "Academia Teste",
            whatsapp: "(11) 99999-0000",
            tier: "start",
        });
        return new Response(null, { status: 201 });
    });
    assert.equal(result, "sent");
});

test("rejects blank input without sending it", async () => {
    const fields = leadFields();
    fields.set("academia", "  ");
    let attempted = false;
    const result = await submitLead(renderUrl, fields, async () => {
        attempted = true;
    });
    assert.equal(result, "invalid");
    assert.equal(attempted, false);
});

test("does not confirm validation errors, proxy errors, or network failure", async () => {
    const fields = leadFields();
    for (const [status, expected] of [[422, "invalid"], [200, "unavailable"], [503, "unavailable"]]) {
        assert.equal(await submitLead(renderUrl, fields, async () => ({ status })), expected);
    }
    assert.equal(await submitLead(renderUrl, fields, async () => {
        throw new TypeError("Failed to fetch");
    }), "unavailable");
});
