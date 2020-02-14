# chef

Meta buildtool for Yocto Project based Linux embedded systems

The aim of this project is to prepare the needed directories and configuration files before running a Yocto Project build.

The tool is called `chef` to follow the culinary metaphore specific to the Yocto Project.

`chef` uses a configuration file called a _menu_ :-) which describes which sources (git repositories for example) have to be downloaded and which commits have to be extracted.
It also describes the specific lines to be written into the `local.conf` file and which layers have to be selected.

`chef` can also call `bitbake` to run the build.

## How to call `chef`

- `chef clear` (not implemented yet) will remove all downloaded layers and build sub-directory from the current directory.

- `chef prepare {menu file}` downloads the needed layers, and fills the configuration files into the build subdirectory.

- `chef build {menu file}` starts as `chef prepare {menu file}` then run `bitbake` to produce the wanted image file.

## Directory map


## Menu content

### Sources

### Common layers

### Targets

#### Target specific layers

#### Target specific configuration

