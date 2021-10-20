import bpy
from time import perf_counter
from typing import Any, Dict

from daz_import.Lib.Settings import Settings


class Props:
    @staticmethod
    def bool_OVR(default, description=""):
        return bpy.props.BoolProperty(default=default, description=description, override={'LIBRARY_OVERRIDABLE'})

    @staticmethod
    def float_OVR(default, description="", precision=2, min=0, max=1):
        return bpy.props.FloatProperty(default=default, description=description, precision=precision, min=min, max=max, override={'LIBRARY_OVERRIDABLE'})

    @staticmethod
    def set_overridable(rna, attr):
        rna.property_overridable_library_set(PropsStatic.ref(attr), True)

    @classmethod
    def set_attr_OVR(cls, rna, attr, value):
        setattr(rna, attr, value)
        rna[attr] = value
        cls.set_overridable(rna, attr)


class PropsOld(Props):

    @staticmethod
    def bool_OVR(default, description=""):
        return bpy.props.BoolProperty(default=default, description=description)

    @staticmethod
    def float_OVR(default, description="", precision=2, min=0, max=1):
        return bpy.props.FloatProperty(default=default, description=description, precision=precision, min=min, max=max)

    @staticmethod
    def set_overridable(*_):
        ...


if bpy.app.version and bpy.app.version < (2, 90, 0):
    Props = PropsOld


class Updating:

    @staticmethod
    def scene(context):
        dg = context.evaluated_depsgraph_get()
        dg.update()

    @staticmethod
    def object(context, ob):
        dg = context.evaluated_depsgraph_get()
        return ob.evaluated_get(dg)

    @staticmethod
    def drivers(rna):
        if rna:
            rna.update_tag()
            if rna.animation_data:
                for fcu in rna.animation_data.drivers:
                    if fcu.driver.type == 'SCRIPTED':
                        fcu.driver.expression = str(fcu.driver.expression)

    @classmethod
    def rig_drivers(cls, context, rig):
        cls.updateScene(context)
        if not rig:
            return
        cls.updateDrivers(rig.data)
        cls.updateDrivers(rig)


class UtilityStatic:

    @staticmethod  # TODO Move to DazPaht
    def inst_ref(ref: str) -> str:
        return ref.rsplit("#", 1)[-1]

    @staticmethod  # TODO Move to DazPaht
    def to_lower(url: str) -> str:
        if not Settings.caseSensitivePaths:
            url = url.lower()
        return url

    @staticmethod
    def clamp(value):
        return min(1, max(0, value))

    @staticmethod
    def next_letter(char):
        return chr(ord(char) + 1)

    @staticmethod
    def is_simple_type(x) -> bool:
        return isinstance(x, int) or \
            isinstance(x, float) or \
            isinstance(x, str) or \
            isinstance(x, bool) or \
            x is None

    @staticmethod  # Unused
    def dict_inner_key(dict_: dict, key: str, inner_key, value):
        if key not in dict_.keys():
            dict_[key] = {}
        dict_[key][inner_key] = value

    @staticmethod
    def sorted(seq):
        slist = list(seq)
        slist.sort()
        return slist

    @staticmethod
    def get_current_value(dict_: Dict[str, Any], default=None) -> Any:
        if "current_value" in dict_.keys():
            return dict_["current_value"]
        elif "value" in dict_.keys():
            return dict_["value"]
        else:
            return default


class PropsStatic:

    @staticmethod
    def ref(prop):
        return '["%s"]' % prop

    @staticmethod
    def final(prop):
        return "%s(fin)" % prop

    @staticmethod
    def rest(prop):
        return "%s(rst)" % prop

    @staticmethod
    def base(string):
        if string[-5:] in ["(fin)", "(rst)"]:
            return string[:-5]
        return string


class UtilityBoneStatic:

    @staticmethod
    def is_drv_bone(string):
        return (string[-3:] == "Drv" or string[-5:] == "(drv)")

    # def baseBone(string):
    #     if string[-5:] in ["(fin)", "(drv)"]:
    #         return string[:-5]
    #     return string

    @classmethod
    def drv_bone(cls, string):
        if cls.is_drv_bone(string):
            return string
        return string + "(drv)"

    @staticmethod
    def is_final(string):
        return (string[-5:] == "(fin)")

    @staticmethod
    def is_rest(string):
        return (string[-5:] == "(rst)")

    @staticmethod
    def fin_bone(string):
        return string + "(fin)"

    @staticmethod
    def base(string) -> str:
        if (string[-3:] in ["Drv", "Fin"]):
            return string[:-3]
        elif (string[-5:] in ["(drv)", "(fin)"]):
            return string[:-5]
        return string

    @staticmethod
    def inherit_scale(pb):
        return (pb.bone.inherit_scale not in ['NONE', 'NONE_LEGACY'])

    @staticmethod
    def has_pose_bones(rig, bnames):
        for bname in bnames:
            if bname not in rig.pose.bones.keys():
                return False
        return True


class Timer:
    def __init__(self):
        self.t = perf_counter()

    def print(self, msg):
        t = perf_counter()
        print("%8.6f: %s" % (t-self.t, msg))
        self.t = t


class Progress:
    @staticmethod
    def start(string):
        print(string)
        wm = bpy.context.window_manager
        wm.progress_begin(0, 100)

    @staticmethod
    def end():
        wm = bpy.context.window_manager
        wm.progress_update(100)
        wm.progress_end()

    @staticmethod
    def show(n, total, string=None):
        pct = (100.0 * n) / total

        wm = bpy.context.window_manager
        wm.progress_update(int(pct))
        if string:
            print(string)
