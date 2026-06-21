from src.config.settings import AppSettings
from src.display.fullscreen_ui import FullscreenApp


def main() -> None:
    settings = AppSettings.from_env()
    app = FullscreenApp(settings=settings)
    app.run()


if __name__ == "__main__":
    main()
