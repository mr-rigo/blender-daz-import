import math
from mathutils import Vector

from daz_import.Lib.Settings import Settings, Settings


class VectorStatic:
    zero = Vector((0, 0, 0))
    one = Vector((1, 1, 1))

    D2R = "%.6f*" % (math.pi / 180)
    D = math.pi / 180

    @classmethod
    def color(cls, value: Vector):
        if cls.is_vector(value):
            x, y, z = value
            return (x+y+z)/3
        else:
            return value

    @staticmethod
    def is_vector(value) -> bool:
        return (hasattr(value, "__len__") and len(value) >= 3)

    @staticmethod
    def index(index: str) -> str:
        if index == "x":
            return 0
        elif index == "y":
            return 1
        elif index == "z":
            return 2
        else:
            return -1

    @classmethod
    def coords(cls, p):
        co: list = list(cls.zero)
        for c in p:
            co[cls.index(c["id"])] = c["value"]
        return cls.scaled(co)

    @staticmethod
    def scaled_v2(v) -> Vector:
        return Settings.scale_*Vector((v[0], -v[2], v[1]))

    @staticmethod
    def _create_vector_v2(v):
        return Vector((v[0], -v[2], v[1]))

    @staticmethod
    def _create_vector_v3(v):
        return Vector((v[0], v[2], v[1]))

    @staticmethod
    def scaled_and_convert_vector(v) -> Vector:
        return Settings.scale_*Vector(v)

    @staticmethod
    def _create_vector(v):
        return Vector(v)

    @classmethod
    def scaled(cls, v) -> Vector:
        if Settings.zup:
            return cls.scaled_v2(v)
        else:
            return cls.scaled_and_convert_vector(v)

    @classmethod
    def create_vector(cls, v) -> Vector:
        if Settings.zup:
            return cls._create_vector_v2(v)
        else:
            return cls._create_vector(v)

    @classmethod
    def create_vector_v2(cls, v) -> Vector:
        if Settings.zup:
            return cls._create_vector_v3(v)
        else:
            return cls._create_vector(v)

    @staticmethod
    def non_zero(vec):
        return max([abs(x) for x in vec]) > 1e-6
