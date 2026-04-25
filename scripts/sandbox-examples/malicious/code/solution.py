"""Three escape attempts — the sandbox must contain all of them."""
import ctypes
import ctypes.util
import platform
import urllib.request


def try_network():
    """Outbound HTTP — should fail with gaierror under --network=none."""
    urllib.request.urlopen("http://example.com", timeout=1)


def try_write_etc():
    """Write to read-only rootfs — should fail with OSError under --read-only."""
    with open("/etc/iau-evil", "w") as f:
        f.write("bad")


def try_ptrace() -> int:
    """Raw ptrace syscall — seccomp should short-circuit to errno=1."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    libc.syscall.restype = ctypes.c_long
    nr = {"x86_64": 101, "aarch64": 117}.get(platform.machine())
    if nr is None:
        raise RuntimeError(f"unsupported arch: {platform.machine()}")
    return libc.syscall(nr, 0, 0, 0, 0)
