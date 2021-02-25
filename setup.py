import sys
from os import listdir
from os.path import isfile, join

from setuptools import setup, find_packages, Extension

if sys.version_info < (3, 6):
    raise Exception("Python 3.6 or higher is required. Your version is %s." % sys.version)

__version__ = ""
exec(open('efb_qq_plugin_iot/__version__.py').read())

long_description = open('README.rst').read()


def get_file_list(path: str):
    return [join(path, f) for f in listdir(path) if isfile(join(path, f)) and f.endswith('.c')]


setup(
    name='efb-qq-plugin-iot',
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    version=__version__,
    description='EQS plugin for IOTBot.',
    long_description=long_description,
    include_package_data=True,
    author='Milkice',
    author_email='milkice@milkice.me',
    url='https://github.com/milkice233/efb-qq-plugin-iot',
    license='GPLv3',
    python_requires='>=3.6',
    keywords=['ehforwarderbot', 'EH Forwarder Bot', 'EH Forwarder Bot Slave Channel',
              'qq', 'chatbot', 'EQS', 'iot', 'OPQBot'],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Communications :: Chat",
        "Topic :: Utilities"
    ],
    install_requires=[
        "efb-qq-slave",
        "botoy",
        "ehforwarderbot",
        "requests",
        "python-magic",
        "cachetools",
        "pydub"
    ],
    entry_points={
        'ehforwarderbot.qq.plugin': 'iot = efb_qq_plugin_iot:IOTBot'
    },
    ext_modules=[Extension('Silkv3',
                           sources=get_file_list('lib/silkv3/src'),
                           include_dirs=["lib/silkv3/interface/"]
                           )]
)
