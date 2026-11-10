import type {Run} from './types';
export function reusableRun(runs:Run[],plugin:string){
    const candidates=runs.filter(r=>r.plugin===plugin&&Object.values(r.params).every(v=>v===null||v===undefined||v===''||v===false||(Array.isArray(v)&&!v.length)));
    return candidates.find(r=>['queued','running','indexing'].includes(r.status))??candidates.find(r=>r.status==='completed');
}
