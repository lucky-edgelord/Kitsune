import logging

from .bot import Kitsune


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    Kitsune().run()


if __name__ == "__main__":
    main()
