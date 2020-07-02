__title__ = 'chef'
__version__ = '1.0.0'
__author__ = "Christophe BLAESS, Patrick BOETTCHER"
__email__ = 'christophe.blaess@logilin.fr, p@yai.se'
__license__ = "GPL"
__url__ = "https://github.com/cpb-/chef"

from setuptools import setup
import os


# Get description from the README file
with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding='utf-8') as f:
    _long_description = f.read()


setup(
    name=__title__,
    version=__version__,
    description='meta build tool for Yocto Project based Linux embedded systems',
    author=__author__,
    author_email=__email__,
    url=__url__,
    license=__license__,
    long_description=_long_description,
    package_data={'': ['chef-menu-schema.json']},

    packages=[
        "chef",
    ],

    entry_points={
        'console_scripts': [
            'chef = chef.chef:main',
        ],
    },

    install_requires=[
        "jsonschema == 3.2.0",
        "urllib3 >= 1.22"
    ],

    project_urls={
        'Bug Reports': 'https://github.com/cpb-/chef/issues',
        'Source': __url__,
    },
)
