const leadFields = ["nome", "academia", "whatsapp", "tier"];
const messages = {
    sent: "DADOS TRANSMITIDOS. ENGENHARIA A CAMINHO.",
    invalid: "REVISE OS DADOS DO FORMULÁRIO E TENTE NOVAMENTE.",
    unavailable: "NÃO FOI POSSÍVEL CONFIRMAR O ENVIO. TENTE NOVAMENTE MAIS TARDE.",
};

export function apiBaseUrl(hostname, configuredUrl) {
    return ["localhost", "127.0.0.1", "[::1]"].includes(hostname)
        ? "http://localhost:8000"
        : configuredUrl.replace(/\/+$/, "");
}

export async function submitLead(baseUrl, fields, fetchImpl = fetch) {
    const payload = Object.fromEntries(
        leadFields.map(name => [name, String(fields.get(name) ?? "").trim()]),
    );
    if (leadFields.some(name => !payload[name])) return "invalid";

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

export function bindLeadForm(form, overlay, message, hostname) {
    const button = form.querySelector('button[type="submit"]');
    const baseUrl = apiBaseUrl(hostname, form.dataset.apiUrl);
    let hideMessage;
    button.disabled = false;
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (button.disabled) return;
        button.disabled = true;
        form.setAttribute("aria-busy", "true");
        overlay.classList.remove("opacity-0", "pointer-events-none");
        message.textContent = "ENVIANDO DADOS...";
        clearTimeout(hideMessage);

        let result;
        try {
            result = await submitLead(baseUrl, new FormData(form));
        } catch {
            result = "unavailable";
        } finally {
            overlay.classList.add("opacity-0", "pointer-events-none");
            form.removeAttribute("aria-busy");
            button.disabled = false;
        }

        if (result === "sent") form.reset();
        message.textContent = messages[result];
        message.classList.toggle("bg-cyan-400", result === "sent");
        message.classList.toggle("text-black", result === "sent");
        message.classList.toggle("bg-magenta-400", result !== "sent");
        message.classList.toggle("text-white", result !== "sent");
        message.classList.remove("-translate-y-full");
        hideMessage = setTimeout(() => message.classList.add("-translate-y-full"), 5000);
    });
}
