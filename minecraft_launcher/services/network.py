"""Apply HTTPS and bounded socket waits, including requests made by launcher-lib.

Installed once at app startup. This process only performs launcher requests.
"""
from urllib.parse import urlsplit
import requests


def configure_network():
    original = requests.sessions.Session.send
    if getattr(original, '_xlauncher', False):
        return

    def send(session, request, **kwargs):
        if urlsplit(request.url).scheme != 'https':
            raise requests.RequestException('Se rechazó una conexión que no utiliza HTTPS.')
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = (15, 60)
        response = original(session, request, **kwargs)
        response.raise_for_status()
        return response

    send._xlauncher = True
    requests.sessions.Session.send = send
