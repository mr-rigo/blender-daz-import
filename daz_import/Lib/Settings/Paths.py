import glob
import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote
from shlex import quote
import subprocess
from itertools import zip_longest

from typing import List


class Paths:
    spacer = '\\' if os.name == 'nt' else "/"

    home = os.getenv('HOME')

    @staticmethod
    def is_global(path) -> bool:
        # not relation
        return path and path[0] == '/'

    @classmethod
    def pattern(cls, path: str) -> str:
        path = cls.pattern_home(path)
        path = cls.strip(path)
        return path

    @classmethod
    def pattern_paths(cls, path) -> List[str]:
        path = cls.pattern_home(path)
        return cls.pattern_blob(path)

    @classmethod
    def pattern_home(cls, path: str) -> str:
        if path.find('~') == 0:
            return cls.join(os.getenv('HOME'), path[1:])
        else:
            return path

    @classmethod
    def pattern_blob(cls, path: str) -> List[str]:
        if path.find('*') != -1:
            return glob.glob(path)
        return [path]

    @classmethod
    def join(cls, *paths: str, full=False) -> str:
        if full:
            return cls.join_full(*paths)
        return cls.join_relation(*paths)

    @classmethod
    def join_relation(cls, *paths: str) -> str:
        out = []
        paths_len = len(paths)
        for index, path in enumerate(paths):
            path: str = '' if path is None else str(path)
            if not path:
                continue

            path = path.rstrip(cls.spacer) if index + 1 != paths_len else path
            path = path.lstrip(cls.spacer) if index != 0 else path
            out.append(path)

        return cls.spacer.join(out)

    @classmethod
    def join_full(cls, *path: str) -> str:
        out = ''
        for point in path:
            out += point + cls.spacer
        return out[:-1] if out and out[-1] == cls.spacer else out

    @classmethod
    def add_spacer(cls, path: str) -> str:
        return path if path[-1] == cls.spacer else path + cls.spacer

    @classmethod
    def strip(cls, path: str) -> str:
        if path == cls.spacer:
            return path
        return path.rstrip(cls.spacer)

    @classmethod
    def strip_full(cls, path: str) -> str:
        if path == cls.spacer:
            return path
        return path.strip(cls.spacer)

    # @staticmethod
    # def parent(path: str) -> str:
    #     if path == '/':
    #         return ''
    #     elif parent := re.match(r'(^.+?)\/(?=[^\/]+\/?$)', path):
    #         return parent.groups()[0]
    #     elif re.match(r'/[^/]+', path):
    #         return '/'
    #     return ''

    @classmethod
    def parent(cls, path: str) -> str:
        path = cls.strip(path)
        parent = os.path.dirname(path)
        return parent if parent != path else ''

    @classmethod
    def relative_path(cls, path: str, pwd: str) -> str:
        if path.find('/') == 0:
            return path
        if path.find('../') == 0:
            if parent := cls.parent(pwd):
                return cls.relative_path(path[3:], parent)
        else:
            return cls.join(pwd, path)

    @classmethod
    def children(cls, *paths, recursive=False,
                 time_sort=False, only_files=False,
                 only_folders=False, result_filter=None,
                 filters=None, folder_filter=None) -> str:
        # child
        if filters is None:
            filters = []

            if only_files:
                filters.append(os.path.isfile)
            elif only_folders:
                filters.append(os.path.isdir)

            if result_filter:
                filters.append(result_filter)
        for folder in filter(os.path.exists, map(str, paths)):
            folder: str = cls.add_spacer(folder)

            if not os.path.isdir(folder):
                continue

            child_paths = (cls.join(folder, x) for x in os.listdir(folder))

            if time_sort:
                child_paths = (str(x) for x in sorted(
                    child_paths, key=os.path.getmtime))

            for path_ in child_paths:
                if all(filter_(path_) for filter_ in filters):
                    yield path_

                if recursive and os.path.isdir(path_):
                    if folder_filter and not folder_filter(path_):
                        continue
                    yield from cls.children(path_, recursive=recursive,
                                            time_sort=time_sort, filters=filters,
                                            folder_filter=folder_filter)

    # @classmethod
    # def get_children(cls, path, recursive=False):
    #     try:
    #         path = cls.end_slash(path)
    #         paths = os.listdir(path)
    #     except:
    #         paths = []
    #     out = []
    #     for name in paths:
    #         path_ = cls.join_paths(path, name)
    #         out.append(path_)
    #         if recursive and os.path.isdir(path_):
    #             out.extend(cls.get_children(path_, recursive=recursive))
    #     return out

    @staticmethod
    def uniq(path):
        "Функция для защиты от совпадения имен"
        if not os.path.exists(path):
            return path
        is_dir = os.path.isdir(path)

        if is_dir:
            extension, name_and_path = None, None
        else:  # Получаем файла расширение а также имя файла и путь в одном
            dot_cut = path.split('/')[-1].split('.')
            extension = dot_cut[-1] if len(dot_cut) > 1 else ''
            name_and_path = path[:-len(extension) - 1]

        # Ищем путь в котором нет файла или папки
        new_path, index = path, 1
        while True:
            if is_dir or not extension:
                new_path = f'{path}_{index}'
            else:
                new_path = f'{name_and_path}_{index}.{extension}'

            if not os.path.exists(new_path):
                return new_path
            index += 1

    # @classmethod
    # def mkdir(cls, path, recursive=True):
    #     # mkdir
    #     path = cls.end_clear(path)
    #     if os.path.exists(path):
    #         return True
    #     parent = os.path.dirname(path)
    #     parent_exists = os.path.exists(parent)
    #     if not parent_exists and recursive:
    #         cls.mkdir(parent, recursive)
    #     elif not parent_exists:
    #         raise NotADirectoryError
    #     os.mkdir(path)
    #     return True

    @classmethod
    def mkdir(cls, path, recursive=True):
        if not recursive:
            return os.mkdir(path)

        point, create = path, []

        while point and not cls.exists(point):
            create.append(point)
            point = cls.parent(point)

        for point in reversed(create):
            if os.path.isfile(point):
                raise FileExistsError("Не могу создать каталог", point)
            os.mkdir(point)

    @classmethod
    def mkdir_parent(cls, path):
        if parent := cls.parent(path):
            cls.mkdir(parent, recursive=True)

    @classmethod
    def get_extension(cls, path) -> str:
        if data := re.match(r'^.*?([^\/]+?)(\.([^\/.]+))?$', path):
            if ext := data.groups()[2]:
                return ext
        return ''

    @classmethod
    def extension_equal(cls, path, ext: str) -> bool:
        ext_b = cls.get_extension(path)
        return ext.lower() == ext_b.lower()

    @staticmethod
    def get_extensions(path: str) -> List[str]:
        if math := re.findall(r'(?<=\w)\.[^\/]+$', path):
            return list(filter(lambda item: item if item else None, math[0].split('.')))
        return []

    @classmethod
    def set_extension(cls, path: str, ext: str):
        ext_old = cls.get_extension(path)
        path = path[:-len(ext_old) - 1] if ext_old else path
        return path + ('' if path[-1] == '.' else '.') + ext

    @classmethod
    def split(cls, path: str):
        return list(filter(bool, path.split(cls.spacer)))

    @staticmethod
    def remove(path):
        os.remove(path)

    @classmethod
    def remove_tree(cls, path):
        if cls.exists(path):
            shutil.rmtree(path)

    @classmethod
    def get_name(cls, path, full=False) -> str:
        for point in reversed(cls.split(path)):
            if full:
                return point
            else:
                points = list(cls.get_extension_points(point))
                if len(points) == 1:
                    return point
                else:
                    return '.'.join(list(points)[:-1])

    @staticmethod
    def get_extension_points(file_name) -> List[str]:
        return filter(bool, file_name.split('.'))

    @staticmethod
    def exists(path) -> bool:
        return os.path.exists(path)

    @classmethod
    def touch(cls, path):
        if cls.exists(path):
            raise FileExistsError(path)

        Path(path).touch()

    @classmethod
    def fix_procent(cls, path) -> str:
        name = cls.get_name(path)
        ext = cls.get_extension(path)
        ext = '.' + ext if ext else ''

        folder = cls.parent(path)
        while True:
            name_cache = unquote(name)
            if name_cache == name:
                break
            name = name_cache
        return cls.join(folder, name + ext)

    @classmethod
    def is_link(cls, path, depth=0) -> bool:
        if os.path.islink(path):
            return True

        if depth == 0:
            return False

        for index, point in enumerate(cls.parents(path)):
            index += 1
            if index > depth:
                break
            if os.path.islink(point):
                return True

        return False

    @classmethod
    def link_path(cls, path, parse=False):
        if not cls.is_link(path):
            return ''
        link = os.readlink(path)

        if not parse:
            return link

        return cls.real_path(link, cls.parent(path))

    # @classmethod
    # def split(cls, path: str):
    #     return path.split('/')

    @classmethod
    def real_path(cls, path: str, folder: str) -> str:
        if not path or path[0] == '/':
            return path
        points = []
        for point in cls.split(path):
            if point == '..':
                folder = cls.parent(folder)
            else:
                points.append(point)

        return cls.join(folder, *points)

    @classmethod
    def parents(cls, path):
        path = cls.parent(path)
        while path:
            yield path
            path = cls.parent(path)

    @classmethod
    def set_parent(cls, path: str, folder: str):
        return cls.join(folder, cls.get_name(path, full=True))

    @classmethod
    def copy(cls, path, new_file, tree=False, mkdir=False):
        if mkdir:
            if folder_ := cls.parent(new_file):
                cls.mkdir(folder_)

        if tree:
            shutil.copytree(path, new_file)
        else:
            shutil.copyfile(path, new_file)

    @staticmethod
    def open(path: str):
        subprocess.Popen(f'xdg-open {quote(path)}', shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def symlink(cls, path, link, is_local=False):
        os.symlink(cls._symlink_path(path, link, is_local), link)

    @classmethod
    def _symlink_path(cls, path, link, is_local=False):
        folder, link_path, src_path = [], [], []

        path = cls.strip(path)
        link = cls.strip(link)

        if not (cls.is_global(path) and cls.is_global(link)):
            raise ValueError('Адреса должны быть глобальные', path, link)

        if not is_local:
            return path

        for src_, link_ in zip_longest(cls.split(path), cls.split(link), fillvalue=None):
            if not link_path and src_ == link_:
                folder.append(link_)
            else:
                link_path.append(link_)
                src_path.append(src_)

        src_path = list(filter(None, src_path))
        link_path = list(filter(None, link_path))

        link = '../' * (len(link_path) - 1) + '/'.join(src_path)
        return link

    @staticmethod
    def sub(path, parent):
        path, parent = str(path), str(parent)
        if path.find(parent) == 0:
            return path[len(parent):]
        raise ValueError(
            'Каталог для вычитания должен быть родительский', path, parent)

    @staticmethod
    def is_folder(path: str) -> bool:
        return os.path.isdir(path)

    @classmethod
    def move(cls, input_path: str, path: str = None, folder: str = None, safe_mode=True):
        if path:
            move_path = path
        elif folder:
            move_path = cls.join(
                folder, cls.get_name(input_path, full=True))
        else:
            raise ValueError(
                'Не указано куда переместить файл', input_path)

        if input_path == path or not move_path:
            return

        if safe_mode:
            move_path = cls.uniq(move_path)
        else:
            if os.path.exists(move_path):
                raise FileExistsError("Такой файл уже существует ", move_path)

        if parent := cls.parent(move_path):
            cls.mkdir(parent, recursive=True)

        # os.rename(self._path, move_path)
        # print(input_path, move_path)
        shutil.move(input_path, move_path)

        if os.path.exists(input_path):
            raise FileExistsError('Узел не переместился', input_path)

    @staticmethod
    def path_fix(path: str) -> str:
        filepath = os.path.expanduser(path).replace("\\", "/")
        return filepath.rstrip("/ ")


def test_set_extension():
    res = "/home/user/content.mp4"
    assert Paths.set_extension('/home/user/content.txt', 'mp4') == res
    assert Paths.set_extension('/home/user/content', 'mp4') == res
    assert Paths.set_extension('/home/user/content.', 'mp4') == res


def test_set_folder():
    assert Paths.set_parent('content', '/tmp') == '/tmp/content'
    assert Paths.set_parent('/content.txt/', '/tmp') == '/tmp/content.txt'
    assert Paths.set_parent(
        '/home/user/content.txt', '/tmp') == '/tmp/content.txt'


def test_get_name():
    assert Paths.get_name('/home/user/content') == 'content'
    assert Paths.get_name('/home/user/content.txt') == 'content'
    assert Paths.get_name('/home/user/content.test.txt') == 'content.test'


def test_link_bin():
    assert Paths.link_path('/bin', True) == '/usr/bin'


def test_cope_breeze():
    Paths.copy('/usr/share/icons/breeze/index.theme',
               '/tmp/test/index.theme', mkdir=True)
    assert Paths.exists('/tmp/test/index.theme') == True


# py.test -v -s Spacks/Lib/Paths.py
