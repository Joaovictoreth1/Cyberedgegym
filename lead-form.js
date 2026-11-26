const leadFields = ["nome", "academia", "whatsapp", "tier"];
const plans = new Set(["start", "pro", "enterprise"]);
const fieldMessages = {
    nome: "Informe seu nome (entre 2 e 120 caracteres).",
    academia: "Informe o nome da academia (entre 2 e 120 caracteres).",
    whatsapp: "Informe um número com DDD, de 10 a 13 dígitos.",
    tier: "Selecione um dos planos disponíveis.",
};
const messages = {
    sending: "Enviando solicitação. A primeira resposta do servidor pode demorar.",
    sent: "Solicitação recebida. Nossa equipe entrará em contato pelo WhatsApp informado.",
    invalid: "Revise os dados do formulário e tente novamente.",
    unavailable: "Não foi possível confirmar o envio. Seus dados continuam no formulário para uma nova tentativa.",
};

export function apiBaseUrl(hostname, configuredUrl) {
    return ["localhost", "127.0.0.1", "[::1]"].includes(hostname)
        ? "http://localhost:8000"
        : configuredUrl.replace(/\/+$/, "");
}

export function validateLead(fields) {
    const payload = Object.fromEntries(
        leadFields.map(name => {
            const value = fields.get(name);
            return [name, typeof value === "string" ? value.trim() : ""];
        }),
    );
    const errors = {};
    for (const field of ["nome", "academia"]) {
        const length = Array.from(payload[field]).length;
        if (length < 2 || length > 120) errors[field] = fieldMessages[field];
    }
    if (payload.whatsapp.length > 32 || !/^\+?[0-9() .-]+$/.test(payload.whatsapp) ||
        !/^[0-9]{10,13}$/.test(payload.whatsapp.replace(/[^0-9]/g, ""))) {
        errors.whatsapp = fieldMessages.whatsapp;
    }
    payload.tier = payload.tier.toLowerCase();
    if (!plans.has(payload.tier)) errors.tier = fieldMessages.tier;
    return { payload, errors };
}

export async function submitLead(baseUrl, fields, fetchImpl = fetch) {
    const { payload, errors } = validateLead(fields);
    if (Object.keys(errors).length) return "invalid";

    try {
        const response = await fetchImpl(`${baseUrl}/api/contato`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: AbortSignal.timeout(90_000),
        });
        if (response.status === 201) return "sent";
        if (response.status === 422) return "invalid";
    } catch {
        return "unavailable";
    }
    return "unavailable";
}

export function bindLeadForm(form, message, hostname, planLinks = []) {
    const button = form.querySelector('button[type="submit"]');
    const baseUrl = apiBaseUrl(hostname, form.dataset.apiUrl);
    const controls = Object.fromEntries(leadFields.map(name => [name, form.elements.namedItem(name)]));
    const errorElements = Object.fromEntries(leadFields.map(name => [name, form.querySelector(`#lead-${name}-error`)]));
    let sending = false;

    function setError(name, error = "") {
        if (error) controls[name].setAttribute("aria-invalid", "true");
        else controls[name].removeAttribute("aria-invalid");
        errorElements[name].textContent = error;
        errorElements[name].hidden = !error;
    }

    function display(status) {
        message.textContent = messages[status] ?? "";
        message.dataset.state = status;
    }

    form.noValidate = true;
    button.disabled = false;
    for (const field of leadFields) {
        controls[field].addEventListener(field === "tier" ? "change" : "input", () => {
            setError(field);
            if (!sending) display("");
        });
    }
    for (const link of planLinks) {
        link.addEventListener("click", () => {
            const plan = link.dataset.leadTier;
            if (sending || !plans.has(plan)) return;
            controls.tier.value = plan;
            setError("tier");
            display("");
        });
    }
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (sending) return;
        const values = new FormData(form);
        const { errors } = validateLead(values);
        for (const field of leadFields) setError(field, errors[field]);
        const firstInvalid = leadFields.find(field => errors[field]);
        if (firstInvalid) {
            display("invalid");
            controls[firstInvalid].focus();
            return;
        }

        sending = true;
        button.setAttribute("aria-disabled", "true");
        form.setAttribute("aria-busy", "true");
        form.querySelector("fieldset").disabled = true;
        display("sending");

        let result = "unavailable";
        try {
            result = await submitLead(baseUrl, values);
        } finally {
            sending = false;
            button.removeAttribute("aria-disabled");
            form.removeAttribute("aria-busy");
            form.querySelector("fieldset").disabled = false;
        }

        if (result === "sent") form.reset();
        display(result);
    });
}
