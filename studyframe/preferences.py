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
    def checked(provider, source, model, pin, glass_tint=25):
        if provider not in ('openrouter_free', 'openai') or source not in ('loopback', 'microphone'):
            raise ValueError('Unsupported setup choice.')
        if not isinstance(model, str) or len(model) > 4096 or '\0' in model or type(pin) is not bool:
            raise ValueError('Invalid setup preferences.')
        if type(glass_tint) is not int or not 0<=glass_tint<=90:raise ValueError('Invalid glass tint.')
        return dict(version=2, provider=provider, source=source, model=model, pin=pin,glass_tint=glass_tint)

    def load(self):
        try:
            with self.path.open('rb') as source:
                data = source.read(16385)
            if len(data) > 16384:
                raise ValueError()
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError()
            version=result.get('version')
            if type(version) is not int or version not in (1,2):
                raise ValueError()
            fields={'version','provider','source','model','pin'}|({'glass_tint'} if version==2 else set())
            if set(result)!=fields:raise ValueError()
            return self.checked(result['provider'], result['source'], result['model'], result['pin'],result.get('glass_tint',25))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError, KeyError):
            self.warning = 'Saved setup could not be read; safe defaults are in use.'
            return {}

    def save(self, provider, source, model, pin,glass_tint=25):
        data = json.dumps(self.checked(provider, source, model, pin,glass_tint), ensure_ascii=True).encode('utf-8')
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
