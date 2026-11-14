#!/bin/bash
# Mac: double-click in Finder to start Launchpad in its own window (the Mac twin of Launchpad.bat).
# First time only, in Terminal from this folder:  chmod +x Launchpad.command
# Keep the Terminal window open while you use the app; closing it stops Launchpad.
# To use your normal browser instead of a window, add --browser to the python3 line.
# Other options: --cwd <project folder> to plan in another project, --fake for the zero-token demo.
# Session files go to <project>/.launchpad/ (git-ignored).
cd "$(dirname "$0")" || exit 1
python3 -m app.launch "$@"
status=$?
if [ $status -ne 0 ]; then
  echo
  echo "Launchpad stopped with an error. See the message above."
  read -r -p "Press Enter to close..."
fi
