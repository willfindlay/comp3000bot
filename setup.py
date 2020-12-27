from setuptools import setup

version = '0.0.2'

setup(
    name='comp3000bot',
    version=version,
    url='https://github.com/comp3000bot.git',
    author='William Findlay',
    author_email='william@williamfindlay.com',
    description='A Discord bot for the COMP3000 course at Carleton.',
    packages=['comp3000bot'],
    install_requires=['discord', 'python-decouple', 'humanreadable', 'bidict'],
    scripts=['bin/comp3000bot'],
)
