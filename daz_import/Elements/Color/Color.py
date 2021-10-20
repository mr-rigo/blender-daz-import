from mathutils import Vector


class ColorStatic:
    WHITE = Vector((1.0, 1.0, 1.0))
    GREY = Vector((0.5, 0.5, 0.5))
    BLACK = Vector((0.0, 0.0, 0.0))

    @staticmethod
    def isWhite(color):
        return (tuple(color[0:3]) == (1.0, 1.0, 1.0))

    @staticmethod
    def isBlack(color):
        return (tuple(color[0:3]) == (0.0, 0.0, 0.0))
