"""Small, atomic, explicitly non-secret setup preferences. No session history."""
import json
from pathlib import Path
from PySide6.QtCore import QSaveFile, QIODevice, QStandardPaths


class Preferences:
    def __init__(self, path):
        self.path = Path(path)
        self.warning = ''

    @classmethod
    def default(cls):
        return cls(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)) / 'setup.json')

    @staticmethod
    def checked(provider, source, model, pin):
        if provider not in ('openrouter_free', 'openai') or source not in ('loopback', 'microphone'):
            raise ValueError('Unsupported setup choice.')
        if not isinstance(model, str) or len(model) > 4096 or '\0' in model or type(pin) is not bool:
            raise ValueError('Invalid setup preferences.')
        return dict(version=1, provider=provider, source=source, model=model, pin=pin)

    def load(self):
        try:
            with self.path.open('rb') as source:
                data = source.read(16385)
            if len(data) > 16384:
                raise ValueError()
            result = json.loads(data)
            if not isinstance(result, dict) or set(result) != {'version', 'provider', 'source', 'model', 'pin'}:
                raise ValueError()
            if type(result['version']) is not int or result['version'] != 1:
                raise ValueError()
            return self.checked(result['provider'], result['source'], result['model'], result['pin'])
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError, KeyError):
            self.warning = 'Saved setup could not be read; safe defaults are in use.'
            return {}

    def save(self, provider, source, model, pin):
        data = json.dumps(self.checked(provider, source, model, pin), ensure_ascii=True).encode('utf-8')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        target = QSaveFile(str(self.path))
        target.setDirectWriteFallback(False)
        if not target.open(QIODevice.OpenModeFlag.WriteOnly):
            raise OSError('Setup storage is not writable.')
        if target.write(data) != len(data):
            target.cancelWriting()
            raise OSError('Setup write did not complete.')
        if not target.commit():
            raise OSError('Setup could not be published atomically.')
