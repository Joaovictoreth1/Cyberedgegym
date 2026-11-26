'use strict';

const form = document.querySelector('#edge-form');
const notice = document.querySelector('#lead-notice');
const submitButton = form.querySelector('button[type="submit"]');
const fields = form.querySelectorAll('input, select');
const config = document.querySelector('meta[name="cyberedge-api"]');
const endpoint = config.content ? new URL(config.content + '/api/contato') : null;
let submitting = false;
let lastRequest = null;

function showNotice(state, message) {
    notice.dataset.state = state;
    notice.textContent = message;
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submitting || !endpoint) return;

    const values = new FormData(form);
    const body = JSON.stringify(Object.fromEntries(
        ['nome', 'academia', 'whatsapp', 'tier'].map(key => [key, values.get(key).trim()]),
    ));
    if (lastRequest?.body !== body) {
        lastRequest = { body, key: crypto.randomUUID() };
    }

    submitting = true;
    submitButton.disabled = true;
    fields.forEach(field => { field.disabled = true; });
    form.setAttribute('aria-busy', 'true');
    showNotice('pending', 'Enviando solicitação…');

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Idempotency-Key': lastRequest.key },
            body,
            credentials: 'omit',
            signal: AbortSignal.timeout(8000),
        });
        if (response.status === 201) {
            form.reset();
            lastRequest = null;
            showNotice('success', 'Solicitação recebida. Nossa equipe entrará em contato.');
        } else if (response.status === 422) {
            showNotice('error', 'Confira o nome, a academia, o WhatsApp com DDD e o plano.');
        } else if (response.status === 429) {
            showNotice('error', 'Muitas tentativas. Aguarde um minuto e tente novamente.');
        } else {
            showNotice('error', 'Não foi possível confirmar o envio. Tente novamente.');
        }
    } catch {
        showNotice('error', 'Não foi possível confirmar o envio. Tente novamente.');
    } finally {
        submitting = false;
        form.removeAttribute('aria-busy');
        fields.forEach(field => { field.disabled = false; });
        submitButton.disabled = false;
    }
});

if (endpoint) {
    submitButton.disabled = false;
} else {
    showNotice('error', 'Formulário indisponível. Escreva para contato@cyberedgegym.com.br.');
}
