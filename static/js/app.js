(() => {
    "use strict";

    document.querySelectorAll("[data-dismiss-flash]").forEach((button) => {
        button.addEventListener("click", () => button.closest(".flash")?.remove());
    });

    document.querySelectorAll("[data-confirm]").forEach((button) => {
        button.addEventListener("click", (event) => {
            if (!window.confirm(button.dataset.confirm)) event.preventDefault();
        });
    });

    document.querySelectorAll("[data-history-back]").forEach((button) => {
        button.addEventListener("click", () => window.history.back());
    });

    document.querySelectorAll("[data-password-toggle]").forEach((button) => {
        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) return;

        button.addEventListener("click", () => {
            const passwordIsVisible = input.type === "text";
            input.type = passwordIsVisible ? "password" : "text";
            button.setAttribute("aria-pressed", String(!passwordIsVisible));
            button.setAttribute("aria-label", passwordIsVisible ? "Mostra password" : "Nascondi password");
        });
    });

    const clue = document.getElementById("frase_indizio");
    const counter = document.querySelector('[data-character-count="frase_indizio"]');
    if (clue && counter) {
        const updateCounter = () => {
            counter.textContent = `${clue.value.length} / 200`;
        };
        clue.addEventListener("input", updateCounter);
        updateCounter();
    }

    const word = document.getElementById("parola");
    if (word) {
        word.addEventListener("input", () => {
            word.value = word.value.toLocaleUpperCase("it-IT");
        });
    }

    const form = document.getElementById("crosswordForm");
    if (!form) return;

    form.addEventListener("submit", (event) => {
        if (document.getElementById("website")?.value) {
            event.preventDefault();
            return;
        }

        if (!form.checkValidity()) {
            event.preventDefault();
            form.reportValidity();
        }
    });
})();
