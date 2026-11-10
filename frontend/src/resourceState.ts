export type ResourceState<T> = {status:'idle'|'loading'|'error';value:null;error:string}|{status:'ready';value:T;error:''};

// Failed reads never publish defaults. A late read cannot replace a retry.
export class ResourceGate<T>{
    private revision=0;
    private state:ResourceState<T>={status:'idle',value:null,error:''};
    private listeners=new Set<()=>void>();
    snapshot=()=>this.state;
    subscribe=(notify:()=>void)=>{this.listeners.add(notify);return()=>{this.listeners.delete(notify)}};
    private update(state:ResourceState<T>){this.state=state;for(const notify of this.listeners)notify()}
    invalidate(){this.revision++}
    async load(read:()=>Promise<T>){
        const revision=++this.revision;
        this.update({status:'loading',value:null,error:''});
        try{const value=await read();if(revision===this.revision)this.update({status:'ready',value,error:''})}
        catch(error){if(revision===this.revision)this.update({status:'error',value:null,error:error instanceof Error?error.message:String(error)})}
    }
}
