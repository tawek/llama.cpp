"""
Profile manager - saves/loads named presets of config option values.
Stores profiles as JSON files in ~/.llama-gui/profiles/
"""

import os
import json


class ProfileManager:
    def __init__(self):
        self._dir = os.path.expanduser('~/.llama-gui/profiles')
        os.makedirs(self._dir, exist_ok=True)

    def list_profiles(self):
        names = []
        if not os.path.isdir(self._dir):
            return names
        for f in sorted(os.listdir(self._dir)):
            if f.endswith('.json'):
                name = f[:-5]
                if name:
                    names.append(name)
        return names

    def load(self, name):
        path = os.path.join(self._dir, f'{name}.json')
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get('options', {})
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, name, options):
        path = os.path.join(self._dir, f'{name}.json')
        data = {'name': name, 'options': options}
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    def delete(self, name):
        path = os.path.join(self._dir, f'{name}.json')
        if os.path.exists(path):
            os.remove(path)
