try:
    from setuptools import setup
except:
    from distutils.core import setup

setup(name="rst2epub2",
      version='0.1',
      author='matt harrison',
      description="script/library to create epubs programatically and from rst",
      scripts=["rst2epub.py"],
      package_dir={"epublib":"epublib"},
      packages=['epublib'],
)
