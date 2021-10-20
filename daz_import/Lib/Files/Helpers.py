import bpy
from typing import List, Set
from bpy_extras.io_utils import ImportHelper
from daz_import.Lib.Settings import Settings
from bpy.props import StringProperty, CollectionProperty
from daz_import.Lib.Files.FilePath import FilePath
from daz_import.Collection import Collection


class SingleFile(ImportHelper):
    filepath: StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        default="")

    def invoke(self, context, _) -> Set[str]:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MultiFile(ImportHelper):
    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement)

    directory: StringProperty(
        subtype='DIR_PATH')

    def invoke(self, context, event) -> Set[str]:
        Collection.clear_import()
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def getMultiFiles(self, extensions: List[str]) -> List[str]:
        return FilePath.getMultiFiles(self.files, extensions, self.directory)
