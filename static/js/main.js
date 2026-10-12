(function () {
    "use strict";

    const doc = document;
    const root = doc.documentElement;

    /* ============================================================
       1. Тема: применяем сохранённую, слушаем переключатель
       ============================================================ */
    const THEME_KEY = "theme";
    const themeToggle = doc.querySelector("[data-theme-toggle]");

    function getStoredTheme() {
        try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
    }
    function setStoredTheme(v) {
        try { localStorage.setItem(THEME_KEY, v); } catch (e) {}
    }
    function applyTheme(theme) {
        root.setAttribute("data-theme", theme);
        if (themeToggle) {
            const isDark = theme === "dark";
            themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
            themeToggle.setAttribute(
                "aria-label",
                isDark ? "Переключить на светлую тему" : "Переключить на тёмную тему"
            );
        }
        const meta = doc.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", theme === "dark" ? "#0B1424" : "#14243A");
    }

    // Синхронизируем состояние с тем, что уже поставил inline-скрипт в <head>
    applyTheme(root.getAttribute("data-theme") || getStoredTheme() || "light");

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
            applyTheme(next);
            setStoredTheme(next);
        });
    }

    /* ============================================================
       2. Мобильное меню
       ============================================================ */
    const toggle = doc.querySelector("[data-menu-toggle]");
    const sidebar = doc.querySelector("[data-sidebar]");
    const MQ_DESKTOP = window.matchMedia("(min-width: 981px)");

    function closeMenu() {
        if (!sidebar || !toggle) return;
        sidebar.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        doc.body.style.overflow = "";
    }
    function openMenu() {
        if (!sidebar || !toggle) return;
        sidebar.classList.add("is-open");
        toggle.setAttribute("aria-expanded", "true");
        doc.body.style.overflow = "hidden";
    }
    function isMenuOpen() {
        return sidebar && sidebar.classList.contains("is-open");
    }

    if (toggle && sidebar) {
        toggle.addEventListener("click", () => {
            isMenuOpen() ? closeMenu() : openMenu();
        });

        // Закрытие после выбора раздела
        sidebar.addEventListener("click", (e) => {
            const link = e.target.closest("a.nav-link");
            if (link) closeMenu();
        });

        // Закрытие по Escape
        doc.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && isMenuOpen()) {
                closeMenu();
                toggle.focus();
            }
        });

        // Клик вне меню
        doc.addEventListener("click", (e) => {
            if (!isMenuOpen()) return;
            if (sidebar.contains(e.target) || toggle.contains(e.target)) return;
            closeMenu();
        });

        // При переходе к десктопной ширине меню закрывается автоматически
        const onDesktopChange = (ev) => {
            if (ev.matches) {
                closeMenu();
            }
        };
        if (MQ_DESKTOP.addEventListener) {
            MQ_DESKTOP.addEventListener("change", onDesktopChange);
        } else if (MQ_DESKTOP.addListener) {
            MQ_DESKTOP.addListener(onDesktopChange);
        }
    }

    /* ============================================================
       3. KaTeX: рендер формул по data-latex
       ============================================================ */
    function renderLatex(scope) {
        if (!window.katex) return;
        const nodes = (scope || doc).querySelectorAll("[data-latex]");
        nodes.forEach((node) => {
            if (node.dataset.rendered === "1") return;
            const latex = node.getAttribute("data-latex");
            if (!latex) return;
            try {
                window.katex.render(latex, node, {
                    throwOnError: false,
                    displayMode: true,
                });
                node.dataset.rendered = "1";
            } catch (err) {
                // Оставляем исходный текст, чтобы страница не потеряла смысл
                node.textContent = latex;
            }
        });
    }

    if (doc.readyState === "loading") {
        doc.addEventListener("DOMContentLoaded", () => renderLatex(doc));
    } else {
        renderLatex(doc);
    }

    /* ============================================================
       4. Появление блоков при прокрутке
       ============================================================ */
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const reveals = doc.querySelectorAll(".reveal, .section-head, .feature-card, .route-step, .example, .formula-card");

    if (!reduceMotion.matches && "IntersectionObserver" in window && reveals.length) {
        // Помечаем все элементы как «ожидающие появления» только если JS работает
        reveals.forEach((el) => el.classList.add("reveal"));

        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    io.unobserve(entry.target);
                }
            });
        }, {
            rootMargin: "0px 0px -10% 0px",
            threshold: 0.08,
        });

        reveals.forEach((el) => io.observe(el));
    } else {
        // Ничего не прячем, если анимации отключены
        reveals.forEach((el) => el.classList.add("is-visible"));
    }

    /* ============================================================
       5. Копирование формул
       ============================================================ */
    function showToast(text) {
        const box = doc.querySelector("[data-toast]");
        if (!box) return;
        box.hidden = false;
        box.textContent = text;
        // перезапуск анимации
        box.classList.remove("is-visible");
        void box.offsetWidth;
        box.classList.add("is-visible");
        clearTimeout(showToast._t);
        showToast._t = setTimeout(() => {
            box.classList.remove("is-visible");
            setTimeout(() => { box.hidden = true; }, 250);
        }, 1600);
    }

    doc.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-copy-text]");
        if (!btn) return;
        const text = btn.getAttribute("data-copy-text");
        if (!text) return;

        const label = btn.querySelector("[data-copy-label]");
        const previous = label ? label.textContent : btn.textContent;

        const done = () => {
            btn.classList.add("is-copied");
            if (label) label.textContent = "Скопировано";
            showToast("Формула скопирована");
            setTimeout(() => {
                btn.classList.remove("is-copied");
                if (label) label.textContent = previous;
            }, 1400);
        };

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done).catch(() => {
                showToast("Не удалось скопировать");
            });
        } else {
            // Резервный способ
            const ta = doc.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.left = "-9999px";
            doc.body.appendChild(ta);
            ta.select();
            try { doc.execCommand("copy"); done(); }
            catch (err) { showToast("Не удалось скопировать"); }
            doc.body.removeChild(ta);
        }
    });

    /* ============================================================
       6. Кнопка «Наверх»
       ============================================================ */
    const toTop = doc.querySelector("[data-to-top]");
    if (toTop) {
        let ticking = false;

        function updateToTop() {
            const y = window.scrollY || window.pageYOffset;
            const visible = y > 320;
            if (visible && toTop.hidden) toTop.hidden = false;
            toTop.classList.toggle("is-visible", visible);
            if (!visible) {
                // Скрываем после завершения анимации
                setTimeout(() => {
                    if (window.scrollY <= 320) toTop.hidden = true;
                }, 250);
            }
            ticking = false;
        }

        toTop.addEventListener("click", () => {
            const behavior = reduceMotion.matches ? "auto" : "smooth";
            window.scrollTo({ top: 0, behavior });
        });

        window.addEventListener("scroll", () => {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(updateToTop);
        }, { passive: true });

        updateToTop();
    }

    /* ============================================================
       7. Плавная подсветка активного раздела в навигации
       ============================================================ */
    // На сервере уже проставлен .is-active, но если ссылка ведёт на текущий URL
    // и по какой-то причине класс не выставлен — подсветим её локально.
    const path = window.location.pathname;
    doc.querySelectorAll(".nav-link").forEach((link) => {
        try {
            const url = new URL(link.href, window.location.origin);
            if (url.pathname === path && !link.classList.contains("is-active")) {
                link.classList.add("is-active");
                link.setAttribute("aria-current", "page");
            }
        } catch (err) { /* игнорируем */ }
    });

    /* ============================================================
       8. Аккуратное восстановление кнопок после возврата со страницы
       ============================================================ */
    window.addEventListener("pageshow", () => {
        doc.querySelectorAll(".btn.is-loading").forEach((btn) => {
            btn.classList.remove("is-loading");
            btn.disabled = false;
        });
    });

})();