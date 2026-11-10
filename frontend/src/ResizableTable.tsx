import {useEffect,useLayoutEffect,useRef,useState,type ReactNode,type CSSProperties,type PointerEvent,type KeyboardEvent} from 'react';
import {ArrowDownUp,Filter} from 'lucide-react';
import {columnWidths,clampColumnWidth,MIN_COLUMN_WIDTH,MAX_COLUMN_WIDTH} from './columnWidths';
import {tr} from './i18n';
import './ResizableTable.css';

type Props={pageKey:string;rowNumberDigits:number;scope:string;columns:string[];sort:string;direction:string;onSort:(column:string)=>void;children:ReactNode;filterColumns?:string[];onFilter?:(column:string)=>void};
type Drag={pointer:number;column:string;x:number;base:Map<string,number>;width:number};
export function ResizableTable({pageKey,rowNumberDigits,scope,columns,sort,direction,onSort,children,filterColumns=[],onFilter}:Props){
    const table=useRef<HTMLTableElement>(null),drag=useRef<Drag|null>(null);
    const [widths,setWidths]=useState(()=>columnWidths.read(scope));
    const [fixed,setFixed]=useState(false);
    const metadata=useRef([40,22]);
    const frame=useRef(0),pendingWidth=useRef<Map<string,number>|null>(null);
    useEffect(()=>()=>{cancelAnimationFrame(frame.current)},[]);
    function measured(){
        const cells=table.current?.tHead?.rows[0].cells;
        const next=new Map(widths);
        if(cells){
            const cell=table.current!.querySelector<HTMLTableCellElement>('.index-cell');
            const canvas=document.createElement('canvas').getContext('2d')!;
            const css=getComputedStyle(cell??cells[1]);canvas.font=css.font;
            metadata.current=[cells[0].getBoundingClientRect().width,Math.max(20,Math.ceil(canvas.measureText('9'.repeat(rowNumberDigits)).width+parseFloat(css.paddingLeft)+parseFloat(css.paddingRight)))];
            columns.forEach((column,i)=>next.set(column,clampColumnWidth(cells[i+2].getBoundingClientRect().width)));
        }
        return next;
    }
    function commit(next:Map<string,number>){setWidths(next);columnWidths.save(scope,next);setFixed(true);}
    useLayoutEffect(()=>{
        const initial=measured();
        // Saved widths belong to column names, regardless of visibility/order.
        for(const column of columns)if(widths.has(column))initial.set(column,widths.get(column)!);
        for(const column of columns){
            if(columnWidths.read(scope).has(column)||!(column===columns.at(-1)||/^(ImageFileName|Process|Name|ProcessName)$/i.test(column)))continue;
            initial.set(column,Math.min(column===columns.at(-1)?4096:1200,Math.max(initial.get(column)??64,naturalWidth(column))));
        }
        setWidths(initial);setFixed(true);
    },[rowNumberDigits,pageKey]);
    function naturalWidth(column:string){
        const element=table.current;if(!element)return 160;
        const index=columns.indexOf(column)+2,heading=element.tHead!.rows[0].cells[index],first=element.tBodies[0]?.rows[0]?.cells[index]??heading;
        const canvas=document.createElement('canvas').getContext('2d')!,css=getComputedStyle(first);
        canvas.font=css.font;const pad=parseFloat(css.paddingLeft)+parseFloat(css.paddingRight)+8;
        let width=canvas.measureText(column).width+pad+48;
        for(const row of Array.from(element.tBodies[0].rows)){const cell=row.cells[index];if(cell)width=Math.max(width,canvas.measureText(cell.textContent??'').width+pad+(parseFloat(cell.style.paddingLeft)||0))}
        return clampColumnWidth(width);
    }
    function fit(column:string){const next=measured();next.set(column,naturalWidth(column));commit(next)}
    function start(event:PointerEvent<HTMLSpanElement>,column:string){
        if(event.button!==0)return;
        event.preventDefault();event.stopPropagation();
        const base=measured();drag.current={pointer:event.pointerId,column,x:event.clientX,base,width:base.get(column)!};
        event.currentTarget.setPointerCapture(event.pointerId);
    }
    function move(event:PointerEvent<HTMLSpanElement>){
        const active=drag.current;if(!active||active.pointer!==event.pointerId)return;
        const next=new Map(active.base);next.set(active.column,clampColumnWidth(active.width+event.clientX-active.x));pendingWidth.current=next;
        if(!frame.current)frame.current=requestAnimationFrame(()=>{frame.current=0;if(pendingWidth.current)setWidths(pendingWidth.current)});
    }
    function end(event:PointerEvent<HTMLSpanElement>,cancel=false){
        const active=drag.current;if(!active||active.pointer!==event.pointerId)return;
        cancelAnimationFrame(frame.current);frame.current=0;
        commit(cancel?active.base:pendingWidth.current??active.base);pendingWidth.current=null;
        drag.current=null;
        if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
    }
    function keys(event:KeyboardEvent<HTMLSpanElement>,column:string){
        if(event.key==='Enter'){event.preventDefault();event.stopPropagation();fit(column);return;}
        if(event.key!=='ArrowLeft'&&event.key!=='ArrowRight')return;
        event.preventDefault();event.stopPropagation();
        const next=measured(),step=event.shiftKey?64:16;
        next.set(column,clampColumnWidth(next.get(column)!+(event.key==='ArrowRight'?step:-step)));commit(next);
    }
    const width=metadata.current.reduce((a,b)=>a+b,0)+columns.reduce((sum,c)=>sum+(widths.get(c)??160),0);
    const pinPID=columns[0]?.toLowerCase()==='pid'&&(widths.get(columns[0])??160)<=240;
    const tableStyle=fixed?{width,'--index-left':metadata.current[0]+'px','--pid-left':(metadata.current[0]+metadata.current[1])+'px'} as CSSProperties:undefined;
    return <table ref={table} className={'data-table resizable-data-table'+(fixed?' sizing-ready':'')+(pinPID?' pin-pid':'')} style={tableStyle}>
        <colgroup><col style={fixed?{width:metadata.current[0]}:undefined}/><col style={fixed?{width:metadata.current[1]}:undefined}/>{columns.map(c=><col key={c} style={widths.has(c)?{width:widths.get(c)}:undefined}/>)}</colgroup>
        <thead><tr><th className="bookmark-cell"/><th className="index-cell">#</th>{columns.map(c=><th key={c} aria-sort={sort===c?(direction==='asc'?'ascending':'descending'):undefined}>
            <button className="column-sort" onClick={()=>onSort(c)} title={c}>{c}<ArrowDownUp size={11} className={sort===c?'sorting':''}/></button>
            {onFilter&&<button className={'column-value-filter'+(filterColumns.includes(c)?' active':'')} aria-label={tr('Фильтр значений: {0}',c)} title={tr('Фильтр значений: {0}',c)} aria-pressed={filterColumns.includes(c)} onClick={()=>onFilter(c)}><Filter size={12}/></button>}
            <span className="column-resizer" role="separator" tabIndex={0} aria-orientation="vertical"
                aria-label={tr('Ширина столбца {0}',c)} aria-valuemin={MIN_COLUMN_WIDTH} aria-valuemax={MAX_COLUMN_WIDTH} aria-valuenow={Math.round(widths.get(c)??160)}
                title={tr('Перетащите границу. Двойной щелчок — ширина по содержимому страницы. Стрелки — изменить ширину, Enter — подобрать.')}
                onPointerDown={e=>start(e,c)} onPointerMove={move} onPointerUp={e=>end(e)} onPointerCancel={e=>end(e,true)} onLostPointerCapture={e=>{if(drag.current)end(e)}}
                onDoubleClick={e=>{e.preventDefault();e.stopPropagation();fit(c)}} onClick={e=>e.stopPropagation()} onKeyDown={e=>keys(e,c)}/>
        </th>)}</tr></thead><tbody>{children}</tbody>
    </table>;
}
