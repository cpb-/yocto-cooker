#!/usr/bin/env python3
""" chef.py: meta build tool for Yocto Project based Linux embedded systems."""

import argparse
import json
import sys
import os
from urllib.parse import urlparse
import jsonschema
import pkg_resources


def debug(*args):
    if ChefCall.DEBUG:
        print(*args)


def info(*args):
    print(*args)


def warn(*args):
    if ChefCall.WARNING:
        print('WARN:', *args)


def fatal_error(*args):
    print('FATAL:', *args)
    sys.exit(1)


class Config:
    DEFAULT_CONFIG_FILENAME = '.chefconfig'

    def __init__(self):
        debug('Looking for', Config.DEFAULT_CONFIG_FILENAME)

        self.cfg = {
            'menu': '',
            'layer-dir': 'layers',
            'build-dir': 'builds',
            'dl-dir': 'downloads',
        }
        self.filename = os.path.join(os.getcwd(), self.DEFAULT_CONFIG_FILENAME)

        path = os.getcwd().split(os.sep)
        while path:
            filename = '/' + os.path.join(*path, self.DEFAULT_CONFIG_FILENAME)

            debug(' Trying', filename)

            if os.path.isfile(filename):
                debug('  Found')

                self.filename = filename

                try:
                    with open(self.filename) as json_file:
                        self.cfg = json.load(json_file)
                    return
                except Exception as e:
                    fatal_error('configuration load error', e)

                break

            path.pop() # cd ..

        debug('No config-file found. Will be using', self.filename)


    def project_root(self):
        return os.path.dirname(self.filename)


    def set_menu(self, menu_file):
        self.cfg['menu'] = os.path.realpath(menu_file)


    def set_layer_dir(self, path):
        # paths in the config-file are relative to the project-dir
        self.cfg['layer-dir'] = os.path.relpath(path, self.project_root())


    def layer_dir(self, name=''):
        return os.path.join(self.project_root(), self.cfg['layer-dir'], name)


    def set_build_dir(self, path):
        self.cfg['build-dir'] = os.path.relpath(path, self.project_root())


    def build_dir(self, name=''):
        return os.path.join(self.project_root(), self.cfg['build-dir'], name)


    def set_dl_dir(self, path):
        self.cfg['dl-dir'] = os.path.relpath(path, self.project_root())


    def dl_dir(self):
        return os.path.join(self.project_root(), self.cfg['dl-dir'])


    def menu(self):
        return self.cfg['menu']


    def save(self):
        debug('Saving configuration file')
        with open(self.filename, 'w') as json_file:
            json.dump(self.cfg, json_file, indent=4)


    def empty(self):
        return not self.cfg['menu']


class BuildConfiguration:
    ALL = {}

    def __init__(self, name, config, layers, local_conf, target, inherit):
        self.name_ = name
        self.config_ = config
        self.layers_ = layers
        self.local_conf_ = local_conf
        self.target_ = target
        self.inherit_ = inherit

        self.parent_ = None
        self.children_ = []

        BuildConfiguration.ALL[name] = self


    def add_child(self, child):
        self.children_.append(child)


    def target(self):
        return self.target_

    def name(self):
        return self.name_


    def build_dir(self):
        return self.config_.build_dir('build-' + self.name_)


    def resolve_parent(self):
        if self.inherit_:
            if not self.inherit_ in BuildConfiguration.ALL:
                fatal_error('target "{}"\'s parent "{}" not found in targets-section'
                            .format(self.name_, self.inherit_))
            self.parent_ = BuildConfiguration.ALL[self.inherit_]
            self.parent_.add_child(self)


    def target(self):
        return self.target_


    def layers(self):
        if self.parent_:
            layers = self.parent_.layers()
        else:
            layers = []
        return layers + self.layers_


    def local_conf(self):
        if self.parent_:
            lines = self.parent_.local_conf()
        else:
            lines = []
        return lines + self.local_conf_


    def resolve():
        for _, build in BuildConfiguration.ALL.items():
            build.resolve_parent()


class ChefCommands:
    """ The class aggregates all functions representing a low-lever chef-command """

    DEFAULT_INIT_BUILD_SCRIPT = 'poky/oe-init-build-env'

    def __init__(self, config, menu):
        self.config = config
        self.menu = menu


    def init(self, menu_name, layer_dir=None, build_dir=None, dl_dir=None):
        """ chef-command 'init': (re)set the configuration file """
        self.config.set_menu(menu_name)

        if layer_dir:
            self.config.set_layer_dir(layer_dir)

        if build_dir:
            self.config.set_build_dir(build_dir)

        if dl_dir:
            self.config.set_dl_dir(dl_dir)

        self.config.save()


    def update(self):
        info('Update layers in project directory')

        for source in self.menu['sources']:
            self.update_source(source)


    def update_source(self, source):
        method = 'git'
        remote_dir = ''
        local_dir = ''

        if 'method' in source:
            method = source['method']

        if method == 'ignore':
            return

        if 'dir' in source:
            local_dir = source['dir']

        if 'url' in source:
            try:
                url = urlparse(source['url'])
            except Exception as e:
                fatal_error('url-parse-error', source['url'], e)

            remote_dir = url.geturl()
            if local_dir == '':
                local_dir = url.path[1:]

        local_dir = os.path.realpath(self.config.layer_dir(local_dir))

        if not os.path.isdir(local_dir):
            self.update_directory_initial(method, remote_dir, local_dir)

        branch = source.setdefault('branch', '')
        rev = source.setdefault('rev', '')

        if os.path.isdir(local_dir):
            self.update_directory(method, local_dir, remote_dir != '', branch, rev)


    def update_directory_initial(self, method, remote_dir, local_dir):
        info('Downloading source from ', remote_dir)

        if ChefCall.VERBOSE:
            redirect = ''
        else:
            redirect = ' >/dev/null 2>&1'

        if method == 'git':
            if os.system('git clone --recurse-submodules {} {} {}'.format(remote_dir, local_dir, redirect)) != 0:
                fatal_error('Unable to clone', remote_dir)


    def update_directory(self, method, local_dir, has_remote, branch, rev):
        if ChefCall.VERBOSE:
            redirect = ''
        else:
            redirect = ' >/dev/null 2>&1'

        if method == 'git':

            if rev == '':

                if branch == '':
                    warn('ATTENTION! source "{}" has no "rev" nor "branch" field, the build will not be reproducible at all!'.format(local_dir))
                    info('Trying to update source {}... '.format(local_dir))
                    if has_remote:
                        if os.system('cd ' + local_dir + '; git pull' + redirect) != 0:
                            fatal_error('Unable to pull updates for {}'.format(local_dir))
                else:
                    warn('source "{}" has no "rev" field, the build will not be reproducible!'.format(local_dir))
                    info('Updating source {}... '.format(local_dir))
                    if os.system('cd ' + local_dir + '; git checkout ' + branch + redirect) != 0:
                        fatal_error('Unable to checkout branch {} for {}'.format(branch, local_dir))
                    if has_remote:
                        if os.system('cd ' + local_dir + '; git pull' + redirect) != 0:
                            fatal_error('Unable to pull updates for {}'.format(local_dir))

            else:
                info('Updating source {}... '.format(local_dir))
                if os.system('cd ' + local_dir + '; git fetch; git checkout ' + rev + redirect) != 0:
                    fatal_error('Unable to checkout rev {} for {}'.format(rev, local_dir))

            if os.system('cd ' + local_dir + '; git submodule update --recursive --init ' + redirect) != 0:
                fatal_error('Unable to update submodules in ' + local_dir)


    def generate(self):
        info('Generating build dirs for target in project directory')

        for target in BuildConfiguration.ALL.values():
            if target.target(): # only create a build-dir if a build-target is set
                self.prepare_build_directory(target)


    def prepare_build_directory(self, target):
        debug('Preparing directory:', target.build_dir())

        os.makedirs(target.build_dir(), exist_ok=True)

        conf_path = os.path.join(target.build_dir(), 'conf')
        os.makedirs(conf_path, exist_ok=True)

        dl_dir = '${TOPDIR}/' + os.path.relpath(self.config.dl_dir(), target.build_dir())

        sstate_dir = os.path.join(self.config.project_root(), 'sstate-cache')
        sstate_dir = '${TOPDIR}/' + os.path.relpath(sstate_dir, target.build_dir())

        with open(os.path.join(conf_path, 'local.conf'), 'w') as file:
            file.write('\n# DO NOT EDIT! - This file is automatically created by chef.\n\n')

            layer_dir = os.path.join('${TOPDIR}', os.path.relpath(self.config.layer_dir(), target.build_dir()))

            file.write('CHEF_LAYER_DIR = "{}"\n'.format(layer_dir))
            file.write('DL_DIR = "{}"\n'.format(dl_dir))
            file.write('SSTATE_DIR = "{}"\n'.format(sstate_dir))

            for line in target.local_conf():
                file.write(line + '\n')

            file.write('''DISTRO ?= "poky"
PACKAGE_CLASSES ?= "package_rpm"
BB_DISKMON_DIRS ??= "\\
\tSTOPTASKS,${TMPDIR},1G,100K \\
\tSTOPTASKS,${DL_DIR},1G,100K \\
\tSTOPTASKS,${SSTATE_DIR},1G,100K \\
\tSTOPTASKS,/tmp,100M,100K \\
\tABORT,${TMPDIR},100M,1K \\
\tABORT,${DL_DIR},100M,1K \\
\tABORT,${SSTATE_DIR},100M,1K \\
\tABORT,/tmp,10M,1K"
CONF_VERSION = "1"
''')

        with open(os.path.join(conf_path, 'bblayers.conf'), 'w') as file:
            file.write('\n# DO NOT EDIT! - This file is automatically created by chef.\n\n')
            file.write('''POKY_BBLAYERS_CONF_VERSION = "2"
BBPATH = "${TOPDIR}"
BBFILES ?= ""
''')
            file.write('BBLAYERS ?= " \\\n')
            for layer in target.layers():
                layer_path = os.path.relpath(self.config.layer_dir(layer), target.build_dir())
                file.write('${{TOPDIR}}/{} \\\n'.format(layer_path))
            file.write('"\n')

        with open(os.path.join(conf_path, 'templateconf.cfg'), 'w') as file:
            file.write("meta-poky/conf\n")


    def show_target_tree(self, build, level):
        print(2*level * ' ', '-', build.name())
        for child in build.children_:
            self.show_target_tree(child, level + 1)

    def show(self, targets, layers, conf, tree, build):

        # check if selected targets exist
        for target in targets:
            if not target in BuildConfiguration.ALL:
                fatal_error('cannot show infos about target', target, 'as it does not exists.')

        # empty given targets - use all existing ones
        if not targets:
            targets = BuildConfiguration.ALL.keys()

        # print information per target
        for target_name in sorted(targets):
            target = BuildConfiguration.ALL[target_name]

            if target.target():
                build_info = '(bakes {})'.format(target.target())
            else:
                build_info = ''

            info('target:', target.name(), build_info)

            if layers:
                info(' used layers')
                for layer in target.layers():
                    info('  - {} ({})'.format(layer, self.config.layer_dir(layer)))

            if conf:
                info(' local.conf entries')
                for entry in target.local_conf():
                    info('  - {}'.format(entry))

            if build:
                if target.target():
                    info('  .',
                         os.path.relpath(self.config.layer_dir(ChefCommands.DEFAULT_INIT_BUILD_SCRIPT), os.getcwd()),
                         os.path.relpath(target.build_dir(), os.getcwd()))
                else:
                    info('target', target.name(), 'has no build-target')

        if tree:
            info('targets parent-child-tree:')
            self.show_target_tree(BuildConfiguration.ALL['root'], 0)


    def build(self, targets, sdk):
        debug('Building targets')

        filtered_targets = []

        if targets: # filter out unwanted targets
            for target in targets:
                if not target in BuildConfiguration.ALL:
                    fatal_error('undefined target:', target)

                if not BuildConfiguration.ALL[target].target():
                    fatal_error('target has no build-target:', target)

                filtered_targets.append(BuildConfiguration.ALL[target])

        else: # use all targets which have build-targets
            filtered_targets = [ x for x in BuildConfiguration.ALL.values() if x.target() ]

        for target in filtered_targets:
            self.build_target(target, sdk)


    def build_target(self, target, sdk):
        try:
            info('Building target', target.name())

            directory = target.build_dir()

            init_script = self.config.layer_dir(ChefCommands.DEFAULT_INIT_BUILD_SCRIPT)
            if not os.path.isfile(init_script):
                fatal_error('init-script', init_script, 'not found')

            command_line = 'env bash -c "source {} {} && bitbake {}"'.format(init_script, directory, target.target())

            debug('    Executing : "{}"'.format(command_line))
            if os.system(command_line) != 0:
                fatal_error('execution of "{}" failed'.format(command_line))

            if sdk:
                command_line = 'env bash -c "source {} {} && bitbake -c populate_sdk {}"'.format(init_script, directory, target.target())
                debug('    Executing : "{}"'.format(command_line))
                if os.system(command_line) != 0:
                    fatal_error('execution of "{}" failed'.format(command_line))

        except Exception as e:
            fatal_error('build for', target_name, 'failed', e)


class ChefCall:
    """
    ChefCall represents a call of the chef-tool, handles all arguments, opens the config-file,
    loads the menu, checks the menu and calls the appropriate low-level commands
    """

    DEBUG = False
    WARNING = True
    VERBOSE = False

    def __init__(self):
        parser = argparse.ArgumentParser(prog='Chef')

        parser.add_argument('--debug', action='store_true', help='activate debug printing')
        parser.add_argument('-v', '--verbose', action='store_true', help='activate verbose printing (of called subcommands)')

        # parsing subcommand's arguments
        subparsers = parser.add_subparsers(help='subcommands of Chef')

        # `cook` command (`init` + `update` + `generate`)
        cook_parser = subparsers.add_parser('cook', help='prepare the directories and build the targets of the menu')
        cook_parser.add_argument('-s', '--sdk', action='store_true', help='build also the SDK')
        cook_parser.add_argument('menu', help='filename of the JSON menu', type=argparse.FileType('r'), nargs=1)
        cook_parser.add_argument('targets', help='target to build', nargs='*')
        cook_parser.set_defaults(func=self.cook)

        # `init` command
        init_parser = subparsers.add_parser('init', help='initialize the project-dir')
        init_parser.add_argument('-f', '--force', help='re-init an existing project',
                                 default=False, action='store_true')
        init_parser.add_argument('-l', '--layer-dir', help='path where layers will saved/cloned')
        init_parser.add_argument('-b', '--build-dir', help='path where the build-directories will be placed')
        init_parser.add_argument('-d', '--dl-dir', help='path where yocto-fetched-repositories will be saved')
        init_parser.add_argument('menu', help='filename of the JSON menu', type=argparse.FileType('r'), nargs=1)
        init_parser.set_defaults(func=self.init)

        # `update` command
        update_parser = subparsers.add_parser('update', help='update source layers')
        update_parser.set_defaults(func=self.update)

        # `generate` command
        generate_parser = subparsers.add_parser('generate', help='generate build-configuration')
        generate_parser.set_defaults(func=self.generate)

        # `show` command
        show = subparsers.add_parser('show', help='show targets and target information')
        show.add_argument('-l', '--layers', help='list layers per target', action='store_true', default=False)
        show.add_argument('-c', '--conf', help='list local.conf-entries per target', action='store_true', default=False)
        show.add_argument('-t', '--tree', help='list all targets as a parent-child-tree', action='store_true', default=False)
        show.add_argument('-b', '--build', help='show poky-command-line to enter the build-dir and initialize the environment', action='store_true', default=False)
        show.add_argument('-a', '--all', help='show all information about the targets', action='store_true', default=False)
        show.add_argument('targets', help='show information of the given targets', nargs='*')
        show.set_defaults(func=self.show)

        # `build` command
        build_parser = subparsers.add_parser('build', help='build the targets from the menu')
        build_parser.add_argument('-s', '--sdk', action='store_true', help='build also the SDK')
        build_parser.add_argument('targets', help='target to build', nargs='*')
        build_parser.set_defaults(func=self.build)

        self.clargs = parser.parse_args()

        ChefCall.DEBUG = self.clargs.debug
        ChefCall.VERBOSE = self.clargs.verbose

        # find and initialize config
        self.config = Config()

        debug('Project root', self.config.project_root())

        if self.config.empty():
            debug('empty config')
        else:
            debug('config present')

        # figure out which menu-file to use
        menu_file = None
        if 'menu' in self.clargs and self.clargs.menu is not None: # menu-file from the cmdline has priority
            menu_file = self.clargs.menu[0]
        elif not self.config.empty(): # or the one from the config-file
            try:
                menu_file = open(self.config.menu())
            except Exception as e:
                fatal_error('menu load error', e)

        self.menu = None
        if menu_file:
            try:
                self.menu = json.load(menu_file)
            except Exception as e:
                fatal_error('menu load error:', e)

            schema = json.loads(pkg_resources.resource_string(__name__, "chef-menu-schema.json"))
            try:
                jsonschema.validate(self.menu, schema)
            except Exception as e:
                fatal_error('menu file validation failed:', e)

            debug('menu file validation passed')

            # create build-configurations and resolve parents

            # the main config is root containing the menu's layers and
            # local.conf-fields

            BuildConfiguration('root',
                               self.config,
                               self.menu.setdefault('layers', []),
                               self.menu.setdefault('local.conf', []),
                               None,
                               None)

            for name, target in self.menu['targets'].items():
                BuildConfiguration(name,
                                   self.config,
                                   target.setdefault('layers', []),
                                   target.setdefault('local.conf', []),
                                   target.setdefault('target', None),
                                   target.setdefault('inherit', 'root'))

            BuildConfiguration.resolve()


        self.commands = ChefCommands(self.config, self.menu)

        if 'func' in self.clargs:
            self.clargs.func() # call function of selected command
        else:
            debug('no function selected, did nothing')

        sys.exit(0)


    def init(self):
        """ function use by command-line-arg-parser as entry point for the 'init' """
        if not self.clargs.force and not self.config.empty():
            fatal_error('Project in', self.config.project_root(), 'has already been initalized')

        self.commands.init(self.clargs.menu[0].name,
                           self.clargs.layer_dir,
                           self.clargs.build_dir,
                           self.clargs.dl_dir)


    def update(self):
        """ entry point for 'update' """
        if self.menu is None:
            fatal_error('update needs a menu')

        self.commands.update()


    def cook(self):
        self.commands.init(self.clargs.menu[0].name)
        self.commands.update()
        self.commands.generate()
        self.commands.build(self.clargs.targets, self.clargs.sdk)


    def generate(self):
        if self.menu is None:
            fatal_error('generate needs a menu')

        self.commands.generate()


    def show(self):
        if self.menu is None:
            fatal_error('show command needs a menu')

        self.commands.show(self.clargs.targets,
                           self.clargs.layers or self.clargs.all,
                           self.clargs.conf or self.clargs.all,
                           self.clargs.tree or self.clargs.all,
                           self.clargs.build or self.clargs.all)


    def build(self):
        if self.menu is None:
            fatal_error('build needs a menu')

        self.commands.build(self.clargs.targets, self.clargs.sdk)

def main():
    ChefCall()
