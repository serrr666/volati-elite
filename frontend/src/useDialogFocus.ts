import {useEffect,useRef,type RefObject} from 'react';
const stack:HTMLElement[]=[];
export function useDialogFocus(ref:RefObject<HTMLElement|null>,close:()=>void){
    const latest=useRef(close);latest.current=close;
    useEffect(()=>{
        const dialog=ref.current;if(!dialog)return;
        const previous=document.activeElement as HTMLElement|null;
        const controls=()=>Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],summary,input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(el=>el.getClientRects().length&&!el.matches(':disabled'));
        stack.push(dialog);
        if(!dialog.contains(document.activeElement))controls()[0]?.focus();
        const key=(event:KeyboardEvent)=>{
            if(stack.at(-1)!==dialog)return;
            if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();latest.current()}
            else if(event.key==='Tab'){
                const items=controls(),first=items[0],last=items.at(-1);if(!first||!last){event.preventDefault();return}
                if(!dialog.contains(document.activeElement)||(!event.shiftKey&&document.activeElement===last)){event.preventDefault();first.focus()}
                else if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
            }
        };
        window.addEventListener('keydown',key,true);
        return()=>{window.removeEventListener('keydown',key,true);const index=stack.indexOf(dialog);if(index>=0)stack.splice(index,1);if(previous?.isConnected&&(!stack.length||stack.at(-1)?.contains(previous)))previous.focus()};
    },[ref]);
}
