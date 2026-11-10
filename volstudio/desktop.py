from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

from . import __version__


def main():
    if len(sys.argv)>1 and sys.argv[1]=="--pipeline-worker":
        from .pipeline import run
        return run(sys.argv[2])
    if len(sys.argv)>1 and sys.argv[1]=="--engine-worker":
        from .engine_worker import run
        return run(sys.argv[2])
    if len(sys.argv)>1 and sys.argv[1]=="--catalog":
        from .catalog import discover
        try:
            result=discover(json.loads(sys.argv[3]))
            Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,default=str),encoding="utf-8")
            return 0
        except Exception:
            import traceback
            Path(sys.argv[2]).with_suffix(".error.txt").write_text(traceback.format_exc(),encoding="utf-8")
            return 1
    data=Path(os.environ.get("VOLSTUDIO_DATA",Path(os.environ.get("LOCALAPPDATA",Path.home()))/"Vol3Studio"))
    data.mkdir(parents=True,exist_ok=True)
    os.environ["VOLSTUDIO_DATA"]=str(data)
    os.environ["PYTHONUTF8"]="1"
    import faulthandler
    crash_log=open(data/"native-crash.log","a",encoding="utf-8",buffering=1)
    faulthandler.enable(file=crash_log,all_threads=True)
    from .security import API_TOKEN,TOKEN_HEADER
    os.environ['VOLSTUDIO_TOKEN']=API_TOKEN
    if sys.stdout is None:
        sys.stdout=open(data/"desktop-output.log","a",encoding="utf-8",buffering=1)
    if sys.stderr is None:
        sys.stderr=open(data/"desktop-error.log","a",encoding="utf-8",buffering=1)
    logging.basicConfig(filename=data/"application.log",level=logging.INFO,encoding="utf-8",format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv)>1 and sys.argv[1]=="--serve":
        import uvicorn
        (data/'desktop-ready.json').write_text(json.dumps({'port':int(sys.argv[2]),'pid':os.getpid(),'version':__version__,'token':API_TOKEN}),encoding='utf8')
        uvicorn.run("volstudio.app:app",host="127.0.0.1",port=int(sys.argv[2]),log_config=None,access_log=False)
        return 0
    from .desktop_runtime import configure_graphics,dispose_webengine,CloseGate
    graphics_mode=configure_graphics()
    from PySide6.QtCore import qVersion
    from shiboken6 import delete as delete_qobject
    from PySide6.QtCore import QEvent,QFile,QLockFile,QObject,Qt,QTimer,QUrl,Slot
    from PySide6.QtGui import QColor,QDesktopServices,QFont,QIcon,QPainter,QPixmap
    from PySide6.QtWidgets import QApplication,QFileDialog,QMainWindow,QMessageBox,QSplashScreen,QWidget
    from PySide6.QtWebEngineCore import QWebEngineDownloadRequest,QWebEnginePage,QWebEngineProfile,QWebEngineScript,QWebEngineUrlRequestInterceptor,QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    import uvicorn

    from .localization import native_text

    def preferred_setting(key,default):
        try:
            import sqlite3
            with sqlite3.connect(data/"studio.sqlite3") as c:
                row=c.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
            return json.loads(row[0]) if row else default
        except Exception:
            return default

    def preferred_language():
        from .localization import default_language
        return preferred_setting('language',default_language())

    if graphics_mode=='software':QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)
    application=QApplication(sys.argv)
    logging.info('Desktop runtime: Qt=%s graphics=%s',qVersion(),graphics_mode)
    application.setApplicationName("Volati Elite")
    application.setOrganizationName("Vol3Studio")
    # One worker queue and one session key per profile. A second desktop must
    # never reset active jobs or overwrite desktop-ready.json for the first.
    profile_lock=QLockFile(str(data.resolve()/'.studio.lock'))
    profile_lock.setStaleLockTime(0)
    if not profile_lock.tryLock(0):
        QMessageBox.information(None,'volati elite',native_text(
            'This workspace is already open in another volati elite window. Switch to that window.',
            'Это рабочее пространство уже открыто в другом окне volati elite. Переключитесь в него.'))
        return 0
    root=Path(__file__).resolve().parent.parent
    icon=QIcon(str(root/"assets"/"app.ico"))
    application.setWindowIcon(icon)
    splash_pixmap=QPixmap(360,144)
    from .localization import default_theme
    light_start=preferred_setting('theme',default_theme())=='light'
    splash_pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(splash_pixmap);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#e3dae0" if light_start else "#352a32"))
    painter.setBrush(QColor("#faf7f9" if light_start else "#151115"))
    painter.drawRoundedRect(1,1,358,142,16,16)
    painter.setPen(QColor("#2b1724" if light_start else "#f5eef3"))
    font=painter.font();font.setPixelSize(26);font.setWeight(QFont.Weight.DemiBold);painter.setFont(font)
    painter.drawText(0,0,360,144,Qt.AlignmentFlag.AlignCenter,"volati elite")
    painter.end()
    splash=QSplashScreen(splash_pixmap)
    splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    splash.show()
    application.processEvents()

    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(("127.0.0.1",0))
    sock.listen(128)
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config("volstudio.app:app",host="127.0.0.1",port=port,log_config=None,access_log=False))
    server_thread=threading.Thread(target=lambda:server.run(sockets=[sock]),name="studio-local-backend",daemon=True)
    server_thread.start()

    class LocalSession(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self,info):
            url=info.requestUrl()
            if url.scheme()=='http' and url.host()=='127.0.0.1' and url.port()==port:
                info.setHttpHeader(TOKEN_HEADER.encode(),API_TOKEN.encode())

    class Page(QWebEnginePage):
        def acceptNavigationRequest(self,url,nav_type,is_main_frame):
            local=url.scheme()=='http' and url.host()=='127.0.0.1' and url.port()==port
            if is_main_frame and not local and url.toString()!='about:blank':
                if url.scheme() in ('http','https') and nav_type==QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                    QDesktopServices.openUrl(url)
                return False
            return super().acceptNavigationRequest(url,nav_type,is_main_frame)

    class MemoryView(QWebEngineView):
        def dragEnterEvent(self,event):
            if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
                event.acceptProposedAction()
            else:
                super().dragEnterEvent(event)
        def dragMoveEvent(self,event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                super().dragMoveEvent(event)
        def dropEvent(self,event):
            paths=[u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile() and Path(u.toLocalFile()).is_file()]
            if paths:
                window.deliver_path(paths[0])
                event.acceptProposedAction()
            else:
                super().dropEvent(event)

    class NativeDropFilter(QObject):
        # WebEngine's internal render widget may receive drops before its view.
        def eventFilter(self,obj,event):
            if event.type() not in (QEvent.Type.DragEnter,QEvent.Type.DragMove,QEvent.Type.Drop):
                return False
            if not isinstance(obj,QWidget) or not (obj is window.view or window.view.isAncestorOf(obj)):
                return False
            if not event.mimeData().hasUrls():
                return False
            paths=[url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            if not paths:
                return False
            if event.type()==QEvent.Type.Drop:
                window.deliver_path(paths[0])
            event.acceptProposedAction()
            return True

    class Bridge(QObject):
        @Slot(bool,str,int)
        def finishClose(self,success,detail,generation):
            window.finish_close(success,detail,generation)
        @Slot(str,result=str)
        def pickFile(self,language):
            from . import db
            title=native_text("Open memory image","Открыть образ памяти",language)
            filters=native_text("Memory images","Образы памяти",language)+" (*.raw *.mem *.vmem *.vmss *.vmsn *.dmp *.lime *.bin *.elf *.img *.core *.kcore);;"+native_text("All files","Все файлы",language)+" (*)"
            selected,_=QFileDialog.getOpenFileName(window,title,db.settings().get('last_image_directory',''),filters)
            if selected:
                db.save_settings({'last_image_directory':str(Path(selected).parent)})
            return selected
        @Slot(str,result=str)
        def pickDirectory(self,language):
            from . import db
            selected=QFileDialog.getExistingDirectory(window,native_text("Choose OS analysis data directory","Выбрать папку с данными ОС для анализа",language),db.settings().get('last_symbol_directory',''))
            if selected:
                db.save_settings({'last_symbol_directory':selected})
            return selected
        @Slot()
        def openDataDirectory(self):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(data)))

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Volati Elite")
            self.setWindowIcon(icon)
            available=application.primaryScreen().availableGeometry()
            # Reserve space for the native frame/taskbar. A fixed 960px height
            # otherwise puts Run/Save and the bottom scrollbar off screen.
            width,height=min(1460,max(320,available.width()-40)),min(960,max(320,available.height()-70))
            self.setMinimumSize(min(900,width),min(650,height))
            self.resize(width,height)
            self.view=MemoryView(self)
            self.view.setAcceptDrops(True)
            self.drop_filter=NativeDropFilter(self)
            application.installEventFilter(self.drop_filter)
            self.profile=QWebEngineProfile("Vol3Studio",self)
            self.profile.setPersistentStoragePath(str(data/"web-profile"))
            self.profile.setCachePath(str(data/"web-cache"))
            self.session=LocalSession(self.profile)
            self.profile.setUrlRequestInterceptor(self.session)
            self.page=Page(self.profile,self.view)
            self.page.setBackgroundColor(QColor("#faf7f9" if light_start else "#0f0b0e"))
            self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,False)
            self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,False)
            self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent,False)
            self.view.setPage(self.page)
            self.channel=QWebChannel(self.page)
            self.bridge=Bridge(self)
            self.channel.registerObject("studio",self.bridge)
            self.page.setWebChannel(self.channel)
            file=QFile(":/qtwebchannel/qwebchannel.js")
            if not file.open(QFile.OpenModeFlag.ReadOnly):
                raise RuntimeError("Qt WebChannel resource is unavailable")
            js=bytes(file.readAll()).decode("utf-8")
            file.close()
            js+='\nnew QWebChannel(qt.webChannelTransport,function(c){window.volstudioNative={pickFile:function(){return new Promise(function(resolve){c.objects.studio.pickFile(document.documentElement.lang,resolve);});},pickDirectory:function(){return new Promise(function(resolve){c.objects.studio.pickDirectory(document.documentElement.lang,resolve);});},openDataDirectory:function(){c.objects.studio.openDataDirectory();},finishClose:function(success,detail,generation){c.objects.studio.finishClose(success,detail,generation);}};window.dispatchEvent(new Event("volstudio:native-ready"));});'
            script=QWebEngineScript()
            script.setName("Vol3StudioNativeBridge")
            script.setSourceCode(js)
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script.setRunsOnSubFrames(False)
            self.page.scripts().insert(script)
            self.profile.downloadRequested.connect(self.download)
            self.setCentralWidget(self.view)
            self.pending_path=next((str(Path(a).resolve()) for a in sys.argv[1:] if Path(a).is_file()),None)
            self.shutting_down=False
            self.shutdown_complete=False
            self.shutdown_thread=None
            self.close_gate=CloseGate()
            self.view.loadFinished.connect(self.page_ready)
            self.page.renderProcessTerminated.connect(self.renderer_stopped)
        def renderer_stopped(self,status,code):
            if self.shutting_down or self.close_gate.pending or self.close_gate.allowed or status==QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus:
                return
            logging.error("WebEngine renderer terminated: status=%s code=%s",status,code)
            answer=QMessageBox.warning(self,'volati elite',native_text(
                'The interface stopped unexpectedly. Analysis runs remain in the local engine. Reload the interface?',
                'Интерфейс неожиданно остановился. Запуски анализа остаются в локальном движке. Перезагрузить интерфейс?'),
                QMessageBox.StandardButton.Retry|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Retry)
            if answer==QMessageBox.StandardButton.Retry:self.view.reload()
        def deliver_path(self,path):
            if self.shutting_down:return
            payload=json.dumps({"path":str(Path(path).resolve()),"name":Path(path).name},ensure_ascii=True)
            self.page.runJavaScript('window.__volstudioPendingDrop='+payload+';window.dispatchEvent(new CustomEvent("volstudio:drop",{detail:window.__volstudioPendingDrop}));')
        def page_ready(self,ok):
            if self.shutting_down:return
            if ok and self.pending_path:
                self.deliver_path(self.pending_path)
                self.pending_path=None
        def download(self,request):
            if self.shutting_down:
                request.cancel();return
            if request.url().scheme()!='http' or request.url().host()!='127.0.0.1' or request.url().port()!=port:
                request.cancel();return
            from . import db
            initial=str(Path(db.settings().get('last_export_directory',''))/request.suggestedFileName())
            filename,_=QFileDialog.getSaveFileName(self,native_text("Save result","Сохранить результат"),initial)
            if not filename:
                request.cancel();return
            target=Path(filename)
            db.save_settings({'last_export_directory':str(target.parent)})
            request.setDownloadDirectory(str(target.parent))
            request.setDownloadFileName(target.name)
            def download_state(state):
                if self.shutting_down:return
                if state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
                    title=native_text("Export failed","Ошибка экспорта")
                    message=native_text("The download was interrupted. The saved file may be incomplete; do not use it as evidence.\n","Загрузка прервана. Сохранённый файл может быть неполным; не используйте его как результат анализа.\n")
                    QMessageBox.critical(self,title,message+request.interruptReasonString())
            request.stateChanged.connect(download_state)
            request.accept()
        def closeEvent(self,event):
            if not self.close_gate.allowed:
                event.ignore()
                generation=self.close_gate.begin()
                if generation is None:return
                script='''(function(){
                    if(!window.volstudioNative||!window.volstudioNative.finishClose)return false;
                    Promise.resolve().then(function(){return window.__volstudioFlushDrafts?window.__volstudioFlushDrafts():undefined;})
                    .then(function(){window.volstudioNative.finishClose(true,"",__GENERATION__);},function(error){window.volstudioNative.finishClose(false,String(error&&error.message||error),__GENERATION__);});
                    return true;
                })()'''.replace('__GENERATION__',str(generation))
                self.page.runJavaScript(script,lambda hooked:self.finish_close(True,'',generation) if hooked is not True else None)
                QTimer.singleShot(15000,lambda:self.finish_close(False,'Draft save timeout',generation))
                return
            if self.shutdown_complete:
                event.accept();return
            event.ignore()
            if not self.shutting_down:
                self.shutting_down=True
                # Leave the WebChannel callback/close event stack before Qt
                # objects are destroyed. Engine shutdown never blocks the GUI.
                QTimer.singleShot(0,self.begin_shutdown)
        def begin_shutdown(self):
            self.hide()
            self.view.stop()
            def stop_engine():
                from . import runner
                try:runner.shutdown()
                finally:
                    server.should_exit=True
                    server_thread.join(timeout=5)
            self.shutdown_thread=threading.Thread(target=stop_engine,name='studio-shutdown',daemon=True)
            self.shutdown_thread.start()
            self.wait_for_shutdown()
        def wait_for_shutdown(self):
            if self.shutdown_thread.is_alive():
                QTimer.singleShot(50,self.wait_for_shutdown);return
            application.removeEventFilter(self.drop_filter)
            # Qt requires every Page to be destroyed BEFORE its Profile.
            # deleteLater() followed by application exit cannot guarantee that.
            dispose_webengine(self.view,self.profile,delete_qobject)
            logging.info('Desktop shutdown: page/view and profile disposed in order')
            self.shutdown_complete=True
            self.close()
            # The window was hidden before teardown; lastWindowClosed is not
            # guaranteed for an already hidden window. End the event loop too.
            application.quit()
        def finish_close(self,success,detail,generation):
            if not self.close_gate.finish(generation,success):return
            if success:
                QTimer.singleShot(0,self.close)
            else:
                QMessageBox.warning(self,native_text('Draft not saved','Черновик не сохранён'),
                    native_text('The draft could not be saved. The window stays open to protect your notes. Try saving again.\n','Не удалось сохранить черновик. Окно остаётся открытым, чтобы не потерять заметки. Повторите сохранение.\n')+detail)

    try:
        window=Window()
    except Exception as exc:
        logging.exception("Desktop initialization failed")
        splash.close()
        QMessageBox.critical(None,"volati elite",native_text("Unable to open the interface:","Не удалось открыть интерфейс:")+"\n"+str(exc))
        server.should_exit=True
        return 1
    started=time.monotonic()
    timer=QTimer()
    def ready():
        if server.started:
            timer.stop()
            (data/"desktop-ready.json").write_text(json.dumps({"port":port,"pid":os.getpid(),"version":__version__,"token":API_TOKEN}),encoding="utf-8")
            window.view.load(QUrl(f"http://127.0.0.1:{port}/"))
            window.show()
            splash.finish(window)
        elif time.monotonic()-started>150 or not server_thread.is_alive():
            timer.stop();splash.close()
            QMessageBox.critical(None,"volati elite",native_text("Unable to start the engine. Details:","Не удалось запустить движок. Подробности:")+" "+str(data/"application.log"))
            application.quit()
    timer.timeout.connect(ready)
    timer.start(100)
    result=application.exec()
    server.should_exit=True
    return result
