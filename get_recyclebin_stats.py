# -*- coding: utf-8 -*-
import ctypes
from ctypes import wintypes


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('i64Size', ctypes.c_int64),
        ('i64NumItems', ctypes.c_int64),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cbSize = ctypes.sizeof(self)


def get_recyclebin_stats():
    info = SHQUERYRBINFO()
    if ctypes.windll.shell32.SHQueryRecycleBinW('C:\\', ctypes.byref(info)) == 0:
        return {'size': info.i64Size, 'items': info.i64NumItems}
    return {'size': 0, 'items': 0}


if __name__ == '__main__':
    stats = get_recyclebin_stats()
    import json
    print(json.dumps(stats, indent=2))
