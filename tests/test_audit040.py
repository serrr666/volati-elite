from volstudio import runner,db

def test_progress_layer_name_does_not_misdiagnose_missing_windows_types(monkeypatch):
    monkeypatch.setattr(db,'settings',lambda:{'language':'en'})
    raw="Progress: 0.00 Scanning layer_name using PdbSignatureScanner\nUnable to validate the plugin requirements: ['plugins.PsScan.kernel.symbol_table_name']"
    result=runner.friendly_error(raw,'windows')
    assert 'memory translation layer could not' not in result
    assert result.endswith(raw)

def test_windows_offline_pdb_failure_has_actionable_settings_guidance(monkeypatch):
    raw="OfflineException: unable to access ntkrnlmp.pdb\nUnable to validate plugins.PsScan.kernel.symbol_table_name"
    for lang in ['ru','en']:
        monkeypatch.setattr(db,'settings',lambda:{'language':lang})
        result=runner.friendly_error(raw,'windows')
        assert ('Настройки → Анализ' if lang=='ru' else 'Settings → Analysis') in result
        assert result.endswith(raw)
