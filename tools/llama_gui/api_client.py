"""
API client for llama.cpp server endpoints.
Handles polling of /slots, /metrics, /health, /props.
"""

import json
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


class ServerAPI:
    def __init__(self, base_url: str = 'http://127.0.0.1:8080'):
        self.base_url = base_url.rstrip('/')

    def _request(self, path: str, method: str = 'GET',
                 timeout: int = 5) -> Optional[Dict]:
        url = f'{self.base_url}{path}'
        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode('utf-8')
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {'raw': data}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            return None

    def _request_post(self, path: str, data: Dict,
                      timeout: int = 10) -> Optional[Dict]:
        url = f'{self.base_url}{path}'
        payload = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = resp.read().decode('utf-8')
                try:
                    return json.loads(resp_data)
                except json.JSONDecodeError:
                    return {'raw': resp_data}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            return None

    def health(self) -> Optional[Dict]:
        return self._request('/health')

    def health_v1(self) -> Optional[Dict]:
        return self._request('/v1/health')

    def slots(self) -> Optional[Dict]:
        return self._request('/slots')

    def metrics(self) -> Optional[str]:
        result = self._request('/metrics')
        if result and 'raw' in result:
            return result['raw']
        return None

    def props(self) -> Optional[Dict]:
        return self._request('/props')

    def models(self) -> Optional[Dict]:
        return self._request('/models')

    def chat_completion(self, messages: list, **kwargs) -> Optional[Dict]:
        data = {
            'messages': messages,
            'stream': False,
            **kwargs
        }
        return self._request_post('/v1/chat/completions', data)

    def completion(self, prompt: str, **kwargs) -> Optional[Dict]:
        data = {
            'prompt': prompt,
            'stream': False,
            **kwargs
        }
        return self._request_post('/v1/completions', data)

    def is_alive(self) -> bool:
        result = self.health()
        return result is not None and 'status' in result and result['status'] == 'ok'


def parse_prometheus_metrics(text: str) -> Dict[str, float]:
    """Parse Prometheus-style metrics text into a dict."""
    metrics = {}
    if not text:
        return metrics

    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split(' ')
        if len(parts) >= 2:
            name = parts[0]
            try:
                value = float(parts[1])
                metrics[name] = value
            except ValueError:
                continue

    return metrics

