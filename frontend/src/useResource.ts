import {useCallback,useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {ResourceGate} from './resourceState';
export function useResource<T>(read:()=>Promise<T>){
    const reader=useRef(read);reader.current=read;
    const [gate]=useState(()=>new ResourceGate<T>());
    const state=useSyncExternalStore(gate.subscribe,gate.snapshot);
    const reload=useCallback(()=>gate.load(()=>reader.current()),[gate]);
    useEffect(()=>{void reload();return()=>gate.invalidate()},[gate,reload]);
    return {state,reload};
}
