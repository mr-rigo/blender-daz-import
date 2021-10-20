import bpy
import os
import sys
import traceback

from daz_import.Lib.Settings import Settings, Settings, Settings


class ErrorsStatic:

    @staticmethod
    def clear():
        Settings.theMessage_ = ""
        Settings.theErrorLines_ = []

    @staticmethod
    def invoke(value, warning=False):
        value = str(value)

        if warning:
            Settings.theMessage_ = "WARNING:\n" + value
        else:
            Settings.theMessage_ = "ERROR:\n" + value

        if Settings.theSilentMode_:
            print(Settings.theMessage_)
        else:
            bpy.ops.daz.error('INVOKE_DEFAULT')

    @staticmethod
    def error_path() -> str:
        return os.path.realpath(os.path.expanduser(Settings.errorPath))

    @classmethod
    def report(cls, msg, instances={}, warnPaths=False, trigger=(2, 3), force=False):
        trigWarning, trigError = trigger

        if Settings.verbosity >= trigWarning or force:
            print(msg)

        if Settings.verbosity >= trigError or force:
            Settings.theUseDumpErrors_ = True
            if warnPaths:
                msg += ("\nHave all DAZ library paths been set up correctly?\n" +
                        "See https://diffeomorphic.blogspot.se/p/setting-up-daz-library-paths.html         ")

            msg += ("\nFor details see\n'%s'" % cls.error_path())
            raise DazError(msg)

        return None

    @classmethod
    def handle_daz(cls, context, warning=False, dump=False):
        if not (dump or Settings.theUseDumpErrors_):
            return
        Settings.theUseDumpErrors_ = False

        filepath = cls.error_path()

        try:
            fp = open(filepath, "w", encoding="utf_8")
        except:
            print("Could not write to %s" % filepath)
            return

        fp.write(Settings.theMessage_)

        try:
            if warning:
                string = cls.getMissingAssets()
                fp.write(string)
                print(string)
            else:
                cls.printTraceBack(context, fp)
        except:
            pass
        finally:
            fp.write("\n")
            fp.close()
            print(Settings.theMessage_)
            Settings.reset()

    @classmethod
    def dump(cls, context):
        filepath = cls.error_path()
        with open(filepath, "w") as fp:
            cls.printTraceBack(context, fp)

    @staticmethod
    def getMissingAssets() -> str:
        if not Settings.missingAssets_:
            return ""
        string = "\nMISSING ASSETS:\n"
        for ref in Settings.missingAssets_.keys():
            string += ("  %s\n" % ref)
        return string

    @classmethod
    def printTraceBack(cls, context, fp):
        from daz_import.Elements.Assets import Assets
        type, value, saveTraceBack = sys.exc_info()

        fp.write("\n\nTRACEBACK:\n")
        traceback.print_tb(saveTraceBack, 30, fp)

        from daz_import.Elements.Node import Node

        fp.write("\n\nFILES VISITED:\n")
        for string in Settings.theTrace_:
            fp.write("  %s\n" % string)

        fp.write("\nASSETS:")
        refs = list(Assets.keys())
        refs.sort()

        for ref in refs:
            asset = Assets.get_direct(ref)
            asset.errorWrite(ref, fp)

        fp.write("\n\nOTHER ASSETS:\n")
        
        refs = list(Assets.loaded_other.keys())
        refs.sort()

        for ref in refs:            
            fp.write('"%s"\n    %s\n\n' % (ref, Assets.loaded_other[ref]))

        fp.write("\nDAZ ROOT PATHS:\n")
        from daz_import.Collection import Collection

        for n, path in enumerate(Collection.paths):
            fp.write('%d:   "%s"\n' % (n, path))

        string = cls.getMissingAssets()
        fp.write(string)

        fp.write("\nSETTINGS:\n")
        settings = []
        scn = bpy.context.scene

        for attr in dir(scn):
            if attr[0:3] == "Daz" and hasattr(scn, attr):
                value = getattr(scn, attr)
                if (isinstance(value, int) or
                    isinstance(value, float) or
                    isinstance(value, str) or
                        isinstance(value, bool)):
                    settings.append((attr, value))

        settings.sort()

        for attr, value in settings:
            if isinstance(value, str):
                value = ('"%s"' % value)
            fp.write('%25s:    %s\n' % (attr, value))


class DazError(Exception):

    def __init__(self, value, warning=False):
        ErrorsStatic.invoke(value, warning)

    def __str__(self):
        return repr(Settings.theMessage_)
