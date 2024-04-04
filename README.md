<p><img width="64px" src="https://github.com/cpb-/yocto-cooker/blob/master/doc/cooker-logo-small-size.png"></p>

# Yocto Cooker

![unit-tests workflow](https://github.com/cpb-/yocto-cooker/actions/workflows/unit-tests.yaml/badge.svg)

Meta buildtool for Yocto Project based Linux embedded systems

The aim of this project is to prepare the needed directories and configuration
files before running a Yocto Project build.

The tool is called `cooker` to follow the culinary metaphor specific to the
Yocto Project.

`cooker` uses a project file called a _menu_ :-).

A menu describes which sources (layers) (git repositories for example)
have to be downloaded and which revision has to be checked out.

It also contains custom lines to be written into the `local.conf` file and
which layers have to be included.

With the help of a _menu_ a reproducible build can be achieved. Menu-files are
files written in JSON and can thus be stored anywhere.

`cooker` can also call directly `bitbake` to run the build.


## Maintainers

- [Christophe Blaess](https://github.com/cpb-/)
- [Patrick Boettcher](https://github.com/pboettch)

## Installing Yocto Cooker

Install Yocto Cooker using PyPi:
``` bash
$ python3 -m pip install --upgrade git+https://github.com/cpb-/yocto-cooker.git
```

Install Yocto Cooker from source:
```
$ git clone https://github.com/cpb-/yocto-cooker
$ cd yocto-cooker
$ sudo pip3 install .
```

### Installing Yocto Cooker to contribute

To ease software modifications of Yocto Cooker itself, use the `-e` option with pip3 to
install `cooker` with editable mode enabled.
This way you can bring your modifications to `cooker.py` and call your updated `cooker`
tool anywhere you want to run it.
```
sudo pip3 install -e .
```

## `cooker` command line arguments

The `cooker` command accepts some arguments to know what to do. The first
argument is the sub-command name (`cook`, `build`, `init` and others) sometimes
followed by options, menu filename or build-config-names.

The top-level sub-command proposed by `cooker` is:

- `cooker cook <menu-file> [<build-configs>...]`: does the whole production job from the
  initial configuration and downloading up to the final image(s).

In fact, `cooker cook` is equivalent to a collection of low-level commands:

- `cooker init <menu-file>`: store the current menu filename into the
  `.cookerconfig` configuration file. The content of the configuration will be
  explained later.

- `cooker update`: fetch and checkout the version of each layer indicated in the
  current menu file.

- `cooker generate`: prepare the build-dir and configuration files (`local.conf`,
  `bblayers.conf`, `template.conf`) needed by Yocto Project.

- `cooker build [-d] [-k] [-s] [<build-configs>...]` runs `bitbake` to produce the given
  build-configs. If no build-config is indicated on the command line, `cooker`
  builds all the build-configs of the menu file. With the `-d` (or `--download`)
  option, `cooker` will only download all the needed files without doing any real
  compilation. With the `-k` (or `--keepgoing`) option, `cooker` will continue its
  work as long as possiible when encountering an error. With the `-s` (or `--sdk`)
  option, `cooker` will also build the cross-compiler toolchain and headers.

Each time you do some changes in the menu file, you may need to call:

- `cooker update`: if you have modified a commit number or you want to pull the
  latest version of a branch

- `cooker generate`: if you have modified a `local.conf` or a `layers`-attribute.

Then `cooker build` to restart the compilations.

Another useful sub-command is:

- `cooker clean <recipe> [<build-configs>...]` that will erase all files produced
during the compilation of a recipe (and also the shared-state-cache associated
files).

- `cooker shell <build-config>` provides you a new shell into the build directory
  with all the environment variables set. Some typical uses could be to
  run `bitbake -c menuconfig virtual/kernel` or `runqemu qemuarm` for instance.
  Simply `exit` the shell to return back to your previous working directory.
  Alternatively, you can run `cooker shell <build-config> -- <command>` to run
  the command in the environment.
  For example : `cooker shell <build-config> -- runqemu nographics`.

- `cooker diff` shows the current revision differences of all sources compared
  to the referenced revision in the menu.

- `cooker log <build-configs> <menu-from> [<menu-to>] [-H <history>] [-o <format>]`
  prints the changes (added, modified, deleted) of the build sources between two
  menu versions, `menu-from` and `menu-to` (default is the current menu file).
  Expands the git commit history of a space-separated modified source list with
  the `-H | --history` option. Supported output format are:
    - `text` (default): raw format, easy to parse.
    - `linked-text`, `ltxt`: raw format, supports commit links to github and gitlab.
    - `markdown`, `md`: markdown format with added, modified and deleted sections.
    - `linked-markdown`, `lmd`: markdown format, supports commit links to github and gitlab.

Each sub-command has additional command line options, e.g. with `init` the
download-dir can be set using the `-d` switch.

## How to build a standard image for Raspberry Pi 3?

Create and enter a project directory where everything will be downloaded,
stored and built.

```
$ mkdir  ~/yocto-project
$ cd  ~/yocto-project
```

You can call `cooker` with a single command to build the whole content
of a menu file:

```
$ cooker  cook  /path/to/yocto-cooker/sample-menus/pi3-sample-menu.json
```

Or you can proceed by using the low-level commands:

First, ask `cooker` to `initialize` the project-dir.

```
$ cooker  init  /path/to/yocto-cooker/sample-menus/pi3-sample-menu.json
```

Then let `cooker` download the layers mentioned in the menu.

```
$ cooker  update
```

Here no menu-file needs to be given. This works with the help of a
`.cookerconfig`-file written in the project dir.


Generating the build-directories, one per build-configuration with

```
$ cooker  generate
```

When this is done, the directory-structure should looks like this:

```
$ ls
build-pi3 layers
$ ls layers
meta-openembedded  meta-raspberrypi  poky
```

Then you can run a full build with:

```
$ cooker  build
```

You will see the classic Yocto Project progress messages, and after a while
the build will complete with:

```
Build Configuration:
BB_VERSION           = "1.44.0"
BUILD_SYS            = "x86_64-linux"
NATIVELSBSTRING      = "ubuntu-18.04"
TARGET_SYS           = "arm-poky-linux-gnueabi"
MACHINE              = "raspberrypi3"
DISTRO               = "poky"
DISTRO_VERSION       = "3.0.1"
TUNE_FEATURES        = "arm vfp cortexa7 neon vfpv4 thumb callconvention-hard"
TARGET_FPU           = "hard"
meta
meta-poky
meta-yocto-bsp       = "HEAD:12a4c177bb541b3187c7a54d5804f30c35f22d8c"
meta-oe              = "HEAD:e855ecc6d35677e79780adc57b2552213c995731"
meta-raspberrypi     = "HEAD:d17588fe8673b794b589335a753f4c1c90e12f88"

Initialising tasks: 100% |########################################################| Time: 0:00:04
Sstate summary: Wanted 1199 Found 1188 Missed 11 Current 0 (99% match, 0% complete)
NOTE: Executing Tasks
NOTE: Setscene tasks completed
NOTE: Tasks Summary: Attempted 3513 tasks of which 3189 didn't need to be rerun and all succeeded.
```

The image to write to your SD-card is:

```
build-pi3/tmp/deploy/images/raspberrypi3/core-image-base-raspberrypi3.rpi-sdimg
```


## Directory map

`cooker` downloads the needed layers in the `layers` directory (by default) and
creates the build-sub-directories into the `builds` directory.  For example,
after running `cooker init <menu-file>; cooker update; cooker generate`, the working
directory might contain:

```
./---+---layers--+--- poky/
     |           +--- meta-openembedded/
     |           +--- meta-raspberrypi/
     |           +--- meta-sunxi/
     |           +--- meta-custom-layer/
     |
     +---builds--+--- build-bananapi/
     |           +--- build-pi3/
     |           +--- build-pi4/
     |
     +-download--+- (packages dowloaded by bitbake)
     |
     +-sstate-cache--...
```


## Menu content

The menu file follows the JSON syntax and contains three main parts:

- `sources`: which describes how to download the required versions of the
 layers,
- `layers`: (optional) the list of the layers used globally for all targets
 or on a per-target-base
- `builds`: a collection of build-configurations to build.
- `local.conf`: a list of lines to be used in the configuration files of all
 build-configs (more on this below).

### Sources

The `sources` section is an array of methods to get the layers.
Each object of the array describes one layer.

The following attributes can be used:

- `url`: the URL used to download the layer. This attribute is mandatory.
- `method`: the way to handle the versioning of the layer. `cooker` is currently
developed mainly for `git`. Other methods will be available in the future.
The `ignore` method tells `cooker` to not download anything and to consider that
the layer is already present.
- `dir`: the path of the layer relative to the directory where you run `cooker`.
if `method` is `ignore` the layer must already be there and `dir` is
mandatory. Otherwise, this is the place to store the downloaded layer.
- `branch`: the `git` branch to use. Especially useful when no `rev` is
given.
- `rev`: the `git` tag or index of the revision desired.

`cooker` aims to build reproducible systems.
Using a specific `rev` number for each layer is the best way to do this.

If only a `branch` attribute is given, `cooker` will try to pull the last remote
update if an `url` is present. But this is not as reproducible as giving a
fixed `rev` number or tag.


### Common layers

This section contains an array of layers common to all build-configurations.

Most of the build-configurations uses

- `poky/meta`
- `poky/meta-poky`
- `poky/meta-yocto-bsp`
- `meta-openembedded/meta-oe`


### Build configurations

The `builds` section is a collection of build-configurations.
The name of the build-config is used to create the build directory.

For example, when preparing the compilation of the `pi3` build-config, `cooker`
creates the `build-pi3` directory.

A build-configuration may contain the following attributes: specific layers,
specific local.conf-entries, the bitbake-target to be produced and one or more
parent build-configuration from which it inherits layers and local
configuration entries.

#### Build-config specific layers

The `layers` attribute is an array of layer names which can be downloaded
from the `sources` section.

We recommend to indicate in this section the layers used only for this
build-config and to keep the more general ones in the `layers` section seen
above.


#### Target specific configuration

The `local.conf` attribute is an array of lines to add into the build's
configuration file.

`cooker` produces a standard `local.conf` file and add the given lines.

Basically, each build-config will contain at least a `MACHINE` specification
with the form:

```
  "MACHINE = 'raspberrypi3'"
```

You can use simple quotes to surround variable value, and double quotes for
the whole JSON line.

### Comments

You can add a `notes` section (array of free strings ignored by `cooker`) to
insert your own comments at the root-level of the menu or in the `builds`
section.

### Advanced use

If you intend to build for a custom system outside of Poky scheme (for example
the Arago Project), you may need to call a initialization script different from
`poky/oe-init-build-env`. In this case, you can specify it with the
`init-build-script` attribute:

```
    "sources": [ ... ],
    "layers" : [ ... ],
    "init-build-script" : "my-layer/build-env-setup-script",
    "builds" : [ ... ],
```

When this attribute is not specified, the default init script is the usual
`poky/oe-init-build-env`.

## Internal tests

Ideally each functionally is unit and functional tested via a script within the
`test/`-path.

To run the tests, `cmake` and `ctest` are used.

```bash
mkdir test-dir
cd test-dir

cmake path/to/yocto-cooker/test
make    # prepare the test-environment, nothing is compiled
ctest   # run the tests and show the result-summary

# useful ctest arguments

ctest -N   # shows the available tests
ctest -V   # shows verbose outputs of tests, all tests are run
ctest -R <pattern> -V   # run tests matching "pattern" and show their verbose output
```

Tests are written as a sequence of (cooker-)-commands and checks to see whether
the expected result or output has been generated or not.

The CMakeLists.txt in the test-folder contains the list of tests to be run.

The name of the test is identical to its subdirectory in the test-folder, e.g.,
the `basic/init`-test is located in `test/basic/init/`. This folder has to
contain a file called `test` (written in bash-syntax) which is sourced by the
test-driver (`driver.sh`). A non-zero exit-code indicates that a test has
failed. Any failing commands which end the test-run.

Within the script `test` the variable `$S` references the test's source-dir and
`$T` the test's runtime-dir.

The runtime-dir is wiped out before a test-run, but can be inspected after a
run.

Files related to and used by the test can be stored in the test's source-dir
accessible with `$S`.

Test-result evaluation functions are available in the `function.sh`-library and
are sourced by the test-driver.

## What will `cooker` do?

The `--dry-run` (or `-n`) option can be used to see what a `cooker` invocation
would produce without actually doing anything.

For example, `cooker --dry-run cook <menu-filename>` will display all the shell
commands that `cooker` would execute. The output could even be redirected into a
file that may later be run as a shell script.

The `--dry-run` output also displays the content of the files produced by
`cooker`.


## Licenses

The source code and the afferent files of the Yocto Cooker project are
distributed under [GPLv.2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)
license terms.

The present documention and the Yocto Cooker logo are distributed under
[Creative Commons 4.0 CC-By-Sa](https://creativecommons.org/licenses/by-sa/4.0/).
