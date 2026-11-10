"""Process-local graphics selection and deterministic WebEngine teardown."""
import os
import re

def configure_graphics(environ=None,platform=None):
    env=os.environ if environ is None else environ
    windows=(os.name=='nt') if platform is None else platform=='nt'
    mode=env.get('VOLSTUDIO_GRAPHICS','software' if windows else 'auto').lower()
    if mode not in ('software','auto'):
        mode='software' if windows else 'auto'
    if mode=='software':
        flags=env.get('QTWEBENGINE_CHROMIUM_FLAGS','')
        flags=re.sub(r'(?<!\S)--(?:enable-gpu|disable-gpu=false)(?!\S)', '',flags).strip()
        if not re.search(r'(?<!\S)--disable-gpu(?!\S)',flags):flags=(flags+' --disable-gpu').lstrip()
        env['QTWEBENGINE_CHROMIUM_FLAGS']=flags
        env['QT_OPENGL']='software'
        env['QT_QUICK_BACKEND']='software'
    return mode

def dispose_webengine(view,profile,delete):
    # Page is parented to the view. Destroying the view first synchronously
    # releases its Page/WebChannel before the non-owning profile is destroyed.
    delete(view)
    delete(profile)


class CloseGate:
    """Only the current draft-flush attempt may authorize closing the window."""
    def __init__(self):
        self.pending=False
        self.allowed=False
        self.generation=0
    def begin(self):
        if self.pending or self.allowed:return None
        self.pending=True;self.generation+=1
        return self.generation
    def finish(self,generation,success):
        if not self.pending or generation!=self.generation:return False
        self.pending=False;self.allowed=bool(success)
        return True
