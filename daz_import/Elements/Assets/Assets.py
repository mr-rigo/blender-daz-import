from __future__ import annotations
from typing import List, Any, Type, Dict, Type

from daz_import.Lib.Errors import ErrorsStatic
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Files.Json import Json
from daz_import.Collection import Collection, DazPath
from collections import defaultdict
from .Accessor import Accessor


class Assets:
    loaded = {}
    loaded_other = {}

    sources = defaultdict()
    sources.default_factory = list

    @classmethod
    def push(cls, asset: Accessor, url: str):
        cls.loaded[url] = asset

    @classmethod
    def get(cls, asset: Accessor, index: str, strict=True) -> Accessor:
        if isinstance(index, Accessor):
            return index

        index = DazPath.normalize(index)

        if "?" in index:
            # Attribute. Return None
            return None

        ref = DazPath.ref(index, asset.fileref)

        if asset_ := cls.get_direct(ref):
            return asset_

        if index[0] != "#":
            from .FileAsset import FileAsset

            return FileAsset.get_new(index, ref, strict)

        if asset.caller:
            ref = DazPath.ref(index, asset.caller.fileref)
            if asset_ := cls.get_direct(ref):
                return asset_

        ref = DazPath.ref(index, asset.fileref)

        if asset_ := cls.get_direct(ref):
            return asset_

        if asset_ := cls.loaded_other.get(ref):
            return asset_

        if strict:
            msg = ("Missing local asset:\n  '%s'\n" % ref)
            if asset.caller:
                msg += ("in file:\n  '%s'\n" % asset.caller.fileref)
            ErrorsStatic.report(msg, trigger=(2, 3))
        return None

    @classmethod
    def get_typed(cls, asset,  id_: str, type: Type[Accessor]) -> Accessor:
        asset = cls.get(asset, id_)

        if asset is None\
                or type is None \
                or isinstance(asset, type):
            return asset

        if asset.caller:
            if asset := cls.get_typed(asset, id_, type):
                return asset

        msg = (f"Asset of type {type} not found: \n  {id_}\n" +
               f"File ref: \n  {asset.fileref}\n")

        return ErrorsStatic.report(msg, trigger=(2, 3), warnPaths=True)

    @classmethod
    def save(cls, asset: Accessor, dict_: dict, other_asset: Accessor) -> None:
        ref = ref2 = DazPath.normalize(other_asset.id)

        if asset.caller:
            if "id" in dict_.keys():
                ref = DazPath.id(dict_["id"], asset.caller.fileref)
            else:
                print("No id", dict_.keys())

        asset2 = cls.get_direct(ref)

        if asset2 and asset2 != other_asset:
            msg = ("Duplicate asset definition\n" +
                   "  Asset 1: %s\n" % other_asset +
                   "  Asset 2: %s\n" % asset2 +
                   "  Ref 1: %s\n" % ref +
                   "  Ref 2: %s\n" % ref2)
            ErrorsStatic.report(msg, trigger=(2, 4))
            cls.push(other_asset, ref2)
        else:
            cls.push(other_asset, ref)
            cls.push(other_asset, ref2)
        return

        # if not other_asset.caller:
        #     return

        # ref2 = DazPath.lower_path(other_asset.caller.id) + "#" + dict_["id"]
        # ref2 = DazPath.normalize(ref2)

        # if asset2 := cls.get_direct(ref2):

        #     if other_asset != asset2 and Settings.verbosity > 1:
        #         msg = ("Duplicate asset definition\n" +
        #                f"  Asset 1: {other_asset}\n" +
        #                f"  Asset 2: {asset2}\n" +
        #                f"  Caller: {other_asset.caller}\n" +
        #                f"  Ref 1: {ref}\n" +
        #                f"  Ref 2: {ref2}\n")
        #         return ErrorsStatic.report(msg, trigger=(2, 3))

        # else:
        #     print("REF2", ref2)
        #     print("  ", other_asset)
        #     cls.push(other_asset, ref2)

    @classmethod
    def parse_url(cls, url: str,  asset_i, dict_: dict, type=None) -> Accessor:  # -> Asset
        asset = cls.get_typed(asset_i, url, type)

        if asset.is_instense('Asset'):
            asset.caller = asset_i
            asset.update(dict_)
            cls.save(asset_i, dict_, asset)
            return asset
        elif asset is not None:
            msg = ("Empty asset:\n  %s   " % url)
            return ErrorsStatic.report(msg, warnPaths=True)
        else:
            asset = cls.get(asset_i, url)
            msg = ("URL asset failure:\n" +
                   "URL: '%s'\n" % url +
                   "Type: %s\n" % type +
                   "File ref:\n  '%s'\n" % asset_i.fileref +
                   "Found asset:\n %s\n" % asset)
            return ErrorsStatic.report(msg, warnPaths=True, trigger=(3, 4))

    @classmethod
    def parse_typed(cls, asset: Accessor, dict_: Dict, type_: Type[Accessor]) -> Accessor:
        asset_other = cls.get_by_dict(dict_, asset.fileref)

        if asset_other:
            if asset_other.is_instense('Geometry'):
                msg = ("Duplicate geometry definition:\n  %s" %
                       asset_other)
                ErrorsStatic.report(msg, trigger=(2, 4))
            return asset_other
        else:
            asset_other = type_(asset.fileref)

        asset_other.parse(dict_)
        cls.save(asset, dict_, asset_other)

        return asset_other

    @classmethod
    def get_by_dict(cls, struct: Dict[str, Any], fileref: str) -> Any:
        return cls.get_direct(DazPath.id(struct["id"], fileref))

    @classmethod
    def get_direct(cls, id_) -> Accessor:
        return cls.loaded.get(id_)

    @classmethod
    def keys(cls):
        return cls.loaded.keys()

    @classmethod
    def items(cls) -> Accessor:
        return cls.loaded.items()

    @classmethod
    def clear(cls):
        cls.loaded = {}
        cls.sources = defaultdict()
        cls.sources.default_factory = list
        cls.loaded_other = {}
