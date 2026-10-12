(function () {
    "use strict";

    const form = document.querySelector("[data-lab-form]");
    if (!form) return;

    const table = form.querySelector("[data-points-table]");
    const addBtn = form.querySelector("[data-add-point]");
    const submitBtn = form.querySelector("[data-lab-submit]");
    const MIN_POINTS = 2;
    const MAX_POINTS = 200;

    /* ---------- Валидация отдельного поля ---------- */
    function isValidNumber(value) {
        if (value == null) return false;
        const s = String(value).trim().replace(",", ".");
        if (s === "") return false;
        const n = Number(s);
        return Number.isFinite(n);
    }

    function markInvalid(input, invalid) {
        if (!input) return;
        input.classList.toggle("is-invalid", invalid);
        if (invalid) {
            input.setAttribute("aria-invalid", "true");
        } else {
            input.removeAttribute("aria-invalid");
        }
    }

    function validateRow(row) {
        const inputs = row.querySelectorAll('input[name="x[]"], input[name="y[]"]');
        let ok = true;
        inputs.forEach((input) => {
            const valid = isValidNumber(input.value);
            markInvalid(input, !valid);
            if (!valid) ok = false;
        });
        return ok;
    }

    function validateAll() {
        const rows = table.querySelectorAll(".point-row");
        if (rows.length < MIN_POINTS) return false;
        if (rows.length > MAX_POINTS) return false;
        let ok = true;
        rows.forEach((row) => {
            if (!validateRow(row)) ok = false;
        });
        return ok;
    }

    /* ---------- Удаление точки ---------- */
    function bindRemove(btn) {
        btn.addEventListener("click", () => {
            const rows = table.querySelectorAll(".point-row");
            if (rows.length <= MIN_POINTS) {
                flashRow(rows[0]);
                return;
            }
            const row = btn.closest(".point-row");
            row.style.transition = "opacity 150ms ease, transform 150ms ease";
            row.style.opacity = "0";
            row.style.transform = "translateX(-8px)";
            setTimeout(() => row.remove(), 150);
        });
    }

    function flashRow(row) {
        if (!row) return;
        row.classList.remove("is-changed");
        // перезапуск анимации
        void row.offsetWidth;
        row.classList.add("is-changed");
        setTimeout(() => row.classList.remove("is-changed"), 400);
    }

    table.querySelectorAll("[data-remove-point]").forEach(bindRemove);

    /* ---------- Добавление точки ---------- */
    if (addBtn) {
        addBtn.addEventListener("click", () => {
            const rows = table.querySelectorAll(".point-row");
            if (rows.length >= MAX_POINTS) {
                showMessage("Достигнуто максимальное количество точек: " + MAX_POINTS + ".");
                return;
            }
            const row = document.createElement("div");
            row.className = "point-row";
            row.innerHTML = `
                <label>
                    <span>x</span>
                    <input type="text" name="x[]" value="0"
                           inputmode="decimal" autocomplete="off"
                           aria-label="Значение x">
                </label>
                <label>
                    <span>y</span>
                    <input type="text" name="y[]" value="0"
                           inputmode="decimal" autocomplete="off"
                           aria-label="Значение y">
                </label>
                <button type="button" class="btn-remove"
                        data-remove-point aria-label="Удалить точку">×</button>
            `;
            table.appendChild(row);
            bindRemove(row.querySelector("[data-remove-point]"));
            flashRow(row);
            const firstInput = row.querySelector('input[name="x[]"]');
            if (firstInput) firstInput.focus();
        });
    }

    /* ---------- Валидация при вводе ---------- */
    table.addEventListener("input", (e) => {
        const input = e.target;
        if (!input.matches('input[name="x[]"], input[name="y[]"]')) return;
        if (input.classList.contains("is-invalid")) {
            markInvalid(input, !isValidNumber(input.value));
        }
    });

    table.addEventListener("blur", (e) => {
        const input = e.target;
        if (!input.matches('input[name="x[]"], input[name="y[]"]')) return;
        markInvalid(input, !isValidNumber(input.value));
    }, true);

    /* ---------- Вспомогательное сообщение ---------- */
    function showMessage(text) {
        let box = form.querySelector("[data-lab-inline-message]");
        if (!box) {
            box = document.createElement("div");
            box.className = "alert alert-error";
            box.setAttribute("role", "alert");
            box.setAttribute("data-lab-inline-message", "");
            table.parentNode.insertBefore(box, table);
        }
        box.textContent = text;
        clearTimeout(showMessage._t);
        showMessage._t = setTimeout(() => {
            if (box.parentNode) box.parentNode.removeChild(box);
        }, 4000);
    }

    /* ---------- Блокировка кнопки при отправке ---------- */
    form.addEventListener("submit", (e) => {
        const action = (e.submitter && e.submitter.value) || "calculate";
        if (action === "reset" || action === "load_example") {
            return;
        }
        if (!validateAll()) {
            e.preventDefault();
            showMessage("Проверьте введённые значения: они должны быть числами.");
            const firstBad = form.querySelector("input.is-invalid");
            if (firstBad) firstBad.focus();
            return;
        }
        if (submitBtn) {
            submitBtn.classList.add("is-loading");
            submitBtn.disabled = true;
        }
    });

    /* ---------- Восстановление кнопки при возврате на страницу ---------- */
    window.addEventListener("pageshow", () => {
        if (submitBtn) {
            submitBtn.classList.remove("is-loading");
            submitBtn.disabled = false;
        }
    });
})();