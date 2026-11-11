#!/usr/bin/env sh
# Smart HTML Editor: open an HTML file in the editor.  ./open-editor.sh page.html
exec python3 "$(dirname "$0")/editor/she.py" open "$@"
