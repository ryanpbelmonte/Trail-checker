/**
 * In-page recheck for /saved-trails cards (POST JSON, no navigation).
 */
(function () {
    const root = document.querySelector("[data-saved-trails-page]");
    if (!root) {
        return;
    }

    const csrfToken = root.dataset.csrfToken;

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function recommendationBadge(recommendation) {
        const map = {
            good: { className: "text-bg-success", label: "Good" },
            caution: { className: "text-bg-warning", label: "Use Caution" },
            poor: { className: "text-bg-danger", label: "Poor" },
            unknown: { className: "text-bg-secondary", label: "Unknown" },
        };
        const info = map[recommendation] || map.unknown;
        return (
            `<span class="badge ${info.className} fs-6 px-3 py-2">` +
            `${escapeHtml(info.label)}</span>`
        );
    }

    function airQualityHtml(data) {
        if (data.aqi != null) {
            let html = `AQI ${escapeHtml(data.aqi)}`;
            if (data.pm2_5 != null) {
                html += ` <span class="text-muted">· PM2.5 ${escapeHtml(data.pm2_5)}</span>`;
            }
            return `<p class="mb-0">${html}</p>`;
        }
        return '<p class="small text-muted mb-0">No AQI data on last check.</p>';
    }

    function weatherHtml(data) {
        let line = `${Math.round(data.temp_f)} °F`;
        if (data.wind_mph != null) {
            line += ` · Wind ${Number(data.wind_mph).toFixed(1)} mph`;
        }
        return (
            `<p class="mb-1"><strong>${escapeHtml(data.weather_main)}</strong>` +
            `<span class="text-muted"> — ${escapeHtml(data.weather_description)}</span></p>` +
            `<p class="small mb-0">${escapeHtml(line)}</p>`
        );
    }

    function updateCard(card, data) {
        const recEl = card.querySelector("[data-recheck-recommendation]");
        const condEl = card.querySelector("[data-recheck-conditions]");
        const emptyEl = card.querySelector("[data-recheck-empty]");
        const errEl = card.querySelector("[data-recheck-error]");

        errEl.classList.add("d-none");
        errEl.textContent = "";

        recEl.classList.remove("d-none");
        recEl.innerHTML = recommendationBadge(data.recommendation);

        emptyEl.classList.add("d-none");
        condEl.classList.remove("d-none");

        condEl.querySelector("[data-recheck-weather]").innerHTML = weatherHtml(data);
        condEl.querySelector("[data-recheck-air]").innerHTML = airQualityHtml(data);
        condEl.querySelector("[data-recheck-checked-at]").textContent =
            `Last checked ${data.checked_at}`;
        condEl.querySelector("[data-recheck-saved-at]").textContent =
            `Saved ${data.saved_at}`;
    }

    function showError(card, message) {
        const errEl = card.querySelector("[data-recheck-error]");
        errEl.textContent = message;
        errEl.classList.remove("d-none");
    }

    root.querySelectorAll("[data-recheck-btn]").forEach((button) => {
        button.addEventListener("click", async () => {
            const trailId = button.dataset.trailId;
            const card = root.querySelector(`[data-saved-trail-id="${trailId}"]`);
            const label = button.textContent;

            button.disabled = true;
            button.textContent = "Checking…";

            try {
                const response = await fetch(`/saved-trails/${trailId}/recheck`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken,
                        Accept: "application/json",
                    },
                    credentials: "same-origin",
                });

                const payload = await response.json();

                if (!response.ok || !payload.ok) {
                    const msg =
                        (payload.error && payload.error.message) ||
                        "Could not refresh conditions. Try again later.";
                    showError(card, msg);
                    return;
                }

                updateCard(card, payload.data);
            } catch (_err) {
                showError(card, "Network error. Try again later.");
            } finally {
                button.disabled = false;
                button.textContent = label;
            }
        });
    });
})();
