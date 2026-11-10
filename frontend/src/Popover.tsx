import {useEffect,useRef,type ReactNode,type RefObject,type KeyboardEventHandler} from 'react';

type Props={children:ReactNode;className:string;label:string;id?:string;dismiss:()=>void;surfaceRef?:RefObject<HTMLDivElement|null>;onKeyDown?:KeyboardEventHandler<HTMLDivElement>};

// A non-modal surface: outside clicks dismiss it without stealing focus.
// Escape restores the trigger only when focus belongs to this surface/trigger.
export function Popover({children,className,label,id,dismiss,surfaceRef,onKeyDown}:Props){
    const ownRef=useRef<HTMLDivElement>(null),ref=surfaceRef??ownRef;
    const latest=useRef(dismiss);latest.current=dismiss;
    useEffect(()=>{
        const outside=(event:PointerEvent)=>{
            const parent=ref.current?.parentElement;
            if(parent&&event.target instanceof Node&&!parent.contains(event.target))latest.current();
        };
        const escape=(event:KeyboardEvent)=>{
            const parent=ref.current?.parentElement;
            if(event.key!=='Escape'||!parent?.contains(document.activeElement))return;
            event.preventDefault();event.stopPropagation();
            latest.current();parent.querySelector<HTMLButtonElement>(':scope > button')?.focus();
        };
        document.addEventListener('pointerdown',outside);
        document.addEventListener('keydown',escape);
        return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape)};
    },[ref]);
    return <div ref={ref} id={id} role="dialog" aria-label={label} className={className} onKeyDown={onKeyDown}>{children}</div>;
}
