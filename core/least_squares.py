"""
Вычислительное ядро метода наименьших квадратов.

Все функции возвращают структурированные результаты либо поднимают
LeastSquaresError с понятным сообщением на русском языке.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

MIN_POINTS = 2
MAX_POINTS = 200
MAX_ABS_VALUE = 1e9
NUMERIC_EPS = 1e-9


class LeastSquaresError(ValueError):
    """Понятная ошибка вычислительного ядра."""


# ---------------------------------------------------------------------------
# Структуры результата
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool
    x: np.ndarray | None = None
    y: np.ndarray | None = None
    message: str = ""

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise LeastSquaresError(self.message)


@dataclass
class FitResult:
    a: float
    b: float
    x: np.ndarray
    y: np.ndarray
    y_hat: np.ndarray
    residuals: np.ndarray
    sse: float
    x_mean: float
    y_mean: float
    n: int
    extras: dict = field(default_factory=dict)

    def equation(self) -> str:
        sign = "+" if self.b >= 0 else "−"
        return f"ŷ = {self.a:.4g}·x {sign} {abs(self.b):.4g}"

    def as_dict(self) -> dict:
        return {
            "a": self.a,
            "b": self.b,
            "sse": self.sse,
            "x_mean": self.x_mean,
            "y_mean": self.y_mean,
            "n": self.n,
            "equation": self.equation(),
            "x": self.x.tolist(),
            "y": self.y.tolist(),
            "y_hat": self.y_hat.tolist(),
            "residuals": self.residuals.tolist(),
        }


# ---------------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------------

def validate_data(
    x: Sequence[float] | None,
    y: Sequence[float] | None,
) -> ValidationResult:
    """Проверяет корректность экспериментальных данных.

    Возвращает ValidationResult. При ошибке поле message содержит
    понятное объяснение на русском.
    """
    if x is None or y is None:
        return ValidationResult(False, message="Данные не переданы.")

    try:
        x_arr = np.asarray(x, dtype=float).ravel()
        y_arr = np.asarray(y, dtype=float).ravel()
    except (TypeError, ValueError):
        return ValidationResult(False, message="Координаты должны быть числами.")

    if x_arr.size != y_arr.size:
        return ValidationResult(
            False, message="Количество значений x и y должно совпадать."
        )

    if x_arr.size < MIN_POINTS:
        return ValidationResult(
            False,
            message=f"Нужно минимум {MIN_POINTS} точки для построения прямой.",
        )

    if x_arr.size > MAX_POINTS:
        return ValidationResult(
            False,
            message=f"Слишком много точек (максимум {MAX_POINTS}).",
        )

    if not np.all(np.isfinite(x_arr)) or not np.all(np.isfinite(y_arr)):
        return ValidationResult(
            False, message="Данные содержат NaN или бесконечные значения."
        )

    if np.any(np.abs(x_arr) > MAX_ABS_VALUE) or np.any(np.abs(y_arr) > MAX_ABS_VALUE):
        return ValidationResult(
            False, message="Значения слишком велики (модуль больше 10^9)."
        )

    if np.allclose(x_arr, x_arr[0]):
        return ValidationResult(
            False,
            message=(
                "Все значения x одинаковы — по такой выборке нельзя "
                "однозначно определить наклон прямой."
            ),
        )

    return ValidationResult(True, x=x_arr, y=y_arr, message="OK")


# ---------------------------------------------------------------------------
# Подгонка
# ---------------------------------------------------------------------------

def fit_linear_least_squares(
    x: Sequence[float],
    y: Sequence[float],
) -> FitResult:
    """Находит коэффициенты a и b линейной модели ŷ = a·x + b.

    Использует устойчивое решение через numpy.linalg.lstsq.
    """
    vr = validate_data(x, y)
    vr.raise_if_invalid()

    x_arr = vr.x
    y_arr = vr.y
    n = x_arr.size

    x_mean = float(np.mean(x_arr))
    y_mean = float(np.mean(y_arr))

    # Центрированные данные нужны для устойчивости и для формулы наклона.
    x_centered = x_arr - x_mean
    y_centered = y_arr - y_mean

    # Матрица регрессоров: [x, 1]
    A = np.column_stack([x_arr, np.ones_like(x_arr)])
    solution, _res_lstsq, rank, _ = np.linalg.lstsq(A, y_arr, rcond=None)
    a = float(solution[0])
    b = float(solution[1])

    y_hat = predict(a, b, x_arr)
    residuals = calculate_residuals(y_arr, y_hat)
    sse = calculate_sse(residuals)

    extras = {
        "x_centered": x_centered.tolist(),
        "y_centered": y_centered.tolist(),
        "products": (x_centered * y_centered).tolist(),
        "x_centered_squared": (x_centered ** 2).tolist(),
        "numerator": float(np.sum(x_centered * y_centered)),
        "denominator": float(np.sum(x_centered ** 2)),
        "rank": int(rank),
    }

    return FitResult(
        a=a,
        b=b,
        x=x_arr,
        y=y_arr,
        y_hat=y_hat,
        residuals=residuals,
        sse=sse,
        x_mean=x_mean,
        y_mean=y_mean,
        n=n,
        extras=extras,
    )


def predict(a: float, b: float, x: Sequence[float] | np.ndarray) -> np.ndarray:
    """Предсказанные моделью значения ŷ = a·x + b."""
    x_arr = np.asarray(x, dtype=float)
    return a * x_arr + b


def calculate_residuals(
    y_true: Sequence[float] | np.ndarray,
    y_pred: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Остатки e_i = y_i − ŷ_i."""
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    if y_t.shape != y_p.shape:
        raise LeastSquaresError("Размеры массивов y и ŷ не совпадают.")
    return y_t - y_p


def calculate_sse(residuals: Sequence[float] | np.ndarray) -> float:
    """Сумма квадратов остатков SSE = Σ e_i²."""
    r = np.asarray(residuals, dtype=float)
    if r.size == 0:
        raise LeastSquaresError("Массив остатков пуст.")
    if not np.all(np.isfinite(r)):
        raise LeastSquaresError("Остатки содержат NaN или бесконечные значения.")
    return float(np.sum(r ** 2))


def sse_for_coefficients(
    x: Sequence[float],
    y: Sequence[float],
    a: float,
    b: float,
) -> float:
    """SSE для произвольных коэффициентов (для сравнения моделей в лаборатории)."""
    if not (np.isfinite(a) and np.isfinite(b)):
        raise LeastSquaresError("Коэффициенты должны быть конечными числами.")
    vr = validate_data(x, y)
    vr.raise_if_invalid()
    y_hat = predict(a, b, vr.x)
    residuals = calculate_residuals(vr.y, y_hat)
    return calculate_sse(residuals)


# ---------------------------------------------------------------------------
# Разбор ввода
# ---------------------------------------------------------------------------

def parse_points_from_form(
    x_raw: list[str],
    y_raw: list[str],
) -> tuple[list[float], list[float]]:
    """Преобразует строки из формы в числа, поднимая понятную ошибку."""
    if len(x_raw) != len(y_raw):
        raise LeastSquaresError("Количество x и y не совпадает.")

    xs: list[float] = []
    ys: list[float] = []
    for i, (sx, sy) in enumerate(zip(x_raw, y_raw), start=1):
        sx = (sx or "").strip().replace(",", ".")
        sy = (sy or "").strip().replace(",", ".")
        if not sx or not sy:
            raise LeastSquaresError(f"Строка {i}: пустое значение.")
        try:
            xv = float(sx)
            yv = float(sy)
        except ValueError:
            raise LeastSquaresError(f"Строка {i}: «{sx}» или «{sy}» — не число.")
        if not (np.isfinite(xv) and np.isfinite(yv)):
            raise LeastSquaresError(f"Строка {i}: значение не является конечным числом.")
        xs.append(xv)
        ys.append(yv)
    return xs, ys