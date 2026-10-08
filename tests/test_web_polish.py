from parcom_analytics.web.bridge import DesktopBridge


def test_theme_defaults_light_before_login_and_respects_saved_preferences(tmp_path):
    bridge = DesktopBridge(root=tmp_path)
    assert bridge.getPreferences() == {"theme": "light", "reducedMotion": False}
    assert bridge.setPreferences("dark", True)["ok"]
    restored = DesktopBridge(root=tmp_path)
    assert restored.getPreferences() == {"theme": "dark", "reducedMotion": True}
    assert not restored.setPreferences("invalid", False)["ok"]
