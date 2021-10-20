from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty


class DbzFile:
    filename_ext = ".dbz"
    filter_glob: StringProperty(default="*.dbz;*.json", options={'HIDDEN'})


class JsonFile:
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})


class JsonExportFile(ExportHelper):
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    filepath: StringProperty(
        name="File Path",
        description="Filepath used for exporting the .json file",
        maxlen=1024,
        default="")


class ImageFile:
    filename_ext = ".png;.jpeg;.jpg;.bmp;.tif;.tiff"
    filter_glob: StringProperty(
        default="*.png;*.jpeg;*.jpg;*.bmp;*.tif;*.tiff", options={'HIDDEN'})


class DazImageFile:
    filename_ext = ".duf"
    filter_glob: StringProperty(
        default="*.duf;*.dsf;*.png;*.jpeg;*.jpg;*.bmp", options={'HIDDEN'})


class DazFile:
    filename_ext = ".dsf;.duf;*.dbz"
    filter_glob: StringProperty(
        default="*.dsf;*.duf;*.dbz", options={'HIDDEN'})


class DufFile:
    filename_ext = ".duf"
    filter_glob: StringProperty(default="*.duf", options={'HIDDEN'})


class DatFile:
    filename_ext = ".dat"
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})


class TextFile:
    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})


class CsvFile:
    filename_ext = ".csv"
    filter_glob: StringProperty(default="*.csv", options={'HIDDEN'})
