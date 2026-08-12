from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer

from src.desktop.resources import prepare_desktop_environment
from src.desktop.window import MainWindow, create_application, save_window_screenshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native idea-discovery graph inspector")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prepare_desktop_environment()
    app = create_application()
    window = MainWindow()
    window.show()
    if args.smoke_test:
        def finish_smoke() -> None:
            print(f"GUI smoke passed: nodes={len(window.nodes)} edges={len(window.edges)}")
            app.quit()

        QTimer.singleShot(200, finish_smoke)
    elif args.screenshot is not None:
        def finish_screenshot() -> None:
            save_window_screenshot(window, args.screenshot.resolve())
            print(f"GUI screenshot: {args.screenshot.resolve()}")
            app.quit()

        QTimer.singleShot(500, finish_screenshot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
