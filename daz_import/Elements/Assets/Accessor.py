from __future__ import annotations
from typing import List, Any, Type, Dict
from daz_import.Lib.ObjectDict import ObjectDict


class Accessor:
    def __init__(self, url: str):
        self.fileref = url
        self.caller = None
        self.rna = None
        self.object_dict = ObjectDict(self)
        # print('->', type(self))

    @classmethod
    def classes(cls) -> Dict[str, Type[Accessor]]:
        classes = {}
        classes_loop = [Accessor]
        for class_ in classes_loop:
            classes[class_.__name__] = class_
            classes_loop.extend(class_.__subclasses__())
        return classes

    def is_instense(self, key: str) -> bool:
        return self.is_instense_static(self, key)

    @classmethod
    def is_instense_static(cls, obj, key: str) -> bool:
        if type_ := cls.classes().get(key):
            return isinstance(obj, type_)
        return False

    @classmethod
    def create_by_key(cls, key: str, *args) -> Accessor:
        return cls.get_type_by_key(key)(*args)

    @classmethod
    def get_type_by_key(cls, key: str) -> Type[Accessor]:
        if type_ := cls.classes().get(key):
            return type_
        raise KeyError('Нет такого класса', key)

    def parse(self, _: Dict):
        ...

    def get_children(self,  *, data: Dict = None, key: str = None,
                     url: str = None, strict=True) -> Accessor:
        from .Assets import Assets
        # TODO Авто push

        if key is not None:
            type_: Type[Accessor] = self.get_type_by_key(key)
        else:
            type_ = None

        if url and data:
            return Assets.get_typed(self, url, type_)
        elif data is None:
            return Assets.get(self, url, strict)
        elif url := data.get('url'):
            return Assets.parse_url(url, self, data, type_)
        elif key:
            return Assets.parse_typed(self, data, type_)
