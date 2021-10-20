from __future__ import annotations
from typing import List, Any, Type, Dict
from daz_import.Lib.Errors import ErrorsStatic
from daz_import.Collection import DazPath

from .Assets import Assets
from .Accessor import Accessor
from daz_import.Lib.Utility import UtilityStatic
from daz_import.Lib import dicttools


class Asset(Accessor):

    def __init__(self, fileref: str):
        super().__init__(fileref)

        self.id = None
        self.url: str = None
        self.name = None

        self.label = None
        self.type = None
        self.visible = True
        self.source = None
        self.sourcing = None
        self.drivable = True
        self.value = None

        self.parent: Asset = None
        self.children: List[Asset] = []

    def __repr__(self):
        return ("<Asset %s t: %s r: %s>" % (self.id, self.type, self.rna))

    def errorWrite(self, ref: Any, fp: Any) -> None:
        fp.write('\n"%s":\n' % ref)
        fp.write("  %s\n" % self)

    def selfref(self) -> str:
        return ("#" + self.id.rsplit("#", 2)[-1])

    def getLabel(self, inst=None) -> str:
        if inst and inst.label:
            return inst.label
        elif self.label:
            return self.label
        else:
            return self.name

    def getName(self) -> str:
        if self.id is None:
            return "None"

        return DazPath.unquote(self.id.rsplit("#", 1)[-1])

    def copySource(self, asset: Asset):
        for key, value in asset.object_dict.items():
            if not hasattr(self, key):
                continue
            self.object_dict[key] = value

    def copySourceFile(self, source: str) -> Accessor:
        # file = source.rsplit("#", 1)[0]
        asset = self.get_children(data={"url": source})

        if asset is None:
            return None

        old = asset.id.rsplit("#", 1)[0]
        new = self.id.rsplit("#", 1)[0]

        self.copySourceAssets(old, new)

        for other in Assets.sources[old]:
            self.copySourceAssets(other, new)
        Assets.sources[old].append(new)

        return asset

    @staticmethod
    def copySourceAssets(old, new) -> None:
        nold, adds = len(old), []

        for key, asset in Assets.items():
            if key[0:nold] != old:
                continue
            adds.append((new + key[nold:], asset))

        for key, asset in adds:
            if key in Assets.loaded_other.keys():
                continue
            Assets.loaded_other[key] = asset

    def parse(self, data: dict) -> Asset:
        if id_ := data.get("id"):
            self.id = DazPath.id(id_, self.fileref)
        else:
            self.id = "?"

            msg = f"Asset without id\nin file \"{self.fileref}\":\n{data}    "
            ErrorsStatic.report(msg, trigger=(1, 2))

        if url := dicttools.get_key(data, "url", "id"):
            self.url = url

        if name := dicttools.get_key(data, "name", "id"):
            self.name = name
        elif self.url:
            self.name = self.url
        else:
            self.name = "Noname"

        dicttools.mix(self.object_dict, data, ["label", "type"])
        channel = data.get("channel", {})
        dicttools.mix(self.object_dict, channel, ["visible", "label"])

        if parent := data.get("parent"):
            self.parent = self.get_children(url=parent)
            if self.parent:
                self.parent.children.append(self)

        if source := data.get("source"):
            self.parseSource(source)

        return self

    def parseSource(self, url: str) -> None:
        asset = self.get_children(url=url)
        if not asset:
            return

        if self.type != asset.type:
            msg = ("Source type mismatch:   \n" +
                   f"{asset.type} != {self.type}\n" +
                   f"URL: {url}           \n" +
                   f"Asset: {self}\n" +
                   f"Source: {asset}\n")
            ErrorsStatic.report(msg, trigger=(2, 3))
            return

        self.source = asset
        asset.sourcing = self
        Assets.push(self, url)

    def update(self, struct: Dict[str, Any]) -> Asset:
        dicttools.mix(self.object_dict, struct, [
                      "type", "name", "url", "label"])

        if parent := struct.get("parent"):
            if self.parent is None and self.caller:
                self.parent = self.caller.get_children(url=parent)

        if value := struct.get("channel"):
            self.value = UtilityStatic.get_current_value(value)

        # if False and self.source:
        #     self.children = self.source.children
        #     self.sourceChildren(self.source)

        return self

    def sourceChildren(self, source: Asset) -> None:
        for srcnode in source.children:
            srcnode: Asset

            url = self.fileref + "#" + srcnode.id.rsplit("#", 1)[-1]
            print("HHH", url)
            Assets.push(srcnode, url)
            self.sourceChildren(srcnode)

    def build(self, context: Any, inst: Any = None) -> None:
        ...

    def buildData(self, context: Any, inst: Any, center: Any) -> None:
        print("BDATA", self)
        if self.rna is None:
            self.build(context)

    def connect(self, _: Dict) -> None:
        ...

    def setExtra(self, data):
        ...
