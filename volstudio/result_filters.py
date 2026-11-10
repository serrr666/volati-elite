"""Typed column-value filters; SQL identifiers and values are never interpolated."""
import json
from fastapi import HTTPException

EXACT="CASE WHEN j.type='integer' AND (j.value>9007199254740991 OR j.value< -9007199254740991) THEN studio_exact_integer(result_rows.data,j.key) ELSE j.value END"
TOKEN="coalesce(j.type,'missing')||':'||coalesce(CAST(("+EXACT+") AS TEXT),'')"

def decode(encoded,columns):
    if not encoded:return {}
    try:
        if len(encoded)>16000:raise ValueError()
        rules=json.loads(encoded)
        if not isinstance(rules,dict) or len(rules)>32:raise ValueError()
        for column,rule in rules.items():
            if column not in columns or not isinstance(rule,dict) or set(rule)!={'exclude','values'}:raise ValueError()
            if type(rule['exclude']) is not bool or not isinstance(rule['values'],list) or len(rule['values'])>1000:raise ValueError()
            if any(not isinstance(v,str) or len(v)>8192 for v in rule['values']):raise ValueError()
        return rules
    except (ValueError,TypeError):raise HTTPException(422,'Invalid column value filters')

def predicate(run_id,columns,q='',encoded='',ignore=None):
    if len(q)>1000:raise HTTPException(422,'Search text exceeds the 1,000 character limit')
    where='result_rows.run_id=?';args=[run_id]
    if q:where+=' AND studio_contains(result_rows.data,?)';args.append(q)
    for column,rule in decode(encoded,columns).items():
        if column==ignore:continue
        values=list(dict.fromkeys(rule['values']))
        if not values:
            if not rule['exclude']:where+=' AND 0'
            continue
        # LEFT JOIN includes rows where a plugin omitted the selected field.
        where+=" AND (SELECT "+TOKEN+" FROM (SELECT 1) LEFT JOIN json_each(result_rows.data) j ON j.key=?) "+('NOT IN' if rule['exclude'] else 'IN')+' ('+','.join('?' for _ in values)+')'
        args.extend([column,*values])
    return where,args

def values_page(db,run_id,columns,column,q,encoded,search,offset,limit):
    if column not in columns:raise HTTPException(422,'Unknown result column')
    if len(search)>1000:raise HTTPException(422,'Value search is too long')
    where,args=predicate(run_id,columns,q,encoded,ignore=column)
    if search:where+=" AND instr(lower(coalesce(CAST(j.value AS TEXT),'')),lower(?))>0";args.append(search)
    offset=max(0,offset);limit=min(200,max(1,limit))
    rows=db.all_rows("SELECT "+TOKEN+" token,j.type type,"+EXACT+" value,COUNT(*) count FROM result_rows LEFT JOIN json_each(result_rows.data) j ON j.key=? WHERE "+where+" GROUP BY token ORDER BY CAST(value AS TEXT) COLLATE studio_text,j.type LIMIT ? OFFSET ?",[column,*args,limit+1,offset])
    return {'values':rows[:limit],'has_more':len(rows)>limit,'offset':offset}
