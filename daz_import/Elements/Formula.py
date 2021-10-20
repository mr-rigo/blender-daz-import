from mathutils import Vector
from daz_import.Elements.Assets.Asset import Asset
from daz_import.Lib.Settings import Settings, Settings
from daz_import.Lib.Errors import DazError, ErrorsStatic
from urllib.parse import unquote

from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Elements.Assets import Assets


# -------------------------------------------------------------
#   Formula
# -------------------------------------------------------------


class Formula:

    def __init__(self):
        self.__assset: Asset = self
        self.formulas = []
        self.built = False

    def parse(self, struct: dict):
        if cache := struct.get("formulas"):
            self.formulas = cache

    def build(self, context, inst):
        for formula in self.formulas:
            ref, key, value = self._compute_formula(formula)
            if ref is None:
                continue

            asset: Asset = self.__assset.get_children(url=ref)
            if asset is None or key != "value":
                continue

            if asset.is_instense('Morph'):
                asset.build(context, inst, value)

    def postbuild(self, _, inst):
        if not Settings.useMorphOnly_:
            return
            
        for formula in self.formulas:
            ref, key, value = self._compute_formula(formula)
            if ref is None:
                continue

            asset = self.__assset.get_children(url=ref)
            if not asset or not asset.is_instense('Node'):
                continue

            if inst := asset.getInstance(ref, self.caller):
                inst.formulate(key, value)

    def _compute_formula(self, formula: dict):
        if len(formula.get("operations", [])) != 3:
            return None, None, 0
        stack = []

        for struct in formula.get("operations", []):
            op = struct.get("op")
            if op == "push":
                if url := struct.get("url"):
                    ref, key = self.getRefKey(url)

                    if ref is None or key != "value":
                        return None, None, 0

                    asset = self.__assset.get_children(url=ref)

                    if not hasattr(asset, "value"):
                        return None, None, 0
                    stack.append(asset.value)

                elif val := struct.get("val"):
                    stack.append(val)
                else:
                    ErrorsStatic.report("Cannot push %s" %
                                        struct.keys(), trigger=(1, 5), force=True)
            elif op == "mult":
                x = stack[-2]*stack[-1]
                stack = stack[:-2]
                stack.append(x)
            else:
                ErrorsStatic.report("Unknown formula %s %s" % (
                    op, struct.items()), trigger=(1, 5), force=True)

        if len(stack) != 1:
            raise DazError(f"Stack error {stack}")

        ref, key = self.getRefKey(formula["output"])
        return ref, key, stack[0]

    def evalFormulas(self, rig, mesh):
        exprs = {}
        for formula in self.formulas:
            self.evalFormula(formula, exprs, rig, mesh)

        if not exprs and Settings.verbosity > 3:
            print("Could not parse formulas", self.formulas)

        return exprs

    @classmethod
    def evalFormula(cls, formula: dict, exprs: dict, rig, mesh):
        from daz_import.Elements.Bone import getTargetName

        words = unquote(formula["output"]).split("#")
        fileref = words[0].split(":", 1)[-1]
        driven = words[-1]
        output, channel = driven.split("?")

        if channel == "value":
            if mesh is None and rig is None:
                if Settings.verbosity > 2:
                    print("Cannot drive properties", output)
                    print("  ", unquote(formula["output"]))
                return False
            # pb = None
        else:
            output1 = getTargetName(output, rig)
            if output1 is None:
                ErrorsStatic.report(
                    "Missing bone (evalFormula): %s" % output, trigger=(2, 4))
                return False

            output = output1
            if output not in rig.pose.bones.keys():
                return False

            # pb = rig.pose.bones[output]

        path, idx, default = cls.parseChannel(channel)

        if output not in exprs.keys():
            exprs[output] = {"*fileref": (fileref, channel)}

        if path not in exprs[output].keys():
            exprs[output][path] = {}

        if idx not in exprs[output][path].keys():
            exprs[output][path][idx] = {
                "factor": 0,
                "factor2": 0,
                "prop": None,
                "bone": None,
                "bone2": None,
                "path": None,
                "comp": -1,
                "comp2": -1,
                "mult": None}

        expr = exprs[output][path][idx]

        if "stage" in formula.keys():
            cls.evalStage(formula, expr)
        else:
            cls.evalOperations(formula, expr)

    @classmethod
    def evalStage(cls, formula: dict, expr: dict):
        if formula["stage"] == "mult":
            opers = formula["operations"]
            prop, type, path, comp = cls.evalUrl(opers[0])
            if type == "value":
                expr["mult"] = prop

    @classmethod
    def evalOperations(cls, formula, expr):
        opers = formula["operations"]
        prop, type, path, comp = cls.evalUrl(opers[0])
        factor = "factor"
        if type == "value":
            if expr["prop"] is None:
                expr["prop"] = prop
        elif expr["bone"] is None:
            expr["bone"] = prop
            expr["comp"] = comp
        else:
            expr["bone2"] = prop
            factor = "factor2"
            expr["comp2"] = comp
        expr["path"] = path
        cls.evalMainOper(opers, expr, factor)

    @classmethod
    def evalUrl(cls, oper: dict):
        if "url" not in oper.keys():
            print(oper)
            raise RuntimeError("BUG: Operation without URL")

        url = oper["url"].split("#")[-1]
        prop, type = url.split("?")
        prop = unquote(prop)
        path, comp, default = cls.parseChannel(type)
        return prop, type, path, comp

    @staticmethod
    def evalMainOper(opers, expr, factor):
        if len(opers) == 1:
            expr[factor] = 1
            return
        oper = opers[-1]
        op = oper["op"]
        if op == "mult":
            expr[factor] = opers[1]["val"]
        elif op == "spline_tcb":
            expr["points"] = [opers[n]["val"] for n in range(1, len(opers)-2)]
        elif op == "spline_linear":
            expr["points"] = [opers[n]["val"] for n in range(1, len(opers)-2)]
        else:
            ErrorsStatic.report("Unknown formula %s" % opers, trigger=(2, 6))
            return

    @staticmethod
    def parseChannel(channel):
        if channel == "value":
            return channel, 0, 0.0
        elif channel == "general_scale":
            return channel, 0, 1.0
        attr, comp = channel.split("/")
        idx = VectorStatic.index(comp)
        if attr in ["rotation", "translation", "scale", "center_point", "end_point"]:
            default = Vector((0, 0, 0))
        elif attr in ["orientation"]:
            return None, 0, Vector()
        else:
            msg = ("Unknown attribute: %s" % attr)
            ErrorsStatic.report(msg)
        return attr, idx, default

    @staticmethod
    def getExprValue(expr, key):
        if ("factor" in expr.keys() and
                key in expr["factor"].keys()):
            return expr["factor"][key]
        else:
            return None

    @staticmethod
    def getRefKey(string):
        base = string.split(":", 1)[-1]
        return base.rsplit("?", 1)
