import {useRef,type ReactNode} from 'react';
import {useDialogFocus} from './useDialogFocus';
import {X} from 'lucide-react';
import {tr} from './i18n';
export function Dialog({title,children,close,wide=false}:{title:string;children:ReactNode;close:()=>void;wide?:boolean}){
    const ref=useRef<HTMLElement>(null);useDialogFocus(ref,close);
    return <div className="studio-dialog-backdrop" onMouseDown={e=>e.target===e.currentTarget&&close()}><section ref={ref} role="dialog" aria-modal="true" aria-label={title} className={'studio-dialog'+(wide?' studio-dialog-wide':'')}><div className="studio-dialog-heading"><h2>{title}</h2><button className="icon-button" aria-label={tr('Закрыть')} onClick={close}><X size={18}/></button></div>{children}</section></div>;
}
