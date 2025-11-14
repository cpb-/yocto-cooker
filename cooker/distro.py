from typing import Tuple


class Distro:
    DISTRO_NAME: str
    BASE_DIRECTORY: str
    BUILD_SCRIPT: str
    TEMPLATE_CONF: Tuple[str, ...]
    DEFAULT_CONF_VERSION: str
    LAYER_CONF_NAME: str
    LAYER_CONF_VERSION: str
    PACKAGE_FORMAT: str
    DEFAULT_BITBAKE_MAJOR_VERSION: int
    BITBAKE_INIT_FILE: str


class AragoDistro(Distro):
    DISTRO_NAME = "arago"
    BASE_DIRECTORY = "openembedded-core"
    BUILD_SCRIPT = "oe-init-build-env"
    TEMPLATE_CONF = ("meta/conf",)
    DEFAULT_CONF_VERSION = "1"
    LAYER_CONF_NAME = "LCONF_VERSION"
    LAYER_CONF_VERSION = "7"
    PACKAGE_FORMAT = "package_ipk"
    DEFAULT_BITBAKE_MAJOR_VERSION = 2
    BITBAKE_INIT_FILE = "sources/bitbake/lib/__init__.py"


class NoPokyDistro(Distro):
    DISTRO_NAME = "defaultsetup"
    BASE_DIRECTORY = "openembedded-core"
    BUILD_SCRIPT = "oe-init-build-env"
    TEMPLATE_CONF = ("meta/conf/templates/default",)
    DEFAULT_CONF_VERSION = "2"
    LAYER_CONF_NAME = "LCONF_VERSION"
    LAYER_CONF_VERSION = "7"
    PACKAGE_FORMAT = "package_rpm"
    DEFAULT_BITBAKE_MAJOR_VERSION = 2
    BITBAKE_INIT_FILE = "bitbake/lib/bb/__init__.py"


class PokyDistro(Distro):
    DISTRO_NAME = "poky"
    BASE_DIRECTORY = "poky"
    BUILD_SCRIPT = "oe-init-build-env"
    TEMPLATE_CONF = ("meta-poky/conf", "meta-poky/conf/templates/default")
    DEFAULT_CONF_VERSION = "1"
    LAYER_CONF_NAME = "POKY_BBLAYERS_CONF_VERSION"
    LAYER_CONF_VERSION = "2"
    PACKAGE_FORMAT = "package_rpm"
    DEFAULT_BITBAKE_MAJOR_VERSION = 2
    BITBAKE_INIT_FILE = "bitbake/lib/bb/__init__.py"
