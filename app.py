"""Flask-приложение: маршруты, сессии, CSRF, проверка ответов.

Готово к запуску на хостинге Render через gunicorn.
Локально: python app.py (или flask --app app run --debug).
"""

from __future__ import annotations

import math
import os
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
    abort,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from core.least_squares import (
    LeastSquaresError,
    fit_linear_least_squares,
    validate_data,
    sse_for_coefficients,
    parse_points_from_form,
)
from core.security import get_csrf_token, check_csrf, safe_float, safe_int
from data.examples_data import EXAMPLES
from data.practice_data import PRACTICE_TASKS
from data.quiz_data import QUIZ_QUESTIONS


app = Flask(__name__)
app.config.from_object(Config)

# Render работает за обратным прокси — доверяем заголовкам X-Forwarded-*,
# чтобы url_for генерировал https-ссылки и сессии корректно привязывались к домену.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# ---------------------------------------------------------------------------
# Общие данные для шаблонов
# ---------------------------------------------------------------------------

NAV_ITEMS = [
    {"endpoint": "index", "url": "/", "label": "Главная"},
    {"endpoint": "theory", "url": "/theory", "label": "Введение в МНК"},
    {"endpoint": "model", "url": "/model", "label": "Математическая модель"},
    {"endpoint": "calculation", "url": "/calculation", "label": "Методика вычислений"},
    {"endpoint": "examples", "url": "/examples", "label": "Разобранные примеры"},
    {"endpoint": "lab", "url": "/lab", "label": "Интерактивная лаборатория"},
    {"endpoint": "practice", "url": "/practice", "label": "Практические задания"},
    {"endpoint": "quiz", "url": "/quiz", "label": "Итоговый тест"},
    {"endpoint": "results", "url": "/results", "label": "Результаты"},
    {"endpoint": "formulas", "url": "/formulas", "label": "Справочник формул"},
    {"endpoint": "about", "url": "/about", "label": "О проекте"},
]

ROUTE_ORDER = [
    "index", "theory", "model", "calculation", "examples",
    "lab", "practice", "quiz", "results", "formulas", "about",
]

CONTENT_ROUTES = ["theory", "model", "calculation", "examples", "lab", "practice", "quiz"]


@app.context_processor
def inject_globals():
    """Добавляет в шаблоны общие данные: навигацию, CSRF, прогресс, год."""
    endpoint = request.endpoint or "index"
    try:
        idx = ROUTE_ORDER.index(endpoint)
    except ValueError:
        idx = -1

    progress = 0
    if endpoint in CONTENT_ROUTES:
        progress = int(((CONTENT_ROUTES.index(endpoint) + 1) / len(CONTENT_ROUTES)) * 100)
    elif endpoint == "results":
        progress = 100

    return {
        "nav_items": NAV_ITEMS,
        "csrf_token": get_csrf_token(),
        "current_endpoint": endpoint,
        "current_index": idx,
        "progress_percent": progress,
        "quiz_total": len(QUIZ_QUESTIONS),
        "current_year": datetime.now().year,
    }


@app.before_request
def before_request_hook():
    if request.method == "POST":
        check_csrf()


@app.template_filter("fmtnum")
def fmtnum(value, digits: int = 3):
    """Аккуратный вывод чисел в шаблонах."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(v):
        return "—"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{digits}f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Страницы
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", title="Главная")


@app.route("/theory")
def theory():
    return render_template("theory.html", title="Введение в МНК")


@app.route("/model")
def model():
    return render_template("model.html", title="Математическая модель")


@app.route("/calculation")
def calculation():
    example = EXAMPLES[0]
    fit = fit_linear_least_squares(example["x"], example["y"])
    rows = []
    for i in range(fit.n):
        rows.append({
            "i": i + 1,
            "x": fit.x[i],
            "y": fit.y[i],
            "x_centered": fit.extras["x_centered"][i],
            "y_centered": fit.extras["y_centered"][i],
            "product": fit.extras["products"][i],
            "x_centered_squared": fit.extras["x_centered_squared"][i],
            "y_hat": fit.y_hat[i],
            "residual": fit.residuals[i],
            "residual_squared": fit.residuals[i] ** 2,
        })
    return render_template(
        "calculation.html",
        title="Методика вычислений",
        fit=fit,
        rows=rows,
    )


@app.route("/examples")
def examples():
    enriched = []
    for ex in EXAMPLES:
        fit = fit_linear_least_squares(ex["x"], ex["y"])
        enriched.append({**ex, "fit": fit})
    return render_template("examples.html", title="Разобранные примеры", examples=enriched)


@app.route("/lab", methods=["GET", "POST"])
def lab():
    default_x = [1, 2, 3, 4, 5]
    default_y = [2, 3, 5, 4, 6]

    points = list(zip(default_x, default_y))
    error = None
    manual_a = ""
    manual_b = ""

    if request.method == "POST":
        action = request.form.get("action", "calculate")
        if action in ("reset", "load_example"):
            points = list(zip(default_x, default_y))
        else:
            x_raw = request.form.getlist("x[]")
            y_raw = request.form.getlist("y[]")
            try:
                xs, ys = parse_points_from_form(x_raw, y_raw)
                vr = validate_data(xs, ys)
                vr.raise_if_invalid()
                points = list(zip(xs, ys))
            except LeastSquaresError as exc:
                error = str(exc)
                points = list(zip(default_x, default_y))

        manual_a = request.form.get("manual_a", "").strip()
        manual_b = request.form.get("manual_b", "").strip()

    fit = None
    sse_manual = None
    manual_a_val = None
    manual_b_val = None

    if not error:
        try:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            fit = fit_linear_least_squares(xs, ys)
            if manual_a != "" and manual_b != "":
                manual_a_val = safe_float(manual_a, default=float("nan"))
                manual_b_val = safe_float(manual_b, default=float("nan"))
                if math.isfinite(manual_a_val) and math.isfinite(manual_b_val):
                    sse_manual = sse_for_coefficients(xs, ys, manual_a_val, manual_b_val)
        except LeastSquaresError as exc:
            error = str(exc)
            fit = None

    return render_template(
        "lab.html",
        title="Интерактивная лаборатория",
        points=points,
        fit=fit,
        error=error,
        manual_a=manual_a,
        manual_b=manual_b,
        manual_a_val=manual_a_val,
        manual_b_val=manual_b_val,
        sse_manual=sse_manual,
    )


# ---------------------------------------------------------------------------
# Практические задания
# ---------------------------------------------------------------------------

@app.route("/practice")
def practice():
    return render_template(
        "practice.html",
        title="Практические задания",
        tasks=PRACTICE_TASKS,
    )


@app.route("/practice/check", methods=["POST"])
def practice_check():
    task_id = request.form.get("task_id", "")
    user_answer = request.form.get("answer", "").strip()

    task = next((t for t in PRACTICE_TASKS if t["id"] == task_id), None)
    if task is None:
        return jsonify({"ok": False, "message": "Задание не найдено."}), 404

    correct = False
    if task["type"] == "numeric":
        try:
            value = float(user_answer.replace(",", "."))
            correct = abs(value - task["answer"]) <= task.get("tolerance", 0.01)
        except ValueError:
            correct = False
    else:
        correct = user_answer == task["answer"]

    return jsonify({
        "ok": True,
        "correct": correct,
        "solution": task["solution"],
        "hint": task["hint"],
    })


# ---------------------------------------------------------------------------
# Тест
# ---------------------------------------------------------------------------

def _init_quiz_session():
    session["quiz"] = {
        "order": [q["id"] for q in QUIZ_QUESTIONS],
        "current": 0,
        "answered": {},
        "started": True,
        "finished": False,
    }


def _find_question(qid: str):
    return next((q for q in QUIZ_QUESTIONS if q["id"] == qid), None)


@app.route("/quiz")
def quiz():
    if "quiz" not in session or not session["quiz"].get("started"):
        _init_quiz_session()

    state = session["quiz"]
    order = state["order"]
    idx = state["current"]

    if idx >= len(order):
        state["finished"] = True
        session["quiz"] = state
        session.modified = True
        return redirect(url_for("results"))

    qid = order[idx]
    question = _find_question(qid)
    if question is None:
        abort(500)

    answered = state["answered"].get(qid, {})

    safe_question = {
        "id": question["id"],
        "type": question["type"],
        "prompt": question["prompt"],
        "options": question.get("options", []),
        "points": question["points"],
    }

    return render_template(
        "quiz.html",
        title="Итоговый тест",
        question=safe_question,
        index=idx,
        total=len(order),
        already_correct=answered.get("correct", False),
        attempts=answered.get("attempts", 0),
    )


@app.route("/quiz/check", methods=["POST"])
def quiz_check():
    if "quiz" not in session:
        return jsonify({"ok": False, "message": "Тест не начат."}), 400

    state = session["quiz"]
    if state.get("finished"):
        return jsonify({"ok": False, "message": "Тест уже завершён."}), 400

    idx = state["current"]
    order = state["order"]
    if idx >= len(order):
        return jsonify({"ok": False, "message": "Вопросы закончились."}), 400

    qid = order[idx]
    question = _find_question(qid)
    if question is None:
        return jsonify({"ok": False, "message": "Вопрос не найден."}), 400

    record = state["answered"].get(qid, {"correct": False, "attempts": 0, "points": 0})

    if record.get("correct"):
        return jsonify({
            "ok": True,
            "correct": True,
            "explanation": question["explanation"],
            "common_mistake": question["common_mistake"],
            "correct_answer": question["answer"],
            "already_correct": True,
        })

    record["attempts"] = record.get("attempts", 0) + 1

    user_answer = request.form.getlist("answer")
    correct = False

    if question["type"] == "single":
        correct = len(user_answer) == 1 and user_answer[0] == question["answer"]
    elif question["type"] == "multiple":
        correct = sorted(user_answer) == sorted(question["answer"])
    elif question["type"] == "numeric":
        try:
            value = float(user_answer[0].replace(",", "."))
            correct = abs(value - question["answer"]) <= question.get("tolerance", 0.01)
        except (ValueError, IndexError):
            correct = False

    if correct:
        record["correct"] = True
        record["points"] = question["points"]

    state["answered"][qid] = record
    session["quiz"] = state
    session.modified = True

    return jsonify({
        "ok": True,
        "correct": correct,
        "explanation": question["explanation"],
        "common_mistake": question["common_mistake"],
        "correct_answer": question["answer"],
        "points": question["points"],
    })


@app.route("/quiz/next", methods=["POST"])
def quiz_next():
    if "quiz" not in session:
        return jsonify({"ok": False, "message": "Тест не начат."}), 400

    state = session["quiz"]
    idx = state["current"]
    order = state["order"]
    if idx >= len(order):
        return jsonify({"ok": False, "message": "Вопросы закончились."}), 400

    qid = order[idx]
    record = state["answered"].get(qid, {})
    if not record.get("correct"):
        return jsonify({
            "ok": False,
            "message": "Сначала ответьте правильно на текущий вопрос.",
        }), 400

    state["current"] = idx + 1
    if state["current"] >= len(order):
        state["finished"] = True
    session["quiz"] = state
    session.modified = True

    return jsonify({"ok": True, "finished": state["finished"]})


@app.route("/quiz/restart", methods=["POST"])
def quiz_restart():
    _init_quiz_session()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Результаты
# ---------------------------------------------------------------------------

TOPIC_LABELS = {
    "definition": "Определение МНК",
    "approximation": "Аппроксимация",
    "residuals": "Остатки",
    "sse": "Сумма квадратов остатков",
    "squares": "Причины использования квадратов",
    "slope": "Коэффициент наклона",
    "intercept": "Свободный член",
    "formula": "Формулы коэффициентов",
    "normal_equations": "Система нормальных уравнений",
    "calculation": "Расчёт на данных",
    "interpretation": "Интерпретация графика",
    "limitations": "Ограничения метода",
}

TOPIC_RECOMMENDATIONS = {
    "definition": "Повторите раздел «Введение в МНК».",
    "approximation": "Перечитайте подраздел об аппроксимации в «Введении».",
    "residuals": "Разберите SVG-иллюстрацию остатков и пример 1.",
    "sse": "Повторите формулу SSE и пример 1.",
    "squares": "Перечитайте подраздел «Почему именно квадраты».",
    "slope": "Повторите раздел «Математическая модель».",
    "intercept": "Повторите раздел «Математическая модель».",
    "formula": "Сверьтесь со «Справочником формул».",
    "normal_equations": "Повторите систему нормальных уравнений на странице «Математическая модель».",
    "calculation": "Пройдите ещё раз «Методику вычислений» и примеры.",
    "interpretation": "Посмотрите SVG-иллюстрации и раздел «Примеры».",
    "limitations": "Перечитайте подраздел об ограничениях МНК.",
}


@app.route("/results")
def results():
    state = session.get("quiz")
    if not state or not state.get("started"):
        return render_template(
            "results.html",
            title="Результаты",
            no_data=True,
        )

    answered = state.get("answered", {})
    order = state.get("order", [])
    total_questions = len(order)
    answered_count = sum(1 for qid in order if qid in answered)
    correct_count = sum(1 for qid in order if answered.get(qid, {}).get("correct"))
    attempts_total = sum(answered.get(qid, {}).get("attempts", 0) for qid in order)
    points_earned = sum(answered.get(qid, {}).get("points", 0) for qid in order)
    points_max = sum(q["points"] for q in QUIZ_QUESTIONS)

    percent = round((points_earned / points_max) * 100) if points_max else 0

    if percent >= 90:
        grade = "Отличное понимание материала"
        grade_note = "Вы уверенно владеете методом наименьших квадратов."
    elif percent >= 75:
        grade = "Хорошее понимание"
        grade_note = "Основные идеи усвоены, есть небольшие пробелы."
    elif percent >= 60:
        grade = "Основные идеи усвоены, но есть пробелы"
        grade_note = "Рекомендуется повторить отдельные разделы."
    else:
        grade = "Рекомендуется повторить ключевые разделы"
        grade_note = "Пройдите теоретические разделы и примеры заново."

    weak_topics = []
    for q in QUIZ_QUESTIONS:
        rec = answered.get(q["id"], {})
        if rec and not rec.get("correct"):
            weak_topics.append(q["topic"])

    weak_topics = sorted(set(weak_topics))
    recommendations = [
        {"topic": TOPIC_LABELS.get(t, t), "advice": TOPIC_RECOMMENDATIONS.get(t, "")}
        for t in weak_topics
    ]

    strong_topics = sorted({
        q["topic"] for q in QUIZ_QUESTIONS
        if answered.get(q["id"], {}).get("correct")
    })
    strong_labels = [TOPIC_LABELS.get(t, t) for t in strong_topics]

    return render_template(
        "results.html",
        title="Результаты",
        no_data=False,
        total_questions=total_questions,
        answered_count=answered_count,
        correct_count=correct_count,
        attempts_total=attempts_total,
        percent=percent,
        grade=grade,
        grade_note=grade_note,
        points_earned=points_earned,
        points_max=points_max,
        recommendations=recommendations,
        strong_labels=strong_labels,
        finished=state.get("finished", False),
    )


# ---------------------------------------------------------------------------
# Справочник и «О проекте»
# ---------------------------------------------------------------------------

FORMULAS = [
    {
        "title": "Уравнение линейной модели",
        "latex": r"\hat{y} = a x + b",
        "text": "y_hat = a*x + b",
        "when": "Основная формула линейной аппроксимации.",
    },
    {
        "title": "Остаток наблюдения",
        "latex": r"e_i = y_i - \hat{y}_i",
        "text": "e_i = y_i - y_hat_i",
        "when": "Показывает вертикальное отклонение точки от модели.",
    },
    {
        "title": "Сумма квадратов остатков",
        "latex": r"S(a,b) = \sum_{i=1}^{n} (y_i - a x_i - b)^2",
        "text": "S(a,b) = sum((y_i - a*x_i - b)^2)",
        "when": "Критерий качества подгонки — его и минимизирует МНК.",
    },
    {
        "title": "Среднее значение x",
        "latex": r"\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i",
        "text": "x_bar = (1/n) * sum(x_i)",
        "when": "Используется в формулах наклона и свободного члена.",
    },
    {
        "title": "Среднее значение y",
        "latex": r"\bar{y} = \frac{1}{n}\sum_{i=1}^{n} y_i",
        "text": "y_bar = (1/n) * sum(y_i)",
        "when": "Используется в формулах наклона и свободного члена.",
    },
    {
        "title": "Коэффициент наклона",
        "latex": r"a = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sum (x_i - \bar{x})^2}",
        "text": "a = sum((x_i - x_bar)*(y_i - y_bar)) / sum((x_i - x_bar)^2)",
        "when": "Даёт наклон прямой МНК для модели с константой.",
    },
    {
        "title": "Свободный член",
        "latex": r"b = \bar{y} - a\bar{x}",
        "text": "b = y_bar - a*x_bar",
        "when": "Сдвиг прямой по вертикали после нахождения наклона.",
    },
    {
        "title": "Система нормальных уравнений",
        "latex": r"\begin{cases} a\sum x_i^2 + b\sum x_i = \sum x_i y_i \\ a\sum x_i + b n = \sum y_i \end{cases}",
        "text": "a*sum(x_i^2) + b*sum(x_i) = sum(x_i*y_i); a*sum(x_i) + b*n = sum(y_i)",
        "when": "Получается из условия минимума SSE; эквивалентна формулам наклона и сдвига.",
    },
    {
        "title": "Прогноз модели",
        "latex": r"\hat{y}(x_0) = a x_0 + b",
        "text": "y_hat(x0) = a*x0 + b",
        "when": "Подстановка нового x в найденную модель.",
    },
]


@app.route("/formulas")
def formulas():
    return render_template("formulas.html", title="Справочник формул", formulas=FORMULAS)


@app.route("/about")
def about():
    return render_template("about.html", title="О проекте")


# ---------------------------------------------------------------------------
# Ошибки
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(_e):
    return render_template("errors/404.html", title="Страница не найдена"), 404


@app.errorhandler(500)
def server_error(_e):
    return render_template("errors/500.html", title="Внутренняя ошибка"), 500


@app.errorhandler(400)
def bad_request(e):
    return render_template(
        "errors/404.html",
        title="Некорректный запрос",
        message=getattr(e, "description", "Некорректный запрос."),
    ), 400


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Локальный запуск. На Render этот блок не выполняется —
    # там приложение поднимает gunicorn (см. Procfile).
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug)