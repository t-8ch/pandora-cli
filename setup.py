from setuptools import setup, find_packages


with open('README.rst', 'r') as f:
    readme = f.read()

with open('CHANGES.rst', 'r') as f:
    changes = f.read()

setup(
    name='pandora-cli',
    version='0.1.0',
    author='Thomas Weißschuh',
    author_email='pandora-cli@t-8ch.de',
    url='https://github.com/t-8ch/pandora-cli',
    packages=find_packages(),
    license='GPL3',
    description='CLI wrapper for pandora.com',
    long_description=readme + '\n\n' + changes,
    keywords='pandora.com pandora cli download music stream',
    entry_points={
        'console_scripts': [
            'pandora-cli = pandora_cli.cli:main',
            ],
        },
    install_requires=[
        'requests',
        'cryptography',
        'click',
        'mutagen',
    ]
    )
