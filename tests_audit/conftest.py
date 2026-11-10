import os
import tempfile

# These tests compare paths the installer reports (always resolved) with paths
# built from the temp dir. On macOS the default temp dir sits behind the
# /var -> /private/var system link, so hand out the resolved location.
tempfile.tempdir = os.path.realpath(tempfile.gettempdir())
