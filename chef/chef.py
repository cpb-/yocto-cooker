#!/usr/bin/env python3
""" chef.py: meta build tool for Yocto Project based Linux embedded systems."""

import argparse
import json
import sys
import os
from urllib.parse import urlparse
import jsonschema


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

        branch = ''
        if 'branch' in source:
            branch = source['branch']

        commit = ''
        if 'commit' in source:
            commit = source['commit']

        if os.path.isdir(local_dir):
            self.update_directory(method, local_dir, remote_dir != '', branch, commit)


    def update_directory_initial(self, method, remote_dir, local_dir):
        info('Downloading source from ', remote_dir)

        if ChefCall.VERBOSE:
            redirect = ''
        else:
            redirect = ' >/dev/null 2>&1'

        if method == 'git':
            if os.system('git clone --recurse-submodules {} {} {}'.format(remote_dir, local_dir, redirect)) != 0:
                fatal_error('Unable to clone', remote_dir)


    def update_directory(self, method, local_dir, has_remote, branch, commit):
        if ChefCall.VERBOSE:
            redirect = ''
        else:
            redirect = ' >/dev/null 2>&1'

        if method == 'git':

            if commit == '':

                if 'branch' == '':
                    warn('ATTENTION! source "{}" has no "commit" nor "branch" field, the build will not be reproducible at all!'.format(local_dir))
                    info('Trying to update source {}... '.format(local_dir))
                    if has_remote:
                        if os.system('cd ' + local_dir + '; git pull' + redirect) != 0:
                            fatal_error('Unable to pull updates for {}'.format(local_dir))
                else:
                    warn('source "{}" has no "commit" field, the build will not be reproducible!'.format(local_dir))
                    info('Updating source {}... '.format(local_dir))
                    if os.system('cd ' + local_dir + '; git checkout ' + branch + redirect) != 0:
                        fatal_error('Unable to checkout branch {} for {}'.format(branch, local_dir))
                    if has_remote:
                        if os.system('cd ' + local_dir + '; git pull' + redirect) != 0:
                            fatal_error('Unable to pull updates for {}'.format(local_dir))

            else:
                info('Updating source {}... '.format(local_dir))
                if os.system('cd ' + local_dir + '; git checkout ' + commit + redirect) != 0:
                    fatal_error('Unable to checkout commit {} for {}'.format(commit, local_dir))

            if os.system('cd ' + local_dir + '; git submodule update --recursive --init ' + redirect) != 0:
                fatal_error('Unable to update submodules in ' + local_dir)


    def generate(self):
        info('Generating build dirs for target in project directory')

        for target, content in self.menu['targets'].items():
            directory = self.config.build_dir('build-' + target)
            self.prepare_build_directory(directory, content)


    def prepare_build_directory(self, path, target):
        debug('Preparing directory:', path)

        os.makedirs(path, exist_ok=True)

        conf_path = os.path.join(path, 'conf')
        os.makedirs(conf_path, exist_ok=True)

        dl_dir = '${TOPDIR}/' + os.path.relpath(self.config.dl_dir(), path)

        sstate_dir = os.path.join(self.config.project_root(), 'sstate-cache')
        sstate_dir = '${TOPDIR}/' + os.path.relpath(sstate_dir, path)

        with open(os.path.join(conf_path, 'local.conf'), 'w') as file:
            file.write('\n# DO NOT EDIT! - This file is automatically created by chef.\n\n')

            layer_dir = os.path.join('${TOPDIR}', os.path.relpath(self.config.layer_dir(), path))

            file.write('CHEF_LAYER_DIR = "{}"\n'.format(layer_dir))
            file.write('DL_DIR = "{}"\n'.format(dl_dir))
            file.write('SSTATE_DIR = "{}"\n'.format(sstate_dir))

            for line in target['local.conf']:
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
            for layer in self.menu['layers'] + target['layers']:
                layer_path = os.path.relpath(self.config.layer_dir(layer), path)
                file.write('${{TOPDIR}}/{} \\\n'.format(layer_path))
            file.write('"\n')

        with open(os.path.join(conf_path, 'templateconf.cfg'), 'w') as file:
            file.write("meta-poky/conf\n")


    def target_info(self):
        for target in self.menu['targets']:
            path = self.config.build_dir('build-' + target)

            info('target', target, 'build-dir can be initialized by calling')
            info('  .',
                 os.path.relpath(self.config.layer_dir(ChefCommands.DEFAULT_INIT_BUILD_SCRIPT), os.getcwd()),
                 os.path.relpath(path, os.getcwd()))


    def build(self, targets, sdk):
        debug('Building targets')

        filtered_targets = {}

        if targets: # filter out unwanted targets
            for target in targets:
                if not target in self.menu['targets']:
                    fatal_error('target', target, 'not defined in menu')
                filtered_targets[target] = self.menu['targets'][target]
        else: # use all targets
            filtered_targets = self.menu['targets']

        for name, target in filtered_targets.items():
            self.build_target(name, target, sdk)


    def build_target(self, target_name, target, sdk):
        try:
            info('Building target', target_name)

            directory = self.config.build_dir('build-' + target_name)

            if 'image' in target:
                image = target['image']
            else:
                image = 'core-image-base'

            init_script = self.config.layer_dir(ChefCommands.DEFAULT_INIT_BUILD_SCRIPT)
            if not os.path.isfile(init_script):
                fatal_error('init-script', init_script, 'not found')

            command_line = 'env bash -c "source {} {} && bitbake {}"'.format(init_script, directory, image)

            debug('    Executing : "{}"'.format(command_line))
            if os.system(command_line) != 0:
                fatal_error('execution of "{}" failed'.format(command_line))

            if sdk:
                command_line = 'env bash -c "source {} {} && bitbake -c populate_sdk {}"'.format(init_script, directory, image)
                debug('    Executing : "{}"'.format(command_line))
                if os.system(command_line) != 0:
                    fatal_error('execution of "{}" failed'.format(command_line))

        except Exception as e:
            fatal_error('build for', target_name, 'failed', e)


class ChefCall:
    """
    ChefCall represents a call of the chef-tool, handled all arguments, opens the config-file,
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

        # `cook` command (`prepare` + `build`)
        cook_parser = subparsers.add_parser('cook', help='prepare the directories and build the targets of the menu')
        cook_parser.add_argument('menu', help='filename of the JSON menu', type=argparse.FileType('r'), nargs=1)
        cook_parser.add_argument('targets', help='target to build', nargs='*')
        cook_parser.set_defaults(func=self.cook)

        # `prepare` command (`init` + `update` + `generate`)
        prepare_parser = subparsers.add_parser('prepare', help='create the content of the menu')
        prepare_parser.add_argument('menu', help='filename of the JSON menu', type=argparse.FileType('r'), nargs=1)
        prepare_parser.set_defaults(func=self.prepare)

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

        target_info = subparsers.add_parser('target-info', help='target information')
        target_info.set_defaults(func=self.target_info)

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

            script_path = os.path.dirname(os.path.realpath(__file__))
            with open(os.path.join(script_path, 'chef-menu-schema.json')) as schema_file:
                schema = json.load(schema_file)
                try:
                    jsonschema.validate(self.menu, schema)
                except Exception as e:
                    fatal_error('menu file validation failed:', e)

                debug('menu file validation passed')

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


    def prepare(self):
        self.commands.init(self.clargs.menu[0].name)
        self.commands.update()
        self.commands.generate()


    def cook(self):
        self.prepare()
        self.commands.build(self.clargs.targets, True)


    def generate(self):
        if self.menu is None:
            fatal_error('generate needs a menu')

        self.commands.generate()


    def target_info(self):
        if self.menu is None:
            fatal_error('target-info needs a menu')

        self.commands.target_info()


    def build(self):
        if self.menu is None:
            fatal_error('build needs a menu')

        self.commands.build(self.clargs.targets, self.clargs.sdk)


def main():
    """ Entry point for chef """
    ChefCall()


if __name__ == '__main__':
    ChefCall()
