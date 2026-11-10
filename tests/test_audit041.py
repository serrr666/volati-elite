import json
import pytest
from fastapi.testclient import TestClient
from volstudio import db,runner
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER
from volstudio.localization import SUPPORTED_LANGUAGES,native_text,native_catalog

@pytest.fixture(scope='module')
def locales41(tmp_path_factory):
    prior=db.DATA;db.DATA=tmp_path_factory.mktemp('locales41')
    old_start,old_shutdown=runner.start,runner.shutdown;runner.start=lambda:None;runner.shutdown=lambda:None
    try:
        with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:yield client
    finally:db.DATA=prior;runner.start,runner.shutdown=old_start,old_shutdown

@pytest.mark.parametrize('language',SUPPORTED_LANGUAGES)
def test_selected_language_survives_preferences_and_boot_html(locales41,language):
    r=locales41.put('/api/preferences',json={'language':language,'theme':'light'})
    assert r.status_code==200 and locales41.get('/api/preferences').json()['language']==language
    assert f'<html lang="{language}"' in locales41.get('/').text

def test_unknown_locale_is_rejected_without_overwriting_selection(locales41):
    before=locales41.get('/api/preferences').json()
    assert locales41.put('/api/preferences',json={'language':'../../escape'}).status_code==422
    assert locales41.get('/api/preferences').json()==before

@pytest.mark.parametrize('language',['zh-CN','es','de','fr'])
def test_native_dialog_catalog_is_local_and_not_russian(language):
    values=native_catalog(language)
    assert len(values)>=675
    assert native_text('Open memory image','Открыть образ памяти',language)==values['Open memory image']
    assert native_text('Export failed','Ошибка экспорта',language)==values['Export failed']
    assert native_text('_RAW_PLUGIN_ARGUMENT_',language=language)=='_RAW_PLUGIN_ARGUMENT_'

def test_native_russian_and_english_keep_existing_behavior():
    assert native_text('Save result','Сохранить результат','ru')=='Сохранить результат'
    assert native_text('Save result','Сохранить результат','en')=='Save result'
