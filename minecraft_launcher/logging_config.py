import logging
from logging.handlers import RotatingFileHandler
from . import __version__


def configure_logging(paths):
    handler = RotatingFileHandler(paths.root / 'logs' / 'xlauncher.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger(__name__).info('XLauncher %s iniciado. Datos: %s', __version__, paths.root)
