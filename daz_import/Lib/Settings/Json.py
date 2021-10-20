import os
import json
import gzip
import codecs
from mathutils import Vector, Color
# from daz_import.Lib.Errors import ErrorsStatic


class Json:
    @staticmethod
    def _safeOpen(filepath, rw: str, dirMustExist=False, fileMustExist=False, mustOpen=False):
        if dirMustExist:
            folder = os.path.dirname(filepath)
            if not os.path.exists(folder):
                raise FileNotFoundError(
                    f"Directory does not exist:      \n{folder}")
                # raise DazError(f"Directory does not exist:      \n{folder}")

        if fileMustExist:
            if not os.path.exists(filepath):
                raise FileNotFoundError(
                    f"""File does not exist:     \n{filepath}""")
                # raise DazError(f"""File does not exist:     \n{filepath}""")

        if rw == "w":
            encoding = "utf_8"
        else:
            encoding = "utf_8_sig"

        try:
            fp = open(filepath, rw, encoding=encoding)
        except FileNotFoundError:
            fp = None

        if fp is None:
            if rw[0] == "r":
                mode = "reading"
            else:
                mode = "writing"
            msg = ("Could not open file for %s:   \n" % mode +
                   "%s          " % filepath)
            if mustOpen:
                raise FileNotFoundError(msg)
                # raise DazError(msg)
            # ErrorsStatic.report(msg, warnPaths=True, trigger=(2, 4))
        return fp

    @classmethod
    def load(cls, filepath: str, mustOpen=False):

        try:
            with gzip.open(filepath, 'rb') as file:
                bytes_ = file.read()
        except IOError:
            bytes_ = None

        data = {}
        msg = ("Could not load %s" % filepath)
        trigger = (2, 3)

        if bytes_:
            try:
                string = bytes_.decode("utf_8_sig")
                data = json.loads(string)
                msg = None
            except json.decoder.JSONDecodeError as err:
                msg = ('JSON error while reading zipped file\n"%s"\n%s' %
                       (filepath, err))
                trigger = (1, 2)
            except UnicodeDecodeError as err:
                msg = ('Unicode error while reading zipped file\n"%s"\n%s' %
                       (filepath, err))
                trigger = (1, 2)
        else:

            if file := cls._safeOpen(filepath, "r", mustOpen=mustOpen):
                try:
                    data = json.load(file)
                    msg = None
                except json.decoder.JSONDecodeError as err:
                    msg = ('JSON error while reading ascii file\n"%s"\n%s' %
                           (filepath, err))
                    trigger = (1, 2)
                except UnicodeDecodeError as err:
                    msg = ('Unicode error while reading ascii file\n"%s"\n%s' %
                           (filepath, err))
                    trigger = (1, 2)
        if msg:
            print(msg)
            # ErrorsStatic.report(msg, trigger=trigger)
        return data

    @classmethod
    def save(cls, struct, filepath, binary=False):
        if binary:
            bytes_ = cls._encode(struct, "")
            #bytes_ = json.dumps(struct)
            with gzip.open(filepath, 'wb') as fp:
                fp.write(bytes_)
        else:

            string = cls._encode(struct, "")
            with codecs.open(filepath, "w", encoding="utf_8") as fp:
                fp.write(string)
                fp.write("\n")

    @classmethod
    def _encode(cls, data, pad=""):
        # from daz_import.Lib.Errors import DazError

        if data is None:
            return "null"
        elif isinstance(data, (bool)):
            if data:
                return "true"
            else:
                return "false"
        elif isinstance(data, (float)):
            if abs(data) < 1e-6:
                return "0"
            else:
                return "%.5g" % data
        elif isinstance(data, (int)):
            return str(data)

        elif isinstance(data, (str)):
            return "\"%s\"" % data
        elif isinstance(data, (list, tuple, Vector, Color)):
            if cls._leaf_list(data):
                string = "["
                string += ",".join([cls._encode(elt) for elt in data])
                return string + "]"
            else:
                string = "["
                string += ",".join(
                    ["\n    " + pad + cls._encode(elt, pad+"    ")
                     for elt in data])
                if string == "[":
                    return "[]"
                else:
                    return string + "\n%s]" % pad
        elif isinstance(data, dict):
            string = "{"
            string += ",".join(
                ["\n    %s\"%s\" : " % (pad, key) + cls._encode(value, pad+"    ")
                 for key, value in data.items()])
            if string == "{":
                return "{}"
            else:
                return string + "\n%s}" % pad
        else:
            try:
                string = "["
                string += ",".join([cls._encode(elt) for elt in data])
                return string + "]"
            except:
                print(data)
                print(data.type)

                # raise DazError("Can't encode: %s %s" % (data, data.type))

    @staticmethod
    def _leaf_list(data: dict) -> bool:
        for elt in data:
            if isinstance(elt, (list, dict)):
                return False
        return True

    @staticmethod
    def load_setting(filepath) -> dict:
        filepath = os.path.expanduser(filepath)
        fp = None
        data = {}

        try:
            fp = open(filepath, "r", encoding="utf-8-sig")
            data = json.load(fp)
        except json.decoder.JSONDecodeError as err:
            print("File %s is corrupt" % filepath)
            print("Error: %s" % err)
            return None
        except:
            print("Could not open %s" % filepath)
            return None
        finally:
            if fp:
                fp.close()

        return data
