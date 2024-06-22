from distutils.core import setup


setup(
    name="vtndb",
    version="1.0.1",
    description="VT-100 Nth Dimensional Borders Wiki Frontend",
    author="DragonMinded",
    license="Public Domain",
    packages=[
        "ndb",
    ],
    install_requires=[
        req for req in open("requirements.txt").read().split("\n") if len(req) > 0
    ],
    python_requires=">3.8",
    entry_points={
        "console_scripts": [
            "vtndb = ndb.__main__:cli",
        ],
    },
)
