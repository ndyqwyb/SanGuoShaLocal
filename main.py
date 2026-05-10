from __future__ import annotations

import argparse
import sys

from sanguosha.cli import run_cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sanguosha-local-1v1")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cli", action="store_true", help="以命令行模式启动")
    group.add_argument("--gui", action="store_true", help="以本地可视化模式启动")
    args = parser.parse_args(argv)

    if args.cli:
        run_cli()
        return 0

    if args.gui:
        try:
            from sanguosha.gui import run_gui

            run_gui()
            return 0
        except Exception as exc:
            print(f"可视化模式启动失败：{exc}", file=sys.stderr)
            return 1

    try:
        from sanguosha.gui import run_gui

        run_gui()
        return 0
    except Exception as exc:
        print(f"可视化模式启动失败，回退到 CLI：{exc}", file=sys.stderr)
        run_cli()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
