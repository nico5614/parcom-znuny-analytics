from types import SimpleNamespace
from unittest.mock import Mock
import json
import sys
import uuid

import pytest

from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.credentials import CredentialStore


def test_save_is_opt_in_and_only_after_successful_authentication():
    vault = Mock()
    vault.get_credential.return_value = None
    store = CredentialStore(vault=vault)
    client = Mock()
    bridge = DesktopBridge(client=client, credential_store=store)
    assert bridge.login("user", "synthetic-secret")["ok"]
    vault.set_password.assert_not_called()
    assert bridge.login("user", "synthetic-secret", True)["ok"]
    vault.set_password.assert_called_once_with(store._service, "user", "synthetic-secret")
    client.login.side_effect = RuntimeError("private detail")
    assert not bridge.login("user", "other-secret", True)["ok"]
    assert vault.set_password.call_count == 1
    assert "synthetic-secret" not in repr(vars(bridge))


def test_password_never_crosses_bridge_and_removal_deletes_previous_identity():
    vault = Mock()
    vault.get_credential.return_value = SimpleNamespace(username="user", password="synthetic-secret")
    client = Mock()
    store = CredentialStore(vault=vault)
    bridge = DesktopBridge(client=client, credential_store=store)
    status = bridge.getSavedCredentials()
    assert status == {"supported": True, "available": True, "username": "user"}
    reply = bridge.loginSaved()
    client.login.assert_called_once_with("user", "synthetic-secret")
    assert "synthetic-secret" not in json.dumps([status, reply])
    assert bridge.removeSavedCredentials()["ok"]
    vault.delete_password.assert_called_once_with(store._service, "user")
    vault.reset_mock()
    store.save("new-user", "new-secret")
    vault.delete_password.assert_called_once_with(store._service, "user")
    vault.set_password.assert_called_once_with(store._service, "new-user", "new-secret")


def test_vault_failure_does_not_prevent_login_or_reveal_details():
    store = Mock()
    store.status.side_effect = store.get.side_effect = store.remove.side_effect = store.save.side_effect = RuntimeError("synthetic-secret")
    bridge = DesktopBridge(client=Mock(), credential_store=store)
    assert bridge.getSavedCredentials() == {"supported": False, "available": False, "username": None}
    assert not bridge.loginSaved()["ok"]
    assert not bridge.removeSavedCredentials()["ok"]
    reply = bridge.login("user", "synthetic-secret", True)
    assert reply["ok"] and reply["data"]["credentialWarning"]
    assert "synthetic-secret" not in json.dumps(reply)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows vault integration")
def test_native_vault_roundtrip_in_isolated_synthetic_target():
    store = CredentialStore(service="ParCom.ZnunyAnalytics.Test." + uuid.uuid4().hex)
    try:
        assert not store.status()["available"]
        store.save("validation", "synthetic-validation-only")
        assert store.status() == {"supported": True, "available": True, "username": "validation"}
        assert store.get().password == "synthetic-validation-only"
        store.save("replacement", "synthetic-replacement-only")
        assert store.status()["username"] == "replacement"
        assert store._backend().get_password(store._service, "validation") is None
        store.remove()
        assert not store.status()["available"]
    finally:
        store.remove()
