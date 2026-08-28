import importlib
from pathlib import Path

from wireup import injectable

from app.core.config import settings


@injectable
class RequestHandlerRegistry:
    def __init__(self) -> None:
        self._scan_dir = Path(settings.HTTP_DIR)

    def __iter__(self):
        for path in sorted(self._scan_dir.rglob('*.py')):
            if path.name == '__init__.py':
                continue
            module_name = ".".join(path.with_suffix("").parts)
            module = importlib.import_module(module_name)
            handler = getattr(module, "RequestHandler", None)
            if handler:
                yield handler
