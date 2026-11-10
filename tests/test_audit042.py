import pytest
from fastapi.testclient import TestClient
from volstudio import db,localization,runner
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER

@pytest.mark.parametrize('name,expected',[
    ('en-US','en'),('en_GB.UTF-8','en'),('English_United States.1252','en'),
    ('ru-RU','ru'),('ru_KZ.UTF-8','ru'),('Russian_Russia.1251','ru'),
    ('zh-CN','zh-CN'),('zh-SG','zh-CN'),('zh-Hans-CN','zh-CN'),
    ('zh-TW','zh-CN'),('zh-Hant-HK','zh-CN'),
    ('Chinese (Simplified)_China.936','zh-CN'),('Chinese (Traditional)_Taiwan.950','zh-CN'),
    ('es-ES','es'),('es-MX','es'),('es-AR','es'),('es-419','es'),('Spanish_Spain.1252','es'),
    ('de-DE','de'),('de-AT','de'),('de-CH','de'),('German_Germany.1252','de'),
    ('fr-FR','fr'),('fr-CA','fr'),('fr-CH','fr'),('fr-CI','fr'),('French_France.1252','fr'),
    ('  FR_ca.UTF-8  ','fr'),('de_DE@euro','de'),
    ('pt-BR',None),('ja-JP',None),('C',None),('',None),(None,None),
])
def test_regional_locales_map_to_supported_ui(name,expected):
    assert localization.language_for_locale(name)==expected

@pytest.mark.parametrize('names,expected',[
    (['en-US','ru-RU'],'ru'),(['en-GB','fr-CA'],'fr'),(['en-US','zh-Hant-TW'],'zh-CN'),
    (['ja-JP','es-MX'],'es'),(['en-US','de-CH'],'de'),
    (['fr-CA','ru-RU','de-DE'],'fr'),(['ru-RU','fr-FR'],'ru'),
    (['en-US','pt-BR','ja-JP'],'en'),([], 'en'),
])
def test_first_configured_translation_wins_with_english_fallback(monkeypatch,names,expected):
    monkeypatch.setattr(localization,'configured_languages',lambda:names)
    localization.default_language.cache_clear()
    try:assert localization.default_language()==expected
    finally:localization.default_language.cache_clear()

@pytest.mark.parametrize('detected',['en','ru','zh-CN','es','de','fr'])
def test_first_launch_and_manual_override_survive_restart(tmp_path,monkeypatch,detected):
    monkeypatch.setattr(db,'DATA',tmp_path/'isolated-profile')
    monkeypatch.setattr(runner,'start',lambda:None)
    monkeypatch.setattr(runner,'shutdown',lambda:None)
    monkeypatch.setattr(localization,'configured_languages',lambda:['en-US',detected])
    localization.default_language.cache_clear()
    try:
        with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:
            assert client.get('/api/preferences').json()['language']==detected
            assert f'<html lang="{detected}"' in client.get('/').text
            assert client.put('/api/preferences',json={'language':'en','theme':'dark'}).status_code==200
        with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:
            assert client.get('/api/preferences').json()['language']=='en'
            assert '<html lang="en"' in client.get('/').text
    finally:localization.default_language.cache_clear()
