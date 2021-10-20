
from daz_import.Lib.Files import SingleFile, DazFile
from daz_import.Lib.Files import FilePath
from .DazOptions import DazOperator

from daz_import.Lib import Registrar

@Registrar()
class DAZ_OT_DecodeFile(DazOperator, DazFile, SingleFile):
    bl_idname = "daz.decode_file"
    bl_label = "Decode File"
    bl_description = "Decode a gzipped DAZ file (*.duf, *.dsf, *.dbz) to a text file"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def run(self, context):
        import gzip

        print("Decode",  self.filepath)
        try:
            with gzip.open(self.filepath, 'rb') as fp:
                bytes = fp.read()
        except IOError as err:
            msg = ("Cannot decode:\n%s" % self.filepath +
                   "Error: %s" % err)
            print(msg)
            raise FileExistsError(msg)

        try:
            string = bytes.decode("utf_8_sig")
        except UnicodeDecodeError as err:
            msg = ('Unicode error while reading zipped file\n"%s"\n%s' %
                   (self.filepath, err))
            print(msg)
            raise ValueError(msg)

        newfile = self.filepath + ".txt"
        with FilePath.safeOpen(newfile, "w") as fp:
            fp.write(string)
        print("%s written" % newfile)
