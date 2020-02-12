# chef

Meta buildtool for Yocto Project based Linux embedded systems

The aim of this project is to prepare the needed directories and configuration files before running a Yocto Project build.

The tool is called `chef` to follow the culinary metaphore specific to the Yocto Project.

`chef` uses a configuration file called a _menu_ :-) which describes which sources (git repositories for example) have to be downloaded and which commits have to be extracted.
It also describes the specific lines to be written into the `local.conf` file and which layers have to be selected.

`chef` can also call `bitbake` to run the build.

## How to call `chef`

## Menu content

### Sources

### Common layers

### Targets

#### Target specific layers

#### Target specific configuration

