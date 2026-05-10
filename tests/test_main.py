from __future__ import annotations

import main


def test_main_cli_flag_runs_cli(monkeypatch) -> None:
    called = {"cli": 0}

    def fake_cli() -> None:
        called["cli"] += 1

    monkeypatch.setattr(main, "run_cli", fake_cli)
    rc = main.main(["--cli"])
    assert rc == 0
    assert called["cli"] == 1


def test_main_gui_flag_runs_gui(monkeypatch) -> None:
    import sanguosha.gui as gui

    called = {"gui": 0}

    def fake_gui() -> None:
        called["gui"] += 1

    monkeypatch.setattr(gui, "run_gui", fake_gui)
    rc = main.main(["--gui"])
    assert rc == 0
    assert called["gui"] == 1


def test_main_default_falls_back_to_cli_when_gui_fails(monkeypatch, capsys) -> None:
    import sanguosha.gui as gui

    called = {"cli": 0}

    def fake_cli() -> None:
        called["cli"] += 1

    def bad_gui() -> None:
        raise RuntimeError("no gui")

    monkeypatch.setattr(gui, "run_gui", bad_gui)
    monkeypatch.setattr(main, "run_cli", fake_cli)
    rc = main.main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert called["cli"] == 1
    assert "回退到 CLI" in captured.err


def test_main_gui_flag_returns_nonzero_when_gui_fails(monkeypatch, capsys) -> None:
    import sanguosha.gui as gui

    def bad_gui() -> None:
        raise RuntimeError("no gui")

    monkeypatch.setattr(gui, "run_gui", bad_gui)
    rc = main.main(["--gui"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "可视化模式启动失败" in captured.err
