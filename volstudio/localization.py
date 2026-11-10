"""Initial UI language follows configured OS locales; explicit preferences win."""
from functools import lru_cache
import locale
import os


def configured_languages():
    result=[]
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        try:
            kernel.GetUserPreferredUILanguages.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.ULONG),wintypes.LPWSTR,ctypes.POINTER(wintypes.ULONG)]
            kernel.GetUserPreferredUILanguages.restype=wintypes.BOOL
            count,size=wintypes.ULONG(),wintypes.ULONG()
            kernel.GetUserPreferredUILanguages(0x8,ctypes.byref(count),None,ctypes.byref(size))
            if 0<size.value<32768:
                buffer=ctypes.create_unicode_buffer(size.value)
                if kernel.GetUserPreferredUILanguages(0x8,ctypes.byref(count),buffer,ctypes.byref(size)):
                    result.extend(''.join(buffer[:size.value]).split('\0'))
            buffer=ctypes.create_unicode_buffer(85)
            kernel.GetUserDefaultLocaleName.argtypes=[wintypes.LPWSTR,ctypes.c_int]
            if kernel.GetUserDefaultLocaleName(buffer,len(buffer)):
                result.append(buffer.value)
        except (OSError,AttributeError):
            pass
    try:
        result.append(locale.getlocale()[0] or '')
    except (ValueError,TypeError):
        pass
    return [value for value in result if value]


def language_for_locale(value):
    """Map regional BCP-47/Python Windows locale names to a shipped UI."""
    if not isinstance(value,str):
        return None
    primary=value.strip().split('.',1)[0].split('@',1)[0].replace('_','-').lower().split('-',1)[0]
    return {
        'en':'en','english':'en',
        'ru':'ru','russian':'ru',
        'zh':'zh-CN','chinese':'zh-CN',
        'chinese (simplified)':'zh-CN','chinese (traditional)':'zh-CN',
        'es':'es','spanish':'es',
        'de':'de','german':'de',
        'fr':'fr','french':'fr',
    }.get(primary)


@lru_cache(maxsize=1)
def default_language():
    # Keep the original RU rule for every translated language: English in the
    # OS list does not mask a configured translation. Windows order breaks ties.
    for value in configured_languages():
        language=language_for_locale(value)
        if language and language!='en':
            return language
    return 'en'


def windows_app_theme():
    """Read the user's application theme, independently of the taskbar theme."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
        value,kind=winreg.QueryValueEx(key,'AppsUseLightTheme')
    if kind!=winreg.REG_DWORD or value not in (0,1):
        return None
    return 'light' if value else 'dark'


def default_theme():
    """First launch follows Windows; unknown/unavailable settings prefer dark."""
    if os.name=='nt':
        try:
            return windows_app_theme() or 'dark'
        except (OSError,ImportError,ValueError):
            pass
    return 'dark'


SUPPORTED_LANGUAGES=('en','ru','zh-CN','es','de','fr')

@lru_cache(maxsize=4)
def native_catalog(language):
    import json,sys
    from pathlib import Path
    if language not in SUPPORTED_LANGUAGES or language in ('en','ru'):return {}
    root=Path(__file__).resolve().parent.parent
    path=root/('locale-data' if getattr(sys,'frozen',False) else 'frontend/src/locales')/(language+'.json')
    return json.loads(path.read_text(encoding='utf8'))

def native_text(english,russian=None,language=None):
    if language not in SUPPORTED_LANGUAGES:
        from . import db
        try:language=db.settings().get('language',default_language())
        except Exception:language=default_language()
    if language=='ru':return russian or english
    return native_catalog(language).get(english,english)
