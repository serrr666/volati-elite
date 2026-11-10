export function matchesRunHistory(run:{id:string;plugin:string;status:string},query:string,statusLabel:string){
    const needle=query.trim().toLocaleLowerCase();
    return !needle||[run.id,run.plugin,run.status,statusLabel].some(value=>value.toLocaleLowerCase().includes(needle));
}
