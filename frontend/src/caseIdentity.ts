export function automaticCaseName(path:string):string{
    const name=path.split(/[\\/]/).filter(Boolean).at(-1)||'Memory image';
    // The case title limit applies to Unicode characters, not UTF-16 units.
    // Keep the full evidence path; shorten only the automatically chosen alias.
    return Array.from(name).slice(0,160).join('');
}
export function caseMatches(c:{name:string;id:string;path:string;sha256?:string|null},query:string):boolean{
    const needle=query.trim().toLowerCase();
    return !needle||[c.name,c.id,c.path,c.sha256||''].some(v=>v.toLowerCase().includes(needle));
}
