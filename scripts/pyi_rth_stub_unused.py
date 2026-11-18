"""PyInstaller runtime hook: stub unused matplotlib imports pulled by mediapipe drawing_utils.

`mediapipe.tasks.python.vision.drawing_utils` executes a top-level
`import matplotlib.pyplot as plt` solely for an unused 3D plotting helper.
Providing lightweight lazy dummy module stubs via `sys.meta_path` avoids
bundling ~90 MB of matplotlib + fonts + GUI backends and eliminates font-cache
startup overhead while keeping `sys.modules` clean until `mediapipe` imports it.
"""

import importlib.abc
import importlib.machinery
import sys
import types


class _DummyCallable:
    def __call__(self, *_args, **_kwargs):
        return self

    def __getattr__(self, _name: str):
        return self


class _MatplotlibStubModule(types.ModuleType):
    __uniphoto_stub__ = True

    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _DummyCallable()


_STUB_ROOT = "matplotlib"
_STUB_SUBMODULES = (
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.axes",
    "matplotlib.colors",
    "matplotlib.cm",
    "matplotlib.figure",
    "matplotlib.patches",
)


class _MatplotlibStubLoader(importlib.abc.Loader):
    def create_module(self, spec):
        mod = _MatplotlibStubModule(spec.name)
        mod.__spec__ = spec
        mod.__file__ = None
        if spec.submodule_search_locations is not None:
            mod.__path__ = []
        return mod

    def exec_module(self, module):
        parts = module.__name__.split(".")
        if len(parts) == 2 and parts[0] == _STUB_ROOT:
            parent = sys.modules.get(_STUB_ROOT)
            if parent is not None:
                setattr(parent, parts[1], module)


class _MatplotlibStubFinder(importlib.abc.MetaPathFinder):
    _loader = _MatplotlibStubLoader()

    def find_spec(self, fullname, path=None, target=None):
        if fullname == _STUB_ROOT or fullname.startswith(_STUB_ROOT + "."):
            is_pkg = fullname == _STUB_ROOT
            return importlib.machinery.ModuleSpec(
                fullname,
                self._loader,
                is_package=is_pkg,
            )
        return None


if not any(isinstance(f, _MatplotlibStubFinder) for f in sys.meta_path):
    sys.meta_path.append(_MatplotlibStubFinder())
