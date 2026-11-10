"""Public Volatility renderer interface; writes observations without a second JSON tree."""
import json
import sys
from volatility3.cli.text_renderer import JsonRenderer
from volatility3.framework import interfaces
from volatility3.framework.renderers import format_hints


class StudioJsonLinesRenderer(JsonRenderer):
    name="studio-jsonl"

    def render(self,grid):
        count=0
        def visit(node,accumulator):
            nonlocal count
            row={"__depth":max(0,node.path_depth-1)}
            for column,val in zip(grid.columns,node.values):
                if isinstance(val,interfaces.renderers.BaseAbsentValue):
                    rendered=None
                elif column.type is format_hints.Hex:
                    rendered=hex(int(val))
                else:
                    render=self._type_renderers.get(column.type,self._type_renderers["default"])
                    rendered=render(val)
                    if isinstance(rendered,int) and not isinstance(rendered,bool) and abs(rendered)>9007199254740991:
                        rendered=str(rendered)
                row[column.name]=rendered
            sys.stdout.write(json.dumps(row,ensure_ascii=True,default=str)+"\n")
            count+=1
            if count%100==0:
                sys.stdout.flush()
            return accumulator
        if not grid.populated:
            error=grid.populate(visit,None)
            if error:
                raise error
        else:
            grid.visit(node=None,function=visit,initial_accumulator=None)
        sys.stdout.flush()
