import { expect, test } from '@playwright/test';

const data = {
    nome: 'Pessoa Teste',
    academia: 'Academia Teste',
    whatsapp: '11999998888',
    tier: 'pro',
};
const endpoint = 'http://localhost:8000/api/contato';

async function fill(page) {
    await page.getByLabel('Nome do gestor').fill(data.nome);
    await page.getByLabel('Nome da academia').fill(data.academia);
    await page.getByLabel('WhatsApp com DDD').fill(data.whatsapp);
    await page.getByLabel('Plano de interesse').selectOption(data.tier);
}

test.beforeEach(async ({ page }) => {
    await page.route(/^https:\/\/(cdnjs\.cloudflare\.com|fonts\.googleapis\.com|fonts\.gstatic\.com)\//, route => route.abort());
    await page.goto('/#contact');
});

test('submits once, only reports success on 201, and works without CDNs', async ({ page }) => {
    let calls = 0;
    let resolveRequest;
    const pending = new Promise(resolve => { resolveRequest = resolve; });
    await page.route(endpoint, async route => {
        calls++;
        expect(route.request().postDataJSON()).toEqual(data);
        expect(route.request().headers()['idempotency-key']).toMatch(/^[a-f0-9-]{36}$/);
        await pending;
        await route.fulfill({ status: 201, json: { id: 1 } });
    });
    await fill(page);
    const button = page.getByRole('button', { name: 'Enviar solicitação' });
    await button.click();
    await expect(button).toBeDisabled();
    await expect(page.getByRole('status')).toHaveText('Enviando solicitação…');
    await page.locator('#edge-form').dispatchEvent('submit');
    resolveRequest();
    await expect(page.getByRole('status')).toHaveText(/Solicitação recebida/);
    await expect(page.getByLabel('Nome do gestor')).toHaveValue('');
    expect(calls).toBe(1);
});

test('keeps inputs and reuses the retry key when delivery is unconfirmed', async ({ page }) => {
    const keys = [];
    await page.route(endpoint, async route => {
        keys.push(route.request().headers()['idempotency-key']);
        if (keys.length === 1) await route.abort();
        else await route.fulfill({ status: 201, json: { id: 2 } });
    });
    await fill(page);
    const button = page.getByRole('button', { name: 'Enviar solicitação' });
    await button.click();
    await expect(page.getByRole('status')).toHaveText(/Não foi possível confirmar/);
    await expect(page.getByLabel('WhatsApp com DDD')).toHaveValue(data.whatsapp);
    expect(await page.evaluate(() => localStorage.length)).toBe(0);
    await button.click();
    await expect(page.getByRole('status')).toHaveText(/Solicitação recebida/);
    expect(keys).toEqual([keys[0], keys[0]]);
});

test('does not report HTTP 200 as a created lead', async ({ page }) => {
    await page.route(endpoint, route => route.fulfill({ status: 200, json: {} }));
    await fill(page);
    await page.getByRole('button', { name: 'Enviar solicitação' }).click();
    await expect(page.getByRole('status')).toHaveText(/Não foi possível confirmar/);
    await expect(page.getByLabel('Nome do gestor')).toHaveValue(data.nome);
});
