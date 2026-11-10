import pytest
from volstudio.desktop_runtime import configure_graphics,dispose_webengine

def test_windows_software_rendering_is_local_and_keeps_the_sandbox():
    env={'QTWEBENGINE_CHROMIUM_FLAGS':'--enable-logging --log-level=1'}
    assert configure_graphics(env,'nt')=='software'
    assert env['QT_OPENGL']=='software' and env['QT_QUICK_BACKEND']=='software'
    assert env['QTWEBENGINE_CHROMIUM_FLAGS']=='--enable-logging --log-level=1 --disable-gpu'
    assert '--no-sandbox' not in env['QTWEBENGINE_CHROMIUM_FLAGS']
    assert '--single-process' not in env['QTWEBENGINE_CHROMIUM_FLAGS']

@pytest.mark.parametrize('value',['software','SOFTWARE','broken'])
def test_repeated_configuration_does_not_duplicate_flags(value):
    env={'VOLSTUDIO_GRAPHICS':value,'QTWEBENGINE_CHROMIUM_FLAGS':'--enable-gpu --disable-gpu=false'}
    configure_graphics(env,'nt');configure_graphics(env,'nt')
    assert env['QTWEBENGINE_CHROMIUM_FLAGS']=='--disable-gpu'

def test_explicit_native_graphics_does_not_change_external_settings():
    env={'VOLSTUDIO_GRAPHICS':'auto','QT_OPENGL':'desktop','QTWEBENGINE_CHROMIUM_FLAGS':'--enable-logging'}
    before=env.copy();assert configure_graphics(env,'nt')=='auto';assert env==before

def test_non_windows_keeps_existing_default():
    env={};assert configure_graphics(env,'posix')=='auto' and env=={}

def test_profile_is_never_disposed_while_its_page_is_live():
    live={'page':True};events=[]
    def delete(obj):
        if obj=='view':live['page']=False
        else:assert not live['page']
        events.append(obj)
    dispose_webengine('view','profile',delete)
    assert events==['view','profile']


def test_late_close_reply_cannot_authorize_another_attempt():
    from volstudio.desktop_runtime import CloseGate
    gate=CloseGate();first=gate.begin();assert gate.begin() is None
    assert gate.finish(first,False) and not gate.allowed
    second=gate.begin();assert second>first
    assert not gate.finish(first,True) and gate.pending and not gate.allowed
    assert gate.finish(second,True) and gate.allowed and not gate.pending
    assert not gate.finish(second,False) and gate.allowed

def test_graphics_setup_preserves_quoted_paths_and_spaces():
    original='--disk-cache-dir="C:\\QA  data\\cache" --enable-logging'
    env={'QTWEBENGINE_CHROMIUM_FLAGS':original}
    configure_graphics(env,'nt')
    assert env['QTWEBENGINE_CHROMIUM_FLAGS']==original+' --disable-gpu'
