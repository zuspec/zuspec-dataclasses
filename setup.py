
import os
from setuptools import setup, find_namespace_packages

version="0.0.1"

if "BUILD_NUM" in os.environ.keys():
    version += "." + os.environ["BUILD_NUM"]

setup(
  name = "zuspec-dataclasses",
  version=version,
  packages=find_namespace_packages(where='src'),
  package_dir = {'' : 'src'},
  author = "Matthew Ballance",
  author_email = "matt.ballance@gmail.com",
  description = "Front-end for capturing Action Relation Level models using dataclasses",
  long_description="""
  PyARL-Dataclasses provides a front-end for capturing actions, and activities
  in a dataclass-centric manner
  """,
  license = "Apache 2.0",
  keywords = ["SystemVerilog", "Verilog", "RTL"],
  url = "https://github.com/zuspec/zuspec-dataclasses",
  setup_requires=[
    'setuptools_scm',
  ],
  install_requires=[
    'pyvsc-dataclasses',
  ],
)

