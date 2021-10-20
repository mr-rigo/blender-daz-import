class ObjectDict:
    def __init__(self, obj, hidden=False):
        self.__obj = obj
        self.__hidden = hidden
        

    def __setitem__(self, key: str, value):
        setattr(self.__obj, key, value)

    def __getitem__(self, key: str):
        return getattr(self.__obj, key, None)

    def items(self):
        for key in self.keys():
            yield key, getattr(self.__obj, key)

    def keys(self):
        for key in dir(self.__obj):
            if not self.__hidden and key[0] == '_':
                continue
            yield key

    def __contains__(self, key) -> bool:
        return key in dir(self.__obj)

    def get(self, key, defalt=None):
        return getattr(self.__obj, key, defalt)

    def exists(self, key) -> bool:
        return key in self.keys()


if __name__ == '__main__':
    class Point:
        def __init__(self):
            self.x = 0
            self.y = 0

    point = Point()

    dict_ = ObjectDict(point)
    print(dict_.exists('x'))
