try:
    from setuptools import setup
except:
    from distutils.core import setup

try:
    readme = open('README.rst').read()
except IOError as e:
    # error if not run from project dir
    readme = ''

setup(name="rst2epub2",
      version='0.3.1',
      author='matt harrison',
      author_email='matthewharrison AT gmail',
      description="script/library to create epubs programatically and from rst",
      long_description=readme,
      url='https://github.com/mattharrison/rst2epub2',
      install_requires=['docutils', 'genshi'],
      scripts=["rst2epub.py"],
      package_dir={"epublib":"epublib"},
      packages=['epublib'],
      package_data={'epublib':['templates/*.css','templates/*.html','templates/*.ncx','templates/*.xml', 'templates/*.opf']},
      zip_safe=False,
      classifiers=(
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',)
)
