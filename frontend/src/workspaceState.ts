export type WorkspaceState={activeId:string;openIds:string[]};
export function restoreWorkspace(ids:string[],pref:{last_case:string;open_cases?:string[]|null}):WorkspaceState{
    const known=new Set(ids),openIds=[...new Set(pref.open_cases??(pref.last_case?[pref.last_case]:[]))].filter(id=>known.has(id));
    return {openIds,activeId:openIds.includes(pref.last_case)?pref.last_case:''};
}
export function openWorkspaceCase(state:WorkspaceState,id:string):WorkspaceState{
    return {activeId:id,openIds:state.openIds.includes(id)?state.openIds:[...state.openIds,id]};
}
export function closeWorkspaceCase(state:WorkspaceState,id:string):WorkspaceState{
    const openIds=state.openIds.filter(x=>x!==id);
    return {openIds,activeId:state.activeId===id?(openIds.at(-1)??''):state.activeId};
}
// Serialize preference writes across rapid close/select/theme changes. A failed
// write stays pending and the native close handshake can retry it.
export class LatestWriter<T>{
    private pending:T|undefined;private task:Promise<void>|null=null;
    constructor(private write:(value:T)=>Promise<unknown>){}
    submit(value:T){this.pending=value;return this.flush()}
    flush():Promise<void>{
        if(this.task)return this.task;
        let successful=false;
        this.task=Promise.resolve().then(async()=>{
            while(this.pending!==undefined){const value=this.pending;await this.write(value);if(this.pending===value)this.pending=undefined}
            successful=true;
        }).finally(()=>{this.task=null;if(successful&&this.pending!==undefined)return this.flush()});
        return this.task;
    }
}
export function parseWindowsBanner(value:unknown){
    if(typeof value!=='string'||/[\r\n]/.test(value))return null;
    const m=/^([^|\r\n]+\.pdb)\|([0-9a-f]{32})\|(\d+)$/i.exec(value);
    return m?{pdb:m[1],guid:m[2],age:m[3]}:null;
}

// Volatility reports progress for individual scanners, not for an entire plugin.
export function measuredProgress(run:{purpose?:string;progress:number}){return run.purpose==='pipeline'&&Number.isFinite(run.progress)?Math.max(0,Math.min(99,run.progress)):null;}
