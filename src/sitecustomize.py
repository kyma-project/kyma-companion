"""Site customization executed at Python startup via PYTHONPATH=/app/src.

Provides a stub for rdflib.plugins.stores.berkeleydb before any package is
imported.  langchain-hana 1.x unconditionally imports HanaRdfGraph, which
triggers `import rdflib`, which in turn executes plugin.py at module level:

    import rdflib.plugins.stores.berkeleydb   # line 42
    ...
    if rdflib.plugins.stores.berkeleydb.has_bsddb:  # line 177

PR #1372 deletes that file from the venv (BDBA hardening).  With the file
missing, line 42 raises ModuleNotFoundError, rdflib initialisation aborts, and
the container crashes at startup.

A naive sys.modules pre-population does not work: Python's import short-circuit
returns the stub from sys.modules without walking the parent-package chain, so
`rdflib.plugins` is never bound as an attribute of the partial `rdflib` module.
Line 177 then raises AttributeError.

The correct fix is a sys.meta_path finder/loader.  Python invokes it inside
_find_and_load_unlocked, which first ensures all parent packages are imported
and their attributes are bound (rdflib.plugins, rdflib.plugins.stores) before
handing off to our loader for the final segment.  After that, line 177's
attribute traversal succeeds.
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import pathlib
import sys
import types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec

_STUB_MODULE = "rdflib.plugins.stores.berkeleydb"


class _BerkeleyDBStubLoader(importlib.abc.Loader):
    """Loader that returns a minimal stub for rdflib.plugins.stores.berkeleydb."""

    def create_module(self, spec: ModuleSpec) -> types.ModuleType:
        stub = types.ModuleType(spec.name)
        # has_bsddb = False matches the behaviour when the berkeleydb C
        # extension is absent — plugin.py checks this flag before registering
        # the BerkeleyDB store.
        stub.has_bsddb = False  # type: ignore[attr-defined]
        return stub

    def exec_module(self, module: types.ModuleType) -> None:
        pass  # stub is fully initialised in create_module


class _BerkeleyDBStubFinder(importlib.abc.MetaPathFinder):
    """Meta-path finder that intercepts the missing berkeleydb module."""

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> ModuleSpec | None:
        if fullname != _STUB_MODULE:
            return None
        loader = _BerkeleyDBStubLoader()
        return importlib.util.spec_from_loader(fullname, loader)


def _install_rdflib_berkeleydb_stub() -> None:
    if _STUB_MODULE in sys.modules:
        return  # real module already imported elsewhere

    # find_spec for a top-level name does NOT import the package.
    rdflib_spec = importlib.util.find_spec("rdflib")
    if rdflib_spec is None or not rdflib_spec.submodule_search_locations:
        return  # rdflib not installed — nothing to patch

    rdflib_root = pathlib.Path(next(iter(rdflib_spec.submodule_search_locations)))
    if (rdflib_root / "plugins" / "stores" / "berkeleydb.py").exists():
        return  # file is present; normal import will work fine

    # berkeleydb.py was removed (BDBA hardening) — install the finder so that
    # when plugin.py runs `import rdflib.plugins.stores.berkeleydb` Python
    # processes the full parent-package chain (binding rdflib.plugins and
    # rdflib.plugins.stores as attributes) and then our loader returns the stub.
    sys.meta_path.insert(0, _BerkeleyDBStubFinder())


_install_rdflib_berkeleydb_stub()
