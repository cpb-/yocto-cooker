<p><img width="64px" src="https://github.com/cpb-/chef/blob/master/doc/chef-logo-small-size.png"></p>

# chef



Meta buildtool for Yocto Project based Linux embedded systems

The aim of this project is to prepare the needed directories and configuration files before running a Yocto Project build.

The tool is called `chef` to follow the culinary metaphore specific to the Yocto Project.

`chef` uses a configuration file called a _menu_ :-) which describes which sources (git repositories for example) have to be downloaded and which commits have to be extracted.
It also describes the specific lines to be written into the `local.conf` file and which layers have to be selected.

`chef` can also call `bitbake` to run the build.

## How to call `chef`

- `chef clear` will remove all downloaded layers and build sub-directory from the current directory.

- `chef prepare {menu file}` downloads the needed layers, and fills the configuration files into the build subdirectory.

- `chef build {menu file} [targets...]` starts as `chef prepare {menu file}` then run `bitbake` to produce the given targets. If no target are indicated on the command line, `chef` builds all the targets of the menu file. With the `--sdk` option on the command line, `chef` will also build the cross-compiler toolchain and headers.

## Directory map

`chef` downloads the needed sources in the current working directory and create a build subdirectory. For example, after running `chef prepare {menu file}`, the working directory could contains:

```
./---+--- poky/
     +--- meta-openembedded/
     +--- meta-raspberrypi/
     +--- meta-custom-layer/
     +--- build-raspberrypi4/
     +--- build-imx6qdl/
```


## Menu content

The menu file contains three main sections: 

- `sources`: which describes how to download the correct version of the layers,
- `layers`: (optional) the list of the layers used by every targets,
- `targets`: a collection of the targets to build.

### Sources

The `sources` section is an array of methods to get the layers. Each object of the array describes one layer.

`chef` is currently developped mainly for `git`.

The following attributes can be used:

- `url`: the main URL to download the layer. If missing, `chef` will consider that the layer is already present.


### Common layers

### Targets

#### Target specific layers

#### Target specific configuration

