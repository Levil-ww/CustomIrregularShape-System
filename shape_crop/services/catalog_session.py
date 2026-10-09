"""Desktop catalog lifetime: one recursive Windows watcher, including SMB shares.

No Qt dependency. ReadDirectoryChangesW supplies individual changed names, so
switching orders never enumerates 200,000 remote files again while watching is
healthy. Unsupported platforms/shares fall back to catalog verification.
"""
import os
import struct
from threading import Event, Lock, Thread
from shape_crop.services.catalog import match_material


class CatalogSession:
    def __init__(self, directory):
        self.directory = os.path.abspath(directory)
        self._lock = Lock()
        self._ready = Event()
        self._stop = Event()
        self._events = []
        self._overflow = False
        self._active = False
        self._handle = None
        self._kernel = None
        self._thread = None
        self._verify = True
        self.watch_error = ''

    def start(self):
        with self._lock:
            dead = self._thread is not None and not getattr(self._thread, 'is_alive', lambda: True)()
            if dead:
                self._thread = None
            if self._thread is None and os.name == 'nt':
                self._stop.clear()
                self._thread = Thread(target=self._watch, name='catalog-watch', daemon=True)
                self._thread.start()
        self._ready.wait(2 if os.name == 'nt' else 0)

    @property
    def active(self):
        with self._lock:
            return self._active and not self._stop.is_set()

    def request_refresh(self):
        with self._lock:
            self._verify = True

    def match(self, target, cancelled=None, progress=None):
        self.start()
        with self._lock:
            events, self._events = self._events, []
            verify = self._verify or self._overflow or not self._active
            self._verify = self._overflow = False
        try:
            if progress and not self.active:
                progress('图库变更监听不可用，正在核对目录索引…')
            match = match_material(target, self.directory, cancelled, progress,
                                   verify=verify, events=events)
            # Deletion or a missed notification must never hand out a dead file.
            if not os.path.isfile(match.path):
                match = match_material(target, self.directory, cancelled, progress, verify=True)
            return match
        except Exception:
            with self._lock:
                self._events = events + self._events
                self._verify = self._verify or verify
            raise

    def close(self):
        self._stop.set()
        with self._lock:
            if self._handle is not None and self._kernel is not None:
                self._kernel.CancelIoEx(self._handle, None)

    def _watch(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.ReadDirectoryChangesW.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                                 wintypes.BOOL, wintypes.DWORD,
                                                 ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, ctypes.c_void_p)
        kernel.ReadDirectoryChangesW.restype = wintypes.BOOL
        kernel.CancelIoEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
        kernel.CancelIoEx.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        # FILE_LIST_DIRECTORY, shared read/write/delete, OPEN_EXISTING,
        # FILE_FLAG_BACKUP_SEMANTICS. 64KiB is the maximum buffer on SMB.
        handle = kernel.CreateFileW(self.directory, 1, 7, None, 3, 0x02000000, None)
        if handle == ctypes.c_void_p(-1).value:
            self.watch_error = f'Windows error {ctypes.get_last_error()}'
            self._ready.set()
            return
        buffer = ctypes.create_string_buffer(65536)
        received = wintypes.DWORD()
        with self._lock:
            self._kernel, self._handle = kernel, handle
            self._active = True
        self._ready.set()
        try:
            while not self._stop.is_set():
                ok = kernel.ReadDirectoryChangesW(handle, buffer, len(buffer), True,
                                                  0x00000001 | 0x00000002,
                                                  ctypes.byref(received), None, None)
                if not ok:
                    if not self._stop.is_set():
                        self.watch_error = f'Windows error {ctypes.get_last_error()}'
                    break
                events, offset = [], 0
                if received.value:
                    raw = buffer.raw[:received.value]
                    while offset + 12 <= len(raw):
                        step, action, size = struct.unpack_from('<III', raw, offset)
                        try:
                            name = raw[offset + 12:offset + 12 + size].decode('utf-16-le')
                        except UnicodeDecodeError:
                            if not step:
                                break
                            offset += step
                            continue
                        path = os.path.normpath(os.path.join(self.directory, name))
                        events.append((action, path))
                        if not step:
                            break
                        offset += step
                with self._lock:
                    if not received.value or len(self._events) + len(events) > 10000:
                        self._overflow = True
                        self._events.clear()
                    else:
                        self._events.extend(events)
        finally:
            with self._lock:
                self._active = False
                self._handle = None
                self._thread = None
                kernel.CloseHandle(handle)
