from setuptools import setup

setup(
    name='pycicle',
    version='0.1.1',
    description='command line parsers for the 21st century',
    long_description='see <https://github.com/gemerden/pycicle>',  # after long battle to get markdown to work on PyPI
    author='Lars van Gemerden',
    author_email='gemerden@gmail.com',
    url='https://github.com/gemerden/pycicle',
    license='MIT License',
    packages=['pycicle', 'pycicle.tools'],
    install_requires=['tkinter'],
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    python_requires='>=3.7',
    keywords='command line parser argparser optparser GUI prompt',
)
