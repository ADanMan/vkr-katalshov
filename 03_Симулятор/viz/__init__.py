"""
viz — пакет визуализации симулятора.

Три независимых модуля:

* `3d_pyvista` — интерактивная 3D-сцена термокамеры в браузере
  (pyvista + trame). Запуск как сервис: `python -m viz.3d_pyvista`.

* `dashboard_dash` — Plotly Dash live-чарт T(t), FSM-state и
  индикатор verdict. Запуск: `python -m viz.dashboard_dash`.

* `plot_static` — публикационные графики (matplotlib + seaborn) для
  PNG в ПЗ.
"""
