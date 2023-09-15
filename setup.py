from setuptools import setup
import os

setup(
    name = "rhel-kernel-get",
    version = "0.1",
    description = "A tool for downloading and preparing RHEL kernels",
    author = "Viktor Malik",
    author_email = "vmalik@redhat.com",
    url = "https://github.com/viktormalik/rhel-kernel-get",
    install_requires = ["setuptools"],
    scripts = ["rhel-kernel-get"],
)
