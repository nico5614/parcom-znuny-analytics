"""Small Qt-compatible settings adapter without importing Qt in the WebView host."""
import configparser
import json
from pathlib import Path
from threading import Lock


class Settings:
    def __init__(self, root: Path):
        self._path = root / "settings.ini"
        self._lock = Lock()

    def _read(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read(self._path, encoding="utf-8")
        if not parser.has_section("General"):
            parser.add_section("General")
        return parser

    def get(self, key, default=None):
        with self._lock:
            raw = self._read().get("General", key, fallback=None)
        if raw is None:
            return default
        try:
            value = json.loads(raw)
            return json.loads(value) if isinstance(value, str) and value[:1] in ("[", "{") else value
        except (TypeError, ValueError):
            return default

    def set(self, values):
        with self._lock:
            parser = self._read()
            for key, value in values.items():
                parser.set("General", key, json.dumps(json.dumps(value, ensure_ascii=False), ensure_ascii=False) if isinstance(value, (dict, list)) else json.dumps(value))
            temporary = self._path.with_suffix(".ini.tmp")
            with temporary.open("w", encoding="utf-8") as output:
                parser.write(output)
            temporary.replace(self._path)
