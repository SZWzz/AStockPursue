"""Pre-built strategy workflow templates.

Each template is a {nodes, edges} dict that can be loaded onto the canvas.
Templates represent common strategy patterns that can be auto-detected from
user code and expanded into visual DAGs.
"""

from .registry import TEMPLATES, match_template, load_template
