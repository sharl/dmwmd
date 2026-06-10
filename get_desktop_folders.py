# -*- coding: utf-8 -*-
from contextlib import contextmanager
from uuid import UUID
import ctypes
import os

# Windows API definitions
# from https://learn.microsoft.com/ja-jp/windows/win32/shell/knownfolderid
FOLDERID_Desktop = UUID('{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}')
# IT FAILS: this is high context Microsoft gag?
FOLDERID_PublicDesktop = UUID('{C4AA340D-F20F-4863-AF6E-F87EF2CC6C2F}')


@contextmanager
def com_string(fid: UUID) -> str | None:
    """
    A context manager for safely releasing pointers obtained from APIs
    """
    path_ptr = ctypes.c_wchar_p()
    fid_bytes = (ctypes.c_byte * 16)(*fid.bytes_le)

    hr = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(fid_bytes), 0, 0, ctypes.byref(path_ptr)
    )

    try:
        if hr == 0:
            yield path_ptr.value
        else:
            yield None
    finally:
        if path_ptr:
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)


def get_desktop_folders(public: bool = False) -> list[str]:
    """
    Get public and user desktop paths without duplicates
    """
    folders = [FOLDERID_Desktop]
    if public:
        folders.append(FOLDERID_PublicDesktop)
    paths = set()

    # from GUIDs
    for fid in folders:
        with com_string(fid) as path:
            if path and os.path.exists(path):
                paths.add(path)

    # For environments where the API fails
    if public:
        fallback = os.path.expandvars(r'%PUBLIC%\Desktop')
        if os.path.exists(fallback):
            paths.add(fallback)

    return sorted(list(paths))


if __name__ == '__main__':
    for b in [False, True]:
        for folder in get_desktop_folders(b):
            print(b, folder)
