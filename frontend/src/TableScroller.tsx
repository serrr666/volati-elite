import {useLayoutEffect,useRef,useState,type ReactNode} from 'react';
import {tr} from './i18n';
import './TableScroller.css';

// The upper native scrollbar controls the table. Horizontal wheel and
// trackpad events remain native; vertical scrolling never turns into sideways motion.
export function TableScroller({children}:{children:ReactNode}){
    const viewport=useRef<HTMLDivElement>(null),rail=useRef<HTMLDivElement>(null);
    const [size,setSize]=useState({width:0,gutter:0,overflow:false});
    useLayoutEffect(()=>{
        const view=viewport.current!;
        const measure=()=>{
            const next={width:view.scrollWidth,gutter:view.offsetWidth-view.clientWidth,overflow:view.scrollWidth>view.clientWidth+1};
            setSize(old=>old.width===next.width&&old.gutter===next.gutter&&old.overflow===next.overflow?old:next);
            if(rail.current)rail.current.scrollLeft=view.scrollLeft;
        };
        let frame=0,child:Element|null=null;
        const schedule=()=>{if(!frame)frame=requestAnimationFrame(()=>{frame=0;measure()})};
        const observer=new ResizeObserver(schedule);
        const attach=()=>{if(child)observer.unobserve(child);child=view.firstElementChild;if(child)observer.observe(child);schedule()};
        observer.observe(view);attach();
        const mutation=new MutationObserver(attach);mutation.observe(view,{childList:true});
        return()=>{observer.disconnect();mutation.disconnect();cancelAnimationFrame(frame)};
    },[]);
    function sync(from:HTMLDivElement,to:HTMLDivElement|null){
        if(to&&Math.abs(to.scrollLeft-from.scrollLeft)>0.5)to.scrollLeft=from.scrollLeft;
    }
    return <div className="table-scroller">
        <div className="table-scroll-top-wrap" hidden={!size.overflow} style={{paddingRight:size.gutter}}>
            <div className="table-scroll-top" ref={rail} tabIndex={0} role="region"
                aria-label={tr('Прокрутка столбцов влево и вправо')}
                title={tr('Перетащите ползунок, чтобы увидеть остальные столбцы')}
                onScroll={e=>sync(e.currentTarget,viewport.current)}>
                <div style={{width:size.width,height:1}}/>
            </div>
        </div>
        <div className="table-scroll" ref={viewport} tabIndex={0} role="region"
            aria-label={tr('Таблица результатов')}
            onScroll={e=>sync(e.currentTarget,rail.current)}>{children}</div>
    </div>;
}
