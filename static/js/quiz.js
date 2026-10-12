(function () {
    "use strict";

    const root = document.querySelector("[data-quiz-root]");
    if (!root) return;

    const csrf = root.getAttribute("data-csrf") || "";
    const type = root.getAttribute("data-type") || "single";
    const checkBtn = root.querySelector("[data-check]");
    const nextBtn = root.querySelector("[data-next]");
    const retryBtn = root.querySelector("[data-retry]");
    const feedback = root.querySelector(".quiz-feedback");

    /* ---------- Утилита: безопасная вставка текста в HTML ---------- */
    function escapeHtml(str) {
        return String(str == null ? "" : str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    /* ---------- Сбор ответов текущего вопроса ---------- */
    function collectAnswers() {
        if (type === "single") {
            const checked = root.querySelector('input[type="radio"]:checked');
            return checked ? [checked.value] : [];
        }
        if (type === "multiple") {
            return Array.from(root.querySelectorAll('input[type="checkbox"]:checked'))
                .map((c) => c.value);
        }
        const input = root.querySelector('input[type="text"]');
        return input && input.value.trim() ? [input.value.trim()] : [];
    }

    /* ---------- Снять визуальные пометки с вариантов ---------- */
    function clearOptionStates() {
        root.querySelectorAll(".option").forEach((el) => {
            el.classList.remove("is-correct", "is-wrong");
        });
    }

    /* ---------- Показать, какие варианты верны/неверны ---------- */
    function markOptions(correctAnswer, userAnswers) {
        const correctSet = new Set(Array.isArray(correctAnswer) ? correctAnswer : [correctAnswer]);
        const userSet = new Set(userAnswers || []);

        root.querySelectorAll(".option").forEach((label) => {
            const input = label.querySelector("input");
            if (!input) return;
            const val = input.value;
            label.classList.remove("is-correct", "is-wrong");

            if (correctSet.has(val)) {
                label.classList.add("is-correct");
            } else if (userSet.has(val)) {
                label.classList.add("is-wrong");
            }
        });
    }

    /* ---------- Блокировка кнопок и состояния «загрузка» ---------- */
    function setBusy(btn, busy) {
        if (!btn) return;
        btn.disabled = busy;
        btn.classList.toggle("is-loading", busy);
    }

    /* ---------- Отрисовка обратной связи ---------- */
    function showFeedback({ kind, title, explanation, mistake, extra }) {
        if (!feedback) return;
        const cls = kind === "correct" ? "feedback-correct" : "feedback-error";
        const parts = ['<p class="' + cls + '">' + escapeHtml(title) + "</p>"];
        if (explanation) {
            parts.push('<div class="feedback-explanation">' + escapeHtml(explanation) + "</div>");
        }
        if (mistake) {
            parts.push(
                '<div class="feedback-explanation"><em>Частая ошибка:</em> ' +
                escapeHtml(mistake) +
                "</div>"
            );
        }
        if (extra) {
            parts.push('<div class="feedback-explanation">' + escapeHtml(extra) + "</div>");
        }
        feedback.innerHTML = parts.join("");
        feedback.hidden = false;
    }

    function clearFeedback() {
        if (!feedback) return;
        feedback.hidden = true;
        feedback.innerHTML = "";
    }

    /* ---------- Инициализация: разложить кнопки по состояниям ---------- */
    if (retryBtn) retryBtn.hidden = true;
    if (nextBtn) nextBtn.hidden = true;

    /* ---------- Проверка ответа ---------- */
    if (checkBtn) {
        checkBtn.addEventListener("click", () => {
            const answers = collectAnswers();
            if (answers.length === 0) {
                showFeedback({
                    kind: "error",
                    title: "Выберите или введите ответ.",
                });
                return;
            }

            const body = new URLSearchParams();
            body.append("_csrf_token", csrf);
            answers.forEach((a) => body.append("answer", a));

            setBusy(checkBtn, true);
            checkBtn.setAttribute("aria-busy", "true");

            fetch("/quiz/check", {
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
                        showFeedback({
                            kind: "error",
                            title: "Ошибка проверки.",
                            explanation: data && data.message ? data.message : "",
                        });
                        return;
                    }

                    markOptions(data.correct_answer, answers);

                    if (data.correct) {
                        showFeedback({
                            kind: "correct",
                            title: "Верно!",
                            explanation: data.explanation,
                        });
                        checkBtn.hidden = true;
                        if (retryBtn) retryBtn.hidden = true;
                        if (nextBtn) {
                            nextBtn.hidden = false;
                            nextBtn.focus();
                        }
                    } else {
                        showFeedback({
                            kind: "error",
                            title: "Пока неверно.",
                            explanation: data.explanation,
                            mistake: data.common_mistake,
                        });
                        if (retryBtn) retryBtn.hidden = false;
                        if (retryBtn) retryBtn.focus();
                    }
                })
                .catch(() => {
                    showFeedback({
                        kind: "error",
                        title: "Сеть недоступна. Попробуйте ещё раз.",
                    });
                })
                .finally(() => {
                    setBusy(checkBtn, false);
                    checkBtn.removeAttribute("aria-busy");
                });
        });
    }

    /* ---------- Повторная попытка ---------- */
    if (retryBtn) {
        retryBtn.addEventListener("click", () => {
            clearFeedback();
            clearOptionStates();
            retryBtn.hidden = true;
            // Снимаем отметки выбора, чтобы студент мог выбрать заново
            root.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((inp) => {
                inp.checked = false;
            });
            const input = root.querySelector('input[type="text"]');
            if (input) input.value = "";
            const firstInput = root.querySelector('input');
            if (firstInput) firstInput.focus();
        });
    }

    /* ---------- Переход к следующему вопросу ---------- */
    if (nextBtn) {
        nextBtn.addEventListener("click", () => {
            setBusy(nextBtn, true);
            const body = new URLSearchParams();
            body.append("_csrf_token", csrf);

            fetch("/quiz/next", {
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
                        showFeedback({
                            kind: "error",
                            title: "Ошибка перехода.",
                            explanation: data && data.message ? data.message : "",
                        });
                        return;
                    }
                    if (data.finished) {
                        window.location.href = "/results";
                    } else {
                        window.location.reload();
                    }
                })
                .catch(() => {
                    showFeedback({
                        kind: "error",
                        title: "Сеть недоступна. Попробуйте ещё раз.",
                    });
                })
                .finally(() => {
                    setBusy(nextBtn, false);
                });
        });
    }

    /* ---------- Восстановление состояния кнопок при возврате на страницу ---------- */
    window.addEventListener("pageshow", () => {
        setBusy(checkBtn, false);
        setBusy(nextBtn, false);
    });
})();