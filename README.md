<p><img width="64px" src="https://github.com/cpb-/chef/blob/master/doc/chef-logo-small-size.png"></p>

# chef


Meta buildtool for Yocto Project based Linux embedded systems

The aim of this project is to prepare the needed directories and configuration
files before running a Yocto Project build.

The tool is called `chef` to follow the culinary metaphore specific to the
Yocto Project.

`chef` uses a project file called a _menu_ :-).

A menu describes which sources (layers) (git repositories for example)
have to be downloaded and which revision has to be checked out.

It also contains custom lines to be written into the `local.conf` file and
which layers have to be included.

With the help of a _menu_ a reproducible build can achieved. Menu-files are
files written in JSON and cna thus be stored anywhere.

`chef` can also call directly `bitbake` to run the build.


## Maintainers

- [Christophe Blaess](https://github.com/cpb-/)
- [Patrick Boettcher](https://github.com/pboettch)

## Installing `chef`

Install `chef` using PyPi:
``` bash
$ python3 -m pip install --upgrade git+https://github.com/cpb-/chef.git
```

Install `chef` from source:
```
$ git clone https://github.com/cpb-/chef
$ cd chef/
$ python3 setup.py install
```

## `chef` command line arguments

The `chef` command accepts some arguments to know what to do. The first
argument is the sub-command name (`cook`, `build`, `init` and others) sometimes
followed by options, menu filename or build-config-names.

The top-level sub-command proposed by `chef` is:

- `chef cook <menu-file> [<build-configs>...]`: does the whole production job from the
  initial configuration and downloading up to the final image(s).

In fact, `chef cook` is equivalent to a collection of low-level commands:

- `chef init <menu-file>`: store the current menu filename into the
  `.chefconfig` configuration file. The content of the configuration will be
  explained later.

- `chef update`: fetch and checkout the version of each layer indicated in the
  current menu file.

- `chef generate`: prepare the build-dir and configuration files (`local.conf`,
  `bblayers.conf`, `template.conf`) needed by Yocto Project.

- `chef build [--sdk] [<build-configs>...]` runs `bitbake` to produce the given
  build-configs. If no build-config is indicated on the command line, `chef`
  builds all the build-configs of the menu file. With the `--sdk` option on the
  command line, `chef` will also build the cross-compiler toolchain and headers.

Each time you do some changes in the menu file, you may need to call:

- `chef update`: if you have modified a commit number or you want to pull the
  latest version of a branch

- `chef generate`: if you have modified a `local.conf` or a `layers`-attribute.

Then `chef build` to restart the compilations.

Another useful sub-command is:

- `chef clean <recipe> [<build-configs>...]` that will erase all files produced
during the compilation of a recipe (and also the shared-state-cache associated
files).

Each sub-command has additional command line options, e.g. with `init` the
download-dir can be set using the `-d` switch.

## How to build a standard image for Raspberry Pi 3?

Create and enter a project directory where everything will be downloaded,
stored and built.

```
$ mkdir  ~/yocto-project
$ cd  ~/yocto-project
```

You can call `chef` with a single command to build the whole content
of a menu file:

```
$ chef  cook  /path/to/chef/sample-menus/pi3-sample-menu.json
```

Or you can proceed by using the low-level commands:

First, ask `chef` to `initialize` the project-dir.

```
$ chef  init  /path/to/chef/sample-menus/pi3-sample-menu.json
```

Then let chef download the layers mentioned in the menu.

```
$ chef  update
```

Here no menu-file needs to be given. This works with the help of a
`.chefconfig`-file written in the project dir.


Generating the build-directories, one per build-configuration with

```
$ chef  generate
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
$ chef  build
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

`chef` downloads the needed layers in the `layers` directory (by default) and
creates the build-sub-directories into the `builds` directory.  For example,
after running `chef init {menu file}; chef update; chef generate`, the working
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
- `method`: the way to handle the versionning of the layer. `chef`is currently
developped mainly for `git`. Other methods will be available in the future.
The `ignore` method tells `chef` to not download anything and to consider that
the layer is already present.
- `dir`: the path of the layer relative to the directory where you run `chef`.
if `method` is `ignore` the layer must already be there and `dir` is
mandatory. Otherwise, this is the place to store the downloaded layer.
- `branch`: the `git` branch to use. Especially usefull when no `commit` is
given.
- `rev`: the `git` tag or index of the revision desired.

`chef` aims to build reproducible systems.
Using a specific `rev` number for each layer is the best way to do this.

If only a `branch` attribute is given, `chef` will try to pull the last remote
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

For example, when preparing the compilation of the `pi3` build-config, `chef`
creates the `build-pi3` directory.

A build-configuration may contain the following attributes: specific layers,
specific local.conf-entries, the bitbake-target to be produced and one or more
parent build-configuration from which it inherits layers and local
configuration entries.

#### Build-config specific layers

The `layers` attribute is an array of layer names which can been downloaded
from the `sources` section.

We recommand to indicate in this section the layers used only for this
build-config and to keep the more general ones in the `layers` section seen
above.


#### Target specific configuration

The `local.conf` attribute is an array of lines to add into the build's
configuration file.

`chef` produces a standard `local.conf` file and add the given lines.

Basically, each build-config will contain at least a `MACHINE` specification
with the form:

```
  "MACHINE = 'raspberrypi3'"
```

You can use simple quotes to surround variable value, and double quotes for
the whole JSON line.

### Comments

You can add a `notes` section (array of free strings ignored by `chef`) to
insert your own comments at the root-level of the menu or in the `builds`
section.

## Internal tests

Ideally each functionally is unit and functional tested via a script within the
`test/`-path.

To run the tests, `cmake` and `ctest` are used.

```bash
mkdir test-dir
cd test-dir

cmake path/to/chef/test
make    # prepare the test-environment, nothing is compiled
ctest   # run the tests and show the result-summary

# useful ctest arguments

ctest -N   # shows the available tests
ctest -V   # shows verbose outputs of tests, all tests are run
ctest -R <pattern> -V   # run tests matching "pattern" and show their verbose output
```

Tests are written as a sequence of (chef-)-commands and checks to see whether
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
