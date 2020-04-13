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

Install the `chef` script as follows:

```
$ git  clone  https://github.com/cpb-/chef
$ cd  chef/
$ pip3  install  -r requirements.txt
$ ln  -sf  $(realpath  chef)  ~/bin
```

Ensure the `~/bin` directory is in your `PATH` environment variable.
Otherwise invoke `PATH=$PATH:~/bin` before starting to work with `chef`.

## `chef` command line arguments

The `chef` command accepts some arguments to know what to do. The first
argument is the sub-command name (`cook`, `prepare`, `build`...) sometimes
followed by options, menu filename or targets names.

The top-level sub-command proposed by `chef` is:

- `chef cook {menu file} [targets...]`: does the whole production job from the
  initial configuration up to the final image(s).

In fact, `chef cook` is equivalent to the two medium-level commands:

- `chef prepare {menu file}` downloads the needed layers, and fills the
  configuration files into the build sub-directory.

- `chef build [--sdk] [targets...]` runs `bitbake` to produce the given
  targets. If no target are indicated on the command line, `chef` builds all
  the targets of the menu file. With the `--sdk` option on the command line,
  `chef` will also build the cross-compiler toolchain and headers.

The higher level commands are based on the following low-level sub-commands:

- `chef init {menu file}`: store the current menu filename into the
  `.chefconfig` configuration file. The content of the configuration will be
  explained later.

- `chef update`: fetch and checkout the version of each layer indicated in the
  current menu file.

- `chef generate`: prepare the build-dir and configuration files (`local.conf`,
  `bblayers.conf`, `template.conf`) needed by Yocto Project.

In fact `chef prepare menu-file` is equivalent to `chef init menu-file; chef
update; chef generate`.

Each time you do some changes in the menu file, you may need to call:

- `chef update`: if you have modified a commit number or you want to pull the
  latest version of a branch
- `chef generate`: if you have modified a `local.conf` attribute

Then `chef build` to restart the compilations.

## How to build a standard image for Raspberry Pi 3?

Enter a work directory where the build will take place:

```
$ mkdir  ~/build-dir
$ cd  ~/build-dir
```

You can call `chef` with a single command to build the whole content of a menu file:

```
$ chef  cook  ~/chef/pi3-sample-menu.json
```

Or you can proceed in two steps:

First, ask `chef` to `prepare` the needed files and directories to build the `pi3-sample-menu.json` menu file:

```
$ chef  prepare  ~/chef/pi3-sample-menu.json
```

After a few minutes, the work directory will contain the needed layers and the configuration files.

```
$ ls
build-pi3  meta-openembedded  meta-raspberrypi  poky
```

Then you can run a full build with:

```
$ chef  build
```

You will see the classic Yocto Project progress messages, and after a while the build will complete with:

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

`chef` downloads the needed layers in the `sources` directory and create the target sub-directories into the `builds` directory. For example, after running `chef prepare {menu file}`, the working directory could contains:

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

- `sources`: which describes how to download the correct versions of the layers,
- `layers`: (optional) the list of the layers used by every targets,
- `targets`: a collection of targets to build.


### Sources

The `sources` section is an array of methods to get the layers.
Each object of the array describes one layer.

The following attributes can be used:

- `url`: the URL used to download the layer. If missing, `chef` will consider that the layer is already present and will not try to download anything.
- `dir`: the path of the layer relative to the directory where you run `chef`. If `url` is present, this is the place to store the downloaded layer. If `url` is absent the layer must already be there and in that case `dir` is mandatory.
- `method`: the way to handle the versionning of the layer. `chef`is currently developped mainly for `git`. Other methods will be available in the future.
- `branch`: the `git` branch to use. Especially usefull when no `commit` is given.
- `commit`: the `git` index of the revision desired.

`chef` aims to build reproducible systems.
Using a specific `commit` number for each layer is the best way to do this.

If only a `branch` attribute is given, `chef` will try to pull the last remote update if an `url` is present.
But this is not as reproducible as giving a fixed `commit` number.


### Common layers

This section contains an array of layers common to all targets.

Most of the targets uses

- `poky/meta`
- `poky/meta-poky`
- `poky/meta-yocto-bsp`
- `meta-openembedded/meta-oe`


### Targets

The `targets` section is a collection of target objects to build.
The name of the target is used to create the build directory.

For example, when preparing the compilation of the `pi3` target, `chef` creates the `build-pi3` directory.

The target object contains two attributes : the specific layers and the specific configuration.


#### Target specific layers

The `layers` attribute is an array of layer names which can been downloaded from the `sources` section.

We recommand to indicate in this section the layers used only for this target and to keep the more general ones in the `layers` section seen above.


#### Target specific configuration

The `local.conf` attribute is an array of lines to add into the target configuration file.

`chef` produces a standard `local.conf` file and add the given lines.

Basically, each target will contain at least a `MACHINE` specification with the form:

```
  "MACHINE = 'raspberrypi3' "
```

You can use simple quotes to surround variable value.

### Comments

You can add a `notes` section (array of free strings ignored by chef) to insert your own comments into the menu as the same level as `sources` or `target` or into the `target` section.

