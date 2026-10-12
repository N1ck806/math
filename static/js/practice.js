(function () {
    "use strict";

    const root = document.querySelector("[data-practice-root]");
    if (!root) return;

    const csrf = root.getAttribute("data-csrf") || "";
    const cards = root.querySelectorAll(".practice-card");

    /* ---------- Утилита: экранирование текста для безопасной вставки ---------- */
    function escapeHtml(str) {
        return String(str == null ? "" : str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    /* ---------- Отрисовка блока обратной связи ---------- */
    function renderFeedback(box, { kind, title, explanation }) {
        const cls = kind === "correct" ? "feedback-correct" : "feedback-error";
        const parts = [];
        parts.push('<p class="' + cls + '">' + escapeHtml(title) + '</p>');
        if (explanation) {
            parts.push(
                '<div class="feedback-explanation">' + escapeHtml(explanation) + '</div>'
            );
        }
        box.innerHTML = parts.join("");
        box.hidden = false;
    }

    /* ---------- Работа с одной карточкой ---------- */
    cards.forEach((card) => {
        const taskId = card.getAttribute("data-task-id");
        const type = card.getAttribute("data-task-type");
        const checkBtn = card.querySelector("[data-check]");
        const retryBtn = card.querySelector("[data-retry]");
        const feedback = card.querySelector(".practice-feedback");
        if (!taskId || !checkBtn || !feedback) return;

        // Скрыть кнопку «Попробовать ещё раз» до первой ошибки
        if (retryBtn) retryBtn.hidden = true;

        function getAnswer() {
            if (type === "single") {
                const checked = card.querySelector('input[type="radio"]:checked');
                return checked ? checked.value : "";
            }
            const input = card.querySelector('input[type="text"]');
            return input ? input.value.trim() : "";
        }

        function clearOptionStates() {
            card.querySelectorAll(".option").forEach((el) => {
                el.classList.remove("is-correct", "is-wrong");
            });
        }

        function setBusy(busy) {
            checkBtn.disabled = busy;
            checkBtn.classList.toggle("is-loading", busy);
        }

        function resetCard() {
            feedback.hidden = true;
            feedback.innerHTML = "";
            clearOptionStates();
            if (retryBtn) retryBtn.hidden = true;
            checkBtn.hidden = false;
            checkBtn.disabled = false;
        }

        retryBtn && retryBtn.addEventListener("click", () => {
            resetCard();
            const input = card.querySelector('input[type="text"], input[type="radio"]');
            if (input) input.focus();
        });

        checkBtn.addEventListener("click", () => {
            const answer = getAnswer();
            if (!answer) {
                renderFeedback(feedback, {
                    kind: "error",
                    title: "Введите ответ.",
                });
                return;
            }

            const body = new URLSearchParams();
            body.append("_csrf_token", csrf);
            body.append("task_id", taskId);
            body.append("answer", answer);

            setBusy(true);

            fetch("/practice/check", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: body.toString(),
                credentials: "same-origin",
            })
                .then((r) => {
                    if (!r.ok) throw new Error("HTTP " + r.status);
                    return r.json();
                })
                .then((data) => {
                    if (!data || !data.ok) {
                        renderFeedback(feedback, {
                            kind: "error",
                            title: "Ошибка проверки.",
                            explanation: data && data.message ? data.message : "",
                        });
                        return;
                    }

                    if (data.correct) {
                        renderFeedback(feedback, {
                            kind: "correct",
                            title: "Верно!",
                            explanation: data.solution || "",
                        });
                        checkBtn.hidden = true;
                        if (retryBtn) retryBtn.hidden = true;
                        // Подсветим правильный вариант
                        if (type === "single") {
                            card.querySelectorAll(".option").forEach((el) => {
                                const input = el.querySelector("input");
                                if (input && input.checked) {
                                    el.classList.add("is-correct");
                                }
                            });
                        }
                    } else {
                        renderFeedback(feedback, {
                            kind: "error",
                            title: "Пока неверно.",
                            explanation: data.hint
                                ? "Подсказка: " + data.hint
                                : "",
                        });
                        if (retryBtn) retryBtn.hidden = false;
                        // Подсветим выбранный неверный вариант
                        if (type === "single") {
                            card.querySelectorAll(".option").forEach((el) => {
                                const input = el.querySelector("input");
                                if (input && input.checked) {
                                    el.classList.add("is-wrong");
                                }
                            });
                        }
                    }
                })
                .catch(() => {
                    renderFeedback(feedback, {
                        kind: "error",
                        title: "Сеть недоступна. Попробуйте ещё раз.",
                    });
                })
                .finally(() => {
                    setBusy(false);
                });
        });
    });
})();