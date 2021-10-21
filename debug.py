
import os
import sys

if True:
    sys.path.append(os.path.dirname(__file__))

from daz_import import register
from daz_import.Elements.Import import import_daz_file
from daz_import.Lib.Settings import Debug
from daz_import.Lib import BlenderStatic

register()

if file := Debug.get('IMPORT_FILE'):
    BlenderStatic.clear_scene()
    import_daz_file(file)
