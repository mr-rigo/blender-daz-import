import os
import bpy
from time import perf_counter
from typing import List, Any

from daz_import.Lib.Files import MultiFile, FilePath
from daz_import.Elements.Render import RenderStatic
from daz_import.Lib.Files.DBZ import DBZ_Static
from daz_import.Elements.Node import transformDuplis

from daz_import.Elements.Import.tools import makeRootCollection
from daz_import.Elements.Import.DazOptions import DazOptions, DazOperator
from daz_import.Lib.Errors import ErrorsStatic, DazError
from daz_import.Lib import Registrar
from daz_import.Lib.Settings import Settings, Settings
from daz_import.Lib.Utility import Progress, Updating
from daz_import.Elements.Assets import Assets
from daz_import.Elements.Assets.FileAsset import FileAsset


@Registrar()
class ImportOperator(DazOperator, DazOptions, MultiFile):
    """Load a DAZ File"""
    bl_idname = "daz.daz_import"
    bl_label = "Import DAZ"
    bl_description = "Load a native DAZ file"
    bl_options = {'PRESET', 'UNDO'}

    def draw(self, context):
        DazOptions.draw(self, context)
        self.layout.separator()
        box = self.layout.box()
        box.label(text="For more options, see Settings Settings.")

    def storeState(self, _):
        ...

    def restoreState(self, _):
        ...

    def run(self, _):
        files = FilePath.getMultiFiles(self.files,
                                       ["duf", "dsf", "dse"],
                                       self.directory)

        import_daz_file(*files, mesh_mode=self.fitMeshes)


class ImportClass:

    @classmethod
    def __import(cls, *filepaths: str):
        context = bpy.context

        if not filepaths:
            raise DazError("No valid files selected")

        t1 = perf_counter()

        for filepath in filepaths:
            cls.__import_file(filepath, context)

        if Settings.render_:
            Settings.render_.build(context)

        # if Settings.useDump:
        #     ErrorsStatic.dump(filepath)

        if len(filepaths) > 1:
            t2 = perf_counter()
            print("Total load time: %.3f seconds" % (t2-t1))

        msg = ""
        if Settings.missingAssets_:
            msg = ("Some assets were not found.\n" +
                   "Check that all Daz paths have been set up correctly.        \n" +
                   "For details see\n'%s'" % ErrorsStatic.error_path())
        else:
            if Settings.hdFailures_:
                msg += "Could not rebuild subdivisions for the following HD objects:       \n"
                for hdname in Settings.hdFailures_:
                    msg += ("  %s\n" % hdname)
            if Settings.hdWeights_:
                msg += "Could not copy vertex weights to the following HD objects:         \n"
                for hdname in Settings.hdWeights_:
                    msg += ("  %s\n" % hdname)
            if Settings.hdUvMissing_:
                msg += "HD objects missing UV layers:\n"
                for hdname in Settings.hdUvMissing_:
                    msg += ("  %s\n" % hdname)
                msg += "Export from DAZ Studio with Multires disabled.        \n"
        if msg:
            ErrorsStatic.clear()
            ErrorsStatic.handle_daz(context, warning=True, dump=True)

            print(msg)
            Settings.warning_ = True
            raise DazError(msg, warning=True)

        # if msg := RenderStatic.check(context, False):
        #     Settings.warning_ = True
        #     raise DazError(msg, warning=True)

        Settings.reset()

    @staticmethod
    def __import_file(filepath: str, context) -> None:
        Settings.scene_ = filepath
        t1 = perf_counter()
        Progress.start("\nLoading %s" % filepath)

        if Settings.fitFile_:
            DBZ_Static.getFitFile(filepath)

        Progress.show(10, 100)

        grpname = os.path.splitext(os.path.basename(filepath))[0].capitalize()

        Settings.collection_ = makeRootCollection(grpname, context)

        print("Parsing data")

        file_asset = FileAsset.create_by_url(filepath, toplevel=True)

        if file_asset is None:
            msg = ("File not found:  \n%s      " % filepath)
            raise DazError(msg)

        Progress.show(20, 100)
        print("Preprocessing...")

        for asset, inst in file_asset.nodes:
            inst.preprocess(context)

        if Settings.fitFile_:
            DBZ_Static.fitToFile(filepath, file_asset.nodes)

        Progress.show(30, 100)

        for asset, inst in file_asset.nodes:
            inst.preprocess2(context)

        for asset, inst in file_asset.modifiers:
            asset.preprocess(inst)

        print("Building objects...")

        for asset in file_asset.materials:
            asset.build(context)

        Progress.show(50, 100)

        nnodes = len(file_asset.nodes)
        idx = 0

        for asset, inst in file_asset.nodes:
            Progress.show(50 + int(idx*30/nnodes), 100)
            idx += 1
            asset.build(context, inst)      # Builds armature

        Progress.show(80, 100)
        nmods = len(file_asset.modifiers)
        idx = 0

        for asset, inst in file_asset.modifiers:
            Progress.show(80 + int(idx*10/nmods), 100)
            idx += 1
            asset.build(context, inst)      # Builds morphs 1

        Progress.show(90, 100)

        for _, inst in file_asset.nodes:
            inst.poseRig(context)

        for asset, inst in file_asset.nodes:
            inst.postbuild(context)

        # Need to update scene before calculating object areas
        Updating.scene(context)
        for asset in file_asset.materials:
            asset.postbuild()

        print("Postprocessing...")

        for asset, inst in file_asset.modifiers:
            asset.postbuild(context, inst)

        for _, inst in file_asset.nodes:
            inst.buildInstance(context)

        for _, inst in file_asset.nodes:
            inst.finalize(context)

        transformDuplis(context)

        t2 = perf_counter()
        print('File "%s" loaded in %.3f seconds' % (filepath, t2-t1))

    def __call__(self, *files: str, mesh_mode: str = 'MORPHED') -> Any:
        Settings.import_mode(mesh_mode)
        self.__import(*files)


import_daz_file = ImportClass()
