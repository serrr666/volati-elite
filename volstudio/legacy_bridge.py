"""Run only inside the optional Python 2 process, with the job on stdin."""
import json
import os
import sys
import urllib


def screen_buffer(screen, truncate=True):
    rows = [unicode(row.Chars.dereference())[:int(screen.ScreenX)]
            for row in screen.Rows.dereference() if row.Chars.is_valid()]
    if truncate:
        width = min(int(screen.ScreenX), 128)
        while rows and rows[-1].count(' ') == width:
            rows.pop()
    return [row.encode('utf-8') for row in rows]


def main():
    job = json.loads(sys.stdin.readline())
    sys.path.insert(0, os.path.dirname(job['entry']))
    from volatility.plugins.overlays.basic import String
    from volatility.plugins.malware.cmdhistory import _SCREEN_INFORMATION
    from volatility.renderers.html import JSONRenderer

    # Python 2's Windows URL functions expect byte strings. Round-trip the
    # image path as UTF-8 so Volatility's FileAddressSpace opens a Unicode path.
    pathname2url, url2pathname = urllib.pathname2url, urllib.url2pathname
    urllib.pathname2url = lambda path: pathname2url(path.encode('utf-8') if isinstance(path, unicode) else path)
    urllib.url2pathname = lambda url: url2pathname(url.encode('ascii') if isinstance(url, unicode) else url).decode('utf-8')

    original_str = String.__str__

    def unicode_console_strings(value):
        if value.encoding.lower().replace('-', '').startswith('utf16'):
            return unicode(value).encode('utf-8')
        return original_str(value)

    # Volatility 2's renderer accepts byte strings. Keep the UTF-16 fields as
    # UTF-8 bytes until JSON encoding, and count screen columns in characters.
    String.__str__ = unicode_console_strings
    _SCREEN_INFORMATION.get_buffer = screen_buffer
    rendered = []

    def render_rows(self, out, tree):
        columns = [column.name for column in tree.columns]

        def write(node, _):
            row = dict(zip(columns, node.values))
            row['__depth'] = node.path_depth - 1
            out.write(json.dumps(row, ensure_ascii=True) + '\n')

        tree.visit(None, write)
        rendered.append(True)

    JSONRenderer.render = render_rows
    sys.argv = [job['entry'], '--conf-file=' + job['config'], '--cache-directory=' + job['cache'],
                '-f', job['image'], '--profile=' + job['profile'], '--output=json',
                '--output-file=' + job['partial'], job['plugin']]
    execfile(job['entry'], {'__name__': '__main__', '__file__': job['entry']})
    if not rendered:
        raise RuntimeError('Volatility 2 did not finish rendering results')
    os.rename(job['partial'], job['result'])


if __name__ == '__main__':
    main()
