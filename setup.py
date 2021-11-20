from setuptools import setup

setup(name="lisby",
      version="0.1",
      description="A small Scheme-like LISP",
      url="https://github.com/susji/lisby",
      author="susji",
      author_email="susji@protonmail.com",
      license="MIT",
      packages=["lisby"],
      install_requires=[
          "ply==3.11",
      ],
      zip_safe=False)
