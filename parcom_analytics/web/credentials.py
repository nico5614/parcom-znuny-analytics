"""Opt-in Windows vault; no automatic backend selection or plaintext fallback."""
import sys


class CredentialStore:
    def __init__(self, service="ParCom.ZnunyAnalytics.Login", vault=None):
        self._service = service
        self._vault = vault

    def _backend(self):
        if self._vault is None:
            if sys.platform != "win32":
                raise RuntimeError("Windows Credential Manager is unavailable")
            from keyring.backends.Windows import WinVaultKeyring
            self._vault = WinVaultKeyring()
            self._vault.persist = "local machine"
            if self._vault.priority <= 0:
                raise RuntimeError("Windows Credential Manager is unavailable")
        return self._vault

    def get(self):
        return self._backend().get_credential(self._service, None)

    def status(self):
        credential = self.get()
        return {"supported": True, "available": credential is not None,
                "username": credential.username if credential else None}

    def save(self, username, password):
        # Avoid WinVaultKeyring's multi-user compound copies of old passwords.
        self.remove()
        self._backend().set_password(self._service, username, password)

    def remove(self):
        credential = self.get()
        if credential:
            self._backend().delete_password(self._service, credential.username)
