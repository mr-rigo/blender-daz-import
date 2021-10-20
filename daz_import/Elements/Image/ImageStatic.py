import os
import bpy
from typing import Dict
from daz_import.Collection import Collection


class ImageStatic:
    _images: Dict[str, bpy.types.Image] = {}

    @classmethod
    def get_by_url(cls, url: str) -> bpy.types.Image:
        if url in cls._images.keys():
            return cls._images[url]
        else:
            return cls.load(url)

    @classmethod
    def load(cls, url: str) -> bpy.types.Image:                
        filepath = Collection.path(url)
        if filepath is None:
            # ErrorsStatic.report('Image not found:  \n"%s"' %
            #                     filepath, trigger=(3, 4))
            print('Image not found:  \n{filepath}')
            return

        img = bpy.data.images.load(filepath)
        img.name = os.path.splitext(os.path.basename(filepath))[0]
        cls._images[url] = img
        # Settings.images[url] = img
        return img

    @staticmethod
    def set_color_space(img, colorspace: str):
        try:
            img.colorspace_settings.name = colorspace
            return
        except TypeError:
            pass

        alternatives = {
            "sRGB": ["sRGB OETF"],
            "Non-Color": ["Non-Colour Data"],
        }

        for alt in alternatives[colorspace]:

            try:
                img.colorspace_settings.name = alt
                return
            except TypeError:
                pass
